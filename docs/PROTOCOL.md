# Universal fighter protocol: tiers and match rules

Status 2026-10-09: design record. Decisions below were made by the user; everything else is
a proposal until a host and a producer implement it and live evidence exists. The wire
formats stay in `PASSTHROUGH.md` (v1) and `PASSTHROUGH_V2.md` (negotiated extensions).
This document defines what the fields *mean*, for every host and every producer.

## Three tiers

| Tier | Owner | Scope | Defined in |
|---|---|---|---|
| 1. Transport | Host | Connection, framing, session/sequence/tick, capability negotiation, deadlines, failure, layer resources and fences | `PASSTHROUGH.md`, `PASSTHROUGH_V2.md` |
| 2. Match rules | Host-defined, game-neutral | Space, time, combat negotiation, health, presentation | This document |
| 3. Adaptation | Each producer | How one source engine realises the rules: units, write-back, reaction choice, HUD isolation | The producer's own docs |

- Hosts may meet tier 1 differently. IKEMEN steps in lock-step; `uf-arena` runs a pipelined
  barrier. What a guest observes must not differ.
- Every host implements tier 2 identically, with no game- or fighter-name branches.
- Producers never see another game's specifics. Cross-game information travels only
  through tier 2 fields, plus namespaced extension fields (`ggxrd.*`, `sf3.*`) that a peer
  may ignore.

In short: **the host decides where, when and whether something happens. The producer decides
how its game expresses it.**

## Rule 1: the arena owns space and time

The host owns position, facing, stage bounds, walls and corners, pushbox separation, the
camera, rounds, the timer and world time.

- **Motion is proposed, placement is decided.** Each tick the guest reports the motion it
  intends and its pushbox. The host resolves walls, corners and separation and sends the
  final transform. The guest adopts it, even when its source engine disagrees.
- **Source-world containment.** A source engine has its own walls and corner logic, which
  the host cannot see. The producer keeps its source fighter clear of them.
- **Relative placement** (throws, command grabs, teleports to the opponent) is a request:
  "bind the defender at offset (dx, dy) for N ticks". The host grants or refuses it. The
  defender's rules may contest it (throw tech, throw invulnerability) through rule 2's
  classification.
- **Units.** Producers own every source-unit, axis and camera conversion. A canonical host
  length unit is not defined yet (open question 1).
- **Camera.** Host-owned. Source camera moves (super zooms) become requests.
- **World time.** Steps are host-granted. Host pause and host hitpause send no step. A
  guest's freeze or slowdown request (superflash, Roman Cancel slowdown) is applied by the
  host withholding steps from the affected fighters. Every stop has exactly one timing owner,
  stated in the event, so no countdown runs twice.

## Rule 2: combat negotiation

> **The attacker decides what the attack is and how much it does. The defender decides
> whether and how it lands. The defender may transform values but cannot ignore the
> attack's classification.**

**Classification (binding, attacker-declared):** kind (strike, throw, projectile, other),
height (high, low, mid, overhead), air-guardable, unblockable, super, and a strength level
hint. Classification lets each defender's rules refuse things without knowing the
attacker's game. For example, SF3 parry does not accept a throw.

| Attacker owns | Defender owns |
|---|---|
| Damage (rule 3 units) | Whether it connects: invulnerability, guard, parry, Faultless Defense, barrier, burst |
| Hitstun and blockstun **frames** (decided) | Which reaction animation plays |
| Hitstop for each side | Gravity, juggle limits, air recovery, wakeup |
| Pushback, launch, knockdown, wall bounce, counter-hit | Combo scaling and damage modifiers (guts, defense, RISC) |
| Its own resources | Its own resources |

- **Attacker frames.** The attacker's frame counts set the reaction's duration. The
  defender's gravity, juggle and recovery rules still govern airborne states and may end
  them early.
- **Disputes go to the defender**, within the classification.
- **Simultaneous hits** (each fighter is the other's defender): the host resolves them as a
  trade by default, and as a clash only when both guests declare a clash capability.
- **One contact per activation.** Producers suppress source-native contacts. Damage and
  reactions are committed once, through the host.
- **Reconciliation.** In following steps the defender reports the outcome it applied
  (guarded, stun remaining, knockdown), so hosts can detect divergence.

## Rule 3: health in native pools (decided)

Each fighter keeps its game's native life pool. The guest reports `Life`, `LifeMax` and
`Defeated` every step. The host ends rounds on that report and is no longer the health
authority.

**Damage transfer.** Each game declares a **reference pool** at hello: its standard health,
not a per-character value.

```
fraction        = attacker damage / attacker game's reference pool
defender damage = fraction × defender game's reference pool, then the defender's own modifiers
```

- This preserves "how many hits kill" as the attacker's game intends.
- Using the game reference rather than each character's maximum keeps per-character
  toughness on the defender's side. That covers both Xrd's defense multipliers and SF3's
  per-character vitality.
- Migration: a negotiated capability (`native-life`). v1's host-committed canonical damage
  stays the default.

## Rule 4: each fighter brings its presentation (decided: native layout)

- **Layers:** a fighter layer (implemented), a HUD layer (proposed), and later an effects
  layer.
- **HUD.** The host assigns a side at hello/reset. The guest draws its own side's native HUD
  elements in their native layout, in screen space. The host composites the HUD without
  camera scaling. The host itself draws only match-level UI: timer, round indicators and
  announcements.
- **Isolation.** The HUD layer contains only this fighter's elements. Anything a source draws
  for a training dummy or a source-side opponent must be excluded.
- **Private mechanics** (meters, stances, off-screen tag partners) stay inside the guest and
  appear through its HUD. Anything that enters the arena (assists, tag-ins, projectile
  entities) becomes an arena entity under rule 1. That is outside the current scope.

## Producer obligations (tier 3 checklist)

1. Freeze between requests; advance exactly one source tick per step.
2. Suppress source-native contacts.
3. Adopt the host transform, and keep the source fighter clear of source-only walls.
4. Apply hit events with the attacker's frames, choosing the source's own reaction.
5. Report native life, maximum and defeat; declare the game's reference pool.
6. Publish isolated layers that exclude the opponent, any dummy, the background and other
   fighters' HUD.
7. Document the mapping: units, input names, reaction selection, known fidelity gaps.

## Implementation status (2026-10-09)

| Rule item | IKEMEN receiver | `uf-arena` | Rev2 producer |
|---|---|---|---|
| Host transform authority | v1: host sends stage-bound/push `X,Y` | Owns `x,y`; no pushback, corners or rounds | Writes host corrections into Rev2; recentres within Rev2's stage |
| Motion proposal and pushbox | No | No | No |
| One contact per activation | Yes | Yes | Native contacts suppressed |
| Defense negotiation | Universal arbiter: high/low guard, parry, barrier | Back-guard only | n/a |
| Attack classification | No | No | No |
| Attacker frames honoured | n/a | Sends hitstun/blockstun | No: maps stun to Rev2 levels, adds its own 5-frame stop, holds the pre-hit pose during stop |
| Native life pools | No: host-canonical health | No: one `LIFE`, arena-drawn bars | No: `--damage-scale` |
| HUD layer | No | No | No: HUD hidden; Rev2's HUD also shows the dummy's side |
| World-time requests | No | No | No |

## Open questions

1. The canonical host length unit, and how producers declare their scale.
2. The motion proposal's form: displacement, velocity, or both.
3. Throw and placement request lifetime, and how a defender contests one.
4. Camera requests: which ones a host must honour.
5. Rev2: overriding source hitstun after `dealHit`, and isolating one HUD side.
6. Slowdown semantics when the host withholds steps (a fixed ratio or a step pattern).
