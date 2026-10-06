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

Remaining gates are command semantics/defaults, source clock and coordinate/facing
oracles, verified 3D-pose sampling/toon presentation, a distinct guest runtime and mixed
match/replay/SDL regressions. The proposed route bakes original 3D poses into host sprite
frames. See `XRD_SIGN_MODDING_PLAN.md` and the runnable importer/checks. The authored
mobility ruleset remains an architecture proof, not Xrd behavior.

Keep new protocol/runtime/combat code separate from host internals. Capture host edits as
versioned patches or a maintained fork: ignored upstream checkout edits alone are not a
deliverable. Every behavior change needs focused validation; visual match acceptance
requires a running renderer and user-input exercise, not just a headless simulator.
