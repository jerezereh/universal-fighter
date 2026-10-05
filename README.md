# Universal Fighter

A compatibility runtime hosted by IKEMEN GO, following [the handoff](handoff_doc.txt).
The first target is a normal IKEMEN fighter versus a separately simulated KOF XIII fighter,
using the user's local Steam installation.

Current status: Phase 1 source reconnaissance is complete. The native Windows host builds
and an automated native/native match passes KO and round-transition checks. The KOF XIII
locomotion backend uses imported Kyo data and sprites; mixed combat remains a later gate.

- [Source analysis and proposed runtime seam](docs/IKEMEN_RUNTIME_ANALYSIS.md)
- [Implementation work plan and validation gates](docs/WORK_PLAN.md)
- [Environment and work record](docs/PROGRESS.md)
- [Windows dependency setup](docs/DEPENDENCIES.md)
- [KOF XIII import and runtime setup](docs/MODDING_PLAN.md)

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

Keep extracted commercial assets in ignored local storage. Universal Modder is a recon
reference and development tool, never a runtime dependency. KOF XIII is the user's selected
first adapter; broader game support remains outside the initial milestone.
