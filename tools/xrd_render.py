"""Validate diagnostic D3D9 readbacks; full-scene pixels never imply isolated RGBA."""
from collections import Counter
import hashlib
import json
import re
import struct
import zlib


def render_pixels(metadata, data):
    for key, low, high in (('width', 1, 2048), ('height', 1, 2048), ('state_size', 1, 0x80000),
                          ('counter', 0, 0xffffffff), ('presentation_index', 3, 3)):
        if type(metadata.get(key)) != int or not low <= metadata[key] <= high:
            raise ValueError('invalid render ' + key)
    width, height, size = metadata['width'], metadata['height'], metadata['state_size']
    if (type(metadata.get('format')) != int or metadata['format'] not in (21, 22) or
            any(type(metadata.get(k)) != int or metadata[k] != 0 for k in ('multisample', 'hresult'))):
        raise ValueError('unsupported/failed D3D9 readback')
    if type(metadata.get('pitch')) != int or not width * 4 <= metadata['pitch'] <= 65536:
        raise ValueError('invalid source pitch')
    if any(metadata.get(key) is not False for key in ('atomic_native_frame', 'isolated_rgba', 'native_render_latency_verified')):
        raise ValueError('diagnostic readback promoted to guest capability')
    if len(data) != size + width * height * 4:
        raise ValueError('incomplete render packet')
    pixels = data[size:]
    # X8's high byte is not alpha. Keep raw bytes; RGB-only previews cannot fabricate a mask.
    rgb = bytearray(width * height * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = pixels[2::4], pixels[1::4], pixels[0::4]
    return pixels, bytes(rgb)


def png_rgb(width, height, rgb):
    if any(type(n) != int or not 1 <= n <= 2048 for n in (width, height)) or len(rgb) != width * height * 3:
        raise ValueError('incomplete RGB preview')
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    rows = b''.join(b'\0' + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')


def save_render(folder, metadata, data, observation):
    pixels, rgb = render_pixels(metadata, data)
    index = len(list(folder.glob('render-*.json'))) + 1
    if index > 8:
        raise ValueError('unbounded render receipt')
    name = f'render-{index:02}'
    result = {k: v for k, v in metadata.items() if k != 'segments'} | dict(
        image=name + '.png', raw=name + '.bgra', observation=observation,
        rgb_sha256=hashlib.sha256(rgb).hexdigest(), raw_sha256=hashlib.sha256(pixels).hexdigest(),
        high_byte_histogram=dict(Counter(pixels[3::4])), high_byte_is_alpha=metadata['format'] == 21,
        preview_rgb_only=True, full_scene=True)
    (folder / (name + '.bgra')).write_bytes(pixels)
    (folder / (name + '.png')).write_bytes(png_rgb(metadata['width'], metadata['height'], rgb))
    (folder / (name + '.json')).write_text(json.dumps(result, indent=2))
    return result


def render_check(captures, records, states):
    linked = []
    for capture in captures:
        matches = [s for r, s in zip(records, states) if r['after'] == capture['counter']]
        linked.append(bool(matches) and all(s == capture['observation']['fighters'] for s in matches))
    return dict(captures=len(captures), counters=[c['counter'] for c in captures],
        distinct_rgb_images=len({c['rgb_sha256'] for c in captures}),
        held_counter_state_linked=bool(captures) and all(linked),
        full_scene=True, native_render_latency_verified=False, atomic_native_frame=False, isolated_rgba=False)


def draw_check(frames):
    if len(frames) != 2:
        raise ValueError('requires two complete draw intervals')
    shapes = dict(SetRenderTarget='up', Clear='upuuuu', SetTexture='up', DrawPrimitive='uuu',
        DrawIndexedPrimitive='uiuuuu', DrawPrimitiveUP='uupu', DrawIndexedPrimitiveUP='uuuupupu',
        SetVertexShader='p', SetStreamSource='upuu', SetIndices='p', SetPixelShader='p')
    threads = set(); methods = Counter(); groups = Counter(); primitives = Counter(); unknown = 0; targets = {}
    # The first binding for each state may be cached before observation. Keep it explicitly unknown.
    state = dict(target=None, vertex_shader=None, pixel_shader=None, vertex_buffer=None, stride=None, texture0=None)
    for i, frame in enumerate(frames, 1):
        if (frame.get('frame') != i or frame.get('isolated_rgba') is not False or
                type(frame.get('counter_before')) != int or not 0 <= frame['counter_before'] <= 0xffffffff or
                frame.get('counter_after') != frame['counter_before'] or
                not isinstance(frame.get('events'), list) or not 1 <= len(frame['events']) <= 8192):
            raise ValueError('incomplete/unheld draw interval')
        for event in frame['events']:
            name, values = event.get('method'), event.get('values')
            shape = shapes.get(name)
            if not shape or not isinstance(values, list) or len(values) != len(shape):
                raise ValueError('invalid draw method/arguments')
            for value, kind in zip(values, shape):
                if kind == 'p': valid = isinstance(value, str) and re.fullmatch(r'0x[0-9a-f]{1,8}', value)
                else: valid = type(value) == int and (-0x80000000 <= value <= 0x7fffffff if kind == 'i' else 0 <= value <= 0xffffffff)
                if not valid: raise ValueError('invalid draw argument')
            if type(event.get('thread')) != int or event['thread'] <= 0 or type(event.get('hresult')) != int or event['hresult'] != 0:
                raise ValueError('failed draw call/thread')
            caller = event.get('caller_rva')
            if caller is not None and (type(caller) != int or not 0 <= caller < 64 << 20):
                raise ValueError('invalid local draw caller')
            threads.add(event['thread']); methods[name] += 1
            if 'surface' in event:
                surface = event['surface']
                if (name != 'SetRenderTarget' or not isinstance(surface, dict) or surface.get('type') != 1 or
                        any(type(surface.get(k)) != int or not 0 <= surface[k] <= 0xffffffff
                            for k in ('format', 'type', 'usage', 'pool', 'multisample', 'width', 'height')) or
                        not 1 <= surface['width'] <= 16384 or not 1 <= surface['height'] <= 16384):
                    raise ValueError('invalid target surface description')
                previous = targets.setdefault(values[1], surface)
                if previous != surface or len(targets) > 32: raise ValueError('target description drift/limit')
            if name == 'SetRenderTarget' and values[0] == 0: state['target'] = values[1]
            elif name == 'SetVertexShader': state['vertex_shader'] = values[0]
            elif name == 'SetPixelShader': state['pixel_shader'] = values[0]
            elif name == 'SetStreamSource' and values[0] == 0:
                state['vertex_buffer'], state['stride'] = values[1], values[3]
            elif name == 'SetTexture' and values[0] == 0: state['texture0'] = values[1]
            elif name.startswith('Draw'):
                key = tuple(state.values())
                groups[key] += 1
                primitives[key] += values[5] if name == 'DrawIndexedPrimitive' else values[3] if name == 'DrawIndexedPrimitiveUP' else values[2] if name == 'DrawPrimitive' else values[1]
                if any(value is None for value in key): unknown += 1
    if len(threads) != 1 or not groups:
        raise ValueError('multithreaded/missing draw trace')
    return dict(passed=True, intervals=2, events=sum(methods.values()), methods=dict(methods),
        threads=sorted(threads), draw_calls=sum(groups.values()), unknown_binding_draws=unknown,
        binding_groups=len(groups), target_count=len(targets), targets=targets, isolated_rgba=False, actor_draw_identity_verified=False,
        groups=[dict(zip(state, key)) | dict(draw_calls=count, primitives=primitives[key])
                for key, count in groups.most_common()])
