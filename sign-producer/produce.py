"""Serves this game's fighter to uf-arena (launch convention: --listen HOST:PORT --ready FILE [--shared-layer]).

    python produce.py --fake            # ufproducer's reference fighter: no game needed
    python produce.py --exe PATH        # the real producer (sign/)
"""
import argparse
import sys

from ufproducer import fake, server

from sign import attach
from sign.producer import SignProducer


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--fake', action='store_true', help="serve ufproducer's reference fighter instead of the game")
    parser.add_argument('--exe', help="the game's executable (verified against pins.json)")
    if '--fake' in sys.argv:
        sys.argv.remove('--fake')
        return fake.main()
    args, _ = parser.parse_known_args()
    if not args.exe:
        parser.error('give --exe PATH (or --fake)')
    source = attach.Source(args.exe)
    try:
        server.main(lambda _: SignProducer(source), parser=parser, game=SignProducer.game)
    finally:
        print('restore:', source.restore())


if __name__ == '__main__':
    main()

