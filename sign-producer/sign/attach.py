"""Finding, verifying and hooking the installed game. Only the fingerprint check is generic; the rest is yours.

Keep this side fully reversible: whatever `attach` changes, `restore` undoes and verifies.
"""
import hashlib
import json
from pathlib import Path
import ctypes
from ctypes import wintypes

PINS = Path(__file__).resolve().parent.parent / 'pins.json'


def pins():
    return json.loads(PINS.read_text(encoding='utf-8'))


def fingerprint(executable):
    """SHA-256 of the executable, streamed."""
    digest = hashlib.sha256()
    with open(executable, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def verify(executable, expected=None):
    """Refuses any build other than the pinned one."""
    expected = (expected or pins()['game']['exe_sha256']).lower()
    actual = fingerprint(executable)
    if actual != expected:
        raise SystemExit(f'{executable} is not the pinned build (SHA-256 {actual[:12]}..., expected {expected[:12]}...)')
    return actual


def process_image(pid):
    """Query a PID's actual image path without opening it for writing or injection."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                 ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        raise OSError(ctypes.get_last_error(), f'cannot query process {pid}')
    try:
        exit_code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)) or exit_code.value != 259:
            raise OSError(f'process {pid} has exited')
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            raise OSError(ctypes.get_last_error(), f'cannot read process {pid} image path')
        return Path(buffer.value).resolve()
    finally:
        kernel.CloseHandle(handle)


def preflight(pid, executable):
    """Exact executable + live-PID check. No scene, hook or producer capability is inferred."""
    target = Path(executable).resolve()
    pin = pins()['game']
    if target.stat().st_size != pin['exe_size']:
        raise ValueError('SIGN executable size differs from the pinned build')
    digest = verify(target)
    actual = process_image(pid)
    if str(actual).casefold() != str(target).casefold():
        raise ValueError('PID belongs to a different executable (possibly Rev2)')
    return dict(pid=pid, executable=str(target), sha256=digest, process_image_verified=True,
                offline_training_verified=False, source_hooks_installed=False)


class Source:
    """The running game. TODO: locate the process (by path and fingerprint, not window title), confirm an offline
    mode, inject once, resolve hook sites, install the step/input/render gates."""

    def __init__(self, executable):
        self.executable = executable
        verify(executable)
        raise NotImplementedError('persistent SIGN bridge is not installed; run preflight.py --pid PID first')

    def restore(self):
        """Undo every change and return a report (restored bytes verified against disk)."""
        raise NotImplementedError

