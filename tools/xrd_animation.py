"""Bounded PSA sampling and UE3 tagged metadata inspection, not a SIGN animator."""
import math
import struct

from xrd_package import MAX_BYTES, Reader


def fname(reader, names):
    index, number = reader.unpack('2i')
    if not 0 <= index < len(names) or number < 0:
        raise ValueError('invalid animation name reference')
    return names[index] + (f'_{number-1}' if number else '')


def properties(reader, names):
    """Read 868/2 tags; arrays/unknown structs remain opaque bounded payloads."""
    result = {}
    for _ in range(10000):
        name = fname(reader, names)
        if name == 'None':
            return result
        kind = fname(reader, names)
        size, index = reader.unpack('2i')
        if size < 0 or index < 0 or (name, index) in result:
            raise ValueError('invalid/duplicate property')
        extra = None
        if kind in ('StructProperty', 'ByteProperty'):
            extra = fname(reader, names)
        elif kind == 'BoolProperty':
            extra = reader.unpack('B')[0]
            if extra not in (0, 1) or size:
                raise ValueError('invalid serialized bool')
        value = reader.take(size)
        if kind in ('IntProperty', 'ObjectProperty', 'FloatProperty'):
            if size != 4:
                raise ValueError('invalid scalar property size')
            value = struct.unpack('<f' if kind == 'FloatProperty' else '<i', value)[0]
            if kind == 'FloatProperty' and not math.isfinite(value):
                raise ValueError('non-finite property')
        elif kind == 'NameProperty':
            if size != 8:
                raise ValueError('invalid name property size')
            value = fname(Reader(value), names)
        elif kind == 'BoolProperty':
            value = bool(extra)
        result[name, index] = {'kind': kind, 'extra': extra, 'value': value}
    raise ValueError('unterminated property list')


def object_properties(virtual, names, entry):
    r = Reader(virtual[entry['offset']:entry['offset']+entry['size']], 4)  # NetIndex
    return properties(r, names)


def array(data, read_item, limit=10000):
    r = Reader(data)
    count = r.integer()
    if not 0 <= count <= limit:
        raise ValueError('invalid metadata array count')
    values = [read_item(r) for _ in range(count)]
    if r.pos != len(data):
        raise ValueError('metadata array has trailing bytes')
    return values


def scale_tracks(virtual, names, exports, sequence):
    refs = array(sequence.get(('MetaData', 0), {'value': b'\0'*4})['value'], lambda r: r.integer())
    tracks = {}
    for ref in refs:
        if not 0 < ref <= len(exports) or exports[ref-1]['class'] != 'AnimMetaData_SkelControlScaleKeyFrame':
            raise ValueError('unclassified animation metadata')
        props = object_properties(virtual, names, exports[ref-1])
        targets = array(props['SkelControlNameList', 0]['value'], lambda r: fname(r, names))
        raw_keys = array(props['ScaleKeys', 0]['value'], lambda r: properties(r, names))
        keys = []
        for key in raw_keys:
            time, scale = key['Time', 0], key['Scale', 0]
            if time['kind'] != 'FloatProperty' or scale['kind'] != 'StructProperty' or scale['extra'] != 'Vector' or len(scale['value']) != 12:
                raise ValueError('unsupported scale key')
            value = list(struct.unpack('<3f', scale['value']))
            if time['value'] < 0 or any(not math.isfinite(x) or x < 0 for x in value):
                raise ValueError('invalid scale key values')
            if keys and time['value'] <= keys[-1]['time']:
                raise ValueError('unordered scale keys')
            keys.append({'time': time['value'], 'scale': value})
        if not keys or not targets:
            raise ValueError('empty scale metadata')
        for target in targets:
            if target in tracks:
                raise ValueError('duplicate scale target')
            tracks[target] = keys
    return tracks


def diagnostic_scales(gltf, tracks, time):
    """Local held scales for inspection only; native controller semantics are pending."""
    nodes = {gltf['nodes'][i]['name']: gltf['nodes'][i] for i in gltf['skins'][0]['joints']}
    absent = []
    for target, keys in tracks.items():
        if target not in nodes:
            absent.append(target)  # A weapon AnimSet also serves the excluded high mesh.
            continue
        available = [x for x in keys if x['time'] <= time+1e-6]
        if not available:
            raise ValueError('no scale key at diagnostic sample time')
        x, y, z = available[-1]['scale']
        nodes[target]['scale'] = [x, z, y]  # glTF basis swaps UE Y/Z.
    return absent


def psa(data):
    """Read pinned UE Viewer's PSA layout and validate the full frame partition."""
    if len(data) > MAX_BYTES:
        raise ValueError('PSA exceeds inspection limit')
    r, chunks = Reader(data), {}
    expected = {'ANIMHEAD': 0, 'BONENAMES': 120, 'ANIMINFO': 168, 'ANIMKEYS': 32, 'SCALEKEYS': 16}
    while r.pos < len(data):
        raw, flags, size, count = r.unpack('20s3i')
        tag = raw.split(b'\0', 1)[0].decode('ascii')
        if tag not in expected or tag in chunks or size != expected[tag] or count < 0:
            raise ValueError('unsupported PSA chunk')
        chunks[tag] = (r.take(size*count), count)
    if set(chunks) != set(expected) or chunks['ANIMHEAD'][1] or chunks['SCALEKEYS'][1]:
        raise ValueError('unsupported PSA header/scale tracks')
    bone_data, bone_count = chunks['BONENAMES']
    if not 0 < bone_count <= 4096:
        raise ValueError('invalid PSA bone count')
    bones = [bone_data[i*120:i*120+64].split(b'\0', 1)[0].decode('ascii') for i in range(bone_count)]
    if any(not x for x in bones) or len(set(bones)) != len(bones):
        raise ValueError('invalid/duplicate PSA bones')
    info, count = chunks['ANIMINFO']
    clips, next_frame = {}, 0
    if not 0 < count <= 10000:
        raise ValueError('invalid PSA sequence count')
    for i in range(count):
        raw = info[i*168:(i+1)*168]
        name = raw[:64].split(b'\0', 1)[0].decode('ascii')
        total, root, style, quota, reduction, track_time, rate, start, first, frames = struct.unpack('<4i3f3i', raw[128:])
        if not name or name in clips or total != bone_count or start or first != next_frame or frames <= 0 or quota != total*frames:
            raise ValueError('invalid PSA sequence frame partition')
        if any(not math.isfinite(x) or x <= 0 for x in (track_time, rate)):
            raise ValueError('invalid PSA sequence clock')
        clips[name] = {'first_frame': first, 'frames': frames, 'rate': rate, 'track_time': track_time}
        next_frame += frames
    keys, count = chunks['ANIMKEYS']
    if count != next_frame*bone_count:
        raise ValueError('PSA key count disagrees with sequences')
    return {'bones': bones, 'clips': clips, 'keys': keys}


def sample(animation, clip, frame):
    selected = animation['clips'][clip]
    if not 0 <= frame < selected['frames']:
        raise ValueError('PSA sample outside sequence')
    offset = (selected['first_frame']+frame)*len(animation['bones'])*32
    result = []
    for i in range(len(animation['bones'])):
        values = struct.unpack_from('<8f', animation['keys'], offset+i*32)
        if any(not math.isfinite(x) for x in values) or abs(sum(x*x for x in values[3:7])-1) > .02:
            raise ValueError('invalid PSA transform')
        result.append(values)
    return result


def posed_gltf(gltf, animation, clip, frame):
    """Apply one explicit exported sample using pinned PSA/glTF basis conversions.

    No sprite-suffix mapping, scale-controller emulation or source shader is implied.
    The caller owns this glTF dict. Its inverse bind matrices remain the mesh bind pose.
    """
    if len(gltf['skins']) != 1:
        raise ValueError('expected one source skin')
    joints = gltf['skins'][0]['joints']
    tracks = dict(zip(animation['bones'], sample(animation, clip, frame)))
    mesh_names = [gltf['nodes'][i]['name'] for i in joints]
    if len(set(mesh_names)) != len(mesh_names) or any(name not in tracks for name in mesh_names):
        raise ValueError('mesh bone missing/ambiguous in PSA')
    if mesh_names[0] != animation['bones'][0]:
        raise ValueError('mesh/PSA root disagreement')
    for bone, node_index in enumerate(joints):
        values = tracks[mesh_names[bone]]
        px, py, pz, qx, qy, qz, qw, time = values
        # Undo ExportPsk.cpp MIRROR_MESH, then ExportGltf.cpp TransformPosition/Rotation.
        translation = [px*.01, pz*.01, -py*.01]
        rotation = [qx, qz, -qy, -qw]
        if bone == 0:
            rotation[:3] = [-x for x in rotation[:3]]  # exporter root conjugation
        gltf['nodes'][node_index]['translation'] = translation
        gltf['nodes'][node_index]['rotation'] = rotation
    return gltf
