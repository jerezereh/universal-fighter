# SIGN producer

This directory starts from `uf-producer-template` and pins the installed SIGN build and
`uf-arena` protocol v1.5. It is a producer workspace, not a playable SIGN adapter yet.

The source game must own simulation, input, reactions and presentation. The host owns
the match and receives source state, boxes and an isolated fighter layer through
`ufproducer`. Source hooks are only for stepping, mirroring the opponent, applying
host results through native game paths, and exporting native output. No sprite bake or
IKEMEN runtime is on this path.

`python produce.py --fake` serves the protocol's reference fighter.
`python preflight.py --pid PID` confirms the pinned executable and exact live SIGN
process using a read-only handle. Add `--fighters` to check the live Sol/Ky native
slots, position and facing. `--clock` also samples the native update counter to
report whether it is advancing. These checks do not establish offline Training.
`produce.py --exe` currently refuses to attach
until a persistent SIGN bridge is implemented. See [PROGRESS.md](PROGRESS.md) for
verified SIGN work and open gates.

`sign/inputs.py` translates uf-arena's absolute held directions and five buttons
to SIGN's inspected native input bits. It is ready for the source bridge but is
not yet connected to a playable step.
