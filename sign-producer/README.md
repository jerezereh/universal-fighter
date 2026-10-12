# SIGN producer

This directory starts from `uf-producer-template` and pins the installed SIGN build and
`uf-arena` protocol v1.5. It is a producer workspace, not a playable SIGN adapter yet.

The source game must own simulation, input, reactions and presentation. The host owns
the match and receives source state, boxes and an isolated fighter layer through
`ufproducer`. Source hooks are only for stepping, mirroring the opponent, applying
host results through native game paths, and exporting native output. No sprite bake or
IKEMEN runtime is on this path.

`python produce.py --fake` serves the protocol's reference fighter. `--exe` verifies
the pinned executable and currently refuses to attach until a persistent SIGN bridge
is implemented. See [PROGRESS.md](PROGRESS.md) for verified SIGN work and open gates.
