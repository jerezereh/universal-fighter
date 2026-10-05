#!/usr/bin/env bash
set -euo pipefail
cd "$1"
export GOPATH="$1/local-cache/go"
export GOMODCACHE="$GOPATH/pkg/mod"
export GOCACHE="$1/local-cache/go-build"
mkdir -p local-cache
exec > >(tee local-cache/dependency-report.txt) 2>&1
for tool in git make gcc pkg-config go nasm yasm python; do
  command -v "$tool"
done
python -c 'import sys, PIL; print("Python", sys.version.split()[0], "Pillow", PIL.__version__)'
export GOROOT=/mingw64/lib/go
export GOEXPERIMENT=arenas
required=$(sed -n 's/^go //p' backends/ikemen/go.mod | tr -d '\r')
installed=$(GOTOOLCHAIN=local go env GOVERSION)
echo "Required Go: $required; installed: $installed"
if [[ "$(printf '%s\n' "$required" "${installed#go}" | sort -V | head -n 1)" != "$required" ]]; then
  echo "Go $required or newer is required. MSYS2 provided $installed; host build is blocked." >&2
  exit 1
fi
pkg-config --modversion sdl2 libxmp
pacman -Q
cd backends/ikemen
go mod download
echo 'Go module downloads completed. FFmpeg/libvpx are gathered by the upstream build script.'
