#!/usr/bin/env bash
set -euo pipefail
cd "$1"
export GOROOT=/mingw64/lib/go
export GOPATH="$1/local-cache/go"
export GOMODCACHE="$GOPATH/pkg/mod"
export GOCACHE="$1/local-cache/go-build"
export GOEXPERIMENT=arenas
export UF_KOF_SPEC="$1/artifacts/host-baseline/chars/kof13/foreign.json"
go test -v runtime/runtime.go runtime/kof13.go runtime/combat.go runtime/state.go runtime/synthetic.go runtime/passthrough.go runtime/passthrough_layer_windows.go runtime/kof13_test.go runtime/combat_test.go runtime/state_test.go runtime/synthetic_test.go runtime/passthrough_test.go runtime/passthrough_layer_windows_test.go
python tools/apply-runtime.py
"$1/tools/build-host.sh" "$1"
