# Passthrough v2: work items from the Rev2 producer

Status 2026-10-08: proposal and work tracking. The game-to-game protocol is still being
designed, so items here describe needs observed in practice, not a frozen wire format. Each
item separates **evidence** (measured with the Rev2 producer,
`jerezereh/xrd-rev2-producer`) from **proposal** (what the receiver should grow).

The v1 receiver (`docs/PASSTHROUGH.md`) stays the baseline. Every v2 piece must be negotiated,
so v1 guests keep working.

## Evidence summary (Rev2, D3D9On12, Intel Iris Xe, offline Training)

| Path | Per step | Notes |
|---|---|---|
| v1 CPU layer (readback + Python conversion + base64 JSON) | 120–250 ms | Dominated by CPU conversion. The agent side is ~15–25 ms with settle = 1 present. |
| Zero-copy GPU layer (shared D3D12 texture + fence) | **19–23 ms** | Includes the GL import and a CPU readback used only for verification. The GPU pass is 1.2 ms. |

- The rendered pose for tick N is on screen at the 1st present after the tick (101/101 steps).
- GPU vs CPU layer: alpha MAE 0.6, colour MAE 8.9 (0–255). The difference is 2x2 filtering
  before the coverage rule.
- Native hit reactions: replaying the receiver's hit through Rev2's own pipeline produces
  Rev2-rendered reactions (`CmnActNokezoriLowLv3`) with native pushback. The receiver needs
  to send more than v1's `HitResult` to choose reactions properly (item 3).

## 1. Shared GPU layer (image by reference)

**Evidence.** The producer renders the isolated layer into a named shared D3D12 texture
(B8G8R8A8, render-target plus simultaneous access, shared committed heap) and signals a named
shared D3D12 fence per frame. Colours are premultiplied over black, with logical channels.

**Proposal.**
- Capability `shared-layer:d3d12` offered by the guest. The receiver opts in per connection;
  otherwise RGBA v1 applies.
- The reply carries `layer` instead of (or alongside) `image`: `kind`, `memory` (name), `fence`
  (name), `value` (fence value for this frame, strictly increasing per session), `width`,
  `height`, `size` (allocation bytes), `pivot` (float pixels), `premultiplied: true`.
- Names are opaque, bounded, per-session strings. The receiver opens them once and reopens
  when they change (the guest may recreate resources).
- Ownership and lifetime: the guest owns the resources and must not overwrite frame N's texture
  until the receiver has consumed it. v1 lock-step guarantees this today (one request in
  flight). Pipelining needs a second texture or a receiver-to-guest release fence; open question.
- Validation: names match a safe character set and length, size/dimensions are bounded, the
  fence value is monotonic, and an RGBA image is still required when the capability is not
  negotiated.

## 2. Receiver importer (IKEMEN OpenGL 3.3)

**Evidence.** On this Intel driver, `GL_EXT_memory_object_win32` rejects D3D12 handle types
(INVALID_ENUM; OPAQUE_WIN32 gives OUT_OF_MEMORY). The working route is: D3D12 fence opened by
name with a CPU wait; texture opened by name in D3D11 (`OpenSharedResourceByName`);
`WGL_NV_DX_interop2`. Registering the opened shared texture is refused, so it is copied on the
D3D11 GPU timeline into a local registered texture each frame. That costs ~3–7 ms including a
verification readback, which IKEMEN does not need.

**Proposal.**
- A Windows-only importer in the receiver, using syscall COM/WGL calls with no new
  dependencies. It wraps the registered GL texture as IKEMEN's `Texture_GL33`
  (`{width, height, depth: 32, handle}`) and draws premultiplied directly (no
  `guestTexturePixels`).
- Try `GL_EXT_memory_object_win32` first on drivers that accept D3D12 resources, then fall back
  to the DX-interop route.
- Vulkan renderer: import with `VK_KHR_external_memory_win32` /
  `VK_KHR_external_semaphore_win32` (D3D12 resource/fence handle types). This machine reports
  support; untested.
- Explicit failure, never silent fallback, if a negotiated shared layer cannot be imported.

## 3. Hit and contact events with properties

**Evidence.** A source engine chooses its reaction (stand, crouch or air; hit or block level;
launch; wall bounce; knockdown) from its own attack model. v1 sends damage, stun, hitstop,
push and guard flags. The Rev2 producer had to map stun to Rev2 attack levels by guesswork,
and it places the hidden attacker on the opponent's side for knockback direction.

**Proposal.**
- `hit` / `contact` carry, besides the canonical result: attack height (high/low/mid/air),
  attack level or strength hint, counter-hit, knockdown/launch/wall-bounce flags, attacker
  position and facing at contact, hitstop for each side, and whether the hit was a projectile.
- The guest reports the reaction it actually applied in following steps (guarded or not, stun
  remaining, knockdown state), so the receiver can reconcile when source rules differ.
- One owner for stun and hitstop timing per contact (receiver or source), stated in the event,
  to avoid double countdowns. v1 already withholds steps during host hitpause.

## 4. Host-to-guest state

**Evidence.** The producer keeps Rev2's facing consistent by placing a hidden dummy where the
receiver's opponent mirror says it is. It writes host stage clamps and pushes back into Rev2.

**Proposal.**
- Keep `X, Y, Facing` and the opponent mirror. Add the opponent's air/ground state and current
  attack direction, the stage walls (left/right bounds in receiver units) and the corner state,
  so source-side wall interactions and pushback stay consistent.
- Pause/frame-advance semantics stay as v1 (no step during host pause).

## 5. Guest-to-host state

**Proposal.** Optional richer state: actionable flag, cancel windows, current move identity
(string) for debug overlays, and the guest's own pushback delta per step, so the receiver can
apply it instead of overwriting.

## 6. Timing and pipelining

**Evidence.** Lock-step costs about one source frame (one tick plus the present, ~12 ms
agent-side) plus the import. 60 fps needs ≤16.7 ms per step.

**Proposal.** Measure the receiver with the shared layer first. If needed, allow one frame of
pipelining (image for tick N-1 delivered with state for tick N) as an explicit, negotiated mode.

## 7. Lifecycle and robustness (producer-side lessons, for guest implementers)

- Inject once per source-game process and keep hooks for the game's lifetime. Repeated
  attach/detach and listener detaching crashed the source game in Frida teardown.
- Create and release source GPU resources on the source render thread only.
- Never hook a relocatable `call` instruction mid-function (it corrupted arguments).

## Receiver work order (this branch)

1. [x] This work-item list.
2. [x] Protocol: negotiate `shared-layer:d3d12`, add and validate `layer`, keep v1 RGBA intact
   (`runtime/passthrough.go`, tests). Config `shared_layer: true` makes the receiver offer
   `accept: ["shared-layer:d3d12"]` at hello. A guest without the capability fails the connection.
   A layer-only reply may omit `image`. Fence values must increase per memory/fence pair. Until
   item 4 lands, the IKEMEN glue panics explicitly if a layer is negotiated.
3. [x] Windows importer: D3D12 fence + D3D11 open + WGL DX interop, standalone with a self-test
   (`runtime/passthrough_layer_windows.go`; non-Windows stub `passthrough_layer_other.go`).
   `openSharedLayer` imports by name into the current GL context. `Update(value, timeout)` releases
   GL ownership, waits for the fence (bounded), refreshes the local copy where the driver refuses
   to register the shared texture, and locks the texture for GL until the next update.
   `TestSharedLayerImportRoundTrip` emulates the producer's resources and passes on Intel Iris Xe.
4. [x] Host glue: `syncPassthroughLayer` imports and updates the layer on IKEMEN's main thread and
   draws it as a `Texture_GL33` that the import owns (no finalizer, premultiplied, NEAREST/CLAMP set
   through IKEMEN's binding cache). Imports are keyed by runtime and touched only on the GL thread.
   `Close` releases them there through `passthroughLayerRelease`. Non-OpenGL 3.3 renderers fail
   explicitly. `play-passthrough.py --shared-layer` runs the demo guests on shared D3D12 layers
   (`tools/shared_layer_demo.py`). Smoke passes, and the window capture is pixel-identical to the RGBA
   path at sampled points.
6. [x] Shared-layer throughput, profiled with `UF_LAYER_PROFILE=1` (per-runtime 60-frame windows in the
   trace). Debug two-guest scene, steady state: both paths run at **60 FPS**. Per frame the shared path
   costs the main thread ~2.1–2.5 ms (DX-interop lock ~1.8 ms, D3D11 copy ~0.2 ms, fence wait ~0–0.7 ms);
   the RGBA path costs ~8.4–9.2 ms (CPU conversion + upload). Guest round trips are equal (~2.5–3 ms).
   The earlier 16.6 FPS reading was not reproduced; IKEMEN's on-screen counter likely reflected a
   single slow frame. The first frame's import creation takes ~130–160 ms. A window capture does not
   affect the rate. Possible follow-ups, none required: create the import before the first drawn
   frame, and batch the interop lock for all guests.
5. [ ] Hit/contact event properties (item 3) once the protocol design settles.
