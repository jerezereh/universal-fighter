#!/usr/bin/env bash
set -euo pipefail
cd "$1/backends/ikemen"
[[ -f Ikemen_GO.exe ]] || { echo 'Build the host first.' >&2; exit 1; }
runtime="$1/artifacts/host-baseline"
mkdir -p "$runtime"
# Preserve any existing runtime configuration, saves and local character edits.
for item in build/screenpack/*; do
  cp -an "$item" "$runtime/"
done
for item in data external font; do
  cp -an "$item" "$runtime/"
done
cp -a Ikemen_GO.exe "$runtime/"
cp -a lib "$runtime/"
echo "Baseline runtime staged at $runtime; launch Ikemen_GO.exe with that working directory."
