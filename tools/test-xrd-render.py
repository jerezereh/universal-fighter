"""Authored padded-readback, preview and held-state association checks; no game required."""
import json
from pathlib import Path
import struct
import tempfile
import zlib

from xrd_render import png_rgb, render_pixels, save_render, render_check, draw_check, pass_pixels


def reject(action):
    try: action()
    except ValueError: return
    raise AssertionError('invalid render accepted')


def main():
    metadata = dict(width=2, height=1, state_size=4, counter=9, presentation_index=3,
        format=21, multisample=0, hresult=0, pitch=16,
        atomic_native_frame=False, isolated_rgba=False, native_render_latency_verified=False)
    data = b'abcd' + bytes([1, 2, 3, 0, 4, 5, 6, 128])
    pixels, rgb = render_pixels(metadata, data)
    assert render_pixels(metadata|dict(diagnostic_settling=True,presentation_index=24),data)==(pixels,rgb)
    reject(lambda:render_pixels(metadata|dict(diagnostic_settling=True,presentation_index=25),data))
    assert pixels == data[4:] and rgb == bytes([3, 2, 1, 6, 5, 4])
    for changes in (dict(width=True), dict(width=2049), dict(height=0), dict(state_size=0),
                    dict(counter=-1), dict(presentation_index=2), dict(format=23), dict(multisample=2),
                    dict(hresult=-1), dict(hresult=False), dict(multisample=False), dict(pitch=7), dict(pitch=65537), dict(isolated_rgba=True),
                    dict(atomic_native_frame=True), dict(native_render_latency_verified=True)):
        reject(lambda: render_pixels(metadata | changes, data))
    reject(lambda: render_pixels(metadata, data[:-1]))
    reject(lambda: render_pixels(metadata, data + b'x'))
    reject(lambda: png_rgb(2, 1, rgb[:-1]))
    reject(lambda: png_rgb(0, 1, b''))
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        capture = save_render(folder, metadata, data, dict(fighters=[dict(x_raw=12)]))
        assert (folder / capture['raw']).read_bytes() == pixels
        assert json.loads((folder / 'render-01.json').read_text())['high_byte_histogram'] == {'0': 1, '128': 1}
        png = (folder / capture['image']).read_bytes()
        assert png[:8] == b'\x89PNG\r\n\x1a\n'
        offset = 8; kinds = []; compressed = b''
        while offset < len(png):
            size = struct.unpack_from('>I', png, offset)[0]
            kind, payload = png[offset+4:offset+8], png[offset+8:offset+8+size]
            assert zlib.crc32(kind + payload) == struct.unpack_from('>I', png, offset+8+size)[0]
            kinds.append(kind)
            if kind == b'IHDR': assert struct.unpack('>IIBBBBB', payload) == (2, 1, 8, 2, 0, 0, 0)
            if kind == b'IDAT': compressed += payload
            offset += 12 + size
        assert kinds == [b'IHDR', b'IDAT', b'IEND'] and zlib.decompress(compressed) == b'\0' + rgb
        checked = render_check([capture], [dict(after=9)], [[dict(x_raw=12)]])
        assert checked['held_counter_state_linked'] and not checked['isolated_rgba']
        assert not render_check([capture], [dict(after=10)], [[dict(x_raw=12)]])['held_counter_state_linked']
        assert not render_check([capture], [dict(after=9)], [[dict(x_raw=13)]])['held_counter_state_linked']
        assert not render_check([], [], [])['held_counter_state_linked']
        x8 = save_render(folder, metadata | dict(format=22), data, dict(fighters=[]))
        assert not x8['high_byte_is_alpha'] and capture['high_byte_is_alpha']
        for _ in range(6): save_render(folder, metadata, data, dict(fighters=[]))
        reject(lambda: save_render(folder, metadata, data, dict(fighters=[])))
    print('Render bounds, BGRA/RGB conversion, raw alpha preservation, PNG integrity and state linkage passed.')
    def event(method, values): return dict(method=method, values=values, thread=7, hresult=0, caller_rva=12)
    events = [event('DrawPrimitive', [4, 0, 1]), event('SetRenderTarget', [0, '0x100']),
        event('SetVertexShader', ['0x200']), event('SetPixelShader', ['0x300']),
        event('SetStreamSource', [0, '0x400', 0, 32]), event('SetTexture', [0, '0x500']),
        event('DrawIndexedPrimitive', [4, -1, 0, 9, 0, 3])]
    frames = [dict(frame=i, counter_before=9, counter_after=9, events=events,
                   isolated_rgba=False) for i in (1, 2)]
    check = draw_check(frames)
    assert check['passed'] and check['draw_calls'] == 4 and check['unknown_binding_draws'] == 1
    assert check['groups'][0]['primitives'] == 7 and not check['actor_draw_identity_verified']
    for changes in (dict(frame=3), dict(counter_after=10), dict(events=[]), dict(isolated_rgba=True)):
        reject(lambda: draw_check([frames[0] | changes, frames[1]]))
    for changes in (dict(method='Unknown'), dict(values=[4]), dict(hresult=-1), dict(thread=8), dict(caller_rva=-1)):
        reject(lambda: draw_check([frames[0] | dict(events=events + [events[-1] | changes]), frames[1]]))
    reject(lambda: draw_check(frames[:1]))
    surface = dict(format=21, type=1, usage=1, pool=0, multisample=0, width=640, height=480)
    described = frames[0] | dict(events=[events[1] | dict(surface=surface)] + events)
    assert draw_check([described, frames[1]])['targets'] == {'0x100': surface}
    reject(lambda: draw_check([described | dict(events=[events[1] | dict(surface=surface | dict(width=0))] + events), frames[1]]))
    print('Held draw intervals, cached/unknown bindings, method shapes, caller/thread/result rejection and grouping passed.')
    meta=dict(width=1,height=1,state_size=4,counter=9,pass_index=1,trace_event=0,
        capture_boundary='before-target-switch',hresult=0,multisample=0,pitch=8,pixel_bytes=8,
        format=113,atomic_native_frame=False,isolated_rgba=False,native_render_latency_verified=False)
    pixels=struct.pack('<4e',.5,1.,0.,.25)
    raw,rgb,analysis=pass_pixels(meta,b'abcd'+pixels)
    assert raw==pixels and rgb==bytes([128,255,0]) and analysis['alpha_range']==[.25,.25]
    raw,rgb,analysis=pass_pixels(meta|dict(format=36),b'abcd'+struct.pack('<4H',0,65535,0,32768))
    assert rgb==bytes([0,255,0]) and analysis['alpha_range']==[32768.,32768.]
    raw,rgb,analysis=pass_pixels(meta|dict(format=114,pixel_bytes=4,pitch=4),b'abcd'+struct.pack('<f',.5))
    assert rgb==bytes([128]*3) and analysis['alpha_range'] is None and not analysis['alpha_is_source_channel']
    raw,rgb,analysis=pass_pixels(meta,b'abcd'+struct.pack('<4e',float('nan'),2.,-1.,1.))
    assert rgb==bytes([0,255,0]) and analysis['nonfinite_values']==1
    for changes in (dict(format=23),dict(pixel_bytes=4),dict(pitch=7),dict(pass_index=25),dict(trace_event=8193),dict(isolated_rgba=True)):
        reject(lambda:pass_pixels(meta|changes,b'abcd'+pixels))
    reject(lambda:pass_pixels(meta,b'abcd'+pixels[:-1]))
    print('Native half/float/integer pass decoding, source alpha retention, nonfinite preview handling and bounds passed.')
    stage=meta|dict(format=21,pixel_bytes=4,pitch=4,capture_boundary='after-original-color-draw',
        original_color_stage=True,original_color_shader='0x1234',presentation_index=3,request_index=0)
    pass_pixels(stage,b'abcd'+bytes([1,2,3,255]))
    for changes in [dict(original_color_stage=False),dict(presentation_index=4),dict(request_index=1),
                    dict(original_color_shader='0x0'),dict(format=113)]:
        reject(lambda:pass_pixels(stage|changes,b'abcd'+bytes([1,2,3,255])))
    print('Original color-stage role, presentation/step, format and shader bounds passed.')
    pipeline=stage|dict(capture_boundary='after-screen-draw',diagnostic_pipeline=True,
        screen_shader='0x1234',presentation_index=1)
    pass_pixels(pipeline,b'abcd'+bytes([1,2,3,255]))
    reject(lambda:pass_pixels(pipeline|dict(presentation_index=3),b'abcd'+bytes([1,2,3,255])))
    first=metadata|dict(diagnostic_pipeline=True,presentation_index=1)
    render_pixels(first,data)
    reject(lambda:render_pixels(first|dict(diagnostic_settling=True),data))


if __name__ == '__main__': main()
