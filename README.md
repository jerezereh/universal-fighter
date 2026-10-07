# Universal Fighter

A compatibility runtime hosted by IKEMEN GO, following [the handoff](handoff_doc.txt).
The first target is a normal IKEMEN fighter versus a separately simulated KOF XIII fighter,
using the user's local Steam installation.

Current status: Phase 1 source reconnaissance is complete. The native Windows host builds
and an automated native/native match passes KO and round-transition checks. The KOF XIII
backend uses imported Kyo data, sprites and collision boxes. A bounded mixed-melee
prototype adds one source normal, a weak ground-flame projectile and native/foreign
hit handling. The bounded first milestone now passes automated contact/lifecycle,
offline GGPO replay and real SDL keyboard/render acceptance. Two authored executable
rulesets now add parry, air dash, confirmed cancels and defensive resource spending.
Online netplay and full source-game fidelity remain open.

- [Source analysis and proposed runtime seam](docs/IKEMEN_RUNTIME_ANALYSIS.md)
- [Implementation work plan and validation gates](docs/WORK_PLAN.md)
- [Environment and work record](docs/PROGRESS.md)
- [Windows dependency setup](docs/DEPENDENCIES.md)
- [KOF XIII import and runtime setup](docs/MODDING_PLAN.md)
- [Authored rulesets and controls](docs/SYNTHETIC_RULESETS.md)
- [Xrd SIGN source inspection and adapter gates](docs/XRD_SIGN_MODDING_PLAN.md)

Run `./tools/bootstrap.ps1` in PowerShell to obtain the exact upstream revisions in
`tools/upstreams.json`. Existing checkouts are never reset or overwritten. The upstream
folders are local working copies ignored by this repository; future engine changes must
be captured as reviewable patches or in a maintained fork before delivery.

Run `./tools/gather-dependencies.ps1 -Build` to gather a project-local Windows toolchain
and attempt the baseline build. Use `-CheckOnly` to verify the toolchain independently.
For host build details, see `backends/ikemen/BUILDING.md` at the pinned revision. This revision
declares Go 1.27.0 and uses `GOEXPERIMENT=arenas`, MSYS2/MinGW on Windows, SDL2,
libxmp, and FFmpeg development libraries. Its README also requires a separate screenpack
for running the engine. `./tools/smoke-host.ps1` verifies a bounded native AI match;
visual presentation and human controls still require interactive validation.

Run `./tools/smoke-determinism.ps1` to check mixed save/restore with the pinned host's
offline GGPO sync test. It exercises melee, both projectile directions, host Pause,
and KO/round reset with per-frame checksums. Use `./tools/play-foreign.ps1 -Debug`
for collision boxes and the foreign action/frame/stop/state overlay. P1 uses arrow
keys, **Z** for the normal and **X** for the standing ground flame.
Add `-Practice` for a stationary native opponent, unlimited time and a local input
trace. **Pause** freezes/resumes; **Scroll Lock** is the host's single-frame hotkey.
`python tools/smoke-controls.py` drives these keys in the real Windows host and saves
native screenshots plus a completed KO match. It requires the desktop for brief
foreground input and no other IKEMEN instances running.

Run `./tools/play-synthetic.ps1 -Rules airdash-test -Practice` for the authored mobility
fighter, or select `parry-test`. **X** opens a ground parry for the latter; for air dash
it spends meter on a dash in air or a confirmed normal cancel. **Back+X** requests
resource guard. `./tools/smoke-synthetic.ps1 -Sync` checks cross-ruleset contacts and
private state under strict offline rollback; `python tools/smoke-controls.py --synthetic`
exercises their actual keyboard path. These are architecture experiments, not Xrd/SFIII
adapters; see the ruleset document for timing, costs and limits.

Keep extracted commercial assets in ignored local storage. Universal Modder is a recon
reference and development tool, never a runtime dependency. KOF XIII is the user's selected
first adapter; broader game support remains outside the initial milestone.

The next real-game target is the locally installed Xrd **SIGN** edition. Its pinned
offline tool setup is `./tools/gather-xrd-tools.ps1`; `python tools/xrd-sign-import.py
--graphics` inspects a copied Sol/common slice and exports original graphics into ignored
storage. `python tools/test-xrd-package.py` checks its reader/native framing. SIGN move
semantics, rendered fidelity and a playable guest runtime remain under implementation.
Graphics import now defaults to palette `0101`, matching the standard Sol colors in the
original-game reference. Use `--palette 0` to reproduce earlier `0100` diagnostic imports.

`python tools/xrd-sign-poses.py <import-folder> --frames 0,5,10,15,20,25 --blender
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"` creates a diagnostic Sol
sample bake using an installed Blender. Use the folder printed by the graphics importer;
omit `--blender` to prepare posed glTFs only. Samples are explicit PSA indices, not verified
sprite suffixes. Base-color textures and held local scale keys are previews; facial blends,
native scale evaluation and toon passes are incomplete. `python tools/test-xrd-animation.py`
checks the animation reader, rig binding and local metadata links. All generated assets
remain ignored and no Xrd fighter is bound to the host yet.
Every rendered part/sample now passes an independent comparison between glTF skinning
and Blender's evaluated vertices. The authored integration check runs with
`blender --background --factory-startup --python tools/test-xrd-gltf.py`.

`./tools/gather-xrd-oracle.ps1` and `./tools/play-xrd-source.ps1` prepare and launch the
original SIGN bootstrap for manual offline comparisons. They change no global runtime
installation or permanent PATH. For newer 3D fighters, the next investigation is a native
passthrough feasibility slice; see the work plan. The importer/baker remains a fallback
and a source-data oracle.

SIGN's native investigation now includes a bounded idle freeze/three-step proof with
graphics progress and automatic recovery. This is development instrumentation, not a
playable SIGN guest. Setup, commands and the remaining input/render/combat gates are in
[XRD_SIGN_NATIVE_PROBE.md](docs/XRD_SIGN_NATIVE_PROBE.md).
