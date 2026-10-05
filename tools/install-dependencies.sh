#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  core) pacman -Sy --noconfirm msys2-keyring; pacman -Su --noconfirm ;;
  packages)
    pacman -Dk
    pacman -Syu --noconfirm
    pacman -S --needed --noconfirm git make diffutils \
      mingw-w64-x86_64-pkg-config mingw-w64-x86_64-go \
      mingw-w64-x86_64-toolchain mingw-w64-x86_64-nasm \
      mingw-w64-x86_64-yasm mingw-w64-x86_64-tools-git \
      mingw-w64-x86_64-libxmp mingw-w64-x86_64-SDL2
    ;;
  *) echo 'Expected core or packages' >&2; exit 2 ;;
esac
