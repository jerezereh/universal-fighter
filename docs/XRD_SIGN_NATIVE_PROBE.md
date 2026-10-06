# SIGN native passthrough investigation

The generic IKEMEN receiver is implemented. This step adds an original, read-only
probe for finding SIGN's native producer boundary. It does not install a hook, inject
code, freeze the game, send input, expose a guest endpoint or advertise passthrough
capabilities. All discovered addresses and loaded game bytes remain in ignored local
`artifacts/xrd-sign-native`; they are not source profiles to distribute.

## Run the next source check

Keep the original game under manual UI/input control. If it is closed, the existing
launcher uses the official bootstrap and the cached missing DirectX libraries:

```powershell
./tools/play-xrd-source.ps1
```

Open offline Practice/Training with Sol versus Ky, then obtain its PID and probe:

```powershell
Get-Process GuiltyGearXrd | Select-Object Id, MainWindowTitle
python tools/xrd-sign-probe.py --pid <PID>
```

For disk inspection or tool validation only:

```powershell
./tools/bootstrap.ps1
python tools/test-xrd-native.py
python tools/xrd-sign-probe.py
```

Each probe creates a fresh ignored folder and receipt. The live form fingerprints the
process executable, confirms it is the exact verified SIGN install/app, enumerates the
actual loaded main module, checks PE image bounds and reads its executable code section.
It compares candidate discovery signatures with the disk scan and saves loaded code
for subsequent local disassembly. It has no memory-writing, remote-call, process-suspend
or injection APIs. Access denied, partial reads, wrong PID/build and ambiguous reference
declarations fail explicitly; the tool never chooses another process automatically.

## Reference evidence and verified scope

Two development-only upstreams are pinned in `tools/upstreams.json`:

- [Altimor's legacy Xrd overlay](https://gist.github.com/AltimorTASDK/e236da6255d16b3ddd3e),
  revision `f380ffb436a45271cc8c81e4025eb7551e800846` dated 2016-04-16. Its public source
  supplies fifteen active discovery declarations for engine/world, position/pushbox,
  collision and rendering-related candidates. The probe reads these declarations from
  that pinned checkout rather than embedding retail addresses or copying the mod.
- [kkots' Rev2 overlay](https://github.com/kkots/ggxrd_hitbox_overlay_2211), revision
  `996e5b86e41bb37137bd74b74483335517fa947c`. Its frame-control implementation is a
  reference for the required hooks, not a SIGN plugin or a compatible binary. It gates
  battle update, actor ticks and actor-component ticks; stopping only a wall clock or
  hiding a window does not establish the guest's one-step-per-request behavior.

The verified SIGN executable/app identity remains the existing SHA-256 and app 376300.
Its PE32 code/data sections are bounded and a `.bind` section is present. All fifteen
legacy signatures have **zero on-disk executable-code candidates**. The first code bytes
look opaque; packing is a hypothesis until compared with the normally loaded module.
This is not proof that the legacy tool is incompatible, nor a reason to install Rev2's
hook offsets into SIGN. The loaded-module scan is the next oracle.

Authored checks pass for PE header/section/image bounds, reference parsing, unique,
missing and ambiguous candidate matches, out-of-section adjustments and candidate-only
status. A real own-process Windows oracle confirms the VM_READ-only handle, module
enumeration, exact bytes, process-path identity rejection and invalid-read rejection.
The bootstrap confirms both new pins, Python syntax checks pass and the disk receipt
confirms original executable hashes remain unchanged. The own-process oracle is not
live SIGN verification. No SIGN instance was running for this work package.

## Gate after a loaded-module match

A unique signature is only a candidate. Before building a producer around it:

1. Disassemble the actual loaded candidate and validate instruction boundaries,
   calling convention, global-pointer loads and field accesses. Derive ASLR-relative
   locations from that module; never select the first of several matches.
2. Read source transforms/action/clock/collision through the verified pointer graph
   while the user performs controlled movement and standing Punch. Compare source
   frame identity, side/facing and collision with the original window. P is J in the
   user's current training setup. Public reference fields remain hypotheses until
   these actual values/relationships agree.
3. Prove a native stepping gate freezes simulation between requests while keeping the
   renderer alive, then advances exactly once. Inspect input sampling, actor/component
   dependencies and native hitstop before claiming the `host-step` capability.
4. Isolate Sol's source render layer and associate its RGBA output with the same native
   tick. Exclude HUD/background/opponent and verify alpha/pivot/facing. Whole-window
   capture is an oracle, not the layer consumed by the receiver.
5. Suppress native duplicate contacts, mirror host state and commit universal results;
   then test mixed contacts, KO/reset and source/user input. Keep snapshots unsupported
   until native state ownership/restore is demonstrated.

Neither the generic receiver's authored guests nor a successful memory scan establishes
these native stepping/render/contact gates. SIGN is not yet a playable passthrough guest.
