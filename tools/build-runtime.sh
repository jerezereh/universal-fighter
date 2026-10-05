#!/usr/bin/env bash
set -euo pipefail
cd "$1"
export GOROOT=/mingw64/lib/go
export GOPATH="$1/local-cache/go"
export GOMODCACHE="$GOPATH/pkg/mod"
export GOCACHE="$1/local-cache/go-build"
export GOEXPERIMENT=arenas
export UF_KOF_SPEC="$1/artifacts/host-baseline/chars/kof13/foreign.json"
go test -v runtime/kof13.go runtime/kof13_test.go
python tools/apply-runtime.py
"$1/tools/build-host.sh" "$1"
