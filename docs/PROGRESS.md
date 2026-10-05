# Progress record

## 2026-10-05

- Starting workspace contained only `handoff_doc.txt`, with no Git repository or code.
- Downloaded IKEMEN and Universal Modder working copies; exact revisions are recorded
  in `tools/upstreams.json`. Engine behavior and upstream source remain unchanged.
- Completed Phase 1 static reconnaissance and documented the smallest proposed seam.
- Added source bootstrap, project overview and milestone work packages.
- Initialized local project Git tracking (no commit or remote). Verified bootstrap
  PowerShell syntax, manifest JSON and existing-checkout revision checks; both upstream
  working copies are clean. Source reference line bounds were checked. Host execution
  remains unverified.
- Toolchain inspection: `go` is unavailable in this session's PATH. No Go installation
  was found at `C:\Program Files\Go\bin\go.exe` or
  `C:\msys64\mingw64\bin\go.exe`; `C:\msys64\usr\bin\bash.exe` is also absent.
  These checks do not establish that no toolchain exists elsewhere on the machine.
- No host build, runtime test or mixed-fighter match has been performed. The next work
  package is the unmodified host baseline and Windows build environment.

Universal Modder remains a read-only recon reference. No plugins were installed and no
commercial games or assets were investigated. Its recon workflow will be applied when
the synthetic architecture gate allows the first real-game adapter.

## Dependency setup continuation

- Added `tools/gather-dependencies.ps1`: checksum-verified stable MSYS2 archive, local
  package installation, pinned source bootstrap, Go version checks and module gathering.
- Installed MSYS2 2026-09-27 in `local-cache/msys64`. Native package verification passed:
  Go 1.27.1, SDL2 2.32.10 and libxmp 4.7.3. Go modules gathered successfully; `-CheckOnly`
  also passed using project-local Go caches. Full versions are in the ignored dependency
  report. No permanent machine PATH or registry changes were made by these scripts.
- Corrected release selection after the official latest-release endpoint returned a
  nightly archive. Accommodated the observed MSYS2 core update terminating its shell;
  the next package phase verifies the package database before continuing.
- Pinned and fetched the screenpack. Added a host-build wrapper with runtime staging,
  build logging and a bounded native/native KO and round-lifecycle smoke command.
- All PowerShell and Bash setup scripts pass syntax checks. Host build is underway;
  playable-match and visual validation remain unverified at this entry.

### Baseline result

- Pinned IKEMEN compiled successfully with the native Windows toolchain, including
  upstream-built libvpx and FFmpeg. Output executable: 16,001,024 bytes.
- The first wrapper invocation failed after compilation because a running Bash script
  was edited before its next read. Separated staging into `stage-host.sh`; staging then
  passed against the completed executable. Do not edit a script while it is executing.
- Runtime staged at `artifacts/host-baseline`. `tools/smoke-host.ps1` passed: completed
  native KFM-versus-KFM AI match, multiple rounds and a recorded KO. Evidence:
  `artifacts/host-baseline/baseline-20261005-153408-554.txt`.
- The setup, source bootstrap (including MSYS2 Git), verification, upstream build, staging
  and smoke phases have been exercised. The revised combined wrapper has not been rerun
  end-to-end after staging was separated; its scripts pass syntax checks.
- Human controls and visual presentation remain unverified. There is no foreign backend
  yet. Next: the first foreign idle/movement/jump slice with native behavior regression.

### Repository publication

- User configured `origin` as `https://github.com/jerezereh/universal-fighter.git` and
  authorized committing and pushing completed work throughout the plan. Recorded this
  project workflow in `AGENTS.md`.
- Initial publication groups the architecture foundation and Windows dependency/baseline
  tooling into separate commits. Local toolchains, upstream checkouts and runtime assets
  remain ignored; their pinned manifests and setup scripts are versioned.

### KOF XIII source import

- User installed Ponytail and requested its use. Applied minimal implementation:
  one local reader, existing Pillow, no Lua VM or process hooking dependency.
- User selected installed KOF XIII for the foreign slice, overriding synthetic-first
  sequencing. Used Universal Modder's scan/recon workflow and manual resource checks.
  Its knowledge search could not load PyYAML; a bounded reference search found no
  KOF entry. No extra dependency was installed for that lookup.
- Located Steam app 222940/build 151721. Implemented encoded Lua chunk/table parsing,
  restricted frame-call extraction, zlib PCS reading, DBLPLT tile reconstruction,
  palette-layer composition and host SFFv2/AIR presentation export.
- Exported Kyo (`03`): 13 locomotion actions / 110 frames. Visually inspected the
  reconstructed idle image. Derived assets and source hashes remain ignored locally.
- The first SFF check exposed a sprite-header stride error (32 versus 28 bytes).
  It was inadvertently published with the importer commit, then corrected in the
  immediate follow-up before host use. Authored parser/SFF checks now pass.
  Unsupported opcodes/transforms fail export;
  general Lua execution and other PCS drawing modes are outside this slice.
- Host runtime binding, input-driven locomotion and interactive acceptance remain
  pending. This import is not a completed foreign fighter or full KOF emulation.

### KOF foreign runtime slice

- Added a shared host scheduling boundary with native and KOF implementations.
  Native methods remain behind their backend wrapper; foreign preparation, simulation,
  finish, update and tick bypass native CNS behavior. Explicit DEF runtime binding
  loads a local manifest. Kyo uses host-sampled input, imported velocities/frame clocks,
  native stage/camera/rendering and size-based host pushing.
- Added source-formula checks for the selected velocity constructors. Adapter code
  selects idle/walk/crouch/normal-jump transitions; full original transitions, option
  flags, effects/audio and combat are not emulated. Airborne facing remains locked.
- Core tests pass on authored data and the installed Kyo manifest: forward/back,
  crouch/release, jump/landing, held-up edge behavior, pause, exactly one frame of
  advance, reset and deterministic restore/replay. They exposed and fixed stale
  jump acceleration after landing. Host snapshots copy mutable runtime state while
  sharing the immutable imported specification; full host rollback remains unverified.
- Runtime is versioned in `runtime/`; host changes are captured in
  `patches/0001-fighter-runtime.patch`. Apply/reverse checks passed on pristine pinned
  source. Reapplication is idempotent, and the helper refuses a different host HEAD.
- Patched host compiled successfully. Native KFM/KFM KO and multiple-round regression
  passed again on the final build (`baseline-20261005-163948-378.txt`). Mixed KFM/Kyo
  renderer smoke passed again (`foreign-20261005-164132-929.stderr.txt`): sampled
  native AI input produced walking, crouch, directional jumps and landing, with
  foreign sprite textures uploaded. The initial smoke observed all 13 imported
  actions; the final random AI run observed 10. The mixed match ended
  by timeout; native melee/projectile paths deliberately exclude the foreign shell.
- Gathered project-local Python 3.14.8 / Pillow 12.3.0 and updated dependency setup and
  verification. Importer checks pass with this toolchain; dependency `-CheckOnly`,
  Bash and PowerShell syntax checks pass. The baseline builder does not apply/remove
  runtime patches; use `build-runtime.sh` for the patched build.
- Added `smoke-foreign.ps1` and an interactive `play-foreign.ps1` command. Pixel-level
  renderer inspection, human controls and actual host pause/frame advance remain open.
  Package 3 is implemented but not fully accepted; next implementation gate is the
  mixed melee protocol, with source hurtboxes and one foreign normal.

### KOF mixed melee implementation

- Applied Ponytail to reuse the pinned host's collision, native defense and current-HitDef
  target bookkeeping. Added a small attack/defense/result protocol for foreign defense;
  native fighters retain their original result routine. Foreign state owns reaction,
  stop/stun/down clocks, input edges and activation IDs; host life remains canonical.
- Reimported local Kyo data as schema 2: 19 actions / 147 frames, source vulnerability
  rectangles, close standing A (4 startup / 4 active / 15 recovery), 25 damage and
  7 hitstop frames. Common rectangle selectors are resolved through the installed
  collision table. Game files, reconstructed assets and frame data remain ignored.
- Added standing/crouching guard and hit presentation, knockback, launch/down recovery,
  and lethal-hitstop draining before host KO flags. Reaction motion and recovery use
  documented compatibility rules, not the complete original KOF behavior. Guard image
  modifier -3 remains metadata whose renderer semantics are not implemented.
- Random AI contacts did not provide reliable acceptance coverage. Authored native
  high/low/launch fixtures and explicit local input probes exposed a real host-boundary
  bug: foreign preparation skipped the native collision-transform reset, leaving box
  scales zero. Foreign preparation now calls that shared reset. Earlier incidental
  contacts are not evidence that imported rectangle geometry was working correctly.
- Corrected a HitDef attribute type mismatch during compilation, then built and staged
  the patched host successfully. All four focused Go tests pass, including the installed
  locomotion manifest, defense negotiation, pause/hitstop/stun clocks, knockback,
  launch/down/recovery, reset and core contact-state restore/replay. Importer parser,
  SFF and rectangle checks pass; installed normal timing/active-box data was inspected.
- Final eight-case host matrix passed: both hit directions, high/low blocks without
  life loss, incorrect guard-height hits, knockdown, lethal hitstop/KO and no duplicate
  foreign activation/defender contacts. Evidence in `artifacts/host-baseline`:
  `melee-foreign-hit-20261005-211818-908.stderr.txt` through
  `melee-foreign-ko-20261005-212104-823.stderr.txt` (one named log per scenario).
- Final native/native multi-round KO regression passed:
  `baseline-20261005-212127-277.txt`. Ordinary sampled AI-input locomotion and sprite
  upload regression also passed: `foreign-20261005-212222-433.stderr.txt`.
  Python, PowerShell and changed Bash scripts pass
  syntax checks; runtime Go files pass formatting checks. The maintained host patch
  passed pristine apply/reverse and idempotent reapplication checks.
- These fixtures establish bounded melee integration, not exhaustive source interaction
  fidelity. Human controls, pixel presentation, actual host pause/frame advance,
  simultaneous-contact coverage and full host rollback remain unverified. Throws,
  custom-state transfers, reversals, down hits and foreign projectile contacts are
  excluded. Next implementation work is package 5 projectiles and complete lifecycle;
  source KO presentation and cleanup are still pending.

### Kyo sprite-facing correction and controls

- User reported Kyo facing away from the opponent in game. Inspected the exported
  idle image and pinned host draw path: IKEMEN facing +1 expects right-facing pixels;
  Kyo's source pixels face left and supported SetImage calls specify X scale -1.
  The importer validated that transform but omitted it during composition.
- Export now mirrors the composed pixels and reflects the sprite axis together.
  Reimported all 147 frames locally. Movement, collision rectangles and host facing
  logic are unchanged; no executable rebuild or game-installation change was needed.
- Authored asymmetric-pixel/axis regression, existing parser/SFF/rectangle checks and
  local reimport passed. Inspected the corrected right-facing idle preview. Host sampled
  AI locomotion and sprite-upload smoke passed:
  `foreign-20261005-212751-618.stderr.txt`. Actual in-game visual confirmation after
  restarting the match remains pending; smoke does not inspect rendered pixels.
- Read the current local `save/config.ini` Player 1 mapping and documented arrows,
  standing `Z` attack, directional jumping and back/down-back guards. Only host button
  `a` (currently `Z`) has a Kyo attack in this slice; other mapped attack buttons,
  crouching/air attacks and source command moves are not yet implemented.
