# Windows dependency setup

From PowerShell at the project root:

```powershell
./tools/gather-dependencies.ps1
./tools/gather-dependencies.ps1 -CheckOnly
./tools/gather-dependencies.ps1 -Build
```

The default command downloads a stable official MSYS2 x64 archive, checks its published
SHA256, extracts it under `local-cache/msys64`, updates packages, installs the MINGW64
toolchain, IKEMEN libraries and Python/Pillow for local KOF import, obtains pinned upstream repositories, checks Go against
the host's `go.mod`, and downloads Go modules. `-Build` additionally runs the upstream
Windows build, which gathers/builds FFmpeg and libvpx. The wrapper stages its binary,
libraries and the pinned screenpack into `artifacts/host-baseline`, preserving existing
runtime configuration and saves. Launch `Ikemen_GO.exe` from that folder.
After a successful build, `./tools/smoke-host.ps1` runs a bounded hidden KFM-versus-KFM
AI match and requires a completed statistics log, at least two rounds, and a recorded KO.
It uses low starting health to keep this baseline short. It verifies lifecycle execution;
human movement controls and visual presentation still require an interactive match.
After building/importing the mixed runtime, `python tools/smoke-controls.py` exercises
the actual SDL keyboard path and native screenshots using the pinned Universal Modder
WinDrive script. It needs Windows PowerShell and the desktop, and adds no dependency.
`-CheckOnly` validates the installed tools and downloads missing Go modules but does not
install or upgrade MSYS2 packages. Network access is required for setup/module gathering.

The script changes no permanent PATH, registry or machine-wide toolchain. Go module and
build caches also live under `local-cache`. It never resets
existing source checkouts. It updates only its own project-local MSYS2 distribution;
avoid running another setup/package-manager instance concurrently. Pacman package
versions are rolling, so the archive identity and installed versions are recorded in
`local-cache/msys2-download.json` and `local-cache/dependency-report.txt`. Source revisions
and the screenpack are pinned in `tools/upstreams.json`; Go dependencies follow the
upstream `go.mod`/`go.sum`. Native package updates are not a fully reproducible lockfile.

Windows x64 and an ASCII project path without spaces are required by this build route.
If an archive was only partially extracted, the script stops instead of overwriting the
directory. Inspect that installation before recovery. A failed package download can be
retried by rerunning the script. It stops if the available Go is older than the host's
requirement, rather than silently changing the host or claiming a successful setup.

MSYS2 archive installation/checksum guidance:
[official installer documentation](https://www.msys2.org/docs/installer/).
IKEMEN package and build requirements: `backends/ikemen/BUILDING.md` at the pinned revision.
The project does not gather commercial-game assets or install Universal Modder plugins.
The separate KOF importer reads a user-specified local game installation; see
`MODDING_PLAN.md`. Running `build-runtime.sh` applies the versioned host patch;
the baseline builder alone does not apply it or remove existing patches.

For SIGN source-game oracle checks, `./tools/gather-xrd-oracle.ps1` extracts three x86
DirectX DLLs from the user's existing Steamworks Shared June 2010 cabinets into a fresh
ignored cache. It verifies Microsoft Authenticode signatures, PE architecture and hashes;
it runs no installer and changes no registry, global PATH or game files. Use the directory
in `local-cache/xrd-tools/oracle-dependencies.json` only in a child game's PATH. A custom
Steam cabinet location can be supplied with `-CabinetRoot`. Windows searches an unpackaged
application's child PATH after its standard DLL locations; see
[Microsoft's DLL search order](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order).
This fixes the observed missing-library loader stage, not every SIGN startup failure.
The subsequent working route uses the **official BootGGXrd bootstrap** with that
child-only PATH. `./tools/play-xrd-source.ps1` fingerprints both executables, verifies
the cached DLL hashes, rejects duplicate instances and restores the caller's PATH.
It opens the original game for manual offline checks; the game creates its normal player
data. Bootstrap command-line window/audio flags were not observed to reach the child.
