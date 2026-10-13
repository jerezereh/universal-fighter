"""Read-only exact-PID SIGN preflight; never attaches hooks or claims offline Training."""
import argparse
import json
from pathlib import Path

from sign.attach import pins, preflight
from sign.scene import observe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True, help='exact SIGN PID, not Rev2')
    parser.add_argument('--exe', type=Path, help='installed executable; defaults to the pinned Steam location')
    parser.add_argument('--fighters', action='store_true', help='read Sol/Ky native fighter slots; does not prove offline Training')
    parser.add_argument('--clock', action='store_true', help='sample the source update counter for 0.3 seconds; implies --fighters')
    args = parser.parse_args()
    pin = pins()['game']
    exe = args.exe or Path(pin['default_install']) / pin['exe']
    print(json.dumps(observe(args.pid, exe, clock=args.clock) if args.fighters or args.clock else
                     preflight(args.pid, exe), indent=2))


if __name__ == '__main__':
    main()
