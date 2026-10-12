"""Finding, verifying and hooking the installed game. Only the fingerprint check is generic; the rest is yours.

Keep this side fully reversible: whatever `attach` changes, `restore` undoes and verifies.
"""
import hashlib
import json
from pathlib import Path

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


class Source:
    """The running game. TODO: locate the process (by path and fingerprint, not window title), confirm an offline
    mode, inject once, resolve hook sites, install the step/input/render gates."""

    def __init__(self, executable):
        self.executable = executable
        verify(executable)
        raise NotImplementedError('attach to the game (PRODUCER_GUIDE.md steps 1-2)')

    def restore(self):
        """Undo every change and return a report (restored bytes verified against disk)."""
        raise NotImplementedError

