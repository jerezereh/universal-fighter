# First milestone work plan

Authority: `handoff_doc.txt`. Gate: a complete IKEMEN versus ForeignTestFighter match.
Phase 1 is a source-only investigation. Package 2 now has a successful Windows build and
automated native/native KO and multi-round baseline; interactive validation remains open.
Packages 3 through 7 remain open.

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
begin one-character SFIII recon with Universal Modder, followed eventually by Xrd.

Keep new protocol/runtime/combat code separate from host internals. Capture host edits as
versioned patches or a maintained fork: ignored upstream checkout edits alone are not a
deliverable. Every behavior change needs focused validation; visual match acceptance
requires a running renderer and user-input exercise, not just a headless simulator.
