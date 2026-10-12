# SIGN producer notes

Verified source build: Steam 376300/build 1028441, native x86/UE3, Direct3D 9,
offline Training with Sol on P1. See the executable pin and the native receipts in
`../docs/XRD_SIGN_NATIVE_PROBE.md` and `../docs/PROGRESS.md`. Diagnostic source
hooks have demonstrated owned tick/input/state/image/contact boundaries. They do not
yet constitute a long-lived producer or a 60 Hz frame path.

Protocol target: `uf-arena/docs/WIRE.md` and `docs/PROTOCOL.md` at
`protocol-v1.5`. The SIGN producer must publish native state and an isolated native
layer, map host transforms into source space, and apply host combat results through
SIGN's own reaction paths. Any feature without live evidence stays unsupported.
