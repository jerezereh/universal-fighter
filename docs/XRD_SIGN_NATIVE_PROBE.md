# SIGN native passthrough investigation

**2026-10-08 correction:** previous screen inspection reversed the D3D9 sampler getter/
setter slots. Its sampler readings and claimed nonmutation are invalid; affected color
captures must be repeated after reopening SIGN. Counter/input/collision and executable
hook restoration do not establish GPU sampler-state restoration. The first experimental
GPU grading trial exits SIGN and is rejected. Corrected native calls now pass independent
installed-header ABI checks; live corrected inspection/grading remains pending.

The generic IKEMEN receiver is implemented. SIGN investigation includes a VM_READ-only
probe/state recorder, a temporary native return observer and a bounded freeze/step
experiment. The last two inject development instrumentation; the probe/recorder do not.
The optional named-input experiment writes only the source update's input register;
none sends desktop keyboard input, exposes a guest endpoint or advertises full passthrough capabilities.
All discovered addresses and loaded game bytes remain in ignored local
`artifacts/xrd-sign-native`; they are not source profiles to distribute.

## Run the next source check

Keep the original game under manual UI/input control. If it is closed, the existing
launcher uses the official bootstrap and the cached missing DirectX libraries:

```powershell
./tools/play-xrd-source.ps1
```

Open offline Practice/Training with Sol versus Ky, then obtain its PID and probe:

```powershell
Get-Process GuiltyGearXrd | Select-Object Id, MainWindowTitle
python tools/xrd-sign-probe.py --pid <PID>
```

For disk inspection or tool validation only:

```powershell
./tools/bootstrap.ps1
python tools/test-xrd-native.py
python tools/xrd-sign-probe.py
```

Each probe creates a fresh ignored folder and receipt. The live form fingerprints the
process executable, confirms it is the exact verified SIGN install/app, enumerates the
actual loaded main module, checks PE image bounds and reads its executable code section.
It compares candidate discovery signatures with the disk scan and saves loaded code
for subsequent local disassembly. It has no memory-writing, remote-call, process-suspend
or injection APIs. Access denied, partial reads, wrong PID/build and ambiguous reference
declarations fail explicitly; the tool never chooses another process automatically.

## Reference evidence and verified scope

Two development-only upstreams are pinned in `tools/upstreams.json`:

- [Altimor's legacy Xrd overlay](https://gist.github.com/AltimorTASDK/e236da6255d16b3ddd3e),
  revision `f380ffb436a45271cc8c81e4025eb7551e800846` dated 2016-04-16. Its public source
  supplies fifteen active discovery declarations for engine/world, position/pushbox,
  collision and rendering-related candidates. The probe reads these declarations from
  that pinned checkout rather than embedding retail addresses or copying the mod.
- [kkots' Rev2 overlay](https://github.com/kkots/ggxrd_hitbox_overlay_2211), revision
  `996e5b86e41bb37137bd74b74483335517fa947c`. Its frame-control implementation is a
  reference for the required hooks, not a SIGN plugin or a compatible binary. It gates
  battle update, actor ticks and actor-component ticks; stopping only a wall clock or
  hiding a window does not establish the guest's one-step-per-request behavior.

The verified SIGN executable/app identity remains the existing SHA-256 and app 376300.
Its PE32 code/data sections are bounded and a `.bind` section is present. All fifteen
legacy signatures have **zero on-disk executable-code candidates**. The initial probe
therefore required comparison with the normally loaded module. That live comparison
now succeeds: normal bootstrap startup exposes usable code, with eleven unique legacy
matches and four ambiguous groups. This does not make every reference hook compatible
or justify installing Rev2's offsets into SIGN.

Authored checks pass for PE header/section/image bounds, reference parsing, unique,
missing and ambiguous candidate matches, out-of-section adjustments and candidate-only
status. A real own-process Windows oracle confirms the VM_READ-only handle, module
enumeration, exact bytes, process-path identity rejection and invalid-read rejection.
The bootstrap confirms both new pins, Python syntax checks pass and the disk receipt
confirms original executable hashes remain unchanged. The own-process oracle is not
live SIGN verification. The initial work package ran without a SIGN instance; the live
results below come from the following work package.

## Live state observation (2026-10-06)

The original bootstrap launcher completes a fresh launch and restores its caller PATH.
The user confirmed Sol-versus-Ky offline training and retained manual UI/input control.
The live/disk code comparison finds 14,840,719 different bytes out of 14,898,688 code
bytes. Original executable fingerprints remain unchanged. No code patch/hook was installed.

`xrd-sign-observe.py` derives a session-local state profile from the verified live receipt
and pinned reference. It validates the engine global's load instruction/data bounds,
then resolves ambiguous position candidates through calls from the unique native throw
envelope. Scalar thiscall getter bodies supply the position/parent fields; public
reference declarations supply slot/collision/facing/scale fields. Addresses, field
offsets, bounded disassembly and profiles remain ignored local evidence. The program
never calls native getters, whose bodies can have side effects.

```powershell
python tools/xrd-sign-probe.py --pid <PID>
python tools/xrd-sign-observe.py <new-live-probe-folder> --seconds 30
python tools/xrd-sign-state-check.py <observation-folder> --collision <import-folder>/COL_SOL.bin
python tools/test-xrd-state.py
```

The profile is bound to the live PID/module/code hash. Source restart, code drift,
missing engine, invalid counts/boxes, duplicate slots, scene changes and parent-relative
fighters fail explicitly. Read-only samples contain raw X/Y, facing, scale, boxes and
candidate pose/state strings. Metadata records UTC start and high-resolution wall time;
**samples are not simulation frames**. Names remain observation candidates rather than
a canonical moveset or full source state implementation.

Verified observations:

- The two grounded fighter slots have opposing raw positions/facing consistent with
  the original training window. Three Sol and five Ky idle hurtboxes are readable.
- A user-controlled standing J/Punch produces `NmlAtk5A` and active pose `sol200_02`.
  Its live attack rectangle and hurtboxes exactly match the imported collision record.
  The observed current-versus-previous state-name fields distinguish the normal's
  activation and return to standing; no retail field offsets are committed.
- In the 45-second capture, all 4,468 sampled Sol box lists match their pose's source
  records exactly. Six samples contain the active normal. This is one recorded attack,
  not six attacks or a verified active-frame duration.
- A 120-second idle capture gives 12,798 matching and three mismatching box lists.
  Two mismatches match other idle poses, consistent with unsynchronized pose/box reads;
  their cause is not established for all three. The recorder deliberately marks
  `atomic_native_frame=false`; a synchronized native boundary is still required.
- Movement/jump/crossover changes were not captured in the observation windows. X had
  changed between initial training inspection and recording, but the recorded ranges
  are static. A controlled movement/facing oracle remains pending.

The shared actor-iterator discovery signature from Rev2 has one SIGN match. Its
component-tick and battle-clock signatures have none. Code inspection and read-only
memory differences identify possible clock-related fields, but no one has been
accepted as the source simulation/render frame identity. Do not transplant the Rev2
freeze/step implementation or promote wall-clock timestamps into frame numbers.

Authored state checks verify getter/operand derivation, bounded raw observation,
invalid parents/counts/NaN/slot rejection and explicitly unsynchronized status. This
establishes live state access and one source-normal collision oracle. Native stepping,
isolated RGBA, input injection and contact suppression remain unimplemented.

## Native return-boundary trace (2026-10-06)

A bounded local disassembly now identifies the enclosing routine of an object counter
increment. Its entry aliases ECX to ESI, its final return has no stack arguments, and
the writer instruction bytes agree with the decoded aligned counter field. The counter
increment occurs before further work, so the observer captures at the routine's return.
One direct caller passes the inner engine object and does not consume a return value.
All retail addresses, candidate profiles and disassembly remain ignored local evidence.

`gather-xrd-instrumentation.py` caches checksum-pinned Frida 17.22.2 in `local-cache`.
It is development tooling only, with no source-directory or global Python installation.
`xrd-sign-boundary.py` validates the exact source hash, session and entire loaded code
before using Frida's temporary entry interception. Unlike the VM_READ polling tool,
this **injects instrumentation and temporarily patches loaded code**. The original
routine runs unchanged; there is no replacement, native invocation or input injection.
Both fighters' scalar/name blocks and collision records are copied on the calling
thread at return, then decoded using the existing bounded state reader. Callbacks record
counter before/after, thread, depth, caller and the engine object's relationship.

```powershell
python tools/gather-xrd-instrumentation.py
python tools/xrd-sign-boundary.py <live-probe-folder> --candidate <local-candidate.json> --seconds 30
python tools/xrd-sign-state-check.py <boundary-folder> --collision <import-folder>/COL_SOL.bin
python tools/test-xrd-boundary.py
```

The candidate JSON contains session-derived `rva`, `writer_rva` and `code_size`, obtained
from local writer/owner disassembly. This intentionally does not select an arbitrary
counter or publish a retail signature. A restart requires a fresh probe/profile and
candidate verification. Teardown attempts stop, unload and detach independently, then
checks that the entire loaded code hash is restored and the disk executable is unchanged.

Two live idle traces contain 284 and 1,418 return observations. Every invocation advances
the candidate counter by exactly one, with zero continuity gaps, one thread, depth zero,
one caller and ECX equal to the engine root plus its inner-object adjustment. All
1,702 Sol pose/box lists match the original collision archive, with zero mismatches,
unmapped poses or trace errors. Both hooks detach and restore the loaded code hash.
This verifies a consistent **observed update boundary**, not a complete simulation-frame
contract. Movement/attacks under this hook, other-thread state ownership, input sampling,
hitstop/pause and rendering remain unverified. `native_tick_verified`,
`atomic_native_frame`, `host_step`, `isolated_rgba` and `universal_contact` remain false.

## Bounded native freeze/step proof (2026-10-06)

The same tool's optional `--gate <clean-boundary-folder>` requires a clean, same-session
return trace: one thread/caller, inner engine object, depth zero, consecutive increments,
identical function bytes and verified detach/code restoration. An authored x86 scratch
routine verifies Frida's thiscall argument register, original-call bypass and restoration
before touching the source routine. Native source exceptions remain native exceptions.

The temporary replacement skips the routine between requests. Each `step` RPC grants
one credit, consumed on its next ordinary source-thread invocation; it calls the original
routine in that context and copies the resulting state at return. A second pending credit
is rejected. Scene/caller/read changes fail open to normal execution. There is no arbitrary
worker-thread tick call and no source keyboard/menu input. An eight-second lease resumes
normal execution without renewals; a twelve-second hard lifetime removes the gate even
while the controller remains connected. This is a development experiment, not a persistent
guest session or the host's transport endpoint.

Graphics observation derives bounded device-method candidates from the pinned legacy
reference's OS `d3d9.dll` constructor pattern. It observes all candidates and validates
each actual device's method-table entry at invocation instead of selecting the first hit.
Successful `Present` and `EndScene` returns are tagged with the held native counter.
These are graphics-call observations, not isolated fighter images or one-to-one frame IDs.
The initial strict constructor-table equality check saw no presentations and failed the
render gate; validating the actual device's corresponding method entry resolves that
observation failure. Source and graphics hook bytes restored after both runs.

```powershell
python tools/xrd-sign-boundary.py <live-probe-folder> --candidate <local-candidate.json> --gate <clean-boundary-folder>
python tools/xrd-sign-boundary.py <live-probe-folder> --candidate <local-candidate.json> --gate <clean-boundary-folder> --lease-check
```

The final 4.5-second idle run records 230 update opportunities: three requested original
calls, each advancing the counter once, and 227 blocked calls with zero counter changes.
Both fighters' observed state stays identical between requested steps. All 230 Sol
pose/box lists exactly match source collision. There are 230 successful presentations
and 460 successful scene-end calls, including repeated successful graphics work at each
held counter. There are no counter gaps or trace errors. Native and graphics hooks restore.

The timeout test requests no steps: 456 blocked opportunities preserve counter/state.
Its lease expires, successful presentations subsequently show increasing counters, and
the full native loaded-code hash is already restored after the hard lifetime **before
controller teardown**. Graphics hooks also restore at teardown. All 456 held Sol
pose/box lists match. This verifies recovery as well as a bounded idle stepping proof.

`controlled_update_step_verified` distinguishes this experiment from the unaccepted
`host_step`/`native_tick_verified`/`atomic_native_frame` capabilities. Input sampling,
movement/crossover/Punch under host requests, source pause/hitstop, renderer-state
association and state ownership beyond the observed fields remain pending. Isolated
RGBA and native contact suppression/result commits are still unimplemented; SIGN is
not yet a playable guest. Source UI remains under manual user control.

Implementation uses the official [Frida API](https://frida.re/docs/javascript-api/)
and [Direct3D Present contract](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-present).

## Native input routing and non-idle stepping (2026-10-06)

The pinned Rev2 input-holder/history discovery patterns have no loaded SIGN matches.
Tracing the actual update owner's calls instead resolves SIGN's input sampler and the
history writer it invokes for each player. Local bounded disassembly derives the ring
origin/stride, current input, history index, entries, held durations and capacity. The
ingress instruction pushes the sampled register into the writer and then records that
same value; its exact call bytes and link to the validated owner are checked. Sampler
and writer function bytes must match before installing instrumentation. Layouts, addresses
and disassembly remain ignored local profiles, not reusable retail constants.

The input observer verifies each writer call against previous/current input, newest ring
entry, bounded index and positive held duration. A five-second pass gives 581 valid calls
across the two players (one call at the observation-window edge), all neutral, no errors
and clean restoration. The initial instruction-hook caller check failed because Frida
relocates the call's return address; observation mode now keeps the original callsite
untouched, while gate mode associates the validated ingress event with its writer call
on the same thread. No first-match or guessed Rev2 input holder is used.

During a requested original update only, the ingress callback substitutes the packet's
core mask into the register consumed by the original instructions. Each player has a
separate mask; this oracle controls Sol and supplies neutral Ky input. Normal execution
outside the gate retains its original inputs. Named direction/P/K/S/HS/D/taunt mapping
lives in `xrd_input.py`, not the generic IKEMEN receiver. Absolute and facing-relative
directions are supported; conflicting axes become neutral, an explicit adapter policy
pending a source SOCD oracle. Unknown names/non-booleans, oversized plans and training/
menu/macros are rejected. `accept_input=false` compiles neutral input. K/S/HS/D/taunt
state semantics and crossover mirroring have not yet been exercised live.

```powershell
python tools/xrd-sign-boundary.py <live-probe-folder> --candidate <local-owner.json> --input-candidate <local-input.json> --seconds 5
python tools/xrd-sign-boundary.py <live-probe-folder> --candidate <local-owner.json> --input-candidate <local-input.json> --gate <clean-boundary-folder> --input-plan tools/xrd-input-oracle.json
python tools/test-xrd-input.py
```

The local input candidate records `sampler_rva`, `sampler_size`, `writer_rva`,
`writer_size` and `ingress_rva` from the bounded discovery. The authored plan expands to
129 requests over a seven-second gate: releases, backward/forward walking, one jump,
landing, and two isolated Punch presses with recovery. It requires grounded idle Sol
and a distant grounded opponent; one request remains pending until its native return is
received. Post-update facing resolves relative directions. This is a source input oracle,
not a persistent session accepting the host's complete request protocol.

Verified native results:

- Both runs execute exactly 129 original calls, each with one counter increment and a
  two-player input-history pair matching its requested masks. Each produces walking
  both ways, positive jump height, landing and two `NmlAtk5A` activations. Eight executed
  source steps have active attack boxes, four for each normal's `sol200_02` pose.
- The first run has 370 update opportunities with 241 blocked; the visual repeat has
  327 with 198 blocked. Observed fighter state/counter stays unchanged between requests,
  with zero continuity gaps or trace errors. Successful presentations continue: 370/327.
  All 370/327 Sol pose/box lists match the imported collision archive exactly.
- The first normal pair gives pose counts of 1, 2, 4, 2, 2, 2 per activation across the
  six `sol200` poses. These are **executed native update observations** in this gate;
  they are stronger than prior polling samples, but do not establish every source
  timing condition or a synchronized image contract.
- With input hooks installed, the no-credit timeout proof records 453 blocked calls,
  unchanged observed state, automatic lease resume, hard-lifetime removal of update
  **and input** hooks before cleanup, and native/graphics code restoration. The original
  executable hash remains unchanged. No tool edits source files, injects keyboard input
  or focuses the window.
- The full-size source-window video/contact sheets show walking, jump rise/fall and
  landing through the original renderer. Whole-window video is an unsynchronized visual
  oracle, not the isolated RGBA layer the host requires. UI control remains with the user.

`source_input_routing_verified` records the bounded packet/history proof. Full `host_step`,
`native_tick_verified`, `atomic_native_frame`, isolated RGBA and universal contacts stay
unaccepted. The next gates are crossover/facing, native pause/hitstop ownership and
isolated rendering with state/image association, followed by a persistent producer and
universal result/contact integration. No SIGN fighter is connected to IKEMEN yet.

## Crossover, mirrored contact and native hitstop (2026-10-06)

`--oracle crossover` uses `xrd-crossover-oracle.json`: approach from the left, jump right
across Ky, land, then walk backward/forward with the new facing. The initial scene
requires grounded idle Sol and a distant grounded opponent. The 135-step run gives
135 single increments, 158 blocked opportunities, zero gaps/errors, matching source
input histories, both inward grounded facing values and relative walking after the flip.
All 293 Sol collision observations match their source pose. That run has successful
EndScene calls but no observed successful Present calls; it is not a new visible-render
acceptance result.

Explicit `left`/`right` now takes precedence over `forward`/`back`. The generic receiver
supplies both; merging them using a different source facing could neutralize the requested
direction. Relative-only packets still use post-update source facing. The correction is
source-side and has a mismatch-facing authored check.

Combat discovery rejected Rev2's fields and an unrelated decrement routine. A native
Punch instead identifies health, hitstop and animation-age candidates. Actual scalar
getter/setter bodies derive local fields; actor timer code decrements the stop field and
its training path restores health. No native getter/setter is invoked. `xrd_combat.py`
validates bounded aligned bytes/fields and captured behavior. Function RVAs and fields
remain ignored local `combat-candidate.json` / `combat-profile.json`, not retail constants.

```powershell
python tools/xrd-sign-boundary.py <live-probe-folder> --candidate <local-owner.json> --input-candidate <local-input.json> --gate <clean-boundary-folder> --input-plan tools/xrd-crossover-oracle.json --oracle crossover
python tools/xrd-sign-boundary.py <live-probe-folder> --candidate <local-owner.json> --input-candidate <local-input.json> --gate <clean-boundary-folder> --input-plan tools/xrd-contact-oracle.json --oracle contact --combat-candidate <local-combat.json>
python tools/test-xrd-combat.py
```

The combat candidate contains `health_getter_rva`, `stop_setter_rva`, `age_getter_rva`.
Regenerate the source observation profile to include rotation using
`xrd-sign-observe.py <live-probe-folder> --seconds 1`. The contact plan requires grounded
idle Sol within 350,000 raw X units of the dummy. It approaches, presses Punch once and
adds bounded 120-ms holds between thirteen recovery steps. `hold_ms` is an oracle delay,
not a source-frame duration. Both verified idle pose families are accepted; the prior
guard rejected the alternate family before any step. Failed post-checks retain cleanup
metadata. Aligned overlapping pose-buffer matching recognizes `kyk` and handles adjacent
scalar bytes. Optional `--scalar-fields <local-json>` records bounded hypotheses; they
receive separate contact/stop checks rather than promotion into verified state.

The final run has 78 updates and 327 blocked opportunities: one increment per request,
zero gaps/errors, matching input histories and 405 successful presentations. All 405 Sol
pose/box observations match source collision. One health loss occurs at step 38, 420 to
410. The left-facing attack overlaps Ky's mirrored hurtboxes on that update. The box
checker follows the pinned legacy scale/facing/Y transform and rejects unverified/nonzero
rotation; general rotated collision and publication of host attack boxes are not implemented.

Sol's observed stop count starts at 12. Ky's reaction applies on the next source update,
where its observed count is 11. Both counts decrease through requested updates and
animation age stays held. Ninety-three blocked observations in hitstop change none of
the watched health/stop/age values. Both stops reach zero, animation age advances again
and native hit reaction/recovery is observed. Training restores health afterward; this
is original behavior, not a universal result commit. Hooks/code restore and EXE hash agrees.

The pinned host was inspected without modification: `runtime/host.go` passes
`Advance=false` during hitpause, and `runtime/passthrough.go` sends no step/input then.
Universal results must choose one stop owner rather than set a native countdown and
also withhold the same host ticks. Original menu pause, clash/superfreeze, damage/guard
translation and contact suppression remain open. Next: isolated RGBA/state association,
then persistent transport/universal results. SIGN remains unconnected to IKEMEN.

## Diagnostic native backbuffer capture

The same bounded gate accepts `--capture-render`:

```powershell
python tools/xrd-sign-boundary.py <fresh-probe> --candidate <local-owner-candidate> --gate <same-session-observation> --capture-render
```

SIGN must already be in offline Sol-vs-Ky training. Reopening the game requires a fresh
module/state probe and clean same-session boundary observation; previous PIDs, loaded
code hashes and return traces are not portable between sessions. The user now authorizes
autonomous offline UI via `xrd-source-ui.py`; see `XRD_SOURCE_UI.md`. Render diagnostics
restore a minimized source using the nonactivating helper, then capture behind other
windows. This option cannot be combined with the automatic lease-expiry experiment.

On the third observed Present for a held counter, the probe uses the actual device's
backbuffer and a matching system-memory surface. It reads on the presenting thread,
copies rows using the returned pitch, snapshots the existing state and rejects counter
drift. It publishes only after that Present succeeds. See Microsoft's
[GetBackBuffer](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-getbackbuffer),
[GetRenderTargetData](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-getrendertargetdata)
and [LockRect](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3dsurface9-lockrect)
contracts. Acquired surface references are released independently in cleanup, including
when readback/unlock fails. Device/render/gameplay state is not changed by capture.

Limits: eight attempted captures, 2048 by 2048, A8R8G8B8 or X8R8G8B8 and no multisampling.
Unsupported descriptions fail the experiment instead of changing source settings.
Ignored `render-XX.bgra` retains raw bytes; `render-XX.png` is an RGB-only visual preview;
`render-XX.json` records the held counter, state, pitch, format, high-byte histogram and
hashes. X8's high byte is not alpha. `render_check` compares each captured fighter state
with all update-trace states for its counter. Three presentations are a diagnostic
settling interval, not a measured native render-delay guarantee.

Verified without the game: bounded packet/format/pitch rejection, raw channel retention,
RGB conversion, PNG integrity, mismatched-state rejection, resource cleanup failures and
source drift. Live verification on 2026-10-07 passes four 1366-by-768 A8R8G8B8 readbacks,
three exact requested updates, stable source state across 241 blocked opportunities,
linked input histories and 243 successful presentations. The new same-session return
trace has 181 consecutive increments without gaps/errors. The PNG shows Sol, Ky, stage
and HUD correctly; update/presentation code restores, the session detaches and the EXE
hash agrees. Evidence is in ignored `20261007-181216-754630`, capture
`boundary-20261007-181401-013148`. These images contain the full scene; native render
delay, isolated RGBA and atomic-frame capabilities remain unverified/false.

The pinned Rev2 GIF route changes gameplay scale fields to hide entities and darkens
the camera background. Its alpha conversion is not a verified SIGN isolated-layer path.
Next identify a render-only Sol boundary and
measure pixels/state delay before excluding opponent/HUD/background or publishing
alpha/pivot/facing to the host.

## Bounded D3D9 draw observation

Add `--trace-draws` to the same gated command, optionally with `--capture-render`.
The helper restores an unminimized source without activation; it can be covered by
another window. A prior minimized
repeat produced EndScene calls but no Present/image output and correctly failed the
render checks. Do not infer a successful render from source stepping alone.

The observer traces two Present intervals, up to 8192 events each, without changing
arguments/results. It records render targets, clears, textures, shaders, stream/index
bindings and DrawPrimitive/DrawIndexedPrimitive plus both UP variants. Methods come
from the actual device's D3D9 vtable, validated against executable memory and unique
targets. Surface descriptions are bounded at 32 unique IDs. See Microsoft's
[DrawIndexedPrimitive](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-drawindexedprimitive)
and [SetRenderTarget](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-setrendertarget)
contracts and the local SDK interface declaration.

The checker requires complete held-counter intervals, successful native calls and one
renderer thread. It groups observed draws by target, shaders, stream-zero buffer/stride
and texture zero. Other sampler stages remain in the raw trace. Cached bindings before
their first observed setter remain unknown; groups are not inferred actor identities.
Raw events/native pointers/callers, descriptions and summary stay in ignored
`draw-trace.json`/`draw-summary.json`.

The live described proof (`boundary-20261007-182822-447114`) passes 980 draws, 8184
events, 261 groups, no unknown draw bindings and 21 targets, including integer and
floating-point intermediate formats. It also passes three exact source updates,
149 blocked opportunities and four full-scene native images. All original source and
graphics bytes agree after full teardown. The stop RPC's immediate comparison can
precede an in-flight callback's removal; preserve it as a separate diagnostic and
verify every saved graphics prefix externally after unload/detachment. An actual byte
mismatch at that final check still fails the experiment.

Next identify fighter groups against native visual evidence and inspect intermediate
surfaces before altering any rendering. No draw suppression, separate fighter target,
isolated alpha or host publication has been accepted.

## Intermediate targets and mesh identity

Use `--trace-draws --capture-passes` with a clean same-session gate to capture the first
completed binding of each target before its next switch. Limits are 24 readbacks and
128 MiB. The source renderer continues its original calls; GPU copies use same-format
system-memory surfaces and release both acquired references. Native bytes/alpha are
retained. RGB previews decode A8/X8, 16-bit integer RGBA, half RGBA and float R; floating
channels are explicitly clamped for viewing. NumPy is an existing local tooling
dependency, used after teardown rather than while source stepping is held.

The live proof reads 21 targets/117333552 bytes, passes three exact updates, 332 blocked
opportunities and restored code. The inspected first bindings include HUD, mixed scene,
depth/postprocess data and unused regions. Alpha is not accepted as fighter coverage;
reuse later in a frame may change a target's contents. No isolated native layer is
claimed from this capture.

`xrd-sign-draw-identity.py <clean-draw-trace> <local-Sol-SkeletalMesh3-folder>` derives
candidate buffer pairs from complete local UEViewer section layouts. It compares
triangle type, base/minimum vertex, remaining vertex range, starting index and triangle
count, requiring the nontrivial sections on one pair in both frames. Missing/ambiguous
matches and shared part identities fail. Source metadata, counts and pointers remain
ignored; the versioned code contains only the derivation and authored fixtures.

`--suppress-draws <local-draw-identity.json>` with capture/draw tracing briefly skips
only those candidate body/head/weapon buffer pairs. This is a visual identity test,
not an accepted guest rendering mode. It is bounded by the same lease/hard lifetime,
and cleanup reverts the draw replacement before verifying original graphics bytes.
The live test skips 2530 selected draws: Sol's mesh disappears, Ky/stage/HUD remain,
native state stays held between three exact updates and four images are captured.
All original code restores; a later background screenshot shows Sol again.

Evidence is under `20261007-181216-754630`, target capture
`boundary-20261007-195653-657685` and suppression proof
`boundary-20261007-201046-185747`; restored UI image is under
`artifacts/xrd-source-ui/20261007-201835-114664`. This establishes the current scene's
mesh draw identity. The next step is private native draw duplication with source
graphics state restored, followed by coverage/color, pivot/facing and render-delay
validation. Contact/result and persistent producer gates remain open.

## Private mesh replay

After the visual mesh identity proof, `--inspect-mesh-shaders` together with the local
`--suppress-draws` identity reads matching shader programs while keeping every original
draw. Despite the shared identity option, this mode performs no suppression. Programs
and GPU pointers remain private. A clean same-session inspection folder is required by
`--capture-layer <folder>`; both modes require `--capture-render --trace-draws` and the
bounded native gate.

The private replay runs each original draw first, then duplicates matching opaque color
draws into a transparent A8 target. A guarded Shader Model 3 epilogue changes only private
output alpha; source shaders are not edited. The private pass preserves RGB instructions,
textures and vertex state, uses source depth without writes, restores MRTs/full state,
and independently releases resources on the renderer thread. Observed destination/
source-color blending is preserved in RGB and keeps the prior opaque alpha. Other blend
semantics/alpha tests are skipped and recorded. The API values are checked against
[Microsoft's blend enumeration](https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3dblend)
and [render-state enumeration](https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3drenderstatetype).

The final live proof `boundary-20261007-205242-036919` passes three exact steps, 289
blocked opportunities, 291 Present calls and four private images with 13 draws each,
no skipped material draws and restored source graphics state. Original code restores
after detach. Native alpha is 0/255 with zero RGB outside coverage; checker previews
show Sol alone and preserve opaque black pixels. The idle crop is 285–286 by 513 pixels.
`xrd_layer.py` writes RGBA/checker crops using native alpha after teardown. All raw source
data and generated previews remain ignored.

Shader-inspection caching, replay recursion rejection, acknowledged step requests and
cached COM call wrappers address failed/slow diagnostic runs; their cleanup evidence
remains in the progress record. This is bounded render investigation. Native HDR/final
postprocess color matching, dynamic coverage, both facings, foot pivot and render latency
are still unverified; no `isolated-rgba` or atomic-frame capability is promoted.
Native instrumentation calls now have five-second controller bounds. The pinned Frida
shim honors cancellation for native calls but its synchronous RPC wait needs a daemon
fallback. `test-xrd-cleanup.py` verifies timeout/unload/detach on an owned helper rather
than injecting failures into a game. A later SIGN repeat stalled after independently
verified source/graphics restoration; its teardown is explicitly unaccepted. The source
window then became unavailable, so subsequent live work requires fresh training/profile
evidence. No disappeared/stale window or failed teardown is accepted as a producer frame.

## Selected native movement and attack renders

`--layer-steps 0,4,8,12,16,20,24,28` selects up to eight requested update indices,
including initial zero. With `--input-plan tools/xrd-render-motion-oracle.json --oracle
render-motion`, each selected source state gets a matching full scene and private mesh
image. `tools/xrd-render-attack-oracle.json --oracle render-attack` instead uses
`--layer-steps 0,1,3,5,7,9,12,20`. Both require the fresh session's gate, native input
profile, draw identity, shader inspection and normal capture/draw options.

The controller waits for selected private images before issuing the next step. Private
replay requires the presentation counter to equal the current native counter and captures
each requested step once. This avoids reusing a previous counter's presentation count.
Native packets are bounded at eight pairs/128 MiB; RGB previews, histograms and disk
encoding run after teardown. The experiment lasts ten seconds, within the unchanged
twelve-second native hard lifetime. Invalid/missing/duplicate/stale-counter/state pairs,
skipped materials, unchanged action images and direction mismatches fail the oracle.

Fresh probe `20261007-211042-686316` rederives state and all graphics identities.
`boundary-20261007-212257-282158` passes 28 exact movement/jump updates, 244 blocked
opportunities and eight pairs; the layer follows native X/Y directions.
`boundary-20261007-212507-124638` passes 20 updates, 248 blocked opportunities and eight
Punch pairs; selected steps 5/7 carry active hitboxes and changing native mesh poses.
Both preserve input history/frozen state and restore original code after detach.
The updated bounded cleanup path also passes the new neutral private rendering check.

Target-edge coverage is reported explicitly: the movement oracle's jump step 24 is
clipped at the top. Motion/action agreement is not complete render/transform acceptance.
Three presentations remain a settling heuristic. Camera/render ownership, exact delay,
HDR/postprocess colors, foot pivot/source units and left-facing visual evidence remain
open; no `host-step`, `isolated-rgba` or atomic-frame capability is promoted.

## Held-counter render settling and shutdown

Use `tools/xrd-render-settle-oracle.json --oracle render-settle --layer-steps 0,1
--layer-presentations 3,6,12,24` with the normal fresh-session private capture options.
The eight pairs preserve the source counter/state within each group. Exact native
mesh/alpha hashes test the settling assumption; earliest tested stable suffixes are
reported as diagnostics rather than a producer delay guarantee.

The recovered-session proof `boundary-20261007-215305-789878` completes one exact
update and 49 blocked opportunities, with 50 Present calls and clean source/graphics
restoration. Idle images match at all four presentations. Walking startup changes
between 3 and 6; the tested 6/12/24 images match. The strict settling oracle fails as
intended. Camera versus skeletal/render ownership is not inferred solely from pixels.

An earlier one-step run expired its lease while waiting for the full duration and
timed out during cleanup, leaving temporary code installed. Its receipt is explicitly
failed; the verified unresponsive offline process was restarted. Render plans now exit
once all steps and both sides of selected image pairs complete. Stop RPC schedules
teardown after Present on the renderer thread, releases pending private resources there,
removes draw/input/graphics hooks, and resumes normal source updates last. External
prefix/code hashes are still checked after unload/detach; scheduling alone is not proof.
Neutral, shader and private repeated-capture checks validate the revised shutdown in
the recovered training session. No native guest capability is promoted by these checks.

## Read-only native vertex transforms

Add `--inspect-layer-transforms` to a private layer capture. Each selected body render
reads the original vertex program, 256 float constant registers and viewport, then uses
the already loaded native D3DX shader disassembler. It preserves the original program
and constants. Getter/disassembler bounds and independent COM release are checked.
Up to eight packets pair with mesh images by source counter, request and presentation;
programs, native assembly and constants are saved only under ignored `transforms/`.
The analyzer reports bitwise changed register indices and viewport differences without
assigning camera or skeletal semantics automatically.

`--inspect-mesh-shaders` also saves the bounded vertex inventory in `mesh-vertices.json`
and local `vertex-XX.bin` files. The current clean inventory has five programs across
depth/color/shadow targets. Vertex bindings remain cached after trace intervals, and
shader IDs are deduplicated independently. Main-color programs have different uniform
bindings, including outline extrusion/depth terms; normalization must derive and validate
each program's bindings rather than reuse the first body's register map.

Fresh probe `20261008-005529-384458`, diagnostic `boundary-20261008-011854-057258`,
passes one exact update/50 blocked opportunities, 51 presentations and eight transform/
scene/mesh pairs. State/history remain held, source graphics restore and complete native
teardown passes. The strict settling oracle still fails: walking presentation 3 differs
from 6/12/24, which agree. Actual disassembly identifies projection, orthographic
projection, local-to-world and bone palette parameters. The 1366x768 viewport and bone
palette stay unchanged within each held group. Shader-used projection/translation inputs
change between walking presentations 3 and 6 and agree thereafter. Changing unused
constant slots are not interpreted as skeletal movement. This does not accept a general
render delay or prove source-independent framing/pivot.

If SIGN becomes minimized during capture, cleanup first restores its verified window
without activation so renderer-thread teardown can run. Pending stop receipts include
saved graphics prefixes for after-detach checking, but a stop that never completes still
fails. SIGN helpers use the exact installed path/hash and profile PID, independent of
a concurrent Rev2 executable with the same name. See `XRD_SOURCE_UI.md`.

## Private projection and bounded pixel readiness

Add `--normalize-layer` to the normal private capture options, using a fresh clean
shader inspection containing `mesh-vertices.json`. Each actual vertex program supplies
its named projection/orthographic/local-to-world bindings; program bytes must still
agree at replay. Unknown/aliased/inline bindings reject. The diagnostic private target
is 640x768, with render-origin pivot (320,700) and two pixels per native world unit.
This is not a calibrated source-logical-unit or host-foot-pivot contract.

The body anchor is observed before the color pass for the same counter/presentation;
head/weapon color order is not assumed. Private depth replaces dependence on the source
stage/opponent depth. Projection, depth, viewport, culling, vertex constants and other
graphics state restore explicitly and through the existing full state block. Source
left-facing pixels are reflected, with winding/culling adjusted, into canonical right-
facing images. Original programs, geometry, textures and RGB instructions remain native.
HDR/postprocess and effect completeness are still unaccepted.
The native outline also extrudes with camera distance, and the fog/reflection vertex
program uses view-space camera position. Named camera bindings are derived independently
for each program. A centered private view initializes its Y/Z offset from the first
native camera/body observation and retains that baseline across requested updates;
camera-world and view-space values are rebased only during private draws. Original
constant bytes restore afterward. This avoids importing source camera-zoom interpolation
into the isolated actor. Neutral left-facing and the subsequent full 135-step crossover
complete with settled pairs and clean restoration. A canonicalized idle silhouette can
match on both sides; the facing oracle no longer mistakes this for missing motion.

When a body program supplies `PreViewTranslation`, diagnostic metadata also records
that vector and `native_absolute_body_origin` from the original local-to-world origin
minus pre-view translation. These shader-derived observations can be compared with
source logical X/Y to derive units without retail field guesses. Walking/jump/crossover
samples verify the same scale horizontally and vertically, with near-zero intercepts.
Run `python tools/xrd_layer.py <motion-trace> <crossover-trace>` to recheck retained
pixel hashes, paired states and restoration and write separate render reassessments and
`unit-calibration.json`. It never changes the original trace inspection. Insufficient
movement, inconsistent geometry, nonfinite coordinates, nonzero depth and differing
axis scales reject. Anatomical foot placement, receiver scale choice and publishable
color remain unaccepted; body-origin calibration does not enable guest capabilities.

`--inspect-screen-shaders` requires neutral `--capture-render --trace-draws` without
diagnostic mesh suppression or an input plan. A private layer retaining original draws
can be combined with this inspection and `--capture-passes`. It records the first
pixel-program/target occurrence among two-triangle draws, up to 32 observations. Native
program/disassembly, original 224 float constant registers, sRGB write state and sixteen
sampler states/successfully observed texture bindings remain local. Unknown initial
bindings stay explicit; repeated use can have different constants and this inventory
does not establish a complete dependency graph. Shader/assembly references release on
all failures. The native proof records 28 occurrences, including fog/distortion,
blur/bloom, generated color grading and SMAA, with disabled sRGB states and clean
source/graphics restoration. Private HDR/color-grading replay and final color fidelity
remain unimplemented; no generic gamma adjustment is accepted from these observations.

The inspection now derives the named `ColorGradingLUT` sampler and uses native texture/
surface getters to link the current 2D resource to a completed target readback. Getter
references release independently. Held counter and draw interval/event identity accompany
the observation. `python tools/xrd_color.py <combined-neutral-trace>` verifies native
program/pixel hashes, settled body/source state and LUT association, then writes an
offline RGBA/checker diagnostic using the observed inline color exponent and captured
packed color cube. It preserves native alpha and transparent RGB. Color improves in the
inspected reference, but standard interpolation, A8 precision loss and omitted bloom/
blur/SMAA prevent full fidelity acceptance. The diagnostic crop retains a derived image
origin; neither anatomical foot placement nor a publishable host frame is implied.

`--hdr-layer` is an opt-in normalized neutral diagnostic, excluding input plans and
settled-frame claims. It verifies the native color target is A16B16G16R16F, duplicates
the mesh into that format and preserves original float16 R/G/B/A under native opaque
coverage. `.hdr` files retain those bytes; `.png` previews explicitly clamp them.
Coverage rejects partial/nonfinite alpha and RGB outside the mask. The native proof
shows sub-A8 dark components and some values above one with clean graphics restoration.
The offline LUT tool accepts these inputs and measures the difference caused by A8
quantization before grading, while preserving coverage. Native HDR pixel readiness,
exact postprocess arithmetic/bloom/blur/SMAA and a publishable host frame stay unverified.

`--grade-layer <screen-inspection>` now has clean bounded native neutral, walk/jump,
standing Punch and full crossover results; it remains a diagnostic, not a producer.
It requires a fresh same-session inventory with independent native-header ABI evidence.
It renders into a private HDR texture, runs the native color program with that texture/
current LUT and black substitutes for bloom/low-resolution inputs, then uses a native
copy program and coverage blending into A8 RGBA. Original shader bytes remain local.
The initial crashed trial remains rejected and its restoration unverified. Fresh-session
inspection revalidates the corrected sampler ABI. The next native diagnostic identifies
vertex/pixel constant banks left changed by state-block application. Explicitly restore
both captured banks afterward, including failure cleanup, then verify every byte alongside
viewport, checked render states, shaders/FVF, depth and modified textures/samplers. Setter
failures or any remaining mismatch reject the trial. Authored incomplete-block/setter/
resource-failure checks and 83 literal native device ABI checks pass.

Probe `20261008-211431-636314` retains successful grading trials: neutral
`boundary-20261008-211808-150816`, walk/jump `boundary-20261008-212322-598030`, Punch
`boundary-20261008-212403-457965` and complete crossover `boundary-20261008-212548-864650`.
These verify graded coverage, held-state pixel equality and graphics/hook restoration.
Source bloom/blur/SMAA, final color fidelity, anatomical pivot and host scale remain
unaccepted. No connected producer, persistent result ownership or universal contact
capability follows from these bounded render checks.

`--source-view-layer` provides a separate neutral grading diagnostic with original camera
constants and viewport, without normalization, input plans or readiness claims. Native
allocation dimensions can exceed the used viewport: the observed 1920x1080 scene target
uses a 1366x768 viewport/backbuffer. Do not scale the entire allocation to compare pixels.
Run `python tools/xrd_compare.py <source-view-trace>` to verify linked/hash-clean captures
and the observed viewport, crop unused allocation space and measure opaque interior RGB.
The mask comes from private coverage; it is not an independently recovered source alpha.
The current source HUD covers the feet and contributes large errors. These measurements
do not establish geometry/material fidelity or isolate bloom/AA errors. Keep all source
images and program inventories local and obtain an unobscured reference before acceptance.
If the source has no HUD toggle, `--exclude-rect x0,y0,x1,y1 --exclusion-note "evidence"`
can omit an explicitly observed overlay region from the diagnostic. At most 16 integer
rectangles inside the source viewport are allowed; removing every interior pixel fails.
The separate excluded report records rectangles and omitted counts and preserves the
unfiltered report. Do not use error-selected masks to claim fidelity, and do not accept
feet/whole-fighter presentation from a comparison which excludes them.
The LUT-consumer screen record additionally retains its bound vertex program/constants
and, for the observed indexed CPU quad call, four bounded vertex records, six indices and
the native declaration. Stage/constant/stride/index/declaration framing and local hashes
are checked before retaining these inputs. Vertex padding has no shader-input meaning;
interpret declared attributes only. The native bloom and low-resolution coordinate
transforms differ, so do not invent a shared zero/normalized UV mapping for effect replay.
`--source-color-layer` requires original-camera mode and inspected native vertex/quad
evidence. It synchronously repeats the actual indexed CPU color draw on an owned target
using its original vertex program/constants/texture inputs, then applies private coverage.
The source scene and effects are reused wholesale; `full_source_color_replayed` distinguishes
these diagnostics from private HDR grading. Never claim isolated bloom or source color
from them. Similar error against the final backbuffer calls for a same-presentation original
color-target comparison before attributing differences to later effects or material replay.
Original-camera grading also captures that original color target at the same counter and
presentation, after the native draw and before private processing. `--color-stage` selects
these reference packets for the offline comparison and verifies stage/shader/state/hash/
viewport linkage. Its report is separate from final-backbuffer comparisons. Full-source
control matches interior RGB exactly; the sampled private-input path differs by at most
one byte in 0.0272% of unexcluded interior pixels. This is base graded RGB evidence only;
silhouette borders, independent source alpha, final postprocessing and host pivot/scale
remain separate gates. Native stage readback failures reject the diagnostic.
`--capture-screen-stages` requires exclusive neutral pass/screen inspection. It retains
every qualifying output from grading through observed SMAA blending, including repeated
copy writes, and captures the matching first-presentation final backbuffer before issuing
more update credits. These warm-up-frame diagnostics cannot claim settled readiness.
Per-draw active texture/surface associations avoid stale associations from shader-key
deduplication. Run `xrd_pipeline.py <trace> --region x0,y0,x1,y1 --note "observation"`
for a hash/state-linked regional report; it explicitly includes background and excludes
auxiliary edge/weight buffers from RGB comparisons. Resource links identify latest retained
writes, not complete write history. The measured sequence first changes color at the
blur-fed composite, with further changes at SMAA and a smaller final-image residual.

`--settle-layer` requires normalization, up to four selected requests, no fixed
`--layer-presentations` and no per-sample transform inspection. It starts candidates at
presentation 3 and compares complete native pixel buffers from consecutive renders at
the same source counter/facing/draw count. Only an identical pair is sent as diagnostic
scene/layer evidence; presentation 24 without equality fails and retains its final
unaccepted images. Python recomputes raw/alpha equality, source-state association and
framing bounds. Native errors abort promptly and tear down hooks. Register arrays and
absolute render-origin values are not used as a universal settling clock.

For the motion plan use `--oracle render-framing --layer-steps 0,4,16,28`; for the Punch
plan use `--oracle render-attack --layer-steps 0,3,7,20`. The crossover plan can use
`--oracle render-facing --layer-steps 0,111,135`. Without an input plan, the normal three
neutral credits verify four settled counters through `--layer-steps 0,1,2,3` (default).
All retain eight published pairs/128 MiB, bounded controller/lease lifetime and complete
after-detach code verification. Local retained candidate buffers are replaced, not
accumulated across unsuccessful presentations.
Pixel equality uses the installed Windows native byte comparator, with a startup
equal/unequal self-check and two reused CPU scratch buffers. It replaces the slow
QuickJS per-byte loop without changing the experiment's deadlines or equality rule.
`tools/test-xrd-pixel-compare.py` exercises the actual ia32 ABI and alpha/state-prefix
behavior on an owned helper. Controller failures report the attach/load/start/observe
phase; source and graphics restoration still require their own evidence.

Live motion and Punch pass 28/20 exact updates and eight pairs each, without clipped
target edges. Motion readiness varies through presentations 3/4, 7/8 and 8/9. Initial
strict samples still reject render 3; private projection reduces the walking difference
to a few edge pixels rather than selecting a globally correct delay. Crossover's first
attempt reaches 111 updates/both source facings, then rejects its unsettled candidate.
Final neutral left-facing capture passes three updates/eight pairs at 3/4, with restored
graphics and inspected right-facing private pixels. The complete transition must be
repeated after resetting the training positions. Full pose/tick atomicity and receiver
capabilities are not promoted by consecutive pixel equality.

## Remaining producer gates

A unique signature is only a candidate. Before building a producer around it:

1. Disassemble the actual loaded candidate and validate instruction boundaries,
   calling convention, global-pointer loads and field accesses. Derive ASLR-relative
   locations from that module; never select the first of several matches.
2. Read source transforms/action/clock/collision through the verified pointer graph
   while the user performs controlled movement and standing Punch. Compare source
   frame identity, side/facing and collision with the original window. P is J in the
   user's current training setup. Public reference fields remain hypotheses until
   these actual values/relationships agree.
3. Prove a native stepping gate freezes simulation between requests while keeping the
   renderer alive, then advances exactly once. Inspect input sampling, actor/component
   dependencies and native hitstop before claiming the `host-step` capability.
4. Isolate Sol's source render layer and associate its RGBA output with the same native
   tick. Exclude HUD/background/opponent and verify alpha/pivot/facing. Whole-window
   capture is an oracle, not the layer consumed by the receiver.
5. Suppress native duplicate contacts, mirror host state and commit universal results;
   then test mixed contacts, KO/reset and source/user input. Keep snapshots unsupported
   until native state ownership/restore is demonstrated.

Neither the generic receiver's authored guests nor a successful memory scan establishes
these native stepping/render/contact gates. SIGN is not yet a playable passthrough guest.

## Repeatable render preparation

With offline Sol versus Ky running and both fighters idle, use the development command:

```powershell
python tools/prepare-xrd-sign-render.py --pid $signPid `
  --candidate $updateCandidatePath --combat-candidate $combatCandidatePath `
  --meshes $localSolMeshDirectory
```

Set the variables to the exact SIGN PID and ignored local candidate/mesh paths. The tool
derives a new module/state probe, update-owner trace, draw identity, mesh shader inventory
and screen/postprocess inventory, then verifies four settled counter-bound source frames.
It checks the battle/fighter identity before and after every bounded stage. It never sends
desktop menu input; an unminimized render window is restored without activation if needed.

The ignored probe folder contains `render-preparation.json`, including stage paths and
`prepared` status. Errors preserve a failed report and existing native receipts; the tool
does not retry failures or enable source capabilities. Scene changes require fresh
preparation. This command prepares evidence for bounded experiments; it is not automatic
live producer rebind, full input/combat acceptance or a distributable retail asset package.

## Experimental rolling frame verification

After successful fresh preparation, use `xrd-sign-boundary.py` with that probe's owner,
draw, mesh and screen paths, the existing normalized settled graded/SMAA transaction
options, the combat candidate, and `--stream-check-steps 20`. This enables neutral rolling
capture instead of the four-frame diagnostic experiment. Counts are limited to 1..120
credits and a 60-second deadline. Incomplete runs fail and preserve `stream-check.json`.
The check requires offline Sol/Ky and performs no menu navigation.

One private state/image packet is sent per readiness receipt. The controller retains the
latest image and saves it after teardown in `latest-layer`; frame receipts retain only
counter/order/hash metadata. Full-scene pixels are omitted. Matching private images remain
a readiness candidate, not atomic pose acceptance. State/telemetry logging is bounded by
the check; an indefinite host producer is not implemented. Capabilities stay false.
After display recovery and fresh preparation, native neutral rolling verification passes
20 credits and 21 linked images with clean restoration. Queued credits wait for existing
renderer-owned private frames to release; pending credits suppress new replay. Source/
render overlap was observed and rejected before this guard. Non-neutral rolling coverage
and indefinite transport still remain pending. Restore a lost SIGN display and derive
fresh graphics evidence before reuse; do not reuse bindings from a failed preparation.

For named horizontal input verification, also supply `--input-candidate`, `--input-plan`
and `--oracle render-position`. The plan's expanded frame count must equal the stream
credit count. Only `left`, `right`, `forward`, `back` and neutral inputs are supported;
vertical/attack inputs and neutral-only plans reject. A tested twenty-credit plan is:

```json
[
  {"frames": 8, "input": {"back": true}, "label": "retreat"},
  {"frames": 8, "input": {"forward": true}, "label": "return"},
  {"frames": 4, "input": {}, "label": "release"}
]
```

This native plan passes exact source input history and both movement directions with
21 linked, normalized, uncropped private frames. Forward/backward speeds differ, so the
plan is not a position reset. Every frame checks coverage and source-facing agreement.
`requests.json`, `input.jsonl` and the stream receipt preserve proof after cleanup.
Jump/normal rolling input coverage, indefinite producer transport and combat ownership
remain unverified; source capabilities remain false.

## Duration-controlled stream lifetime check

Use the existing neutral normalized/settled/graded/SMAA transaction options with
`--stream-duration-check --seconds 90 --transaction-loss-check`. No input candidate or
plan is allowed in duration mode. The fixed credit ceiling is replaced by readiness-driven
neutral credits; this remains a bounded development experiment, not a network producer.

Duration checks accept 28..120 seconds, or 60..120 with controller-loss recovery. They
retain 64 source samples, two frame receipts, 64 recent Present records, sixteen diagnostics
and one image. Aggregate counters preserve gaps and total counts beyond the retained window.
The incoming queue holds at most 256 messages and overflow fails. Full per-update state
JSON logging is disabled in this mode; the empty `state.jsonl` is not a complete trace.

Normal mode stops new credits five seconds before its deadline and waits for the final
frame. Controller-loss mode stops credits nineteen seconds before the deadline and ceases
renewal after that final frame, leaving time to verify the native lease's recovery and
hook removal. The 90-second native check passes 75 credits/76 images and automatic recovery
with clean restoration. This is simulated loss of renewal, not a forced controller crash
or real network disconnect. Total process memory and indefinite transport are unverified.
