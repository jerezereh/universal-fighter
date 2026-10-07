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

## SIGN input ingress and non-idle source updates

Rev2 input signatures do not match SIGN. The actual update owner's sampler/history
writer instead derives the local ring layout and input callsite. Observation checks
previous/current/latest input and held duration. The gated callsite substitutes the
named packet's sampled register only during its owned update; original instructions
write history and record that value. Relocated caller addresses use a same-thread
ingress/writer association rather than the original return address. No OS keyboard input.

Two 129-step tests prove walking both directions, jump/landing and two standing Punches,
with per-step history agreement and eight executed active-normal updates. All 697 Sol
pose/box observations match source collision. Observed state remains frozen between
requests, graphics work continues, and timeout recovery removes input/update hooks.
Source-window video confirms movement/jump. Only private local profiles contain native
addresses/layouts. Crossover, hitstop, isolated RGBA and universal contacts remain gates.
