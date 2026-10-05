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
