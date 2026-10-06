"""Inspect SIGN instruction boundaries using the native executable's ushort table.

Only common framing opcodes are named; remaining parameters are opaque bytes. No VM
or engine defaults are inferred from Rev2. Extracted instruction data stays local.
"""
import struct

from xrd_package import Reader, state_directory

PREFIX = struct.pack('<9H', 36, 4, 40, 4, 12, 4, 24, 12, 20)


def command_sizes(executable):
    at = executable.find(PREFIX)
    if at < 0 or executable.find(PREFIX, at+1) >= 0:
        raise ValueError('native SIGN size table missing or ambiguous')
    # Validate independent framing entries beyond the discovery prefix.
    for index, size in ((15, 36), (16, 4), (21, 8)):
        if struct.unpack_from('<H', executable, at+index*2)[0] != size:
            raise ValueError('native size-table framing mismatch')

    def get(index):
        if not 0 <= index < 3000 or at+2*index+2 > len(executable):
            raise ValueError('unknown native instruction ID')
        size = struct.unpack_from('<H', executable, at+2*index)[0]
        if not 4 <= size <= 512 or size % 4:
            raise ValueError(f'unsupported native instruction size: {index}/{size}')
        return size
    return get


def instructions(script, sizes):
    directory = state_directory(script)
    r = Reader(script, directory['code_offset'])
    result, used = [], {}
    while r.pos < len(script):
        offset = r.pos
        index = r.unpack('I')[0]
        size = sizes(index)
        args = r.take(size-4)
        used[index] = size
        result.append({'offset': offset-directory['code_offset'], 'id': index, 'args': args.hex()})
    boundaries = {item['offset']: item for item in result}
    for entry in directory['states']:
        if entry['offset'] not in boundaries or boundaries[entry['offset']]['id'] != 0:
            raise ValueError('state directory enters an instruction payload')
    return {'directory': directory, 'instruction_count': len(result),
            'sizes': used, 'instructions': result, 'semantics_complete': False}


def linear_poses(audit, state):
    """Source pose literals in one state, not a claim about branches/engine timing."""
    entry = next(x for x in audit['directory']['states'] if x['name'] == state)
    rows = [x for x in audit['instructions'] if x['offset'] >= entry['offset']]
    poses = []
    for row in rows:
        if row['id'] == 1:
            return poses
        if row['id'] == 2:
            raw = bytes.fromhex(row['args'])
            if len(raw) != 36:
                raise ValueError('invalid sprite instruction size')
            name = raw[:32].split(b'\0', 1)[0].decode('ascii')
            duration = struct.unpack_from('<i', raw, 32)[0]
            poses.append({'name': name, 'duration_literal': duration, 'offset': row['offset']})
    raise ValueError('state has no endState boundary')
