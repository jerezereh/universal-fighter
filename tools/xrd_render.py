"""Validate diagnostic D3D9 readbacks; full-scene pixels never imply isolated RGBA."""
from collections import Counter
import hashlib
import json
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
