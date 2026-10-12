"""Unit tests that run without the game. Add your own against recorded source data, never game files."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ufproducer import protocol
from ufproducer.fake import FakeProducer
from ufproducer.server import Connection

from sign import attach
from sign.producer import SignProducer

SCRATCH = Path(__file__).resolve().parents[1] / 'local-cache'
SCRATCH.mkdir(exist_ok=True)


def request(op, sequence, tick, game, **extra):
    q = dict(version=1, session='s' * 32, game=game, sequence=sequence, tick=tick, operation=op,
             context=dict(Advance=op == 'step', AcceptInput=op == 'step', Facing=1.0), X=0.0, Y=0.0, Life=1000)
    q.update(extra)
    return q


class TemplateTests(unittest.TestCase):
    def test_pins_name_a_protocol(self):
        pins = attach.pins()
        self.assertTrue(pins['protocol']['tag'].startswith('protocol-v'))
        self.assertIn('exe_sha256', pins['game'])

    def test_fingerprint_refuses_other_builds(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as folder:
            exe = Path(folder) / 'game.exe'
            exe.write_bytes(b'not the pinned build')
            digest = attach.fingerprint(exe)
            self.assertEqual(attach.verify(exe, digest), digest)
            with self.assertRaises(SystemExit):
                attach.verify(exe, '0' * 64)

    def test_real_producer_does_not_claim_unverified_capabilities(self):
        self.assertEqual(SignProducer.game, 'ggxrd-sign-376300-1028441')
        for capability in protocol.REQUIRED_CAPABILITIES:
            self.assertNotIn(capability, SignProducer.capabilities)

    def test_real_source_refuses_unpinned_build(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as folder:
            exe = Path(folder) / 'GuiltyGearXrd.exe'
            exe.write_bytes(b'not the pinned build')
            with self.assertRaises(SystemExit):
                attach.Source(exe)

    def test_preflight_rejects_rev2_pid_without_hooks(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as folder:
            exe = Path(folder) / 'GuiltyGearXrd.exe'
            exe.write_bytes(b'SIGN')
            with patch.object(attach, 'pins', return_value={'game': {'exe_size': 4}}), \
                 patch.object(attach, 'verify', return_value='verified'), \
                 patch.object(attach, 'process_image', return_value=Path(folder) / 'REV2' / 'GuiltyGearXrd.exe'):
                with self.assertRaisesRegex(ValueError, 'different executable'):
                    attach.preflight(42, exe)

    def test_fake_serves_a_session(self):
        c = Connection(FakeProducer())
        game = FakeProducer.game
        self.assertNotIn('error', c.handle(request('hello', 1, 0, game)))
        reply = c.handle(request('step', 2, 1, game, input=dict(right=True)))
        self.assertEqual(reply['state']['Frame'], 1)
        self.assertIn('image', json.loads(json.dumps(reply)))


if __name__ == '__main__':
    unittest.main()

