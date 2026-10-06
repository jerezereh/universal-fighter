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

## Next implementation phase (in progress)

| Step | Implementation decision and required tests |
|---|---|
| A. Multiple guest runtimes | Replace the concrete KOF-only shell/snapshot binding with owned runtime cloning/restore that can support two authored rulesets. Preserve native/Kyo behavior and reject wrong backend/version/spec blobs before adding mechanics. |
| B. Parry ruleset | Add a short defensive window through pure defense query and committed result. Prove zero damage on a successful parry, one contact/resource commit per activation, missed timing and snapshot/replay. |
| C. Air-dash/cancel ruleset | Add bounded air mobility, cancels and defensive resource spending. Prove legal transitions, exhaustion, landing/round reset and state hashes across stop/pause/replay. |
| D. Cross-ruleset proof | Test attack-to-parry and resource/cancel interactions in both directions without opponent-name branches. Repeat native/Kyo regressions before further real-game adapters. |

Step A is implemented: the shell uses an owned runtime interface, generic pose/attack
descriptors and backend-tagged blobs. Steps B–D remain in progress; these mechanics were
not implemented by the first milestone.

Keep new protocol/runtime/combat code separate from host internals. Capture host edits as
versioned patches or a maintained fork: ignored upstream checkout edits alone are not a
deliverable. Every behavior change needs focused validation; visual match acceptance
requires a running renderer and user-input exercise, not just a headless simulator.
