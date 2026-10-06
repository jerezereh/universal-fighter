#!/usr/bin/env bash
set -euo pipefail
cd "$1"
# External development tool only; no LZO source/binary enters the shipped runtime.
gcc -shared -O2 -I tools/references/ueviewer/libs/include \
    tools/references/ueviewer/libs/lzo/lzo1x_d2.c -o local-cache/xrd-tools/lzo.dll
