# IKEMEN runtime analysis

Analyzed 2026-10-05 against IKEMEN GO commit
`07558c8ca579ed2dff903c440c2aede006b3a2d4`. All line references below refer to this
revision in `backends/ikemen/src`. Findings are static source evidence; the proposed seam
has not been implemented or demonstrated in a running match.

## Finding

IKEMEN has no existing interchangeable fighter backend boundary. `Char`, `CharList`,
the bytecode interpreter, collision handling, round management, and snapshots share
concrete character state. Replacing `Char` throughout the engine would be a substantial
rewrite. The smallest plausible vertical slice retains a `Char` host shell per foreign
player, dispatches its simulation to a separate runtime, and intercepts mixed combat
before the native hit handler applies side effects. Native/native matches keep their
existing path. This is a proposal to validate, not an established compatibility API.

The shell provides player identity, team membership, host-visible life/position/status,
camera tracking and presentation resources. It MUST NOT run CNS/ZSS movement, attacks,
guarding, physics or get-hit state logic for the foreign fighter. Its fields are an
explicit projection of runtime state, not a second simulation authority. Loading a DEF
or AIR for presentation is acceptable; implementing the foreign fighter in CNS is not.

## Source map

| Responsibility | Exact integration candidates | Observed behavior |
|---|---|---|
| Frame orchestration | `system.go:2827 System.action`, `:2694 charList.update`, `:2712 charList.collisionDetection`, `:3218 charList.tick` | Action is gated by `tickFrame`; collision and final tick use `tickNextFrame`. Interpolation/update is a separate pass. Do not step once per rendered frame. |
| Character scheduling | `char.go:13928 updateRunOrder`, `:13982 CharList.action` | Priority then character ID; command update, prepare, action run, finish are separate passes. Helpers may be appended during the action loop. |
| Native simulation | `char.go:12215 actionPrepare`, `:12429 actionRun`, `:12684 actionFinish`, `:12810 update`, `:12974 tick` | `actionRun` runs negative states and current bytecode, derives guard flags, moves and lands characters. Skipping only `runState` would leave native mechanics active. |
| Input | `input.go:2662 CommandList.InputUpdate`; `char.go:13840 commandUpdate` | Input comes from local, replay, network or rollback providers, then native command buffering; auto-facing affects forward/back interpretation. Tap the same sampled input, not a second hardware poll. |
| State bytecode | `char.go:7032 runState`; `bytecode.go` state controllers; `compiler.go` | Bytecode executes against concrete `Char` and global `sys`; it cannot simply operate on a generic interface. |
| Collision geometry | `char.go:10573` collider buffer access, `:10849 clsnCheck`, `:10889 clsnCheckSingle` | Native boxes use animation geometry, transforms, facing and local scale; cross-runtime export must normalize them once. |
| Collision order | `char.go:14869 collisionDetection`, `:14503 pushDetection` | Push/rebinding precedes hits, then get-hit flags reset, player hits, and projectile hits. Mixed pairs must not also run native resolution. |
| Attack eligibility/contact | `char.go:14038 hitDetectionPlayer`, `:14195` contact branch, `:14318 hitDetectionProjectile`, `:14474` projectile hit branch | Native selection includes team filters, guard distance, juggle rules, targets, depth and hit attributes. Not all native prefilters are appropriate to a foreign defender. |
| Hit processing | `char.go:11168 hittableByChar`, `:11358 hitResultCheck` | Native handler combines guard selection, damage, state transitions and hit bookkeeping. It mutates state; it is not a pure query for `DefenseResult`. |
| Rendering | `char.go:13412 Char.cueDraw`, `:14941 CharList.cueDraw`; `system.go:2798 cueDraw`, `:3671 draw` | Host queues and draws sprites in layers. Export foreign presentation to these queues; leave stepping out of rendering. |
| Rounds | `system.go:2472 resetRound`, `:3310 stepRoundState`, `:4203` reset branch | Host owns lifecycle and reads concrete player state. Foreign runtime reset and life/status projection must cover ordinary and training resets. |
| Save/restore | `state.go:199 SaveState`, `:77 LoadState`, `:309 saveCharData`, `:365 loadCharData`; `state_clone.go:340 Char.Clone`, `:477 CharList.Clone` | Snapshots clone characters and restore them into retained pointers, with shared command references repaired. Adding an interface pointer would alias mutable runtime state unless explicitly snapshotted. |
| State hash | `state.go:436 Checksum`, `:451 String` | Current checksum hashes a debug string with FNV-32a. This is not a complete canonical foreign-state serialization contract. |

## Proposed seam and ownership

1. Add an optional backend binding to root player shells, keyed by stable fighter ID.
   Keep the absent-binding path identical. Start with two players and no foreign helpers.
2. Sample input through the existing provider path. Feed absolute directions/buttons to
   the foreign runtime; that runtime owns facing interpretation, command history and
   buffering. Record input history in its state where required.
3. Dispatch foreign stepping within `CharList.action` at the corresponding simulation
   action slot. Audit prepare/finish, update, tick, screen-bound and round code to prevent
   native physics or transitions from running afterward. `FrameContext` carries host
   pause, round phase and bounds; distinguish global pause from fighter-local hitstop.
4. Project host-visible state after stepping and after combat commits. Foreign gravity,
   recovery and resource logic remain internal. The host owns match timer and rounds.
5. Add mixed-pair collision dispatch before native defender-specific eligibility filters
   and before `hitResultCheck`. Export native attack/geometry through an IKEMEN bridge.
   Native/native stays unchanged. The mixed arbiter handles team filters, overlap,
   contact lifetime and ordering; native-specific defense checks belong in its backend.
6. Implement native defense query and native result application separately. Reuse
   carefully extracted native behavior or a narrowly limited bridge for the synthetic
   slice; calling `hitResultCheck` and then applying a protocol result would double-apply
   mutations. Track omitted HitDef features explicitly. Do not claim all MUGEN attacks
   are supported from a one-normal/one-projectile demonstration.
7. Queue foreign render entities using host rendering, with original test art. Add runtime
   type, state, frame, hitbox/hurtbox and active-contact overlays using host debug drawing.
8. Extend host snapshots with owned runtime blobs and arbiter/contact state. Restore
   bindings by stable ID; snapshot objects must remain reusable without mutation.
   Integrate resetRound and match teardown so no stale projectiles or bindings survive.

## Minimal proposed Go API

This sketch documents responsibility boundaries; it is not yet a compilable public API.
Types will be established by the first vertical slice rather than broad speculation.

```go
type FighterRuntime interface {
    Initialize(InitContext) error
    ResetRound(RoundContext) error
    Step(InputFrame, FrameContext)
    State() FighterState
    Entities() []Entity
    Colliders() []Collider
    Attacks() []Attack
    ReceiveAttack(Attack, ContactContext) DefenseResult
    ApplyCombatResult(CombatResult)
    SaveState() ([]byte, error)
    LoadState([]byte) error
    StateHash() [32]byte
}
```

`ReceiveAttack` MUST be a side-effect-free defense query. Both participants receive the
single accepted `CombatResult`; consumption of defensive resources occurs at commit.
Exported slices are read-only views valid for the current phase; snapshot data must own
its memory. State blobs require a format version and backend identity. A failed load
must leave prior state intact. Native runtime save/load may delegate to the whole host
snapshot initially; do not pretend an isolated native `Char` captures global state.

The first protocol needs IDs, transform, input, entity presentation, attack/hurt/push
rectangles, attack identity, damage, guard damage, attacker/defender hitstop, hitstun,
blockstun, knockback and knockdown, defense outcome and a result. Extensions are typed,
versioned backend metadata; unknown optional keys are ignored and unsupported required
features fail explicitly. Cross-character state takeover (`p2stateno`), throws, helpers,
reversals and arbitrary controller redirection are deferred, not silently approximated.

Choose and document a common coordinate scale and positive-axis convention before
geometry implementation. Convert native `localscl`, facing and animation box transforms
at the bridge only. Collision iteration and extension serialization MUST have stable
ordering; contact keys include owner, entity, attack activation and defender IDs.
Prevent repeated damage from an overlapping activation while allowing explicit multihits.
Snapshot input history, timers, RNG, projectiles, resources and contact ledger, not just
position and life. Hash canonical simulation state, excluding render handles and pointers.

## Validation and unresolved risks

Static analysis verifies source locations and coupling, not runtime correctness. First
establish a buildable unmodified host and native/native baseline, then test one foreign
player standing/walking/jumping in the same arena. Add mixed normal hits in both directions
before projectile and round lifecycle work. Verify save/restore/replay at attack startup,
contact, hitstop, projectile lifetime and KO; compare every frame's canonical hash.

Important open questions: exact input sampling extraction without double SOCD processing;
which prepare/finish/tick functions remain safe for foreign shells; minimum valid player
loader metadata; native result application fidelity; simultaneous-hit ordering and native
triggers reading projected fields. Resolve these with source probes and runtime evidence
before finalizing the API. No real-game recon is needed for this phase.

References: [IKEMEN source at analyzed revision](https://github.com/ikemen-engine/Ikemen-GO/tree/07558c8ca579ed2dff903c440c2aede006b3a2d4/src),
[Universal Modder](https://github.com/rehan-remade/universal-modder). The latter is retained
as a pinned tooling reference for later adapter recon; it is not part of the host seam.

## Package 3 seam (before melee)

The user selected KOF XIII as the first adapter. The current implementation is
`runtime/host.go` plus `runtime/kof13.go`, applied by `tools/apply-runtime.py` and
`patches/0001-fighter-runtime.patch`. The five host scheduling phases dispatch via
`FighterBackend`; the native implementation calls the original methods unchanged.
The KOF implementation runs a separate locomotion state machine, then projects
its transform, coarse state type and animation element into the rendering shell.
It consumes `CommandList.Buffer` after `CharList.commandUpdate`, so local, AI,
replay and network sampling follow the existing path without another device poll.

`FighterRuntime` currently supports step/reset/save/load for locomotion only. No
combat protocol or foreign attack handling is implemented yet. Native collision
results cannot enter the foreign shell; mixed pushing uses host size boxes and
bypasses the native Clsn2 prerequisite for these pairs. Immutable imported specs
are shared while `Char.Clone` copies mutable foreign state into a new runtime.
This is a narrow prototype API; host-level rollback/combat replay remains unverified.

## Implemented mixed-melee subset

`runtime/combat.go` defines attacker characteristics, a defense response and a pure
contact arbiter. The foreign runtime exposes `QueryDefense` and `CommitHit` alongside
step/reset/save/load. Its snapshot value includes activation IDs, held input, reaction
pose, stop/stun/down clocks and push motion. Host `Char.Clone` independently copies the
runtime value and already deep-copies native HitDef target lists/buffers.

Foreign source Clsn1/Clsn2 pass through the existing native scale/facing/depth/contact
path. Kyo's one normal initializes a native HitDef envelope once per activation; native
defense, invulnerability and reaction commit remain in `hitResultCheck`. Native attacks
against Kyo use foreign eligibility and intercept that result boundary before any native
custom-state mutation. Native attacker hitpause/contact fields remain committed by the
original outer melee loop. This reuses native collision and result machinery without
executing foreign CNS. Native/native paths retain the original implementation.

The native defender's query remains embedded in its mutating native result routine;
there is not yet a general side-effect-free native defense API. This is deliberately a
bounded bridge, not the finalized universal API. Ordinary melee is supported; foreign
throws, custom-state transfer, reversals, projectiles and full source priorities/juggle
are outside this package. Contact duplication is prevented by current-HitDef targets and
foreign hitonce, rather than a new global ledger. The host's stable ID/priority order is
retained; a simultaneous-contact matrix and native-attacker replay remain pending.

Foreign global pause freezes the core; hitstop freezes pose/motion/stun and drains only
on an advancing tick. Host life remains canonical. A lethal contact drains stop before
publishing host KO/over flags, but source KO presentation and complete lifecycle cleanup
are package 5 work. Core restore tests are not host rollback proof. Pixel presentation,
human controls and actual host frame advance remain separate acceptance gates. Eight
authored host scenarios pass for both hit directions, high/low guard and mismatches,
knockdown, lethal hitstop/KO and foreign activation duplicate protection. This controlled
matrix does not establish exhaustive original-fighter interaction coverage.
