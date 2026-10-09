# First milestone work plan

Authority: `handoff_doc.txt`. Gate: a complete IKEMEN versus ForeignTestFighter match.
Status 2026-10-05: packages 1–7 are implemented and the bounded Kyo milestone is verified.
Evidence combines the native/native KO and multi-round baseline, sixteen controlled
combat scenes, five strict offline replay scenes, real SDL keyboard input with AI/probes
disabled for P1, and inspected native screenshots. The keyboard scenes cover movement,
crouch/release, jumps, both attacks, crossover facing, Pause, three exact single-frame
advances, readable overlays and a complete mixed match by KO. The implemented API and
supported-interaction matrix are recorded in `IKEMEN_RUNTIME_ANALYSIS.md`.

This is an automated interactive acceptance result for the documented Kyo subset.
Physical user play/feel, other displays/devices, exhaustive source interactions and
online netplay remain unmeasured; complete original KOF behavior is not implemented.
User scope update (2026-10-05): use locally
installed KOF XIII for package 3 instead of the synthetic ForeignTestFighter.
See `MODDING_PLAN.md` for the bounded import and runtime route.

| Package | Deliverable | Acceptance gate |
|---|---|---|
| 1. Recon | `IKEMEN_RUNTIME_ANALYSIS.md`, pinned source manifest | Concrete simulation/input/collision/render/snapshot locations and ownership proposal. Completed by static inspection. |
| 2. Host baseline | Reproducible Windows build, screenpack and original/licensed native test fighter | Launch unmodified pinned host; native/native match, KO and round reset; record build and launch commands. |
| 3. First foreign slice | Backend binding, sampled input, idle/walk/jump/crouch, host rendering | Same arena with a native fighter; no foreign CNS simulation; pause and frame advance step exactly once; native baseline still passes. |
| 4. Mixed melee | Small protocol, foreign normal, defense query, result commit | Hits both directions; high/low blocking, damage, hitstop, hitstun, knockback and knockdown; no duplicate contacts. |
| 5. Projectile/lifecycle | Foreign projectile entities, KO and round reset hooks | Projectile hits/blocking both directions; lifetime cleanup; complete rounds and restart without stale state. |
| 6. Determinism/debug | State blobs, contact ledger, hashes, overlays, replay probes | Restore at startup/contact/hitstop/projectile/KO and replay identical inputs; per-frame hashes agree; boxes/state/backend/frame visible. |
| 7. API record | Update analysis to implemented runtime API and supported interaction matrix | Complete mixed match demonstrated, native regression passes, limitations explicit. First milestone complete only here. |

After package 7, implement two synthetic rulesets (parry versus air dash/cancels/defensive
resource spending). Prove their interactions without matchup-specific code. Only then
begin further real-game adapters, including SFIII and eventually Xrd. KOF XIII is
the user's explicitly selected exception to that original adapter order.

## Authored ruleset phase (verified)

| Step | Implementation decision and required tests |
|---|---|
| A. Multiple guest runtimes | Replace the concrete KOF-only shell/snapshot binding with owned runtime cloning/restore that can support two authored rulesets. Preserve native/Kyo behavior and reject wrong backend/version/spec blobs before adding mechanics. |
| B. Parry ruleset | Add a short defensive window through pure defense query and committed result. Prove zero damage on a successful parry, one contact/resource commit per activation, missed timing and snapshot/replay. |
| C. Air-dash/cancel ruleset | Add bounded air mobility, cancels and defensive resource spending. Prove legal transitions, exhaustion, landing/round reset and state hashes across stop/pause/replay. |
| D. Cross-ruleset proof | Test attack-to-parry and resource/cancel interactions in both directions without opponent-name branches. Repeat native/Kyo regressions before further real-game adapters. |

Steps A–C are implemented and verified: owned runtime snapshots, a six-tick parry,
meter-funded air dash/confirmed cancels/resource guard, and atomic private-state restore.
All six authored host scenes pass strict offline rollback. Three SDL keyboard scenes
verify parry, dash/cancel and resource guard plus Pause/exact frame advance; native PNGs
show both guest labels, boxes and meter/window/charge values. Step D's cross-ruleset
scenes and final native/Kyo regression repeat pass. See
`SYNTHETIC_RULESETS.md` for the precise authored rules and remaining limits.

## Xrd SIGN source phase (in progress, 2026-10-06)

The installed target is SIGN, app 376300/build 1028441. Reconnaissance, pinned offline
tool setup, bounded Sol/common extraction, independent package-table comparison and
native instruction framing are verified. The Sol `NmlAtk5A` candidate's pose literals
link to the extracted collision family. Original source hashes remain unchanged.
Bounded animation sampling now matches Sol's body/head/weapon tracks by bone name and
reads their source scale-key metadata. A six-sample Blender base-color diagnostic bake
renders successfully. This is a presentation investigation, not accepted source sprites:
native timing/scale evaluation, facial blending and toon passes remain incomplete.
Independent glTF/Blender skinning checks now pass, and a source-game reference corrected
the chosen standard-color material from palette 0100 to 0101. Original SIGN training has
been reached through its official bootstrap and the local DirectX cache. The user drives
the UI; bounded native experiments now route inputs during requested source updates.
Window capture remains read-only.

Remaining gates are command semantics/defaults, source clock and coordinate/facing
oracles, verified 3D-pose sampling/toon presentation, a distinct guest runtime and mixed
match/replay/SDL regressions. The bounded sprite bake remains a fallback and oracle;
the next preferred investigation is passthrough feasibility below.
See `XRD_SIGN_MODDING_PLAN.md` and the runnable importer/checks. The authored
mobility ruleset remains an architecture proof, not Xrd behavior.

## Next approach for newer 3D fighters: passthrough feasibility

Recommendation following the user's strategy discussion: test the original engine as a
guest simulation/renderer before expanding the SIGN bake or translated moveset. This
would reuse source animation, materials and effects and may avoid reconstructing large
parts of the game's rules. Feasibility remains edition-specific; Rev2 mod features do
not establish working SIGN hooks. The handoff already permits a passthrough runtime and
does not require rollback networking for the MVP. Keep reproducible stepping as a gate;
do not silently claim that the existing rollback/snapshot guarantees cover a guest process.

1. **Render/state proof:** inspect the exact SIGN build's hook route. Obtain an isolated
   Sol render layer and read position, facing, action, collision/attack state and source
   frame identity. A whole-window video over an IKEMEN stage is not this proof. Begin with
   a small local transport; optimize GPU sharing only after correctness is demonstrated.
2. **Controlled stepping:** accept sampled host inputs, freeze the guest when the host
   pauses and advance exactly one guest simulation tick per requested step. Associate the
   published image/state with that tick; measure stale frames and latency. Stop if only
   unsynchronized real-time window capture is available.
3. **Combat integration:** mirror the opposing fighter's relevant state, suppress duplicate
   source contacts and translate both directions of universal combat results into source
   damage/guard/hitstop/reactions. Prove one normal, one contact per activation, KO and reset
   without fighter-name branches. Read the pinned host boundary before implementing changes.
4. **Capability decision:** audit source state ownership and restore/replay feasibility.
   A bounded offline passthrough may precede full rollback support, but unsupported modes
   must fail explicitly. If native simulation control is insufficient, compare a native
   renderer plus owned rules adapter against the existing extraction/translation fallback.

The generic IKEMEN receiving boundary is now implemented: independent guest sessions,
configurable ten-button mappings, tick-tagged state/isolated RGBA/collision, host-driven
stepping, universal contact callbacks, health/KO/reset and unsupported-mode rejection.
Two authored processes exercise the same receiver without game-name branches. See
`PASSTHROUGH.md` for the protocol, launcher and current evidence. This establishes the
receiver; SIGN has no connected producer or accepted isolated source layer/contact
suppression. Its temporary native investigation and stepping proof are recorded below;
the real-game producer gates above remain open.
The existing Kyo and authored in-process runtimes stay usable.

The SIGN producer investigation now has pinned legacy/Rev2 source references and a
bounded read-only loaded-module probe. Live bootstrap comparison confirms usable
code absent from the disk scan. Engine global/position access is resolved through
actual load/getter instructions and caller relationships; original offline training
supplies fighter facing/idle boxes and a J/Punch `NmlAtk5A` collision oracle. Source
box comparison passes all 4,468 samples in the normal capture. Another idle capture
contains three mismatches, so observation is explicitly not an atomic native frame.
Movement/crossover, source simulation frame identity, native stepping, isolated RGBA
and contact suppression were pending at the polling stage. See `XRD_SIGN_NATIVE_PROBE.md` for the exact
probe/observation commands and evidence limits.

A temporary native entry/return observer now verifies one bounded engine update routine:
two idle traces give 1,702 consecutive counter increments and exact Sol pose/box matches,
one thread/caller and clean hook removal with restored loaded-code hashes. Source
function bytes and counter fields are derived locally, never committed as retail profiles.
This establishes a consistent observed return boundary. Exact stepping, input/render
association, hitstop/pause and other-thread ownership remain gates; producer capabilities
are still false. A bounded fail-open gate now passes an idle three-step proof: one original
call per request, unchanged counter/state between requests, successful graphics work at
held counters and clean native/graphics code restoration. Automatic lease resume and
hard-lifetime hook removal pass. This is a short development gate, not a persistent
SIGN producer. Native input ingress is now derived from actual SIGN sampler/history
instructions, with named input mapping kept in the source adapter. Two 129-step oracles
prove walking both ways, jumping/landing, two standing Punch activations, matching source
input histories and exact source collision. Both preserve frozen state between requests,
renderer progress and cleanup; timeout recovery also removes the input hooks. Source-window
video confirms movement/jump. Crossover now passes both inward grounded facings and
relative controls after landing. A native contact proof derives local health/stop/age
access fields and verifies one damage event, mirrored box overlap, held animation age,
stop countdown only on requested updates, pause stability and recovery. Explicit host
absolute directions take precedence over relative input, avoiding a conflicting source
facing. Next is isolated RGBA with state/image association, then a persistent producer
and universal result/contact integration. Full guest capabilities remain unaccepted.
The bounded experiment now includes optional native D3D9 backbuffer readback with held
source-state snapshots, raw pixel preservation and RGB previews. Authored bounds,
format/pitch, PNG, state-link and COM failure/cleanup checks pass. Live readback now passes
four native images across the initial held counter and three requested updates, with
stable held state, input-history agreement and restored code. The user retains menu
control during the original checks. On 2026-10-07 the user authorized autonomous offline
UI scripts. Render diagnostics now restore a minimized source without activation and
run behind the user's foreground app. See `XRD_SOURCE_UI.md` for bounded menu controls
and desktop-activity deferral. These are full-scene diagnostic images; render latency
and isolated alpha
remain unverified. Next identify render-only fighter draw boundaries.
The optional two-interval D3D9 draw observer now passes live: 980 draws, 261 binding
groups and 21 described targets, including floating-point intermediate surfaces.
It preserves all native draws and records unknown initial bindings explicitly. Graphics
restoration is verified after full script/session teardown. Sol's actor draw identity
is not established yet; next compare candidate groups/intermediate surfaces with native
visual evidence, then prove RGBA alpha/pivot/facing and source render delay.
Intermediate readback now exposes 21 actual targets; the inspected completed bindings
do not provide an accepted isolated Sol layer. Complete mesh-section layouts derived
from local source imports match three native buffer pairs. A bounded visual suppression
proof removes Sol's body/head/weapon while retaining Ky/stage/HUD and source collision
state, with restored graphics code. Current-scene Sol mesh identity is established;
next duplicate those draws into a private transparent target and validate native pixels.
Private native replay now captures four Sol mesh layers while preserving every original
source draw, source update ownership and graphics state. Local shader inspection/opaque
alpha variants retain native RGB instructions, and the observed color-product overlay
preserves underlying coverage. Inspected native alpha excludes the opponent/stage/HUD
and preserves black materials. The crop is diagnostic: color/postprocess fidelity,
moving/attack coverage, pivot/facing and image delay remain gates before publication.
Persistent producer and universal contact/result ownership still follow those checks.
Fresh-session non-idle rendering now passes paired native scene/mesh oracles: walking
both ways and jumping across 28 exact updates, and standing Punch startup/active/recovery
across 20 updates. Selected captures require current counter/presentation agreement and
are unique per requested step. Deferred preview work preserves the native watchdog.
These establish motion/action agreement; one jump frame touches the render target edge.
Framing/camera ownership, exact render settling, colors, pivot and left-facing pixels
still require proof before a source frame can be published to IKEMEN.
Repeated held-counter images now reject the third-presentation settling heuristic:
walking startup changes between presentations 3 and 6; 6/12/24 match in the tested case.
No universal fixed delay is accepted. Short render plans finish once both render sides
arrive, and graphics hooks are removed on the renderer thread before source updates
resume. The recovered native checks pass teardown; the settling assertion stays failed.
Next inspect actual draw transforms/viewport for camera/framing/pivot ownership.
Native read-only body vertex observations now pass paired held-counter captures.
The viewport and bone palette remain stable; shader-used projection and actor translation
inputs change between walking presentations 3 and 6, alongside the mesh pixels.
The strict settling assertion remains failed. Next derive frame readiness and independent
framing/pivot from those actual transforms rather than accepting a fixed six-presentation
delay. Source windows are selected by SIGN path/hash/profile PID; screenshots use its
verified handle, and name-based foreground driving refuses concurrent Xrd editions.
Private projection/depth now centers the native body origin independently of the source
camera and normalizes source-facing pixels. Bounded adaptive sampling waits for two
consecutive identical GPU layers, with independently checked source-state/counter pairs;
it does not assume a fixed render delay. Walking/jump and Punch framing pass without
clipping, and final left-facing idle pixels satisfy the right-facing image convention.
The first full facing transition stops at step 111 and is rejected. Repeating it with
the final readiness criterion requires resetting SIGN to its original distant Sol/Ky
positions; the current foreground driver cannot navigate one of two same-name editions.
Logical units/foot pivot, HDR/postprocess/effects, complete pose/tick readiness and
persistent producer/universal result ownership remain gates. SIGN is still unconnected.
The new-session crossover also rejects its landing frame through presentation 24:
native camera depth/height continue changing, and the outline uses camera-distance
extrusion. Private replay now derives a fixed camera baseline from native values and
rebases the camera-world/view-space uniforms while restoring source state. Neutral
left-facing capture passes. After the user's reset, the full 135-step crossover also
completes with paired settled pixels, both grounded facings and restored source/graphics.
The facing oracle now permits identical canonical idle silhouettes; the original failed
assertion is preserved beside an offline pixel/state reassessment. Named pre-view
subtraction supplies absolute body-origin observations. Walking/jump/crossover samples
verify matching horizontal/vertical world-to-logical scales without a retail constant.
Foot placement, receiver scale choice and color/postprocess fidelity remain pending.
Read-only screen-draw inspection now passes 28 native program/target observations with
constants, sampler/sRGB state, held source updates and restored hooks. The observed
pipeline includes generated color grading, bloom and SMAA; generic gamma correction
is not accepted as source color fidelity. Next obtain an unobscured distant fighter
reference and investigate private HDR/LUT replay. The original programs stay local.
The subsequent distant reference links the native LUT sampler to its captured surface
at a held source state. Offline LUT/exponent application now preserves private alpha
and visibly improves diagnostic colors. A8 precision loss, bloom/blur/SMAA and exact
native postprocess replay remain unaccepted; this preview does not enable publication.
Native private HDR capture now passes with opaque alpha and restored source/graphics.
Measured sub-A8 values and a same-input color comparison establish visible quantization
loss before grading. Preserve float precision until native grading; HDR readback itself
has no pixel-readiness acceptance. Original source menu pause/resume is the next manual
ownership check; persistent producer, exact postprocessing and universal results follow.
Original source menu pause/resume now passes read-only counter/snapshot/GPU evidence
after user menu actions. A reusable read-only clock check and pre-attachment stepping
preflight reject held/discontinuous clocks. Menu changes during a persistent transaction,
clash/superfreeze and universal stop/result ownership remain pending.
The native LUT-consumer draw now observes all 13 private HDR mesh draws still live at
four held source counters, before EndScene releases the layer. This provides a verified
location for private GPU color grading; original draws and source/graphics restoration
pass. Grading replay and final RGBA readiness remain the next implementation gate.
The first opt-in GPU grading trial crashes SIGN and is rejected. Corrected reversed
sampler getter/setter slots and added independent installed-header ABI checks. Earlier
screen-inspector sampler readings/nonmutation claims and affected source-color evidence
are withdrawn pending fresh-session revalidation. Experimental GPU grading has authored
checks but no accepted live result. Counter/input/collision evidence does not prove GPU
sampler restoration. Fresh-session corrected inspection now passes native-header checks,
three exact updates and clean hook restoration. Current LUT-consumer sampler reads/write
report disabled sRGB, without validating the older affected color captures. The corrected
grading trial survives but rejects a graphics-state restoration mismatch before accepting
an image. More precise mismatch diagnostics and authored rejection tests are implemented;
two subsequent pre-start attachment timeouts require a clean SIGN restart before collecting
that diagnostic. A separate read-only clock check confirms the current source still runs.
The next fresh session identifies vertex/pixel constant banks as the restoration mismatch.
Explicitly restoring both saved banks after state-block application now passes the live
neutral grading trial, with eight held-state captures and identical private native A8
pixels at presentations 3/4 for four counters. Source/graphics restoration and coverage
checks pass. Repeat graded movement/normal/facing oracles next; native effects, final color,
foot/scale acceptance, persistent ownership and connected producer capabilities remain
pending. The original failed trials remain rejected. Graded walk/jump (28 updates),
standing Punch (20 updates) and full crossover (135 updates) now pass linked native
state/input, stable paired pixels, unclipped coverage and source/graphics restoration.
Both original facings produce canonical right-facing private pixels. Readiness varies
through presentation 10, so fixed-delay publication is still rejected. Reset distant
offline Sol/Ky training next for the source render/effects comparison; final color,
anatomical pivot/host scale and persistent result/contact ownership remain gates.
Original-camera private grading now passes four source-linked captures with an observed
1366x768 viewport inside the 1920x1080 internal allocation. Direct viewport cropping
replaces an invalid whole-allocation resize. Interior RGB comparison reports remaining
differences but the original HUD overlaps Sol's feet, so final material color/effects
acceptance requires a HUD-free reference or observed overlay exclusion. The diagnostic
tool rejects stale/unaligned evidence and never enables producer capabilities.
The user reports no HUD toggle. Optional explicit observed rectangle exclusions now
retain the unfiltered report and record omitted pixels/evidence separately. The bottom
HUD-band comparison retains 47,036 interior pixels with about 5.817/255 mean error; feet
are omitted, so it cannot establish whole-fighter color or foot placement. Continue
effects/geometry investigation using that limited regional diagnostic.
The native LUT-consumer vertex program, constants, four CPU quad vertices, six indices
and declaration are now captured with clean bounded native/source restoration. Separate
bloom/low-resolution coordinate transforms and a partial internal-target rectangle are
observed. Use those inputs for diagnostic effect reuse before private effect generation;
unrelated source scene contributions cannot become accepted isolated fighter pixels.
The opt-in original full-source color-draw diagnostic now passes native input/state and
graphics restoration checks. It retains original vertex coordinates and source scene/
effect inputs and masks the result with private Sol coverage; it never becomes an isolated
fighter render. Final-backbuffer regional error remains similar, so missing bloom is not
an established cause. Next compare the original color target at the same held presentation
before later postprocessing; final color, source-mask/foot and producer gates remain.
Same-presentation original color-target readback now passes with four linked frames.
Full-source replay matches interior RGB exactly; private HDR/LUT grading matches 99.9728%
of unexcluded interior pixels (max channel error 1/255), including sampled foot interiors.
The final-backbuffer error remains about 5.95/255, localizing it after the color draw.
Identify the later presentation pass next; this does not establish independent alpha,
anatomical pivot/host scale, normalized color across inputs or producer capabilities.
Held-presentation post-color capture now retains repeated copy writes and texture/surface
associations through SMAA. The initial color copy is identical; two-axis blur feeds a
color composite which changes the observed region before SMAA adds further changes.
These regional/background-inclusive diagnostics do not establish isolated fidelity.
Next duplicate that private post-color chain with native texture lineage and correct
coverage/luminance handling; final edges, pivot/scale and producer/contact gates remain.
The bounded inspector now captures post-color vertex programs, constant banks and CPU
quad inputs with three exact native updates and clean restoration. Shader/target dedup
does not prove repeated draws share vertex inputs; preserve synchronous current inputs
when replaying reused copy writes. Retail programs and native input data remain local.
Private original-camera post-color replay now passes nine ordered copy/downsample/blur/
composite draws using private textures and current native CPU inputs. Coverage is applied
only at the end. Four held linked captures and source/graphics restoration pass; limited
HUD-excluded interior error is about 3.47/255, without final fidelity acceptance. A fresh
phase-specific inventory handles copies also seen before grading and stops before UI.
Next add private SMAA/lookup inputs with a coverage policy, then normalize dimensions and
repeat movement/normal/facing checks. No source producer capability is enabled.
Private SMAA now passes the native edges/weights/neighborhood draws with private scene
inputs and observed area/search lookups. Four original-camera captures match backbuffer
dimensions; binary coverage crops the HDR allocation without claiming silhouette alpha
fidelity. Limited HUD-excluded interior RGB error is about 0.752/255 and source/graphics
restoration passes. Next normalize postprocess dimensions/UVs and repeat movement/normal/
facing checks; source producer, anatomical pivot/scale and persistent contacts remain.
Normalized 640x768 private blur/composite/SMAA now passes neutral held-counter settling
with matching presentation 3/4 pixels, native input/constant adaptation and restored
source/graphics state. Private intermediates retain the observed quarter-size padding.
Next repeat movement/Punch/facing oracles before foot/scale and silhouette review.
The shorter 10-step movement/jump and 20-step standing Punch oracles pass with normalized
private postprocessing, exact settled image pairs and restored source/graphics. The longer
28-step motion capture remains rejected for incomplete pairs inside the unchanged time
window. Reset offline Sol/Ky to default starting positions manually before the next facing/
crossover check: current spacing is twice the verified crossover setup and menu reset is
outside verified source ingress. Producer/contact ownership and visual acceptance remain.
The user reset passed read-only verification. Full postprocessed crossover reaches 111
exact updates and crosses/lands but misses the settled pair/deadline, so remains rejected.
Clean opposite-facing neutral rendering passes separately and retains canonical-right
private pixels. Frame-scoped retained shader reuse removes duplicate inspections while
preserving per-draw binding/texture/state checks. Next test a shorter mirrored crossover
from the current right-side position; no complete 135-step postprocess proof is claimed.
The existing host withholds steps during hitpause; the producer must avoid applying a
second native countdown for those same externally held ticks. Clash/superfreeze and
universal stop/result ownership still need dedicated validation.

Keep new protocol/runtime/combat code separate from host internals. Capture host edits as
versioned patches or a maintained fork: ignored upstream checkout edits alone are not a
deliverable. Every behavior change needs focused validation; visual match acceptance
requires a running renderer and user-input exercise, not just a headless simulator.
