"""Authored padded-readback, preview and held-state association checks; no game required."""
import json
from pathlib import Path
import struct
import tempfile
import zlib

from xrd_render import png_rgb, render_pixels, save_render, render_check


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


if __name__ == '__main__': main()
