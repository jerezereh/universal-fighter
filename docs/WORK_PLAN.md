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
video confirms movement/jump. Next are crossover/facing and hitstop ownership, isolated
RGBA with state/image association, then a persistent producer and universal result/contact
integration. Full guest capabilities remain unaccepted.

Keep new protocol/runtime/combat code separate from host internals. Capture host edits as
versioned patches or a maintained fork: ignored upstream checkout edits alone are not a
deliverable. Every behavior change needs focused validation; visual match acceptance
requires a running renderer and user-input exercise, not just a headless simulator.
