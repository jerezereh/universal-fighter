"""Authored malformed-data checks plus optional local-stock extraction verification."""
from pathlib import Path
import struct

from xrd_package import Reader, collision_archive, jon, lzo_decoder, package, state_directory
from xrd_script import PREFIX, command_sizes, instructions, linear_poses


def rejects(function, value):
    try:
        function(value)
    except (ValueError, UnicodeError):
        return
    raise AssertionError('malformed data accepted')


script = struct.pack('<I32sI', 1, b'AuthoredState', 0) + struct.pack('<I32sI', 0, b'AuthoredState', 1)
assert state_directory(script)['states'] == [{'name': 'AuthoredState', 'offset': 0}]
rejects(state_directory, script[:20])
bad = bytearray(script); struct.pack_into('<I', bad, 36, 4)
rejects(state_directory, bad)
rejects(lambda data: Reader(data, -1), b'x')
rejects(lambda data: Reader(data).take(10), b'x')
rejects(lambda data: package(data, lambda x, n: x), b'bad-header')
record = b'JONB' + struct.pack('<H', 0) + b'\0'*3 + struct.pack('<I4h', 0, 1, 0, 0, 0) + b'\0'*78 + struct.pack('<I4f', 0, 0, -10, 8, 10)
assert jon(record)['hurt'] == [[0, 0, -10, 8, 10]]
rejects(jon, record[:-1])
bad = bytearray(record); struct.pack_into('<f', bad, len(bad)-4, float('nan'))
rejects(jon, bad)
archive = struct.pack('<4s7I', b'FPAC', 80, 80+len(record), 1, 0xc0000010, 32, 0, 0) + struct.pack('<32s4I', b'authored', 0, 0, len(record), 0) + record
assert len(collision_archive(archive)) == 1
rejects(collision_archive, archive[:-1])
print('Authored cursor/header/state/FPAC/JON rejection checks passed')

executable = bytearray(6000)
executable[:len(PREFIX)] = PREFIX
for index, size in ((15, 36), (16, 4), (21, 8)):
    struct.pack_into('<H', executable, index*2, size)
sizes = command_sizes(executable)
framed = script[:-4] + struct.pack('<I32siI', 2, b'authored_pose', 2, 1)
audit = instructions(framed, sizes)
assert audit['instruction_count'] == 3
assert linear_poses(audit, 'AuthoredState')[0]['duration_literal'] == 2
rejects(command_sizes, b'bad-table')
rejects(command_sizes, executable+PREFIX)
rejects(lambda data: instructions(data, sizes), framed[:-1])
bad = bytearray(framed); struct.pack_into('<I', bad, len(bad)-4, 2999)
rejects(lambda data: instructions(data, sizes), bad)
print('Authored native-size/framing/ambiguity checks passed')

root = Path(__file__).resolve().parent.parent
stock = root/'extracted/xrd-sign/packages/SOL_DAT_SF.upk.dec'
if stock.is_file():
    virtual, names, exports = package(stock.read_bytes(), lzo_decoder((root/'local-cache/xrd-tools/lzo.dll').resolve()))
    assert len(names) == 20 and len(exports) == 8
    from xrd_package import raw_asset
    assets = {entry['name']: raw_asset(virtual, names, entry) for entry in exports if entry['class'].startswith('REDAsset')}
    assert len(state_directory(assets['BBS_SOL'])['states']) == 197
    assert len(state_directory(assets['BBS_SOLEF'])['states']) == 102
    frames = collision_archive(assets['COL_SOL'])
    assert len(frames) == 1165 and sum(bool(f['hit']) for f in frames.values()) == 116
    assert frames['sol200_02']['hit'] and not frames['sol200_01']['hit']
    source = Path('C:/Program Files (x86)/Steam/steamapps/common/GUILTY GEAR Xrd -SIGN-/Binaries/Win32/GuiltyGearXrd.exe')
    if source.is_file():
        sizes = command_sizes(source.read_bytes())
        audit = instructions(assets['BBS_SOL'], sizes)
        assert audit['instruction_count'] == 8323
        poses = linear_poses(audit, 'NmlAtk5A')
        assert [p['duration_literal'] for p in poses] == [1, 2, 4, 2, 2, 2]
        assert all(p['name'] in frames for p in poses)
        assert [bool(frames[p['name']]['hit']) for p in poses] == [False, False, True, False, False, False]
        print('Native SIGN framing and pose/collision linkage passed')
    bad = bytearray(stock.read_bytes()); struct.pack_into('<I', bad, 4, (3 << 16) | 868)
    rejects(lambda data: package(data, lambda x, n: x), bad)
    rejects(lambda data: package(data, lzo_decoder((root/'local-cache/xrd-tools/lzo.dll').resolve())), stock.read_bytes()[:170])
    print('Local Sol state/collision checks passed; complete behavior remains unparsed')
else:
    print('Local stock check skipped: first copy/decode the bounded Sol data package')
