# KOF XIII local foreign slice

The user selected their installed KOF XIII on 2026-10-05 for package 3, replacing
the handoff's synthetic-first order. This changes the first adapter target; it does
not waive the runtime, mixed-combat or determinism gates.

- Steam app 222940, installed manifest build 151721, native 32-bit executable.
- Install: `C:\Program Files (x86)\Steam\steamapps\common\King of Fighters XIII`.
- Universal Modder's read-only scan found native code and no recognized engine,
  loader or anti-cheat files. This is file-inspection evidence, not a guarantee
  about online behavior. No process attachment, game patch or online operation.
- Route: read the local character resource files and implement a bounded foreign
  runtime in IKEMEN. The original installation and saves remain untouched.
- Current supported character: Kyo, resource `03`. The melee importer rejects other
  characters until their action/rectangle mappings are validated.

## Verified resource path

`fighter/03.lua` is XOR-encoded Lua 5.1 bytecode with little-endian 32-bit lengths
and float32 numbers. A table-construction reader preserves functions and calls
as symbolic references. It does not execute Lua. Selected locomotion frame
functions use straight-line method calls; unsupported instructions fail export.

`fighter/03.pcs` has TEXLIST, chunked zlib TEXTURE records, IMGLIST and PRIMTIVE
records. DBLPLT sprites use a 256-wide tile lookup texture and 16-pixel content
tiles. Image primitives carry a lookup block ID and a base content tile offset.
The installed `chip_clut.pso` and `chip_divide.vso` were disassembled read-only
with Windows D3DDisassemble to resolve the lookup indirection. Those dumps stay
in ignored local-cache. Sprite layers use palette rows from `palette/0003_00.png`.

The importer exports 22 actions and 290 frames, including idle, walk, crouch,
jump startup/air, landing, close standing A, reaction presentation and the weak
ground-flame casting/core/removal animations (475/534/538).
The source SetImage X scale -1 is baked into pixels and sprite origins at export,
so host facing +1 draws toward the right while motion and collision facing stay intact.
Reconstructed Kyo's idle image was visually inspected in the locomotion step.
SFF/AIR are presentation assets only; exported constants contain no CNS states.
Velocity selectors reference the source `moves` table, rather than literal speeds.
The slice uses a documented 0.4 coordinate conversion into the host arena.

## Run

Use Python with Pillow (the Codex bundled runtime already supplies it):

```powershell
python tools/kof13-import.py --game 'C:\Program Files (x86)\Steam\steamapps\common\King of Fighters XIII'
python tools/test-kof13-import.py
```

Build and exercise the runtime after importing:

```powershell
$env:MSYSTEM = 'MINGW64'
$env:CHERE_INVOKING = '1'
& ./local-cache/msys64/usr/bin/bash.exe --login /c/Users/Novo-/source/repos/universal-fighter/tools/build-runtime.sh /c/Users/Novo-/source/repos/universal-fighter
./tools/smoke-host.ps1
./tools/smoke-foreign.ps1
./tools/smoke-melee.ps1
./tools/smoke-projectile.ps1
./tools/play-foreign.ps1
```

The Bash build script runs the focused Go checks, applies the versioned host patch,
copies the project runtime into the pinned checkout, then rebuilds/stages IKEMEN.
Applying it twice is safe; a changed upstream source rejects the patch. The staged
executable now includes the foreign seam. Native characters still use the native
backend. The interactive command gives player 1 Kyo against an AI KFM. Host button `a`
presses the close standing A normal; hold back to guard, down-back for low guard.
The current saved Player 1 keyboard mapping is arrow keys for movement/jump/crouch
and `Z` for host button `a`, `X` for host button `b`. `Z` attacks while standing on
the ground; crouching/air attacks are not implemented. Up-left/up-right jump
diagonally. Holding away from
the opponent guards high; down plus away guards low. `X` casts the weak ground
flame while standing. This single-button trigger is a prototype control; original
command recognition is not implemented. Other mapped attack buttons
(`C`, `A`, `S`, `D`) currently have no Kyo action. Keyboard mappings can be
changed in the host's input options; the local saved configuration is not versioned.
Other normals, air guard and source cancels are not implemented. Reimport older
data: the projectile binding requires schema 3 and `runtime=kof13`.

Output is restricted to ignored `artifacts/`. Source hashes are stored in the
local foreign manifest. Neither game files, extracted images nor derived frame
data are committed. Export is not evidence of host simulation or combat fidelity.

## Runtime limits

`runtime/kof13.go` owns action/frame clocks, velocity selection, jump integration
and mutable state. `runtime/host.go` bridges the host's already sampled input,
presentation, stage bounds and size-based player pushing. The host scheduler uses
the same backend boundary for native and foreign players; foreign players bypass
CNS preparation/execution/finish/update/tick paths. The manifest opt-in is explicit
in the generated DEF. Mutable runtime state is copied separately in host snapshots.

The source move constructor's constant/approach velocity formulas are used for
the selected locomotion subset. The input-to-action transitions are adapter code;
the source game's complete transition system is not emulated. Source audio/effect
calls and option flags are retained as data but currently unexecuted. Body pushing
uses the host's size convention. Source SetRect parameter selectors are resolved
through `fighter/collision_table.lua`: common rules followed by character rules.
Ordinary body/head/crouch/air vulnerability becomes Clsn2 and the selected close
standing A attack becomes Clsn1. Rectangles
use center/half extents, positive source Y up, negative host Y up, facing and .4 scale.

Action 68 supplies 4 startup, 4 active and 15 recovery frames. Its common rectangle
rule supplies 25 damage and 7 hitstop frames. The native defender uses the existing
IKEMEN HitDef query/commit path; this is an adapter envelope, not foreign CNS execution.
Native attacks against Kyo translate into `AttackSpec`, a foreign defense query and
one `HitResult`; host life receives damage and the foreign runtime owns reaction clocks.
Native hit flags, team/depth filtering and current-HitDef target bookkeeping remain in
the collision path. Foreign normals reset that ledger once per activation and use hitonce.

Reaction motion/timing is a compatibility policy: 15-frame ground hitstun, 14-frame
blockstun and fixed push for Kyo's normal against native fighters; native incoming
envelopes supply their own damage, stop/stun, velocity, gravity and fall flags.
Foreign friction is .85 per tick, with a 20-tick minimum down recovery. Original
hitback/cancel/juggle/priority behavior is not fully emulated. Reaction Lua behavior
is not executed; only its images/rectangles are imported. A guard-only image
modifier (-3) is preserved in metadata but not mapped
to the host renderer; guard presentation needs visual comparison. Throws, reversals,
custom-state transfers and down hits are excluded. Special startup counter-vulnerability
boxes are imported as ordinary hurtboxes; their original damage multiplier is not applied.

The weak ground flame spawns once at casting action 475's frame offset 15. Its
source object core uses action 534, selector 116 (character rule 36 after 81 common
rules), 60 damage, 11 hitstop and velocity selector 321 (source speed 14; host 5.6).
Spawn offset is source 110 / host 44. The runtime owns its input edge, spawn timing
and activation counter; the host owns the resulting projectile's transform, collision,
hit/guard consumption, removal animation (538), bounds and snapshot. Its 96-tick
maximum active lifetime is a compatibility bound derived from the core timeline;
original object Lua transitions, secondary effects, resources and cancels are not run.
MAPPLT effects use Pillow's BC1 decoder and full-color tile reconstruction. Black-keyed
glow alpha approximates their presentation; source shader/blend fidelity is unverified.

Incoming native projectiles use the same foreign defense/result protocol, with the
projectile's facing, local scale and captured attack multiplier. The original host
commits projectile hitpause and consumes its hits. Projectile platforms, reflection
and full original juggling are outside the adapter subset. Foreign projectiles are
retired on owner defeat or round exit; ordinary host round reset clears all projectile
assets and resets the foreign runtime and activation counters. Defeat drains hitstop,
settles launch motion and holds the imported down pose instead of recovering to idle.

The melee smoke uses an authored native fixture whose states/rectangles are versioned
under `tools/fixtures/melee-native`; staging reuses the baseline's local KFM presentation.
No game art is included in the fixtures. Native inputs are unnecessary: it approaches
and executes one normal with declared high, low or launch behavior. Eight scenarios
exercise both contact directions, high/low blocking, incorrect guard height, knockdown
and lethal hitstop/host KO. Each checks trace contacts and completed-match life results;
foreign activation/defender keys must not repeat. A blocked fixture attack must not
produce an unguarded hit or life loss. Separate KFM/native regression tests retain
coverage of the original native fighter. These controlled boxes prove the bridge;
they do not prove fidelity for every original KFM/KOF interaction.

`smoke-projectile.ps1` adds eight authored scenarios for hit/block contacts in both
directions, high/low foreign guards, invulnerable misses/removal and two-round KO/reset
in both directions. It requires one contact per foreign entity, matching spawn/removal
counts and completed-match damage outcomes. Round checks require empty host projectile
lists at foreign reset, a fresh foreign activation counter and renewed contacts after
the KO at restored health. A targeted run can use
`-Scenario native-hit`; without that parameter the full matrix runs. These checks do
not establish full host snapshot/replay or source effect fidelity.

Foreign input probes (`melee`, `projectile`, `receive`, `guard-high`, `guard-low`) are explicit,
off by default, and disabled for human and network play. `smoke-foreign.ps1` continues
to exercise the ordinary sampled AI-input path. The explicit offline GGPO sync-test
session also permits scripted probes; real network and recorded replay sessions do not.

`./tools/smoke-determinism.ps1` runs five authored scenes through the host's strict
offline GGPO sync test with an eight-frame rewind window: melee, foreign projectile,
native projectile, host Pause, and KO/reset. It requires native GGPO checksum matches
and phase coverage in both forward and replay saves. `-Scenario foreign-projectile`
selects one scene. Each run uses a separate config, trace and statistics file; it
does not enable DesyncTest in the saved play config. Failed sync runs retain the
host's state journal for diagnosis. This proves bounded offline replay, not online
netplay, original-engine fidelity or exhaustive collision order.

`./tools/play-foreign.ps1 -Debug` enables the existing host collision overlay plus a
foreign action/element/frame/stop/stun/activation line. The renderer smoke and human
inspection of boxes, labels, facing and keyboard controls are separate checks.

For a repeatable hands-on check, run `./tools/play-foreign.ps1 -Debug -Practice`.
This uses human P1 input, a stationary native opponent and no round timer. It writes
a unique `practice-*.stderr.txt` input/action trace in the ignored host runtime. In
debug practice, `[foreign-key]` records SDL press/release events and the host logical
tick, pause and step flags; it does not poll a second keyboard source. Ordinary play
keeps this key trace off. The state label appears in two lines above Kyo's standing box.

P1 uses arrows, Z (normal) and X (standing ground flame). The pinned debug hotkeys are
Pause (freeze/resume), Scroll Lock (single paused frame), Ctrl+C (collision boxes),
Ctrl+D (debug panel) and F8 (clear console). Keep injected-key results separate from
physical-keyboard results: a helper can report a successful tap without SDL receiving
the corresponding event. Universal Modder's WinDrive has now delivered real SDL key
events for arrows, Z, X, Pause and Scroll Lock, with matching action/contact traces.

Run `python tools/smoke-controls.py` for a repeatable interactive check. It focuses
the game and sends keys, so run it when the desktop is available and close other
IKEMEN instances first. It uses the pinned WinDrive script, separate temporary config
and logs, P1 AI level zero and no foreign scripted input probe. The first scene checks
walking, crouch/release, jumps, both attacks, crossover facing, Pause and three exact
single-frame advances. The second drives a normal plus ground flame against a native
fixture with 85 starting life and requires a completed KO match with P1 alive/P2 dead.
Native F12 capture saves startup/crossover/KO PNGs under ignored `controls-*` folders;
the images require visual inspection in addition to the script assertions. The helper
is hidden, the game window is visible, and cleanup stops only the processes it launched.
No FFmpeg or additional desktop dependency is installed. These are automated keyboard
and renderer results; physical user play/feel and other display sizes are not measured.

Core checks cover walking, crouch/release, jump/landing, held-up edge behavior,
pause, one-frame advance, reset and deterministic restore/replay with the local
manifest. Combat checks cover high/low defense, chip, stop/stun clocks, knockback,
launch/down/recovery, contact-state restore and reset. Renderer smoke evidence,
exhaustive host interaction coverage and human/visual acceptance are separate gates.

## References

- [Lua 5.1 opcode definitions](https://www.lua.org/source/5.1/lopcodes.h.html)
- [Game Extractor PCS archive reader](https://github.com/wattostudios/GameExtractor/blob/master/src/org/watto/ge/plugin/archive/Plugin_PCS_TEXLIST.java)
- [KOF XIII Lua resource research and character codes](https://github.com/ExMingYan/KOFXIII-LuaHack)

The Java archive reader provided section/chunk format corroboration; the local
tile reconstruction and restricted bytecode reader are implemented here.
