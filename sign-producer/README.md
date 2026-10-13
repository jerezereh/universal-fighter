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

For the experimental direct-GPU route, close SIGN and run
`python tools/launch-xrd-sign-on12.py` from the repository root. The launcher
fingerprints the installed game, official bootstrap and cached DirectX libraries,
then intercepts only its SIGN child before D3D9 device creation. It verifies
`IDirect3DDevice9On12` and `GetD3D12Device`, detaches after 30 seconds and leaves
the game open. `--check` performs only the read-only input and process checks.
For an already prepared offline Sol/Ky session, the development-only
`tools/prepare-xrd-sign-render.py --native-grading-only --on12-probe --on12-readback`
check performs one temporary render-thread GPU copy of the isolated fighter
texture and compares it through uf-arena's independent D3D12 reader.
Add `--on12-frames 4` for a bounded four-step check using a separate shared
texture per step; it does not reuse textures or run as a persistent producer.
It needs the same ignored local `--candidate`, `--combat-candidate` and `--meshes`
inputs as normal render preparation and the sibling `uf-arena/python` checkout
for the development-only reader. The temporary handle is closed during the
check; arena delivery is still under development.
