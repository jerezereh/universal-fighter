# Xrd SIGN adapter reconnaissance

Status 2026-10-06: installed edition and offline extraction route verified. A playable
Xrd guest has not been implemented. The authored air-dash ruleset is separate.
The next recommended investigation is native passthrough feasibility; retain the bounded
import/bake as a fallback and oracle. See `WORK_PLAN.md` for the acceptance gates.

## Verified local target

- Steam **GUILTY GEAR Xrd -SIGN-**, app **376300**, installed build **1028441**;
  manifest reports fully installed. This is not Revelator/Rev2.
- Install: `C:\Program Files (x86)\Steam\steamapps\common\GUILTY GEAR Xrd -SIGN-`.
- `Binaries/Win32/GuiltyGearXrd.exe`: native x86 PE, 21,404,096 bytes, SHA-256
  `f7a2e990b664f882bf16eafa94433ff0460f0b630c083fd0760a0d7949e08b78`.
- 3,031 UPK packages in `REDGame/CookedPCConsole`. Copied Sol/common packages decode
  to Unreal Engine 3 package version **868**, licensee **2**, engine build **10246**.
  UE Viewer independently lists their name/import/export tables.
- Config: `REDGame/Config`; local saves: `SAVE`; launcher: `BootGGXrd.bat` invokes
  `Binaries/Win32/BootGGXrd.exe`. No installation/config/save edits or game launch here.
- The pinned Universal Modder scan indexed 3,333 files, reported no anti-cheat/loader
  positives, but failed to identify UE3 and returned no executable records. Manual PE
  and package inspection supersede that engine result; it is not an anti-cheat audit.

## Compatible tools and edition limits

[gdkchan's decoder](https://github.com/gdkchan/GGXrdRevelatorDec) explicitly supports
`-sign`. Pin `e71c5f912b8b5499dd51a18547619e6057598186`. Build its inspected C# sources
with the installed .NET Framework compiler, and invoke it on copied packages only.

[UE Viewer](https://github.com/gildor2/UEViewer) pin
`a0bfb468d42be831b126632fd8a0ae6b3614f981` includes the working build-1590 `umodel.exe`.
Its website download link returned HTTP 404; the official repository binary works.
Use `-game=guilty` for this game-specific mesh layout. Its bundled safe LZO decoder is
compiled as an ignored development-only DLL. Neither tool becomes a host dependency.

Current [Rev2 hooks](https://github.com/super-continent/ggxrd-mod) and
[Rev2 hitbox/freecam tools](https://github.com/kkots/ggxrd_hitbox_overlay_2211) document
Revelator/Rev2 support. No hook was installed or treated as SIGN-compatible.
The current [BBScript](https://github.com/super-continent/bbscript) `ggrev2.ron` and
[bbtools](https://github.com/dantarion/bbtools) Rev databases misread the local SIGN
instruction lengths after seven instructions. This is demonstrated incompatibility,
not a parsed SIGN moveset. The installed executable supplied a distinct, uniquely
identified **ushort instruction-size table**. Checked independent framing entries and
consumed all 16,030 instructions across four Sol/common scripts, with every state
directory offset landing on the matching instruction boundary. Unknown command
parameters remain opaque: native lengths do not establish their semantics, defaults
or control flow. The original JON/FPAC format notes
helped inspection, but the actual SIGN directory layout differs and was checked locally.

## Bounded source slice and extracted evidence

Choose **Sol**, with idle/walk/crouch/jump and one standing normal as the first candidate.
The local state directory names that normal `NmlAtk5A`. Mapping it to a button, complete
timing/attack semantics and engine defaults still need verification; do not substitute
Rev2 frame data or the synthetic resource rules.

The raw-data reader resolves exports and inline BulkData from decoded 868/2 packages.
Sol contains `BBS_SOL` (210,368 bytes, 197 validated state-directory entries), `BBS_SOLEF`
(41,488 bytes, 102 entries), and `COL_SOL` (402,668 bytes). Common data contains one
character state, 236 effect states and 52 collision records. All directory offsets
point to the matching `beginState` instruction/name; this proves directory structure,
not complete instruction semantics. Native framing now covers 8,323 Sol, 1,622 Sol
effect, 3 common and 6,082 common-effect instructions. `xrd_script.py` discovers the
table from the fingerprinted executable rather than embedding a retail address.

Sol's collision FPAC contains 1,165 JONB records, 116 with attack rectangles. All records
parse with bounds/finite-value checks; trailing point records and unknown metadata are
retained without inventing their meaning. In the `sol200_00`–`sol200_05` frame family,
only `sol200_02` has an attack rectangle. The actual `NmlAtk5A` sprite literals reference
these six records in order with durations **1, 2, 4, 2, 2, 2**. This links the move
directory, native-framed script and collision records. Branch/engine timing, coordinate/facing
mapping and active duration need source-runtime oracles before host combat use.

UE Viewer exported 15 meshes, six PSA animation sets and default-color textures from
the copied Sol packages. The normal body glTF has one mesh/skin and 219 skeleton joints;
its PSA has 114 sequences. Head/weapon animation sets are separate. Exports are
structurally readable; original toon materials, complete head/body/weapon animation
alignment and visual fidelity are not accepted. Unknown material properties were
reported during export, so successful export alone is not a presentation result.

## Extraction fallback and acceptance gates

Keep the IKEMEN runtime seam and 2D arena. Fallback presentation route: bake the user's
extracted 3D mesh/animation into sprite frames, retaining original collision data and
separately simulated SIGN rules. Validate one textured pose and one complete normal
animation before baking broadly. This avoids a speculative 3D host rewrite.

1. **Verified:** reproducible, fingerprinted offline import of the bounded package set;
   original source hashes unchanged; reader checks and independent export-table comparison.
2. **Framing verified, semantics pending:** establish edition-correct command semantics, normal timeline/defaults,
   movement values, animation mapping and collision coordinate/facing transform.
3. Bake and visually verify the selected original poses; import only ignored output.
4. Bind a distinct owned SIGN runtime; unknown required behavior fails explicitly.
5. Core, native/foreign contacts, pause/step, round reset, strict replay and actual SDL
   renderer/keyboard acceptance, followed by Kyo/synthetic/native regression.

Work only on copies under ignored `extracted/xrd-sign`; preserve source install/saves.
Publish tooling and original adapter code, never extracted/decompiled game data. Source
capture, if needed, stays in local offline training; no online hooks or services.

```powershell
./tools/gather-xrd-tools.ps1
python tools/test-xrd-package.py
python tools/xrd-sign-import.py --graphics
```

The importer supports the exact fingerprint recorded above and fails on other builds.
It creates a fresh ignored output folder, validates all export fields against UE Viewer,
records tool/source/decoded/virtual hashes and confirms the original executable/packages
remain unchanged. Data-only imports omit `--graphics`. Malformed headers, cursor ranges,
state targets, FPAC/JON records, native-table ambiguity and invalid instruction sizes are
covered by runnable checks. Its receipt explicitly keeps behavior/visual acceptance false.

The semantic/renderer/runtime gates remain open. This document records an extraction
and instruction-framing proof; it does not mark the second real-game implementation complete.

## Diagnostic animation bake (2026-10-06)

`xrd_animation.py` reads pinned UE Viewer's PSA chunks with bounded frame partitions,
sample transforms and matching UE3 property tags. `xrd-sign-poses.py` checks the decoded
animation-package fingerprint, resolves each normal body/head/weapon AnimSet's `sol200`
sequence, checks its frame count against PSA, and links source scale metadata through the
corresponding animation tree's scale controllers. Every mesh joint must resolve to one
PSA track by name, with matching roots. Body/head have 219/201 joints; the normal weapon
has 37 joints drawn from a 48-track set also serving its high variant. Positional pairing
would silently use the wrong weapon tracks and is rejected.

All three sequences have 31 exported samples. Serialized sequence lengths are about
0.516667 seconds for body/head and 0.5 for weapon; PSA rates are 60/60/62. Their scale
metadata contains 23/2/2 controllers. Two weapon targets have near-zero initial scales:
one belongs to the excluded high mesh, the other hides the normal mesh's alternate
`obake` branch. PSA's empty SCALEKEYS chunk alone misses this behavior. The tooling
retains the source scale keys and validates available targets against tree/bone links.

The Blender preview uses explicit PSA indices 0,5,10,15,20,25, all distinct in each part.
It undoes PSA mirroring and applies the pinned glTF axis/unit/root conversion, preserving
the original inverse bind matrices. Diagnostic local scales hold the preceding source
key; this does **not** establish the native controller's interpolation, spaces or child
behavior. Only base material primitives render with original base-color textures using
the first UV set. Retail outline/shadow/decal passes and facial blending remain open.
The first inspected render exposed the oversized alternate weapon; the scale-key preview
removes it. The face/colors remain incomplete, so these PNGs are not accepted host sprites.

```powershell
python tools/test-xrd-animation.py
python tools/xrd-sign-poses.py <import-folder> --frames 0,5,10,15,20,25 --blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
```

Use the actual graphics-import folder printed by the importer. Outputs get a fresh ignored
`pose-previews` directory; the receipt records inputs, explicit samples, source clocks,
scale keys, image hashes/dimensions and Blender fingerprint. It separately flags rendered
output, pending sprite mapping, incomplete native scale behavior and unaccepted shaders.
No animation sequence clock is promoted to the fighter simulation clock.

## Source reference and corrected palette

After caching the missing signed x86 DirectX libraries, the **official BootGGXrd** launch
creates the original SIGN window. Direct executable launch had returned 0xC0000409;
that result does not describe the working bootstrap route. The source game displayed
normal first-run replay-data creation. Executable/package fingerprints remain unchanged;
normal player-data effects are not claimed immutable. `play-xrd-source.ps1` captures the
working launch/environment route and rejects a duplicate live instance.

The user reached Sol versus Ky in offline training and took over UI/input control.
Read-only native-window captures show standard Sol with brown hair and cream trousers,
right-facing idle, left-facing idle and repeated Punch input labels after the user identified
J as Punch. The first action capture contained other attacks/dummy-recording mode. A second
capture started minimized (620x96) and is unusable. A delayed full-size capture is usable;
its nominal video timestamps are not verified guest simulation ticks or frame data.

The prior assumed standard palette `SOL_MAT_0100_SF` was wrong for that reference.
Copied/exported `SOL_MAT_0101_SF` gives matching brown hair and cream trousers in the bake.
The importer now defaults to palette 1, allows explicit package indices 0..19, records
the choice and independently verifies the selected export table (224 exports for 0101).
The baker uses the receipt's single material package and verifies its decoded fingerprint;
older 0100 receipts remain usable. No UV-flip/swizzle workaround was adopted: those
diagnostics distorted other atlas details. Facial blending, toon passes, source pose clock
and collision/facing transforms still require verification.

An independent standard glTF skinning calculation now checks Blender's evaluated world
vertices in both directions before each render. All six selected samples across three
parts pass: 242,058 evaluated vertices, maximum error about 1.12e-6 meters against a
2e-4-meter tolerance. This verifies transport of the specified exported poses, not native
SIGN controller semantics. An authored translated triangle passes and deliberately wrong
object transforms/geometry are rejected. The receipt includes the check results.

Primary evidence for possible hook capabilities exists in the
[Rev2 overlay source](https://github.com/kkots/ggxrd_hitbox_overlay_2211): frame stepping,
opponent hiding and transparent screenshots. Those features are not verified for SIGN,
and screenshots alone do not implement synchronized fighter passthrough.

## Native producer investigation

The generic IKEMEN receiver now exists; SIGN's source producer is still pending.
`xrd-sign-probe.py` supplies a bounded read-only disk/loaded-module discovery route,
with the legacy and Rev2 overlay references pinned as development-only upstreams.
The fifteen legacy discovery signatures have no on-disk code candidates. Live normal
startup exposes eleven unique and four ambiguous candidate groups. Native load/getter
instructions and caller relationships now establish bounded engine/position access;
the original offline scene supplies a standing-Punch state/pose/collision oracle.
A temporary return observer and bounded native gate now verify an idle update boundary,
exactly three requested calls, frozen observed state between requests, graphics work
while held, automatic timeout recovery and native/graphics code restoration. Candidates
are derived and validated locally, not installed from unverified reference offsets.
Native input routing now passes two 129-step source oracles: backward/forward walk,
jump/landing, two standing Punch activations and exactly matching per-player input
histories/collision. The source-window oracle confirms visible movement/jump. Input
hooks also pass bounded timeout recovery. Crossover now proves both inward facings and
relative controls after landing. A native contact checker proves mirrored box overlap,
one health loss, stop/animation-age stability between requested updates and recovery.
The host already owns hitpause gating; external-result integration must avoid duplicating
that stop in the source countdown. There is still no accepted atomic source-frame/
image contract, isolated render layer or connected SIGN guest. See
[XRD_SIGN_NATIVE_PROBE.md](XRD_SIGN_NATIVE_PROBE.md) for tool tests, actual source evidence
and the next native gates.
