# Producer guide

How to turn one installed fighting game into a producer for `uf-arena`. A producer runs the source game's own
fighter, steps it one tick at a time on the host's request, and publishes that fighter's state, boxes and
image. The host (`uf-arena`) owns the match.

- Wire protocol: `uf-arena/docs/WIRE.md` at the tag pinned in `pins.json`. `ufproducer` implements it for you.
- Match rules and producer obligations: `uf-arena/docs/PROTOCOL.md`.
- Check your producer at any point: `python conformance.py`.

Write what you learn in `NOTES.md` as you go, separating verified facts from guesses. Record the evidence for
each step: commands, logs, captures, kit reports.

## Ground rules

- **The exact build only.** Fingerprint the executable (SHA-256 in `pins.json`) and refuse anything else.
  Hook sites, offsets and data layouts are build-specific.
- **Offline modes only.** Refuse to attach outside an offline mode (Training is the usual one). Never touch
  online play. Find out what anti-cheat the game has before anything else.
- **Never commit the game.** No game files, extracted assets, captures, or decompiled/disassembled code.
  What the producer needs to find and hook the pinned build may be committed: short wildcarded signatures,
  field offsets and addresses. Record each one's source (your own analysis, or a named reference whose
  licence `NOTICE.md` honours). Keep byte runs longer than a signature needs, resolved per-run addresses,
  live pointers and profiles in the ignored `local-cache/` or `artifacts/`.
- **Reversible.** Every hook, patch and setting change is undone on exit and verified (compare restored bytes
  with disk). The game must keep running after the producer stops, including when it is killed.
- **Development tooling stays out.** Universal Modder, Frida, Ghidra, Cheat Engine and RenderDoc are
  investigation tools. Only what the producer needs at run time is a dependency.

## Route, in order

Each step needs live evidence before the next relies on it. Start with `python produce.py --fake`, which
passes the kit, then replace the fake piece by piece in `sign/producer.py`.

1. **Recon.** Engine and version, 32/64-bit, graphics API, anti-cheat, existing mods and tools, the
   community's references (frame data, hitbox overlays). Universal Modder's `game-recon` and
   `game-research-websearch` skills produce a plan. Record the build fingerprint in `pins.json`.
2. **Attach and restore.** Inject once, install nothing, restore, and confirm the game is unaffected (gate 1).
3. **Stepping.** Find the battle update (the per-tick simulation call). Gate it so that each request allows
   exactly one tick, while rendering keeps running. Prove that the engine's own tick counter advances by
   exactly 1 per request and holds still in between. This is the `host-step` capability; nothing else
   matters until it holds.
4. **Input.** Substitute the fighter's input where the source samples it, exactly once per allowed tick. Map
   the host's absolute directions (`left`, `right`, `up`, `down`) to the source's facing-relative input, and
   map button names (`punch`, `kick`, `slash`, `heavy`, `dust`) to source buttons. Neutralise any other
   fighter the source simulates (a training dummy).
5. **State and boxes.** Read position, facing, action, hitstop, stun and the active attack. Convert boxes to
   host units relative to the feet, facing right, up negative. Compare frame by frame with the community's
   overlay or frame data.
6. **Isolated image.** Render only this fighter: hide the HUD, background and opponent, and fix the camera.
   Start with a CPU readback (RGBA images), then move to a shared GPU layer
   (`ufproducer.d3d12.SharedLayer`, or your own D3D12 texture and fences). If the source cannot share its own
   texture (Direct3D 9, or any CPU readback), fill the layer with `ufproducer.d3d12.UploadLayer.upload()`
   (premultiplied B8G8R8A8, facing right; uf-protocol 1.3.0). The KOF XIII producer does this. Measure how many
   presents a pose takes to appear; never assume a fixed delay.
7. **Contacts.** Suppress the source's own hit detection against the opponent (`universal-contact`). The host
   decides contacts. Apply the host's `hit` and `contact` results through the source's own hit pipeline, so
   it plays its native reactions.
8. **Pacing.** A step must fit in one host frame (16.7 ms at 60 Hz). Measure with the kit's timing and
   `uf-arena/tools/latency.py`. Then cut the engine's frame cap and vsync while serving, and render on demand.
9. **Match rules.** Work through PROTOCOL.md's producer obligations: adopt the host transform, keep the source
   fighter clear of source-only walls, honour attacker frame counts, report native life (when negotiated).
10. **Extensions.** Negotiate what the source supports, one capability at a time (uf-arena `docs/WIRE.md`
   "Extensions"): `units` (scale so the round-start separation is 280 host units, reported as `scale`), `pushbox`
   (every reply, plus `Teleport`), `throws` (throw kind, tech and invulnerability queries, the bind while
   holding, generic held reactions when `transform.bound`), `world-time` (superflash and slowdown requests) and
   `camera-hints`. Test each with `uf-arena --dummy-throws --dummy-slow`.

## Lessons from earlier producers

These cost real time. Most come from the Guilty Gear Xrd REV 2 producer, some from the SIGN investigation.

**Injection and hooks**
- Inject once per game process and keep the hooks for the game's lifetime: leave them dormant
  (pass-through) and re-arm them. Repeated attach/detach and detaching listeners crashed the game in Frida
  teardown. A small long-lived host process that owns the injection, serving short-lived producer runs,
  works well.
- Resolve hook sites by patterns that must match exactly once, bounds-check derived sites, and compare
  loaded bytes with disk before patching.
- Hook function entries, never a relocatable `call` instruction mid-function: that corrupted arguments.
- A JavaScript callback could not return an x87 float from a thiscall (no effect live). A few bytes of native
  stub did.
- Create and release GPU resources only on the source's render thread.

**Stepping and timing**
- Gate the tick at a call site of the engine's world/battle update, and report the engine as paused for
  components that tick separately. Verify the counter delta on every request.
- The engine's own frame cap (UE3: `GetMaxTickRate`, clamped to 60) and vsync throttle lock-step serving.
  Raise the cap only while serving; keep the native rate for normal play.
- Render on demand: park the game thread on an event while no request is pending, and set it when one
  arrives. Otherwise each request waits out a loop busy redrawing a frozen frame.
- Prime one frame before writing the ready file: a cold first frame exceeded a 500 ms deadline.
- A minimized window renders nothing. A restored window behind others works.
- A shared-memory request channel between the producer process and the injected code saved the RPC hop.

**Image**
- How many presents a new pose takes to appear varies by action: SIGN needed up to 10, and no fixed delay
  held. Wait for two identical consecutive layers, or for evidence tied to the source frame.
- Camera depth and outline extrusion changed with camera distance. Fix the camera for the private render.
- Colour grading, bloom and anti-aliasing happen after the fighter is drawn; full fidelity means replaying
  them on the private layer.
- If you queue the release-fence wait on the game's own GPU queue (as Rev2 does), a host that misses a
  release stalls the game's rendering. A separate copy queue contains it. To recover a stall, open the
  release fence by name and signal it to the ready fence's completed value.

**Space and contacts**
- The source has walls the host cannot see. Rev2's fighter drifted into its right wall across sessions and
  stopped walking in open arena space. Recentre the source fighter inside its own stage while neutral, moving
  the anchor so the host sees no jump.
- Keep the source's auto-turn agreeing with the host's facing, for example by placing a hidden dummy on the
  host opponent's side.
- Injecting a host hit at the top of the source's hit pipeline was rejected by its attacker/defender checks.
  Injecting below hit-type determination (copy the attack into the defender, then deal the hit) produced
  native reactions and pushback.
- Sanitise source sentinel values: an attack's hitstop field held INT_MAX as a "default" and froze the
  fighter when copied.

**Robustness**
- Stop only between requests. On Ctrl+C or Ctrl+Break, restore the game, then exit.
- Give the injected code a lease that the producer renews: if the producer dies, the game restores itself.
- Treat every malformed request as a protocol error that closes the connection, never as a crash.
  `ufproducer` does this for you; the kit checks it.

## Finishing

- `python conformance.py` passes in the modes you support. Commit the JSON report summary to `NOTES.md`.
- Play it in `uf-arena` by hand: the kit cannot see whether the image shows what the state says, or whether
  the source really stays frozen between requests. Those need your own source oracles.
- Write a field note for the shared knowledge base (Universal Modder's `share-field-notes` skill), with the
  user's OK before publishing anything.
