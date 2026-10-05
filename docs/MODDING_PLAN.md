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
- Default character: Kyo, resource `03`. Other characters are explicit importer
  choices but have not been validated for this subset.

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

The importer exported 13 actions and 110 frames, including idle, walk, crouch,
jump startup/air and landing. Reconstructed Kyo's idle image was visually inspected.
SFF/AIR are presentation assets only; exported constants contain no CNS states.
Velocity selectors reference the source `moves` table, rather than literal speeds.
The slice uses a documented 0.4 coordinate conversion into the host arena.

## Run

Use Python with Pillow (the Codex bundled runtime already supplies it):

```powershell
python tools/kof13-import.py --game 'C:\Program Files (x86)\Steam\steamapps\common\King of Fighters XIII'
python tools/test-kof13-import.py
```

Output is restricted to ignored `artifacts/`. Source hashes are stored in the
local foreign manifest. Neither game files, extracted images nor derived frame
data are committed. Export is not evidence of host simulation or combat fidelity.

## References

- [Lua 5.1 opcode definitions](https://www.lua.org/source/5.1/lopcodes.h.html)
- [Game Extractor PCS archive reader](https://github.com/wattostudios/GameExtractor/blob/master/src/org/watto/ge/plugin/archive/Plugin_PCS_TEXLIST.java)
- [KOF XIII Lua resource research and character codes](https://github.com/ExMingYan/KOFXIII-LuaHack)

The Java archive reader provided section/chunk format corroboration; the local
tile reconstruction and restricted bytecode reader are implemented here.
