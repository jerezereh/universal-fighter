# SIGN producer progress

## 2026-10-11 — template and receiver pivot

- Scaffold copied from the local `uf-producer-template`; pin upgraded from v1.3 to
  `uf-arena` protocol v1.5, matching the active KOF XIII producer. The installed SIGN
  executable's size and SHA-256 were checked locally. Source attachment fails closed.
- Earlier `universal-fighter` native probes verified exact bounded stepping, input,
  source state, contact suppression, isolated RGBA, reset and partial result injection
  in offline SIGN Training. Their short-lived, diagnostic scripts are not a persistent
  producer. The current per-frame image path peaks above a playable frame budget.
- Pending: long-lived reversible SIGN bridge, on-demand D3D9On12/shared-layer capture,
  unrestricted source input and close-range opponent mirror, native result coverage,
  `ufconform` on the real source, and a playable `uf-arena` match.

## 2026-10-11 — exact-process preflight

- Added a read-only PID check using PROCESS_QUERY_LIMITED_INFORMATION. It verifies
  the live process image against the pinned SIGN path, file size and SHA-256; a
  same-name Rev2 process is rejected. It installs no hooks and deliberately does
  not infer offline Training from the process path.
- Live PID 25640 passes exact SIGN preflight; six unit tests and Python compilation
  pass. Offline scene verification and persistent producer attachment remain open.

## 2026-10-12 — read-only native fighter pair

- Added a dependency-free `--fighters` preflight for the pinned SIGN process. It reads
  the native engine's two fighter slots and accepts only live Sol/Ky pose names with
  bounded positions and facing. It verifies slot stability across the read.
- PID 32716 passed exact-image and Sol/Ky checks in the user's current scene:
  Sol at raw X -252000, facing right; Ky at 252000, facing left. A separate two-second
  source observation sampled 197 records and independently found the same pair.
- This proves the fighter pair, not offline Training mode or a controlled game tick.
  No hook was installed. Persistent stepping, images, combat and the producer wire
  remain open; `SignProducer` still advertises no capabilities.

## 2026-10-12 — fresh source update and lease witnesses

- In the same live PID 32716 session, an initial Frida attach timed out before hooks;
  its receipt reports no samples and restored code. One bounded retry observed 301
  consecutive source updates with zero counter gaps/errors and verified code restoration.
- A separate bounded gate executed exactly three credited native updates, blocked 268
  others, held both fighters' observed state stable, and kept rendering active. A
  renewed 28-second hold blocked 1,264 updates and then verified lease recovery and
  automatic hook removal. Both runs restored source code and detached cleanly.
- These are current-session diagnostic proofs. They do not make the short-lived
  script a persistent producer, meet frame latency, or validate the wire lifecycle.

## 2026-10-12 — full-quality image and source clock

- With source graphics quality restored, fresh same-session render preparation
  passed owner, mesh identity, screen-stage and four-frame transaction checks.
  A full-postprocess quarter-resolution stream then passed 20 credits/21 linked
  images with code restoration and detach. Request latency averaged 311 ms and
  peaked at 331 ms; this fails the existing 250 ms diagnostic limit and is far
  above the 16.7 ms 60 Hz target. It is not playable throughput or host transport.
- `preflight.py --clock` now reads six samples of the verified native counter
  alongside the fighter pair without hooks. On PID 32716 it advanced from 40779
  to 40797 in five intervals. A paused or intermittent result is reported, not
  silently treated as a ready source. Eight unit tests and Python compilation pass.
- Next implementation gate is a persistent source-owned render/control path that
  avoids the diagnostic CPU capture cost; then integrate with uf-arena's wire and
  validate match lifecycle and human controls.

## 2026-10-12 — launcher edition isolation

- `tools/play-xrd-source.ps1` now rejects duplicate SIGN instances and selects the
  launched SIGN window by full executable path; a concurrent Rev2 process no longer
  blocks or misidentifies the launcher. PowerShell syntax and a mixed-edition
  selector check pass. It still opens the normal menu; no verified command-line
  shortcut enters Training or chooses characters.
- The next native-grading timing comparison could not start because PID 32716 had
  exited. No matching Windows Application fault event was found in the recent log.
  Cause is unknown; fresh live bindings are needed after the next SIGN launch.

## 2026-10-12 — host input word mapping

- Added the producer-owned mapping for uf-arena's absolute directions and five
  attack buttons to SIGN's inspected native input bits. Simultaneous opposite
  directions cancel. All 512 held-input combinations match the previously
  verified diagnostic mapper; nine unit tests pass.
- This is an adaptation primitive. No persistent SIGN input ingress or arena
  step is connected yet, so capabilities remain disabled.

## 2026-10-12 — fresh native-grading render timing

- After the user reopened offline Sol/Ky Training, exact-image, fighter-pair and
  advancing-clock preflight passed on SIGN PID 30904. Fresh source-owner, draw,
  mesh and screen-stage preparation passed, followed by a four-frame native-
  grading transaction. A bounded quarter-scale native-grading stream then
  completed 20 credited steps and 21 linked images, restoring loaded code and
  detaching cleanly. Its mean request latency was 208 ms, peak 301 ms; the
  previous full-quality stream on a different process averaged 311 ms, peak
  331 ms. This comparison is indicative, not a controlled same-process benchmark.
- The stream still misses the 250 ms diagnostic deadline at peak and the 16.7 ms
  60 Hz budget by a wide margin. It is a short-lived diagnostic, with no live
  producer, negotiated image transport or playable capability. The persistent
  source-owned render/control bridge remains the next implementation gate.
- A second bounded stream in the same PID at half scale also passed 20 steps/21
  images, with restored code and clean detach. Its mean was 201 ms, peak 240 ms.
  The near-equal means at quarter and half scale suggest that merely reducing
  transferred pixels will not solve frame pacing; source rendering/settlement
  and transport still need profiling and an on-demand path. A one-eighth-scale
  request was rejected by the tool's existing input validation before attach.

## 2026-10-12 — D3D9On12 launch and device access

- Added `tools/launch-xrd-sign-on12.py`, a development-only launcher based on the
  verified Rev2 redirect. It fingerprints SIGN, BootGGXrd and the three cached
  x86 DirectX DLLs, rejects an existing SIGN process without rejecting Rev2,
  gates the bootstrap's exact SIGN child, and redirects its early
  `Direct3DCreate9` call to `Direct3DCreate9On12`. No game files are changed.
- A 30-second launch of PID 24740 reports a successful redirect, loaded
  `d3d9on12.dll`, successful `IDirect3DDevice9On12` query and successful
  `GetD3D12Device`. The window remained responsive after hook teardown; an
  earlier launch rendered SIGN's opening screen. Python and embedded JavaScript
  syntax checks pass. The first attempt failed before spawn because Frida's
  child callback had the wrong signature; it was corrected before live launch.
- This establishes access to the underlying D3D12 device only. An isolated
  source-owned fighter texture, GPU copy/shared handle, ready/release fences,
  one-tick frame linkage, throughput and arena conformance remain unverified.

## 2026-10-12 — On12 training render preparation

- The redirected PID 24740 entered offline Sol/Ky Training: exact executable and
  fighter pair passed preflight, and the battle counter advanced. A bare Frida
  attach took 4.16 seconds, close to the former five-second timeout, so only
  the attach allowance is now 15 seconds.
- The existing draw recorder sometimes captured a Present interval crossing an
  owned update. It now discards that transitional interval and retains two
  complete held-counter intervals. Fresh native-grading preparation passed its
  owner, draw, mesh, screen and three-step private-layer stages in the same
  On12 process; cleanup reported restored source/render code and no errors.
- This verifies the private fighter render path still works under On12. The
  prepared layer is not yet unwrapped or shared with uf-arena. GPU copy/fence
  correctness, frame pacing and a playable SIGN producer remain pending.

## 2026-10-12 — private fighter resource interop

- Added an opt-in `--on12-probe` to the bounded native-grading preparation. On
  SIGN's render thread it queries `IDirect3DDevice9On12`, unwraps the private
  graded Sol texture to `ID3D12Resource`, signals a caller fence, returns the
  texture, and releases temporary references. The probe runs once per session
  and the receipt requires exactly one successful unwrap/return pair.
- Two live final-stage checks on redirected PID 24740 passed with eight linked
  layer captures each, exact three native steps, no errors, restored code and
  clean detach. The second receipt records `unwrapped_and_returned: true` and
  `count: 1`; subsequent read-only preflight found an advancing Sol/Ky clock.
  The first attempted check stopped before hook installation because the local
  D3D9 ABI checker treated `REFIID` as an integer; its header parser and test
  now correctly treat that argument as a pointer.
- This proves ownership transfer for the source-owned fighter resource. It
  does not create a shared output texture or fence handle, copy pixels on the
  GPU, publish a frame to uf-arena, or demonstrate playable latency.
