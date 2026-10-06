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

### KOF projectile and lifecycle implementation

- Continued package 5 with Ponytail: reused the pinned host's projectile storage,
  integration, collision, hit consumption, rendering, removal and snapshot clone.
  Source casting action 475 emits a runtime activation ID once at offset 15; the host
  consumes that event once and creates a projectile without foreign CNS simulation.
- Expanded local import to 22 actions / 290 frames, schema 3 / `runtime=kof13`.
  Added weak ground-flame casting/core/removal (475/534/538), character collision
  rules after the 81 common rules, source 60 damage / 11 hitstop, spawn offset 110
  and constant velocity selector 321 (zero-based move table; source 14, host 5.6).
  The core's 96-frame timeline supplies a bounded active lifetime. Original object
  Lua lifecycle, secondary effects, cancels, command recognition and resources
  remain unexecuted. `X` (host button b) casts the standing special as a prototype control.
- Initial export stopped on unsupported MAPPLT; implemented full-color BC1/DXT1
  tile reconstruction with existing Pillow. A preview exposed an incorrect palette
  lookup assumption; corrected it to preserve RGB before publication. Black-keyed
  glow alpha approximates host compositing. Inspected the orange/white flame preview;
  original shader/blend fidelity and in-game pixel presentation remain unverified.
- Native projectiles now negotiate foreign defense/results using projectile facing,
  scale and captured attack multiplier. Original projectile contact/hitpause and
  hit consumption remain host-owned. A failed native fixture exposed stale `stchtmp`
  from a buffered native transition never executed by the foreign backend. Foreign
  preparation now clears it; controlled native projectile hits then passed.
- Added a foreign defeat flag: drain lethal hitstop, settle motion, hold the imported
  down pose, and gate grounded KO completion on that pose. Retire foreign projectiles
  on owner defeat/round exit. Existing host asset cleanup and position reset clear
  entities and reset foreign action/input/reaction/activation/defeat state between rounds.
  Extended traces through defeat after an initial KO-pose check lacked post-combat logs.
- Final patched host built/staged successfully. All five focused Go tests pass:
  authored and installed locomotion, defense negotiation, normal/reaction clocks,
  source-timed projectile emission, held-button/element duplicate prevention, pause,
  spawn-state restore/replay, lethal stop/down persistence and reset. Importer
  parser/SFF/rectangle, sprite reflection and authored BC1 color/transparency checks
  pass. Installed casting duration/spawn timing, core lifetime, damage, stop and speed
  property checks pass. PowerShell/Python/changed Bash syntax and Go formatting pass.
- Maintained patch covers host `char.go`, `state_clone.go` and the projectile removal
  trace in `system.go`. Pristine pinned-source apply/reverse and idempotent reapplication
  checks pass. No toolchains, source game files, extracted art or runtime outputs are
  included in the repository step.
- Final eight-case projectile matrix passed on the final executable: both hit/block
  directions, high/low foreign guards, 12 missed shots with 12 removals/no contacts,
  and KO followed by complete restarted rounds in both directions. Evidence:
  `projectile-foreign-hit-20261005-215955-251.stderr.txt` through
  `projectile-foreign-rounds-20261005-220323-771.stderr.txt` in the ignored host runtime.
  Foreign entity keys include owner/round/activation; no duplicate contacts occurred.
- Strengthened the round checks to require renewed projectile contacts after reset
  and live idle/walk actions for the previously defeated foreign fighter. Focused
  reruns passed: `projectile-native-rounds-20261005-220926-928.stderr.txt` and
  `projectile-foreign-rounds-20261005-220956-500.stderr.txt`. CLI life overrides apply
  initially; restarted rounds restore host health and may complete by timeout.
- Final eight-case melee regression passed on that same executable:
  `melee-foreign-hit-20261005-220353-591.stderr.txt` through
  `melee-foreign-ko-20261005-220638-564.stderr.txt`.
- Final native/native multi-round KO regression and ordinary sampled AI-input
  foreign movement/sprite-upload smoke also passed:
  `baseline-20261005-220651-838.txt` and `foreign-20261005-220806-390.stderr.txt`.
- Projectile platform behavior, reflection, full original juggling and simultaneous
  contacts remain outside this adapter subset. Human controls/pixels, actual host
  pause/frame advance and host snapshot/replay remain separate acceptance gates.
  Native trigger equivalence for foreign owner contact age/get-hit variables also
  remains incomplete. Next: package 6 host snapshot/hash/debug/replay probes.

### Skill installation and continued use

- User explicitly requested skill-installer and confirmation that Universal Modder
  and Ponytail remain in use. Ponytail was already installed and has been applied
  to the project's coding/dependency decisions. Universal Modder was present as an
  ignored pinned reference and used for recon/resource investigation, but its skills
  had not been registered in the global Codex skills folder.
- Installed all ten Universal Modder skills with the official skill-installer helper
  from `rehan-remade/universal-modder` at the project's pinned revision
  `0f5dcdfdcd8ed420f8413815bd6647586ab894a2`. Verified installed entrypoints and
  supporting resources against pinned Git objects (the working checkout uses CRLF).
  New skill discovery is available on the next turn.
- Recorded continuing use of Ponytail for coding and relevant Universal Modder
  workflows for recon, reverse engineering, asset conversion and validation in
  `AGENTS.md`. This installs skills only; optional external services and the full
  plugin/MCP configuration are not enabled by this step. No game/runtime changes.

### Package 6: state blobs, host replay and debug diagnostics

- Continued using Ponytail's minimal implementation guidance and Universal Modder's
  mashup/game-automation workflows: reuse native snapshots, contact lists, sync tests
  and collision rendering rather than creating parallel schedulers or a test engine.
- Added versioned foreign JSON state blobs, manifest SHA-256 identity, atomic validated
  blob restore and SHA-256 state hashes. Existing typed host snapshot copies remain
  the owner of native/foreign world state; a guest blob alone is not a match snapshot.
- Added a stable mixed gameplay projection to saved-state and live rollback checksums.
  It includes guest state, shell attack/defense/contact values and projectile animation,
  motion, hit and removal state. Native-only checksum formatting stays unchanged.
  Optional phase logs use logical ticks; render frame counters do not advance on replay.
- Added `smoke-determinism.ps1`: separate per-run config, strict offline GGPO eight-frame
  rewind, native per-frame checksum verification and forward/replayed phase coverage.
  Scripted probes now work in the explicit offline sync session, whose controller IDs
  differ from ordinary AI play. Real network and recorded replay probes remain disabled.
- The first projectile run found a genuine mismatch: at logical tick 188 the forward
  projectile animation was at clock/element 1/1, while replay remained at 0/0. Full saved
  journals confirmed other projected fields matched. Pinned host `cueDraw()` advanced
  animation outside rollback. Moved that advancement into the end of simulation action,
  after collision/ticks, for native and foreign projectiles. Kept all animation fields
  in the checksum. Host edits are captured in `0001-fighter-runtime.patch`.
- Fixed two verifier issues without weakening native checks: delegate frame identity
  to GGPO instead of the render counter, and include projectile hitpause in phase tags.
- Final Windows build and six focused Go checks passed, including installed-spec
  behavior, blob round trip, replay, hash sensitivity and atomic invalid-blob rejection.
  PowerShell/Bash/Python syntax checks passed. The maintained patch applied to pristine
  pinned source and passed reverse-apply validation.
- Final five-scene offline sync matrix passed with 6,424 GGPO-verified replay frames:
  melee 960, foreign projectile 960, native projectile 960, host Pause 1,960 and
  KO/reset 1,584. Traces in the ignored host runtime:
  `sync-melee-20261006-012828-920.stderr.txt`,
  `sync-foreign-projectile-20261006-012847-942.stderr.txt`,
  `sync-native-projectile-20261006-012905-974.stderr.txt`,
  `sync-pause-20261006-012924-023.stderr.txt`,
  `sync-ko-reset-20261006-012959-191.stderr.txt`.
  Corresponding host `Rollback-Desync-Test` logs independently record matching checksums.
- All eight projectile regressions passed, including twelve missed shots with twelve
  removals and no contacts, both guard heights, and renewed contacts after KO/reset:
  `projectile-foreign-hit-20261006-013040-668.stderr.txt` through
  `projectile-foreign-rounds-20261006-013401-914.stderr.txt`. All eight melee regressions
  passed: `melee-foreign-hit-20261006-013430-975.stderr.txt` through
  `melee-foreign-ko-20261006-013708-001.stderr.txt`. Native/native multi-round KO passed
  (`baseline-20261006-013719-805.txt`). Ordinary sampled foreign AI input, binding,
  locomotion and sprite upload also passed with `UF_FOREIGN_DEBUG=1`
  (`foreign-20261006-013802-681.stderr.txt`); this is renderer execution, not pixel QA.
- Final blob review additionally rejected a jump startup lacking its required air
  transition. The focused atomic-rejection check passed; the final build includes it.
  Rebuilt and repeated the formerly failing foreign-projectile sync scene: another
  960 replay frames passed (`sync-foreign-projectile-20261006-013942-872.stderr.txt`).
- Added `play-foreign.ps1 -Debug` to enable existing collision boxes and foreign
  backend/action/element/frame/stop/stun/activation text. Human inspection of pixels,
  keyboard controls and actual frame advance remains pending. Offline replay checks
  do not establish online netplay, every native field, simultaneous contacts or complete
  KOF source fidelity. Packages 6/7 and full milestone acceptance remain open.

### Live acceptance, readable overlay and implemented API record

- Read Ponytail, Universal Modder game-automation and the installed Computer Use
  workflow before the live checks. Inspected pinned SDL key dispatch, keyboard sampling,
  debug Lua bindings, host pause/tick/step handling and debug-label drawing before edits.
- Live Computer Use capture of the actual renderer verified Kyo initially facing the
  stationary native opponent and imported blue collision boxes. It exposed the foreign
  state text overlapping the host bottom debug panel. Moved that text to two short lines
  above the standing size box; subsequent live capture verified readable backend/player,
  action/element/frame and stop/stun/activation fields, separate from the bottom panel.
- Added `play-foreign.ps1 -Debug -Practice`: human P1, stationary native target, unlimited
  time, per-run action/input log, no scripted probe and explicit control/hotkey help.
  The launcher restores its temporary environment values. Normal launch retains KFM AI.
  Exercised practice launch twice; running scripts were not edited.
- Live Pause injection froze the foreign clock at frame 1,032 across later observations;
  Pause resumed it. Trace: `practice-20261006-022913-378.stderr.txt`. Injected Scroll Lock,
  Z, Right and F8 did not establish their expected effects, so they are not counted as
  successful controls or as confirmed game defects.
- Added key press/release diagnostics only when both foreign trace and debug mode are
  enabled. The pinned SDL event callback supplies these records; no second device poll
  or independent input scheduler is added. Host hooks are in the maintained patch.
  In `practice-20261006-023343-228.stderr.txt`, the helper's Z tap generated no SDL key
  records; Pause generated paired press/release events at tick 1,472 and the core froze
  at frame 1,381. This isolates an injection limitation for Z; it does not prove that
  physical Z, arrows, X or Scroll Lock fail. Physical-keyboard results were requested.
- Recorded the actual `FighterBackend`/`FighterRuntime` contracts, state/coordinate/input
  ownership and supported-interaction matrix in `IKEMEN_RUNTIME_ANALYSIS.md`. Kept the
  earlier API sketch identified as a proposal. The native defender still uses mutating
  host negotiation; this remains a bounded bridge rather than a finalized universal ABI.
- Windows build and all six focused core checks passed. Practice PowerShell syntax,
  diff whitespace, and pristine pinned-source patch apply/reverse checks passed. The
  functional change is debug presentation/diagnostics; combat simulation is unchanged.
  Mocked launch checks also passed for practice/default arguments, inherited-probe
  suppression and environment restoration. The initial mock stored its observation in
  the called script's scope; correcting the harness scope resolved that check failure.
- Initial facing, readable overlays, boxes and live Pause now have visual evidence.
  Complete physical controls, a verified single paused frame, crossover facing and a
  complete human-played mixed match remain open. The startup console also exposes the
  shell's missing native 5900 state warning; normal foreign ticks bind and render, but
  loader warning cleanup has not been addressed. Package 7 documentation is advanced;
  the first milestone has not been accepted.

### SDL keyboard acceptance and bounded first milestone verification

- Continued Ponytail and Universal Modder game-automation. The prior helper's absent
  SDL events were a delivery limitation, not an observed defect in Z or Scroll Lock.
  The pinned WinDrive foreground-guarded driver delivered paired native SDL key events
  for arrows, Z, X, Pause, Scroll Lock and F12. Its initial launch hit PowerShell script
  policy; the documented process-only execution option ran it without changing machine
  settings. The existing user authorization covered brief keyboard checks.
- Manual driver checks on the retained practice process proved Pause freeze/resume and
  three single-frame advances (1,381→1,382→1,383→1,384), walking, crouch/release, normal
  and projectile contacts, and jumping across the target. Native F12 images showed
  Kyo facing left after crossing from the opponent's left to its right.
- Added `smoke-controls.py`, a reproducible Windows input-path check using that existing
  driver and the native screenshot facility. It installs no dependency. It refuses
  existing IKEMEN processes, uses a per-scene config/log/capture folder, disables P1 AI
  and the foreign input probe, and cleans up only its own game/helper processes. The
  practice scene checks input/actions, both contact paths, facing and three exact steps;
  the second sends a normal and ground flame to finish a short mixed match by KO.
- Its initial preflight treated PowerShell's no-process exit status as an error;
  corrected the lookup's empty-result handling. The first working edge screenshot
  showed that queuing-time label bounds still used the wrong aspect. Moved optional
  bounds into the actual debug draw pass and reused native font width/scale. Final
  visual inspection verifies readable state fields at the right stage boundary.
- Removed the foreign shell's state-5900 startup warning at the actual boundary: guest
  reset owns initial action selection and now bypasses native intro CNS initialization.
  Native startup is unchanged. Also declared an empty native fixture command state -1,
  which common hit recovery invokes; this removes its warning without adding commands.
- Final interactive scenes passed on the final rebuilt executable:
  `controls-practice-20261006-030755-650785` and
  `controls-match-20261006-030810-540237`. Inspected startup/crossover/KO native PNGs;
  boxes, facing and state text are visible. Match statistics record round 1 completed,
  P1 life 1,000, P2 life 0 and a KO win. These are real SDL/renderer results via automation,
  not a claim that a physical human played the match.
- All six core checks and Windows build passed. The changed initialization/fixture
  passed the full five-scene offline GGPO matrix (6,424 matching replay frames), all
  eight projectile scenarios, all eight melee scenarios, native/native multi-round KO
  and ordinary foreign AI-input movement/sprite-upload regression. Evidence starts at
  `sync-melee-20261006-025706-312.stderr.txt`,
  `projectile-foreign-hit-20261006-025903-254.stderr.txt`,
  `melee-foreign-hit-20261006-030251-628.stderr.txt`,
  `baseline-20261006-030540-639.txt` and `foreign-20261006-030632-918.stderr.txt`.
  The final draw-only adjustment was then rebuilt and the two interactive scenes repeated.
- Updated the work plan to mark packages 1–7 technically verified for the bounded Kyo
  milestone and record the proposed next phase: multiple runtime ownership/snapshots,
  parry, air dash/cancels/defensive resources and cross-ruleset tests. These mechanics
  remain unimplemented. Physical user play/feel, other devices/resolutions, exhaustive
  simultaneous/source interactions and online netplay remain explicitly unmeasured.

### Next phase A: owned runtime boundary

- Replaced the shell's concrete KOF pointer with `FighterRuntime`. Common value views,
  position adoption, pose/attack descriptors and owned `Clone` now isolate the host
  from backend-private mutable state. Kyo still owns its immutable imported spec.
- KOF snapshot format is now version 2 with backend identity and spec fingerprint.
  Old versions, wrong backends/specs and invalid clocks/transforms reject atomically.
  A clone/view independence check joins the six existing focused checks; all seven pass.
- Windows build passed. All five strict offline GGPO scenes passed with 6,424 matching
  replay frames, including pause/projectiles/KO/reset. All eight melee scenes, eight
  projectile scenes and native/native multi-round KO passed. Evidence starts with
  `sync-melee-20261006-034804-118.stderr.txt`,
  `melee-foreign-hit-20261006-035011-903.stderr.txt`,
  `projectile-foreign-hit-20261006-035310-740.stderr.txt` and
  `baseline-20261006-035709-615.txt` in the ignored runtime.
- Reviewed the host/core diff; pristine pinned patch apply/reverse, Bash/Python syntax
  and diff whitespace checks passed. Host changes are captured in the maintained patch.
- This step changes runtime ownership, not Kyo mechanics. New ruleset implementation
  and interactive validation of those mechanics remain pending; prior Kyo keyboard
  evidence is not counted as acceptance of new mechanics.
