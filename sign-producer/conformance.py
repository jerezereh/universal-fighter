"""Runs uf-arena's conformance kit (pinned in pins.json) against this producer.

    python conformance.py                         # --fake, both image modes
    python conformance.py --modes shared -- --exe "C:/Games/MyGame/game.exe"

Arguments after -- go to produce.py; without any, the reference fighter (--fake) is checked.
"""
import argparse
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--modes', default='rgba,shared')
    p.add_argument('--steps', type=int, default=300)
    p.add_argument('--json', type=Path, default=HERE / 'artifacts' / 'conformance.json')
    p.add_argument('producer_args', nargs=argparse.REMAINDER)
    args = p.parse_args()
    pinned = json.loads((HERE / 'pins.json').read_text(encoding='utf-8'))['protocol']
    try:
        installed = importlib.metadata.version('uf-protocol')
    except importlib.metadata.PackageNotFoundError:
        raise SystemExit('uf-protocol is not installed: pip install -r requirements.txt') from None
    if installed != pinned['uf_protocol']:
        raise SystemExit(f'uf-protocol {installed} is installed but pins.json pins {pinned["uf_protocol"]} '
                         f'({pinned["tag"]}): pip install -r requirements.txt')
    extra = args.producer_args[1:] if args.producer_args[:1] == ['--'] else args.producer_args
    args.json.parent.mkdir(exist_ok=True)
    command = [sys.executable, '-m', 'ufconform', '--launch', '--modes', args.modes, '--steps', str(args.steps),
               '--json', str(args.json), '--', sys.executable, str(HERE / 'produce.py')] + (extra or ['--fake'])
    return subprocess.call(command, cwd=HERE)


if __name__ == '__main__':
    sys.exit(main())

