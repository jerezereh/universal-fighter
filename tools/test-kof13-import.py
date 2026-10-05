"""Small parser check using authored data, without copyrighted fixtures."""
import importlib.util
from pathlib import Path
import struct
import tempfile

spec = importlib.util.spec_from_file_location('kof', Path(__file__).with_name('kof13-import.py'))
kof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kof)

# GETGLOBAL, NEWTABLE, LOADK, SETLIST, SETGLOBAL, RETURN.
proto = dict(constants=['fixture', 42], children=[], code=[
    10, 1 | (1 << 6) | (1 << 14), 34 | (1 << 23) | (1 << 14), 7, 30 | (1 << 23)])
assert kof.tables(proto)[0] == {'fixture': {1: 42}}
try:
    kof.Chunk(bytes(12))
except ValueError:
    pass
else:
    raise AssertionError('Bad Lua header accepted')
try:
    kof.tables(dict(constants=[], children=[], code=[22]))
except ValueError:
    pass
else:
    raise AssertionError('Control flow accepted as static data')

from PIL import Image
asymmetric = Image.new('RGBA', (4, 1))
asymmetric.putpixel((0, 0), (255, 0, 0, 255))
asymmetric.putpixel((3, 0), (0, 0, 255, 255))
mirrored, origin = kof.mirror_sprite(asymmetric, (1, 2))
assert origin == (3, 2)
assert mirrored.getpixel((0, 0)) == (0, 0, 255, 255)
assert mirrored.getpixel((3, 0)) == (255, 0, 0, 255)
# MAPPLT preserves BC1 RGB instead of looking up DBLPLT palette indices.
pcs = kof.Pcs.__new__(kof.Pcs)
pcs.textures = [(b'L8\0\0', bytes(256)), (b'L8\0\0', b''),
                (b'DXT1', struct.pack('<HHI', 0xffff, 0, 0) * 256)]
pcs.images = [(b'MAPPLT\0\0', [(0, 0, 16, 16, 0, 0, 2, 0)])]
pcs.dxt_pixels = None
palette = [(0, 0, 0, 0)] * 256
palette[255] = (255, 128, 0, 255)
flame, axis = pcs.image(0, palette)
assert axis == (0, 0) and flame.size == (16, 16)
assert flame.getpixel((0, 0)) == flame.getpixel((15, 15)) == (255, 255, 255, 255)
pcs.textures[2] = (b'DXT1', struct.pack('<HHI', 0, 0, 0) * 256)
pcs.dxt_pixels = None
assert pcs.image(0, palette)[0].getpixel((0, 0)) == (0, 0, 0, 0)
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / 'fixture.sff'
    kof.write_sff(path, [(Image.new('RGBA', (2, 3), (255, 0, 0, 255)), (1, 2))])
    data = path.read_bytes()
    assert data[:12] == b'ElecbyteSpr\0'
    assert struct.unpack_from('<4H2h', data, 512) == (0, 0, 2, 3, 1, 2)
    offset, length = struct.unpack_from('<2I', data, 528)
    start = struct.unpack_from('<I', data, 52)[0] + offset
    assert data[start + 4:start + 12] == b'\x89PNG\r\n\x1a\n'
    assert start + length == len(data)
print('KOF importer checks passed')

# Source centers use positive-up Y and half extents; AIR uses negative-up edges.
rect = kof.collision_rect([15, 10, 20, 3, 4], {16: {'RectType': 446}})
assert rect['role'] == 'hurt' and rect['bounds'] == [7, -24, 13, -16]
assert kof.collision_rect([29, 10, 20, 3, 4], {30: {'RectType': 428}})['role'] == 'attack'
assert kof.collision_rect([116, 3, 37, 42, 37], {117: {'RectType': 122}})['role'] == 'attack'
for args in ([15, 0, 0, -1, 4], [15.5, 0, 0, 1, 4], [15, float('nan'), 0, 1, 4]):
    try:
        kof.collision_rect(args, {16: {'RectType': 446}})
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid source rectangle accepted')
print('KOF collision rectangle checks passed')
