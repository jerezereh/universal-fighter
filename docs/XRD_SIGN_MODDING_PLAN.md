# Xrd SIGN adapter reconnaissance

Status 2026-10-06: installed edition and offline extraction route verified. A playable
Xrd guest has not been implemented. The authored air-dash ruleset is separate.

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
not a parsed SIGN moveset. Retain unknown commands and find a SIGN-specific command
length/semantic oracle before executing scripts. The original JON/FPAC format notes
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
not complete instruction decoding.

Sol's collision FPAC contains 1,165 JONB records, 116 with attack rectangles. All records
parse with bounds/finite-value checks; trailing point records and unknown metadata are
retained without inventing their meaning. In the `sol200_00`–`sol200_05` frame family,
only `sol200_02` has an attack rectangle. Frame-family association, coordinate/facing
mapping and active duration need source-runtime oracles before host combat use.

UE Viewer exported 15 meshes, six PSA animation sets and default-color textures from
the copied Sol packages. The normal body glTF has one mesh/skin and 219 skeleton joints;
its PSA has 114 sequences. Head/weapon animation sets are separate. Exports are
structurally readable; original toon materials, complete head/body/weapon animation
alignment and visual fidelity are not accepted. Unknown material properties were
reported during export, so successful export alone is not a presentation result.

## Route and acceptance gates

Keep the IKEMEN runtime seam and 2D arena. Proposed presentation route: bake the user's
extracted 3D mesh/animation into sprite frames, retaining original collision data and
separately simulated SIGN rules. Validate one textured pose and one complete normal
animation before baking broadly. This avoids a speculative 3D host rewrite.

1. Reproducible, fingerprinted offline import of the bounded package set; original
   source hashes unchanged; reader checks and independent export-table comparison.
2. Establish edition-correct instruction lengths/semantics, normal timeline/defaults,
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
```

The source-build/script-reading gates remain open. This document records an extraction
proof and decisions; it does not mark the second real-game implementation complete.
