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

## 2026-10-06: SIGN native boundary and bounded stepping

Exact SIGN executable/session checks and local disassembly identify an engine-inner-object
update routine containing a counter increment. One caller ignores its return value. Two
return traces give 1,702 consecutive increments and exact Sol pose/collision matches.
Retail addresses, counter fields, function bytes and local profiles stay ignored.

A temporary Frida gate now suppresses ordinary source-thread calls and grants one original
call per request. The final idle test has three single increments and 227 unchanged blocked
observations; all 230 collision records match. Successful Direct3D presentations continue
at held counters. A no-credit timeout test proves automatic lease resume and native hook
removal before controller cleanup. Native and graphics code restore; source file hashes
remain unchanged. No source input or UI driving was performed. Input, movement/normal,
hitstop, isolated RGBA and universal contact/result integration remain open. All producer
capabilities stay unaccepted; this is a bounded development proof.
