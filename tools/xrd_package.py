"""Bounded reader for decoded SIGN UE3 868/2 packages; never writes game files.

Layout reference: pinned UE Viewer. LZO is its external development-only safe decoder.
This extracts raw assets and state-directory metadata, not executable move semantics.
"""
import ctypes
import hashlib
import math
import re
import struct

MAX_BYTES = 256 * 1024 * 1024


class Reader:
    def __init__(self, data, offset=0):
        if not 0 <= offset <= len(data):
            raise ValueError('invalid package cursor')
        self.data, self.pos = data, offset

    def take(self, size):
        if size < 0 or self.pos + size > len(self.data):
            raise ValueError('truncated package')
        value = self.data[self.pos:self.pos + size]
        self.pos += size
        return value

    def unpack(self, fmt):
        return struct.unpack('<' + fmt, self.take(struct.calcsize('<' + fmt)))

    def integer(self):
        return self.unpack('i')[0]

    def string(self):
        n = self.integer()
        if not n or abs(n) > 4096:
            raise ValueError('invalid FString length')
        text = self.take(n if n > 0 else -2*n)
        encoding, terminator = ('utf-8', b'\0') if n > 0 else ('utf-16-le', b'\0\0')
        if not text.endswith(terminator):
            raise ValueError('unterminated FString')
        return text[:-len(terminator)].decode(encoding)


def lzo_decoder(dll):
    library = ctypes.CDLL(str(dll))
    function = library.lzo1x_decompress_safe
    function.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                         ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p]
    function.restype = ctypes.c_int

    def decode(data, size):
        if not 0 < size <= MAX_BYTES:
            raise ValueError('invalid LZO output size')
        output, length = ctypes.create_string_buffer(size), ctypes.c_size_t(size)
        status = function(data, len(data), output, ctypes.byref(length), None)
        if status or length.value != size:
            raise ValueError(f'LZO decode failed: {status}, {length.value}/{size}')
        return output.raw
    return decode


def package(data, decode):
    if len(data) > MAX_BYTES:
        raise ValueError('package exceeds inspection limit')
    r = Reader(data)
    if r.unpack('II') != (0x9e2a83c1, (2 << 16) | 868):
        raise ValueError('expected decoded Xrd SIGN UE3 868/2 package')
    header_size = r.integer()
    r.string()
    flags, names_n, names_at, exports_n, exports_at, imports_n, imports_at = r.unpack('I6i')
    r.take(20)  # DependsOffset, three >=623 summary fields, >=584 field.
    r.take(16)  # GUID
    generations = r.integer()
    if not 0 <= generations <= 64:
        raise ValueError('invalid generation count')
    r.take(generations * 12)
    engine, cooker, compression, count = r.unpack('4i')
    if engine != 10246 or compression != 2 or not 0 < count <= 4096:
        raise ValueError('unsupported SIGN engine/compression layout')
    chunks = [r.unpack('4i') for _ in range(count)]
    virtual = bytearray()
    for uoff, usize, coff, csize in chunks:
        if not 0 <= uoff <= MAX_BYTES or not 0 < usize <= MAX_BYTES-uoff:
            raise ValueError('invalid virtual chunk bounds')
        c = Reader(data, coff)
        tag, block, total_c, total_u = c.unpack('4I')
        if tag != 0x9e2a83c1 or not 0 < block <= 0x20000 or total_u != usize:
            raise ValueError('invalid compressed chunk header')
        blocks = [c.unpack('2I') for _ in range((usize + block - 1)//block)]
        if sum(x for x, _ in blocks) != total_c or sum(y for _, y in blocks) != usize or c.pos+total_c != coff+csize:
            raise ValueError('inconsistent compressed chunk sizes')
        if not virtual:
            virtual.extend(data[:uoff])
        if len(virtual) != uoff:
            raise ValueError('non-contiguous virtual chunks')
        for compressed, expanded in blocks:
            if not 0 < expanded <= block:
                raise ValueError('invalid compressed block size')
            virtual.extend(decode(c.take(compressed), expanded))
    if not 0 < header_size <= len(virtual):
        raise ValueError('invalid package header size')
    for amount in (names_n, exports_n, imports_n):
        if not 0 <= amount <= 100000:
            raise ValueError('invalid table count')
    n = Reader(virtual, names_at)
    names = []
    for _ in range(names_n):
        names.append(n.string())
        n.take(8)

    def name(index, number=0):
        if not 0 <= index < len(names) or number < 0:
            raise ValueError('invalid name reference')
        return names[index] + (f'_{number-1}' if number else '')

    i = Reader(virtual, imports_at)
    imports = []
    for _ in range(imports_n):
        cp, cpn, cn, cnn, outer, on, onn = i.unpack('7i')
        imports.append(name(on, onn))
    e = Reader(virtual, exports_at)
    exports = []
    for _ in range(exports_n):
        klass, superclass, outer, on, onn, archetype = e.unpack('6i')
        e.take(8)
        size, offset, export_flags, net_count = e.unpack('4i')
        if not 0 <= net_count <= 64:
            raise ValueError('invalid export generation count')
        e.take(net_count * 4 + 20)
        if size < 0 or offset < 0 or offset+size > len(virtual):
            raise ValueError('invalid export payload bounds')
        exports.append({'name': name(on, onn), 'class_index': klass, 'size': size, 'offset': offset})
    for entry in exports:
        index = entry.pop('class_index')
        if index < 0 and -index <= len(imports):
            entry['class'] = imports[-index-1]
        elif 0 < index <= len(exports):
            entry['class'] = exports[index-1]['name']
        elif index == 0:
            entry['class'] = 'Class'
        else:
            raise ValueError('invalid export class reference')
    return bytes(virtual), names, exports


def raw_asset(virtual, names, entry):
    """Read DataSize property and inline, uncompressed UE3 BulkData of RED assets."""
    start, end = entry['offset'], entry['offset'] + entry['size']
    r = Reader(virtual[:end], start)
    r.take(4)  # NetIndex
    prop, prop_number, kind, kind_number, size, array_index, data_size = r.unpack('7i')
    none, none_number = r.unpack('2i')
    if any(not 0 <= x < len(names) for x in (prop, kind, none)):
        raise ValueError('invalid RED asset property reference')
    if names[prop] != 'DataSize' or names[kind] != 'IntProperty' or names[none] != 'None' or (
            prop_number, kind_number, size, array_index, none_number) != (0, 0, 4, 0, 0):
        raise ValueError('unsupported RED asset property layout')
    flags, count, disk_size, offset = r.unpack('4i')
    if flags or count != data_size or disk_size != count or offset != r.pos or not 0 < count <= end-offset:
        raise ValueError('unsupported RED asset bulk layout')
    return r.take(count)


def state_directory(script):
    r = Reader(script)
    count = r.integer()
    if not 0 < count < 10000:
        raise ValueError('invalid BBScript state count')
    entries = []
    for _ in range(count):
        raw, offset = r.unpack('32sI')
        text = raw.split(b'\0', 1)[0].decode('ascii')
        if not text or raw[len(text):] != b'\0' * (32-len(text)):
            raise ValueError('invalid state name padding')
        entries.append({'name': text, 'offset': offset})
    base = r.pos
    if len({x['name'] for x in entries}) != count:
        raise ValueError('duplicate state directory name')
    for entry in entries:
        p = Reader(script, base+entry['offset'])
        if p.integer() != 0 or p.take(32).split(b'\0', 1)[0].decode('ascii') != entry['name']:
            raise ValueError('state directory does not point to matching beginState')
    return {'states': entries, 'code_offset': base, 'sha256': hashlib.sha256(script).hexdigest()}


def collision_archive(data):
    r = Reader(data)
    magic, start, total, count, flags, width, reserved1, reserved2 = r.unpack('4s7I')
    if magic != b'FPAC' or total != len(data) or width != 32 or flags != 0xc0000010 or (
            reserved1, reserved2) != (0, 0) or not 0 < count <= 100000 or start != 32+48*count:
        raise ValueError('unsupported SIGN collision FPAC layout')
    frames = {}
    for _ in range(count):
        raw_name, index, offset, size, entry_flags = r.unpack('32s4I')
        name = raw_name.split(b'\0', 1)[0].decode('ascii')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name in frames or start+offset+size > len(data):
            raise ValueError('invalid collision archive entry')
        try:
            frames[name] = jon(data[start+offset:start+offset+size])
        except ValueError as error:
            raise ValueError(f'{name}: {error}') from error
    return frames


def jon(data):
    r = Reader(data)
    if r.take(4) != b'JONB':
        raise ValueError('unsupported collision record magic')
    images = [r.take(32).split(b'\0', 1)[0].decode('ascii') for _ in range(r.unpack('H')[0])]
    r.take(3)
    chunks, *counts = r.unpack('I4h')
    if chunks > 10000 or any(x < 0 or x > 10000 for x in counts):
        raise ValueError('invalid collision record counts')
    metadata = r.unpack('39H')
    r.take(80*chunks)  # Visual chunks aren't collision boxes; raw source is retained separately.
    groups = {}
    for key, count in zip(('hurt', 'hit', 'auxiliary1', 'auxiliary2'), counts):
        boxes = []
        for _ in range(count):
            index, x, y, width, height = r.unpack('I4f')
            if any(not math.isfinite(v) for v in (x, y, width, height)) or width < 0 or height < 0:
                raise ValueError('invalid collision rectangle')
            boxes.append([index, x, y, width, height])
        groups[key] = boxes
    points = []
    while r.pos < len(data):
        index, x, y, width, height = r.unpack('I4f')
        if width or height or not math.isfinite(x) or not math.isfinite(y):
            raise ValueError('unsupported trailing collision record')
        points.append([index, x, y])  # Point IDs/metadata semantics remain unclassified.
    return {'images': images, 'metadata': list(metadata), 'points': points, **groups}
