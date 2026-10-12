"""Read-only witness for the pinned SIGN Sol/Ky scene. This does not prove offline mode."""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import re
import struct


ENGINE_RVA = 22569420  # Derived from the pinned SIGN build; see docs/XRD_SIGN_NATIVE_PROBE.md.
SLOTS_OFFSET = 196
COUNT_OFFSET = 176
POSE_BYTES = 0x2600


def fighter_pair(read, base):
    """Return the two native slots only when their live pose names identify Sol and Ky."""
    engine, = struct.unpack('<I', read(base + ENGINE_RVA, 4))
    if not engine:
        raise ValueError('SIGN battle engine is absent')
    count, = struct.unpack('<i', read(engine + COUNT_OFFSET, 4))
    if not 2 <= count <= 256:
        raise ValueError('SIGN entity count is outside observed training bounds')
    slots = struct.unpack('<2I', read(engine + SLOTS_OFFSET, 8))
    if not all(slots) or slots[0] == slots[1]:
        raise ValueError('SIGN fighter slots are invalid')
    fighters = []
    for slot, address in enumerate(slots):
        data = read(address, POSE_BYTES)
        names = [match[1][:-1].decode('ascii') for match in
                 re.finditer(rb'(?=([a-z]{2,4}[0-9]{3}_[0-9]{2}\0))', data)
                 if match.start() % 4 == 0]
        expected = ('sol', 'kyk')[slot]
        if not any(name.startswith(expected) for name in names):
            raise ValueError(f'SIGN slot {slot} is not the expected {expected} fighter')
        facing, x, y = struct.unpack_from('<3i', data, 572)
        if facing not in (0, 1) or max(abs(x), abs(y)) > 10_000_000:
            raise ValueError('SIGN fighter transform is invalid')
        fighters.append(dict(slot=slot, character=expected, x_raw=x, y_raw=y,
                             facing_left=bool(facing)))
    if struct.unpack('<I', read(base + ENGINE_RVA, 4))[0] != engine or \
            struct.unpack('<2I', read(engine + SLOTS_OFFSET, 8)) != slots:
        raise ValueError('SIGN scene changed during observation')
    return fighters


class ProcessReader:
    """Owns only query/read rights to one already verified SIGN PID."""

    def __init__(self, pid):
        self.api = c.WinDLL('kernel32', use_last_error=True)
        self.api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        self.api.OpenProcess.restype = w.HANDLE
        self.api.ReadProcessMemory.argtypes = [w.HANDLE, c.c_void_p, c.c_void_p,
                                               c.c_size_t, c.POINTER(c.c_size_t)]
        self.api.ReadProcessMemory.restype = w.BOOL
        self.api.CloseHandle.argtypes = [w.HANDLE]
        self.api.CloseHandle.restype = w.BOOL
        self.handle = self.api.OpenProcess(0x1010, False, pid)
        if not self.handle:
            raise c.WinError(c.get_last_error())

    def read(self, address, size):
        if not 0 < address <= 0xffffffff or not 0 < size <= POSE_BYTES:
            raise ValueError('unbounded SIGN process read')
        data = c.create_string_buffer(size)
        got = c.c_size_t()
        if not self.api.ReadProcessMemory(self.handle, c.c_void_p(address), data,
                                          size, c.byref(got)) or got.value != size:
            raise c.WinError(c.get_last_error())
        return data.raw

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def observe(pid, executable):
    """Check a pinned, live process and read its current fighter pair without hooks."""
    from .attach import preflight

    executable = Path(executable).resolve()
    receipt = preflight(pid, executable)
    class Module(c.Structure):
        _fields_ = [('size', w.DWORD), ('id', w.DWORD), ('pid', w.DWORD),
                    ('global_usage', w.DWORD), ('usage', w.DWORD), ('base', c.c_void_p),
                    ('image_size', w.DWORD), ('module', w.HMODULE), ('name', w.WCHAR * 256),
                    ('path', w.WCHAR * 260)]

    with ProcessReader(pid) as process:
        api = process.api
        api.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
        api.CreateToolhelp32Snapshot.restype = w.HANDLE
        api.Module32FirstW.argtypes = [w.HANDLE, c.POINTER(Module)]
        api.Module32FirstW.restype = w.BOOL
        api.Module32NextW.argtypes = [w.HANDLE, c.POINTER(Module)]
        api.Module32NextW.restype = w.BOOL
        snapshot = api.CreateToolhelp32Snapshot(0x18, pid)
        if snapshot == w.HANDLE(-1).value:
            raise c.WinError(c.get_last_error())
        try:
            row = Module()
            row.size = c.sizeof(row)
            found = api.Module32FirstW(snapshot, c.byref(row))
            while found and row.path.casefold() != str(executable).casefold():
                found = api.Module32NextW(snapshot, c.byref(row))
            if not found or not row.base or row.image_size != 34549760:
                raise ValueError('pinned SIGN main module is absent or changed')
            receipt['fighters'] = fighter_pair(process.read, row.base)
            receipt['fighter_pair_verified'] = True
        finally:
            api.CloseHandle(snapshot)
    return receipt
