"""Read-only exact-PID SIGN preflight; never attaches hooks or claims offline Training."""
import argparse
import json
from pathlib import Path

from sign.attach import pins, preflight


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True, help='exact SIGN PID, not Rev2')
    parser.add_argument('--exe', type=Path, help='installed executable; defaults to the pinned Steam location')
    args = parser.parse_args()
    pin = pins()['game']
    exe = args.exe or Path(pin['default_install']) / pin['exe']
    print(json.dumps(preflight(args.pid, exe), indent=2))


if __name__ == '__main__':
    main()
