# Local adapter journal

## 2026-10-05: KOF XIII import

Read-only Steam discovery and Universal Modder scan identified app 222940/build
151721. No original game files changed. Verified Lua 5.1 resource encoding and
PCS zlib section structure. Read installed shader instructions to resolve tile
lookup addressing. Exported Kyo locomotion data and reconstructed sprites into
ignored artifacts; inspected the idle preview. Host integration is next.

## KOF locomotion backend

Bound the local manifest to a separate Go runtime. Added native/foreign scheduling,
sampled host input, source movement selectors, owned frame clocks, snapshot copying,
render projection and host size pushing. Core movement/restore tests and a mixed
renderer smoke passed. All 13 imported actions appeared in the initial AI-input trace.
Native KO/round regression passed. No game installation files changed; no game
resources are tracked. Combat, pixel-level and human acceptance remain open.
