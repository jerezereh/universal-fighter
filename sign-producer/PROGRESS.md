# SIGN producer progress

## 2026-10-11 — template and receiver pivot

- Scaffold copied from the local `uf-producer-template`; pin upgraded from v1.3 to
  `uf-arena` protocol v1.5, matching the active KOF XIII producer. The installed SIGN
  executable's size and SHA-256 were checked locally. Source attachment fails closed.
- Earlier `universal-fighter` native probes verified exact bounded stepping, input,
  source state, contact suppression, isolated RGBA, reset and partial result injection
  in offline SIGN Training. Their short-lived, diagnostic scripts are not a persistent
  producer. The current per-frame image path peaks above a playable frame budget.
- Pending: long-lived reversible SIGN bridge, on-demand D3D9On12/shared-layer capture,
  unrestricted source input and close-range opponent mirror, native result coverage,
  `ufconform` on the real source, and a playable `uf-arena` match.

## 2026-10-11 — exact-process preflight

- Added a read-only PID check using PROCESS_QUERY_LIMITED_INFORMATION. It verifies
  the live process image against the pinned SIGN path, file size and SHA-256; a
  same-name Rev2 process is rejected. It installs no hooks and deliberately does
  not infer offline Training from the process path.
- Live PID 25640 passes exact SIGN preflight; six unit tests and Python compilation
  pass. Offline scene verification and persistent producer attachment remain open.

## 2026-10-12 — read-only native fighter pair

- Added a dependency-free `--fighters` preflight for the pinned SIGN process. It reads
  the native engine's two fighter slots and accepts only live Sol/Ky pose names with
  bounded positions and facing. It verifies slot stability across the read.
- PID 32716 passed exact-image and Sol/Ky checks in the user's current scene:
  Sol at raw X -252000, facing right; Ky at 252000, facing left. A separate two-second
  source observation sampled 197 records and independently found the same pair.
- This proves the fighter pair, not offline Training mode or a controlled game tick.
  No hook was installed. Persistent stepping, images, combat and the producer wire
  remain open; `SignProducer` still advertises no capabilities.

## 2026-10-12 — fresh source update and lease witnesses

- In the same live PID 32716 session, an initial Frida attach timed out before hooks;
  its receipt reports no samples and restored code. One bounded retry observed 301
  consecutive source updates with zero counter gaps/errors and verified code restoration.
- A separate bounded gate executed exactly three credited native updates, blocked 268
  others, held both fighters' observed state stable, and kept rendering active. A
  renewed 28-second hold blocked 1,264 updates and then verified lease recovery and
  automatic hook removal. Both runs restored source code and detached cleanly.
- These are current-session diagnostic proofs. They do not make the short-lived
  script a persistent producer, meet frame latency, or validate the wire lifecycle.
