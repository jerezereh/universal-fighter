"""Bounded PE/signature inspection and Windows read-only process access.

No injector, remote calls, process suspension or memory-writing APIs. Addresses and
loaded game bytes belong in ignored local evidence, never in versioned profiles.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
from pathlib import Path
import re
import struct

SIGN_HASH = 'f7a2e990b664f882bf16eafa94433ff0460f0b630c083fd0760a0d7949e08b78'
MAX_IMAGE = 64 << 20


class PE:
    def __init__(self, data):
        self.data = data
        if len(data) < 64 or data[:2] != b'MZ':
            raise ValueError('not a PE image')
        pe, = struct.unpack_from('<I', data, 60)
        if pe < 64 or pe + 24 > len(data) or data[pe:pe+4] != b'PE\0\0':
            raise ValueError('invalid PE header')
        machine, count = struct.unpack_from('<HH', data, pe+4)
        optional_size, = struct.unpack_from('<H', data, pe+20)
        optional = pe+24
        if machine != 0x14c or not 1 <= count <= 32 or optional_size < 96 or optional+optional_size+count*40 > len(data):
            raise ValueError('expected bounded x86 PE32 image')
        if struct.unpack_from('<H', data, optional)[0] != 0x10b:
            raise ValueError('not PE32')
        self.entry, self.base = struct.unpack_from('<I', data, optional+16)[0], struct.unpack_from('<I', data, optional+28)[0]
        self.image_size, = struct.unpack_from('<I', data, optional+56)
        if not 4096 <= self.image_size <= MAX_IMAGE:
            raise ValueError('unbounded PE virtual image')
        self.sections = []
        for i in range(count):
            at = optional+optional_size+i*40
            name = data[at:at+8].split(b'\0')[0].decode('ascii')
            virtual, rva, size, raw = struct.unpack_from('<4I', data, at+8)
            flags, = struct.unpack_from('<I', data, at+36)
            if rva+max(virtual, size) > self.image_size or raw+size > len(data):
                raise ValueError('section outside PE bounds')
            self.sections.append(dict(name=name, rva=rva, virtual_size=virtual, raw=raw, size=size, flags=flags))

    def executable_sections(self):
        return [s for s in self.sections if s['flags'] & 0x20000000 and s['name'] != '.bind']


def legacy_patterns(source):
    """Read discovery declarations from the pinned public reference, not retail bytes."""
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
    pattern = r'(\w+)\s*=\s*[^\n;]*?sigscan\(\s*"GuiltyGearXrd.exe",\s*"([^\"]*)",\s*"([x?]+)"\)\s*(?:([+-])\s*(0x[0-9a-fA-F]+|\d+))?'
    rows = []
    for m in re.finditer(pattern, source):
        values = re.findall(r'\\x([0-9a-fA-F]{2})', m[2])
        if re.sub(r'\\x[0-9a-fA-F]{2}', '', m[2]) or len(values) != len(m[3]):
            raise ValueError('unsupported reference signature literal')
        delta = int(m[5], 0) if m[5] else 0
        if m[4] == '-':
            delta = -delta
        rows.append(dict(name=m[1], data=bytes(int(v,16) for v in values), mask=m[3], delta=delta))
    if not rows or len({r['name'] for r in rows}) != len(rows):
        raise ValueError('missing or ambiguous reference declarations')
    return rows


def scan_patterns(sections, patterns):
    result = []
    for p in patterns:
        rx = re.compile(b''.join(re.escape(bytes([v])) if p['mask'][i] == 'x' else b'.'
                                for i,v in enumerate(p['data'])), re.S)
        matches = []
        for s, data in sections:
            start = 0
            while (m := rx.search(data, start)) is not None:
                start = m.start()+1  # Include overlapping matches when checking ambiguity.
                target = s['rva']+m.start()+p['delta']
                if not s['rva'] <= target < s['rva']+len(data):
                    raise ValueError('reference adjustment leaves code section')
                matches.append(dict(section=s['name'], match_rva=s['rva']+m.start(), candidate_rva=target))
                if len(matches) > 64:
                    raise ValueError('signature excessively ambiguous')
        result.append(dict(name=p['name'], matches=matches, unique=len(matches)==1,
                           validated_semantics=False))
    return result


def fingerprint(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


class ReadOnlyProcess:
    """A handle with VM_READ and QUERY_LIMITED_INFORMATION only."""
    def __init__(self, pid, executable=None):
        if not hasattr(C, 'WinDLL'):
            raise OSError('Windows process reads require Windows')
        self.api = C.WinDLL('kernel32', use_last_error=True)
        a = self.api
        a.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]; a.OpenProcess.restype = W.HANDLE
        a.CloseHandle.argtypes = [W.HANDLE]; a.CloseHandle.restype = W.BOOL
        a.QueryFullProcessImageNameW.argtypes = [W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]; a.QueryFullProcessImageNameW.restype = W.BOOL
        a.ReadProcessMemory.argtypes = [W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)]; a.ReadProcessMemory.restype = W.BOOL
        a.CreateToolhelp32Snapshot.argtypes = [W.DWORD,W.DWORD]; a.CreateToolhelp32Snapshot.restype = W.HANDLE
        self.pid = pid
        self.handle = a.OpenProcess(0x1000|0x10, False, pid)
        if not self.handle:
            raise C.WinError(C.get_last_error())
        try:
            size = W.DWORD(32768); name = C.create_unicode_buffer(size.value)
            if not a.QueryFullProcessImageNameW(self.handle,0,name,C.byref(size)):
                raise C.WinError(C.get_last_error())
            self.executable = Path(name.value).resolve()
            if executable is not None and self.executable != Path(executable).resolve():
                raise ValueError('PID executable differs from verified target')
        except Exception:
            self.close()
            raise

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self,*_):
        self.close()

    def read(self, address, size):
        if address <= 0 or not 0 < size <= MAX_IMAGE:
            raise ValueError('unbounded process read')
        buffer = C.create_string_buffer(size); got = C.c_size_t()
        if not self.api.ReadProcessMemory(self.handle,C.c_void_p(address),buffer,size,C.byref(got)):
            raise C.WinError(C.get_last_error())
        if got.value != size:
            raise ValueError('partial process read')
        return buffer.raw

    def module_base(self):
        class ModuleEntry(C.Structure):
            _fields_ = [('size',W.DWORD),('id',W.DWORD),('pid',W.DWORD),('global_usage',W.DWORD),
                        ('usage',W.DWORD),('base',C.c_void_p),('image_size',W.DWORD),('module',W.HMODULE),
                        ('name',W.WCHAR*256),('path',W.WCHAR*260)]
        a = self.api
        for name in ('Module32FirstW','Module32NextW'):
            f = getattr(a,name); f.argtypes=[W.HANDLE,C.POINTER(ModuleEntry)]; f.restype=W.BOOL
        snapshot = a.CreateToolhelp32Snapshot(0x8|0x10,self.pid)
        if snapshot == W.HANDLE(-1).value:
            raise C.WinError(C.get_last_error())
        try:
            row = ModuleEntry(); row.size=C.sizeof(row)
            found = a.Module32FirstW(snapshot,C.byref(row))
            while found:
                if Path(row.path).resolve()==self.executable:
                    return row.base,row.image_size
                found = a.Module32NextW(snapshot,C.byref(row))
            raise ValueError('main process module not found')
        finally:
            a.CloseHandle(snapshot)
