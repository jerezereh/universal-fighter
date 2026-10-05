"""Read local KOF XIII data. Generated game data stays in ignored local-cache."""
import argparse
from collections import Counter
import json
import hashlib
import io
import math
from pathlib import Path
import struct
import zlib


class Chunk:
    def __init__(self, data):
        self.data = bytes(b ^ 0x66 for b in data)
        self.pos = 12
        if self.data[:12] != b'\x1bLua\x51\x00\x01\x04\x04\x04\x04\x00':
            raise ValueError('Unsupported KOF XIII Lua bytecode header')

    def take(self, count):
        if count < 0 or self.pos + count > len(self.data):
            raise ValueError('Truncated Lua chunk')
        value = self.data[self.pos:self.pos + count]
        self.pos += count
        return value

    def u32(self):
        return struct.unpack('<I', self.take(4))[0]

    def string(self):
        count = self.u32()
        return self.take(count)[:-1].decode('utf-8', errors='replace') if count else None

    def proto(self):
        source = self.string()
        self.take(8)
        nups, params, vararg, stack = self.take(4)
        code = [self.u32() for _ in range(self.u32())]
        constants = []
        for _ in range(self.u32()):
            tag = self.take(1)[0]
            if tag == 0:
                value = None
            elif tag == 1:
                value = bool(self.take(1)[0])
            elif tag == 3:
                value = struct.unpack('<f', self.take(4))[0]
            elif tag == 4:
                value = self.string()
            else:
                raise ValueError(f'Unknown Lua constant type {tag}')
            constants.append(value)
        children = [self.proto() for _ in range(self.u32())]
        self.take(4 * self.u32())
        for _ in range(self.u32()):
            self.string()
            self.take(8)
        for _ in range(self.u32()):
            self.string()
        return dict(source=source, code=code, constants=constants, children=children, nups=nups)


def tables(proto):
    """Evaluate only table construction; functions remain opaque data references."""
    registers, globals_, calls = [None] * 256, {}, []
    code, constants = proto['code'], proto['constants']
    def rk(value):
        return constants[value & 255] if value & 256 else registers[value]
    pc, top = 0, 0
    while pc < len(code):
        instruction = code[pc]
        pc += 1
        op, a, b, c = instruction & 63, (instruction >> 6) & 255, instruction >> 23, (instruction >> 14) & 511
        bx = instruction >> 14
        if op == 0:
            registers[a] = registers[b]
        elif op == 1:
            registers[a] = constants[bx]
        elif op == 2:
            registers[a] = bool(b)
            pc += bool(c)
        elif op == 3:
            registers[a:b + 1] = [None] * (b - a + 1)
        elif op == 5:
            registers[a] = globals_.get(constants[bx], ('global', constants[bx]))
        elif op == 7:
            globals_[constants[bx]] = registers[a]
        elif op == 9:
            registers[a][rk(b)] = rk(c)
        elif op == 10:
            registers[a] = {}
        elif op == 28:
            if b == 0 or c > 2:
                raise ValueError('Unsupported CALL result/argument count')
            call = ('call', registers[a], registers[a + 1:a + b])
            calls.append(call)
            if c != 1:
                registers[a] = call
                # Symbolic inspection only: unknown multi-results stay opaque.
                top = a + 1
        elif op == 30:
            return globals_, calls
        elif op == 34:
            if b == 0:
                b = top - a - 1
            if c == 0:
                c = code[pc]
                pc += 1
            for i in range(1, b + 1):
                registers[a][(c - 1) * 50 + i] = registers[a + i]
        elif op == 36:
            child = proto['children'][bx]
            registers[a] = ('function', bx)
            pc += child['nups']
        else:
            raise ValueError(f'Non-data opcode {op} at {pc - 1}')
    raise ValueError('Lua chunk has no return')


def inspect(root, name):
    chunk = Chunk((root / name).read_bytes())
    p = chunk.proto()
    values, calls = tables(p)
    print(json.dumps(dict(file=name, bytes_read=chunk.pos, opcodes=Counter(i & 63 for i in p['code']),
                         children=len(p['children']), globals=list(values), calls=[str(c[1])[:100] for c in calls[:20]],
                         summary={str(k): list(v)[:12] if isinstance(v, dict) else str(v)[:60] for k,v in values.items()}), indent=2))
    out = Path('local-cache/kof13')
    out.mkdir(parents=True, exist_ok=True)
    (out / (Path(name).stem + '.tables.json')).write_text(json.dumps(values, ensure_ascii=False), encoding='utf-8')


def method_calls(proto):
    """Read straight-line method calls, never execute game code or take branches."""
    regs, calls = [None] * 256, []
    for pc, instruction in enumerate(proto['code']):
        op, a, b, c = instruction & 63, instruction >> 6 & 255, instruction >> 23, instruction >> 14 & 511
        if op == 1:
            regs[a] = proto['constants'][instruction >> 14]
        elif op == 2 and c == 0:
            regs[a] = bool(b)
        elif op == 11:
            if not c & 256:
                raise ValueError('Computed method name')
            regs[a], regs[a + 1] = proto['constants'][c & 255], 'self'
        elif op == 28 and b >= 2 and c == 1:
            calls.append((regs[a], regs[a + 2:a + b]))
        elif op == 30:
            return calls
        else:
            raise ValueError(f'Unsupported method opcode {op} at {pc}')
    raise ValueError('Method has no return')


class Pcs:
    def __init__(self, data):
        if data[:8] != b'TEXLIST\0':
            raise ValueError('Unsupported PCS header')
        end = struct.unpack_from('<Q', data, 8)[0] + 16
        self.textures, self.images = [], []
        pos = 16
        while pos < end:
            if data[pos:pos + 8] != b'TEXTURE\0' or data[pos + 20:pos + 24] != b'ZIP\0':
                raise ValueError('Unsupported PCS texture')
            size = struct.unpack_from('<Q', data, pos + 8)[0]
            count = struct.unpack_from('<I', data, pos + 32)[0]
            cursor, raw = pos + 40, bytearray()
            for _ in range(count):
                length = struct.unpack_from('<I', data, cursor)[0]
                cursor += 4
                raw.extend(zlib.decompress(data[cursor:cursor + length]))
                cursor += length
            if cursor != pos + size + 16:
                raise ValueError('PCS texture length mismatch')
            self.textures.append((data[pos + 16:pos + 20], raw))
            pos = cursor
        if data[pos:pos + 8] != b'IMGLIST\0':
            raise ValueError('PCS image list missing')
        pos += 16
        while pos < len(data):
            if data[pos:pos + 8] != b'IMAGE\0\0\0':
                raise ValueError('PCS image missing')
            size = struct.unpack_from('<Q', data, pos + 8)[0]
            kind, pieces = data[pos + 16:pos + 24], []
            for cursor in range(pos + 24, pos + 16 + size, 48):
                if data[cursor:cursor + 8] != b'PRIMTIVE' or struct.unpack_from('<Q', data, cursor + 8)[0] != 32:
                    raise ValueError('Unsupported PCS primitive')
                pieces.append(struct.unpack_from('<8i', data, cursor + 16))
            self.images.append((kind, pieces))
            pos += 16 + size

    def image(self, number, palette):
        from PIL import Image
        kind, pieces = self.images[number]
        if kind != b'DBLPLT\0\0':
            raise ValueError(f'Image {number} needs unsupported {kind!r} rendering')
        left = min(p[0] for p in pieces)
        top = min(p[1] for p in pieces)
        right = max(p[0] + p[2] for p in pieces)
        bottom = max(p[1] + p[3] for p in pieces)
        result = Image.new('RGBA', (right - left, bottom - top))
        lookup = self.textures[0][1]
        for x, y, width, height, flags, map_id, texture, offset in pieces:
            if flags or texture != 1 or width > 256 or height > 256:
                raise ValueError('Unsupported DBLPLT primitive')
            content = self.textures[texture][1]
            tilemap = (map_id // 16 * 16) * 256 + map_id % 16 * 16
            patch = Image.new('RGBA', (width, height))
            pixels = patch.load()
            for py in range(height):
                for px in range(width):
                    tile = offset + lookup[tilemap + py // 16 * 256 + px // 16]
                    index = (tile // 16 * 16 + py % 16) * 256 + tile % 16 * 16 + px % 16
                    pixels[px, py] = palette[content[index]]
            result.alpha_composite(patch, (x - left, y - top))
        return result, (-left, -top)


def mirror_sprite(image, origin):
    """Reflect pixels and the axis together for source SetImage X scale -1."""
    from PIL import Image
    return image.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (image.width - origin[0], origin[1])


def write_sff(path, sprites):
    """Host-native SFFv2 presentation only; runtime simulation lives elsewhere."""
    header = bytearray(512)
    header[:16] = b'ElecbyteSpr\0\0\0\0\2'
    data_start = 512 + len(sprites) * 28 + 16
    # One unused palette keeps the host loader happy with RGBA sprites.
    struct.pack_into('<8I', header, 36, 512, len(sprites), data_start - 16, 1, data_start, 0, 0, 0)
    descriptors, data = bytearray(), bytearray(1024)
    for number, (image, origin) in enumerate(sprites):
        png = io.BytesIO()
        image.save(png, format='PNG')
        block = struct.pack('<I', image.width * image.height * 4) + png.getvalue()
        descriptors.extend(struct.pack('<4H2hH2B2I2H', 0, number, *image.size, *origin, 0, 12, 32, len(data), len(block), 0, 0))
        data.extend(block)
    palette_header = struct.pack('<4H2I', 1, 1, 256, 0, 0, 1024)
    struct.pack_into('<I', header, 56, len(data))
    path.write_bytes(header + descriptors + palette_header + data)


def collision_rect(args, common):
    """SetRect uses a zero-based parameter selector, center and half extents."""
    if len(args) != 5 or any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in args):
        raise ValueError('Invalid source rectangle')
    selector, x, y, rx, ry = args
    if selector != int(selector) or rx < 0 or ry < 0:
        raise ValueError('Invalid rectangle selector or extents')
    parameter = common[int(selector) + 1]
    kind = int(parameter['RectType'])
    # ponytail: only the selected normal and ordinary vulnerability; no throws/armor.
    role = 'hurt' if kind in (445, 446, 447, 448) else 'attack' if kind == 428 else 'other'
    return dict(selector=int(selector), type=kind, role=role,
                bounds=[x - rx, -y - ry, x + rx, -y + ry])


def export(root, output, character):
    from PIL import Image
    if character != '03':
        raise ValueError('The melee slice currently supports Kyo (03) only')
    sources = [root / f'fighter/{character}.lua', root / f'fighter/{character}.pcs', root / f'palette/{int(character, 16):04d}_00.png',
               root / 'fighter/collision_table.lua']
    chunk = Chunk(sources[0].read_bytes())
    proto = chunk.proto()
    if chunk.pos != len(chunk.data):
        raise ValueError('Trailing Lua bytes')
    values, _ = tables(proto)
    collision, _ = tables(Chunk(sources[3].read_bytes()).proto())
    common = collision['rect_param']['common']
    normal = common[30]  # SetRect selector 29, source close standing A.
    if normal['RectType'] != 428:
        raise ValueError('Unsupported close standing A collision rule')
    pcs = Pcs(sources[1].read_bytes())
    colors = list(Image.open(sources[2]).convert('RGBA').get_flattened_data())
    selected = (1, 2, 3, 5, 11, 12, 14, 15, 19, 20, 25, 26, 27, 34, 36, 68, 106, 112, 161)
    reactions = {34, 36, 106, 112, 161}
    animations, sprites, air = {}, [], []
    for action_id in selected:
        action = values['actions'][action_id]
        frames = []
        air.append(f'[Begin Action {action_id}]')
        for index in sorted(k for k in action if isinstance(k, int)):
            frame = action[index]
            if not isinstance(frame, dict):
                continue
            # Reaction behavior branches on original-engine properties. Import its
            # presentation only; the compatibility result owns motion and clocks.
            behavior = [] if action_id in reactions else method_calls(proto['children'][frame[2][1]])
            drawing = method_calls(proto['children'][frame[3][1]])
            layers, rectangles, modifiers = [], [], []
            for method, args in drawing:
                if method == 'SetImage':
                    palette_row = int(args[5])
                    modifier = args[6]
                    if args[1:5] != [0, 0, -1, 1] or any(args[7:]) or (modifier != 0 and not (action_id in (34, 36) and modifier == -3)):
                        raise ValueError('Unsupported image transform')
                    # ponytail: preserve the guard-only -3 modifier as metadata;
                    # its original renderer semantics are not yet mapped.
                    modifiers.append(modifier)
                    layers.append(pcs.image(int(args[0]), colors[palette_row * 256:(palette_row + 1) * 256]))
                elif method == 'SetRect':
                    rectangles.append(collision_rect(args, common))
                elif method != 'OverrideTransition':
                    raise ValueError(f'Unsupported draw method {method}')
            if not layers:
                raise ValueError('Frame has no image')
            left = min(-origin[0] for _, origin in layers)
            top = min(-origin[1] for _, origin in layers)
            right = max(im.width - origin[0] for im, origin in layers)
            bottom = max(im.height - origin[1] for im, origin in layers)
            image = Image.new('RGBA', (right - left, bottom - top))
            for layer, origin in reversed(layers):
                image.alpha_composite(layer, (-origin[0] - left, -origin[1] - top))
            sprite = len(sprites)
            # Every supported SetImage above has X scale -1. Bake that source
            # transform into presentation; host facing still controls boxes/motion.
            sprites.append(mirror_sprite(image, (-left, -top)))
            duration = int(frame[1])
            if duration <= 0:
                raise ValueError('Nonpositive animation duration')
            frames.append(dict(duration=duration, calls=behavior, sprite=sprite,
                               rectangles=rectangles, image_modifiers=modifiers,
                               presentation_only=action_id in reactions))
            for role, group in (('attack', 1), ('hurt', 2)):
                boxes = [r['bounds'] for r in rectangles if r['role'] == role]
                air.append(f'Clsn{group}: {len(boxes)}')
                for number, bounds in enumerate(boxes):
                    air.append(f'Clsn{group}[{number}] = ' + ','.join(str(x) for x in bounds))
            air.append(f'0,{sprite},0,0,{duration}')
        animations[action_id] = frames
        air.append('')
    used = {int(args[0]) for frames in animations.values() for frame in frames
            for name, args in frame['calls'] if name in ('SetMoveVx', 'SetMoveVy')}
    moves = {}
    for selector in sorted(used):
        call = values['moves'][selector + 1]
        if call[0] != 'call' or call[1][0] != 'function':
            raise ValueError('Unsupported move constructor')
        constructor = proto['children'][call[1][1]]
        formula = constructor['children'][1]
        instructions = [(i & 63, i >> 6 & 255, i >> 23, i >> 14 & 511) for i in formula['code']]
        constant = [(30, 0, 2, 0), (30, 0, 1, 0)]
        zero = [(1, 0, 0, 0), *constant]
        approach = [(4, 1, 0, 0), (13, 1, 1, 0), (4, 2, 1, 0), (14, 1, 1, 2), (12, 1, 0, 1), (30, 1, 2, 0), (30, 0, 1, 0)]
        if instructions not in (constant, zero, approach) or call[2][-1] is not False:
            raise ValueError('Unsupported source velocity formula')
        if instructions == zero and (call[2][0] != 0 or formula['constants'] != [0]):
            raise ValueError('Unsupported fixed-position move')
        moves[selector] = call[2]
    output.mkdir(parents=True, exist_ok=True)
    spec = dict(schema=2, backend='kof13-melee', character=character, scale=0.4,
                sources={str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                actions=animations, moves=moves,
                normal=dict(damage=int(float(normal['Attack'])), hitstop=int(float(normal['HitStop'])),
                            source_hitback=float(normal['HitBack'])))
    (output / 'foreign.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
    write_sff(output / 'kof13.sff', sprites)
    (output / 'kof13.air').write_text('\n'.join(air), encoding='utf-8')
    (output / 'kof13.cns').write_text('[Data]\nlife=1000\n[Size]\nxscale=.4\nyscale=.4\nground.back=18\nground.front=18\nheight=95\n', encoding='utf-8')
    (output / 'kof13.cmd').write_text('; Input is sampled by the host and consumed by the foreign runtime.\n', encoding='utf-8')
    (output / 'kof13.def').write_text(f'[Info]\nname="KOF XIII {character} foreign slice"\ndisplayname="KOF XIII {character}"\nruntime=kof13-melee\nmugenversion=1.1\nlocalcoord=320,240\n[Files]\ncmd=kof13.cmd\ncns=kof13.cns\nsprite=kof13.sff\nanim=kof13.air\n', encoding='utf-8')
    sprites[0][0].save(output / 'preview.png')
    print(f'Exported {len(animations)} actions / {len(sprites)} frames to {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--inspect')
    parser.add_argument('--character', default='03', choices=['03'])
    parser.add_argument('--output', type=Path, default=Path('artifacts/host-baseline/chars/kof13'))
    args = parser.parse_args()
    if args.inspect:
        inspect(args.game, args.inspect)
    else:
        if not args.output.resolve().is_relative_to(Path('artifacts').resolve()):
            parser.error('Export output must stay in ignored artifacts/')
        export(args.game, args.output, args.character)
