# Authored cross-ruleset experiments

These executable guests test the compatibility boundary. They are not SFIII or Xrd
adapters. They use authored timelines/boxes and the baseline's KFM sprites, staged
locally by `stage-synthetic-fixtures.py`; no new runtime dependency or retail asset
is required. Their shared body clock reuses the existing locomotion/reaction code
with a separate immutable authored spec. Native CNS never simulates these fighters.

| Ruleset | Controls and bounded rules |
|---|---|
| Both | Arrows move/jump/crouch; Z is a ground normal with 4 startup, 3 active and 11 recovery ticks. Damage 30, chip 3, hitstop 5, ordinary ground high/low guard. |
| `parry-test` | Press/release X in ground neutral: a six-collision-tick window, eighteen-advancing-tick cooldown. A successful ordinary contact consumes the window, deals zero damage/push/stun, and freezes the defender for two ticks. Missed timing and held X cannot reopen it. |
| `airdash-test` | Press X in air: eight ticks of forward air dash, costing 20 meter and the single airtime charge. Landing restores the charge. X during a confirmed normal cancels recovery to neutral for 15 meter; hits and blocks confirm, whiffs and parries do not. Hold Back+X for ground resource guard: each committed eligible guard contact costs 10 and waives chip. With less than 10, normal guard/chip applies. |

Meter starts at 100, never regenerates, and resets with the round. Dash/cancel reject
insufficient funds. Stop/pause freezes private mechanic clocks; snapshot clones own
window, cooldown, dash/charge, confirmation, requests, meter and counters. Synthetic
blobs wrap the validated body blob with backend/version/private fields. Invalid loads
are atomic, including wrong backend/spec/version and cross-ruleset mechanic fields.

`DefenseQuery` exposes parry/resource-guard eligibility without spending anything.
The pure arbiter returns `Parried`, `Barrier` and `ResourceCost` in `HitResult`.
The host owns collision/activation consumption and canonical health; the defender
commits its window/resource/reaction, and `CommitAttack` supplies cancel confirmation.
Native defenders still negotiate through the existing native routine and then notify
the guest attacker. Neither route dispatches combat on an opponent's backend name.

A parry maps to the native guard contact code solely for contact consumption and
attacker guard hitpause/bookkeeping. It remains a distinct result: no defender
guardstun, received-hit increment or cancel confirmation. It does not grant attacker
stun or emulate native parry triggers. Throws, native custom states and reversals remain
excluded. The authored guests have no projectile or air-normal move; universal juggle,
priority, simultaneous trades and original-game fidelity are outside this phase.

```powershell
# Rebuild with tools/build-runtime.sh using the Windows setup in MODDING_PLAN.md.
./tools/play-synthetic.ps1 -Rules airdash-test -Practice
./tools/play-synthetic.ps1 -Rules parry-test
./tools/smoke-synthetic.ps1
./tools/smoke-synthetic.ps1 -Sync
python tools/smoke-controls.py --synthetic
```

The play launcher opens a visible window with both automated input probes disabled.
Practice uses a stationary native target. Debug labels show backend/body clocks and
meter/window/dash/charge. Pause freezes/resumes; Scroll Lock advances one paused frame.
Keyboard automation needs an unlocked Windows desktop and no other IKEMEN instances.

The smoke scenes are explicit offline input oracles, separate from ordinary play.
Parry, missed timing, resource exhaustion, dash/cancel, KO/reset and a native-attacker
parry run actual host collision and match lifecycle. `-Sync` uses strict eight-frame
GGPO rewinds and checks host checksums that include full guest-private blobs. Contact
records exclude resimulation so activation uniqueness isn't confused with replay.
Core, host/replay and SDL/pixel evidence are recorded separately in `PROGRESS.md`.
