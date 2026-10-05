#!/usr/bin/env bash
set -euo pipefail
export GOPATH="$1/local-cache/go"
export GOMODCACHE="$GOPATH/pkg/mod"
export GOCACHE="$1/local-cache/go-build"
cd "$1/backends/ikemen"
exec > >(tee "$1/local-cache/host-build.log") 2>&1
# Bootstrap has already fetched this exact revision.
export SCREENPACK_REF=2d012f14f8fda6a8515879427adcfd422a20333d
export GOROOT=/mingw64/lib/go
export GOEXPERIMENT=arenas
./build/build.sh Win64
"$1/tools/stage-host.sh" "$1"
