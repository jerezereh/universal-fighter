# Generic IKEMEN passthrough receiver

The `passthrough` runtime receives each fighter's simulation and isolated render layer
from an independent guest connection. It has no source-game-name branches. Multiple
games, or multiple fighters from the same game, can participate simultaneously; each
fighter has its own endpoint/session, input mapping, frame clock, activation ledger and
texture. The existing Kyo and authored in-process backends still work.

This receiver is implemented. SIGN's native producer is **not** implemented: its exact
build still needs verified render isolation, stepping, state/collision hooks and native
contact suppression. The runnable guests below are authored protocol oracles, not Sol
or a recreation of SIGN. Window capture does not satisfy the protocol's stepping gate.

## Run the implementation

Build using the existing `tools/build-runtime.sh` route, then run with Python 3:

```powershell
python tools/play-passthrough.py
python tools/play-passthrough.py --no-debug
python tools/play-passthrough.py --smoke
```

The launcher starts two independent Python guest processes and an offline IKEMEN
match. It stages temporary character definitions and logs under ignored `artifacts`.
Closing the host cleans up only those guest processes. Normal play samples IKEMEN's
command buffer with probes disabled. Arrows control movement/jump/crouch; Z (host a)
triggers the demo's normal. The demo advertises other mapped buttons to exercise the
receiver's input API but implements only that one attack. Its facing marker points
towards the opponent; transparent pixels reveal the stage.

The smoke command runs guest/guest, native-to-guest, guest-to-native, KO/two-round
reset and rollback-rejection scenes. It checks request clocks, contact callbacks,
completed match statistics and duplicate outgoing contacts. This does not automate
the keyboard or verify physical user controls. Captures are separate read-only checks.

## Review a local static image

The authored P1 guest can display a local `GuestImage` JSON DTO with `--image`.
It retains authored simulation/contacts and is named **Static image review** in the
host. A cached retail image does not turn this fixture into a live game adapter.
The optional shell scale defaults to `.4`; `--opponent` selects an existing staged
character only for manual review, for example `kof13/kof13.def`.

```powershell
python tools/xrd-preview-image.py <clean-normalized-trace> --capture 6
python tools/play-passthrough.py --no-debug --image <trace>/static-review-image.json --image-scale .4 --opponent kof13/kof13.def
```

The exporter verifies native restoration/pixel hashes and settled canonical framing,
crops transparent borders, swaps BGRA to RGBA and translates the original pivot.
The image/receipt remain local ignored artifacts. Foot placement, relative size and
appearance require review in the host; behavioral, source-contact and persistent clock
acceptance are separate. Source producer capabilities remain disabled. Arrows move
the authored fixture and Z triggers its synthetic normal; the reference image is static.

## Bind a source adapter

Use `runtime = passthrough` in the character definition's `[Info]`. Beside the `.def`,
write `<filename>.def.passthrough.json`, for example:

```json
{
  "version": 1,
  "game": "example-game-build-1",
  "address": "127.0.0.1:41000",
  "timeout_ms": 250,
  "buttons": {"a": "punch", "b": "kick", "c": "slash", "x": "heavy", "y": "dust"}
}
```

The guest listens on this endpoint before IKEMEN loads the fighter. Addresses must be
numeric loopback IPv4 or IPv6; no remote game server is contacted. Game identity is an
adapter/build identity that must match every reply. Ten host buttons (`a,b,c,x,y,z,s,d,w,m`)
can map to arbitrary unique guest names. `forward,back,up,down,left,right` are reserved.
Relative and absolute directions are supplied together. Both player slots use the
same receiving code, with different mappings allowed per definition.

Use character-local units for self position and collision geometry; right is positive
X and up is negative Y. Images/boxes always face right: IKEMEN applies its authoritative
facing. Image pixels map one-to-one to local units before normal character/camera
scaling. The image pivot is the foot/origin in pixel coordinates. Source adapters own
all source-unit/axis/camera conversions. Shell CNS is only static metadata; native CNS
simulation and native animation clocks do not control the foreign fighter.

## Wire protocol v1

One synchronous request/reply at a time on a TCP connection, framed as a four-byte
**big-endian unsigned byte count**, then UTF-8 JSON. No newline framing. Replies are
capped at 8 MiB; configuration at 16 KiB; images at 1024x1024; each box list at 64.
The per-request deadline defaults to 250 ms (configurable 50..2000). This is a local
trusted adapter transport, not an authenticated network service. A malformed/stale
reply, disconnect or timeout aborts the match rather than continuing stale simulation.
CPU/base64 transport is intentionally the first implementation; GPU sharing can be
added after source correctness and throughput measurements justify it.

The authoritative Go DTOs are `GuestRequest`, `GuestResponse`, `GuestImage` and
`GuestOpponent` in `runtime/passthrough.go`. Common body/pose/combat DTOs are reused
from `runtime/runtime.go` and `runtime/combat.go`. Unknown fields/trailing JSON are
rejected. Wire envelope fields are lowercase as below; common DTO fields retain
their Go names (`Frame`, `X`, `AttackID`, `Hitstop`, etc.). Optional booleans/numbers
in a reply default to false/zero, never source-game-specific assumptions.

Every request contains `version,session,game,sequence,tick,operation,context,X,Y,Life`.
`session` is a fresh 128-bit nonce per connection; `sequence` starts at 1 and increases
for **every** operation. `tick` starts at 0, increments only on `step`, and resets to 0
on `reset` without resetting sequence. `Life` is canonical host health; `X,Y` are the
host's latest stage-bound/player-push position. `context` contains `Advance`,
`AcceptInput`, `Facing`. Host pause and native hitpause send no step or input; an
explicit host frame advance sends exactly one step. Private guest hitstop consumes
advancing guest ticks while suppressing guest action clocks. Input outside the live
round is neutralized. The source engine must stay frozen between requests.

| Operation | Guest requirement |
|---|---|
| `hello` | Establish session; return tick 0 and required capabilities `host-step`, `isolated-rgba`, `universal-contact`. |
| `reset` | Clear source fighter/input edges/contacts/KO; adopt host position/health and tick 0. |
| `step` | Apply named `input`, authoritative transform/health/facing and optional `opponent`; advance exactly once; publish that tick's state, image and boxes together. |
| `hit` | Apply `result` to the guest defender (reaction, guard, resources, stop); no simulation tick. Host already committed canonical damage. |
| `contact` | Notify the guest attacker once for the accepted activation; no simulation tick. Native defender result currently provides acceptance/guard, while foreign defender negotiation also provides the full result. |
| `defeat` | Mark the guest defeated; no simulation tick. Finish source stop/KO on following steps. |

The nearest opponent mirror contains `X,Y,Facing,Life,AttackID,Hitboxes,Hurtboxes`.
Positions are in this receiver's local coordinate units. Box coordinates are relative
to the opponent origin, scaled to the receiver's units, facing right; `Facing` supplies
the mirror direction. Native opponents currently have no foreign `AttackID`. It is a
small observation mirror, not native simulation or an entire stage/roster export.

Every successful reply contains:

```json
{
  "version": 1, "session": "echo-request-session", "game": "example-game-build-1",
  "sequence": 1, "tick": 0,
  "capabilities": ["host-step", "isolated-rgba", "universal-contact"],
  "state": {"Frame": 0, "X": 0, "Y": 0, "Action": 1, "RenderAction": 1},
  "pose": {"CanTurn": true},
  "defense": {"CanGuard": true},
  "attack": {}, "hitboxes": [], "hurtboxes": [[-15,-80,15,0]],
  "image": {"Width": 1, "Height": 1, "Pivot": [0,0], "RGBA": "/wAA/w=="}
}
```

`state.Frame` must equal the echoed tick. `image.RGBA` is base64-encoded, tightly packed,
top-down **straight-alpha RGBA**. Host upload converts RGB to IKEMEN's premultiplied
texture convention and preserves transparent/partial-alpha pixels. The isolated layer
must exclude source HUD/background/opponent. The receiver composites it through the
normal character renderer/camera, not a screen overlay. Action numbers are diagnostic
source identifiers; remote frames never depend on an AIR action existing.

The same reply owns presentation, pose, defense, one current normal `attack`, active
hitboxes and hurtboxes. `pose.Normal` requires `pose.Attacking` and a nonzero
`state.AttackID`. IDs must increase for each activation within a round; never reuse an
ID for a new attack. Keep active hitboxes only on that normal's active ticks. The host
uses its existing single-contact ledger and universal arbiter. The producer must
suppress source-native opponent contacts so that damage/reactions are committed once
through `hit`/`contact`. A game-specific adapter implements source parry/resource/guard
semantics through the common defense/result fields rather than host opponent-name logic.

## Current ceiling and acceptance

V1 supports isolated fighter RGBA, sampled ten-button input, nearest-opponent mirror,
one normal per activation, common foreign defense/result callbacks, native mixed
contacts, host health, KO and reset. It explicitly rejects source projectile IDs,
rollback/netplay/replay and guest state blobs/hashes/cloning. Debug save/load returns
without creating a shell-only snapshot. Other in-process runtimes keep their owned
snapshot behavior. Guest connections close at match end; a later reset can establish
a new session. Projectiles/audio/effects beyond the isolated layer, throws/custom
states, snapshot restore and full source fidelity need explicit future protocol work.

Core transport tests prove independent peers/mappings, pause gating, atomic reply
publication, frame identity, bounded data, timeout rejection and alpha conversion.
Native smoke proves the receiving boundary inside the real IKEMEN match lifecycle.
Neither substitutes for a real-game producer's source-frame oracles, interactive
keyboard pause/frame-advance acceptance, or physical user play.
