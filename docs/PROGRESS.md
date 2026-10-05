# Progress record

## 2026-10-05

- Starting workspace contained only `handoff_doc.txt`, with no Git repository or code.
- Downloaded IKEMEN and Universal Modder working copies; exact revisions are recorded
  in `tools/upstreams.json`. Engine behavior and upstream source remain unchanged.
- Completed Phase 1 static reconnaissance and documented the smallest proposed seam.
- Added source bootstrap, project overview and milestone work packages.
- Initialized local project Git tracking (no commit or remote). Verified bootstrap
  PowerShell syntax, manifest JSON and existing-checkout revision checks; both upstream
  working copies are clean. Source reference line bounds were checked. Host execution
  remains unverified.
- Toolchain inspection: `go` is unavailable in this session's PATH. No Go installation
  was found at `C:\Program Files\Go\bin\go.exe` or
  `C:\msys64\mingw64\bin\go.exe`; `C:\msys64\usr\bin\bash.exe` is also absent.
  These checks do not establish that no toolchain exists elsewhere on the machine.
- No host build, runtime test or mixed-fighter match has been performed. The next work
  package is the unmodified host baseline and Windows build environment.

Universal Modder remains a read-only recon reference. No plugins were installed and no
commercial games or assets were investigated. Its recon workflow will be applied when
the synthetic architecture gate allows the first real-game adapter.

## Dependency setup continuation

- Added `tools/gather-dependencies.ps1`: checksum-verified stable MSYS2 archive, local
  package installation, pinned source bootstrap, Go version checks and module gathering.
- Installed MSYS2 2026-09-27 in `local-cache/msys64`. Native package verification passed:
  Go 1.27.1, SDL2 2.32.10 and libxmp 4.7.3. Go modules gathered successfully; `-CheckOnly`
  also passed using project-local Go caches. Full versions are in the ignored dependency
  report. No permanent machine PATH or registry changes were made by these scripts.
- Corrected release selection after the official latest-release endpoint returned a
  nightly archive. Accommodated the observed MSYS2 core update terminating its shell;
  the next package phase verifies the package database before continuing.
- Pinned and fetched the screenpack. Added a host-build wrapper with runtime staging,
  build logging and a bounded native/native KO and round-lifecycle smoke command.
- All PowerShell and Bash setup scripts pass syntax checks. Host build is underway;
  playable-match and visual validation remain unverified at this entry.

### Baseline result

- Pinned IKEMEN compiled successfully with the native Windows toolchain, including
  upstream-built libvpx and FFmpeg. Output executable: 16,001,024 bytes.
- The first wrapper invocation failed after compilation because a running Bash script
  was edited before its next read. Separated staging into `stage-host.sh`; staging then
  passed against the completed executable. Do not edit a script while it is executing.
- Runtime staged at `artifacts/host-baseline`. `tools/smoke-host.ps1` passed: completed
  native KFM-versus-KFM AI match, multiple rounds and a recorded KO. Evidence:
  `artifacts/host-baseline/baseline-20261005-153408-554.txt`.
- The setup, source bootstrap (including MSYS2 Git), verification, upstream build, staging
  and smoke phases have been exercised. The revised combined wrapper has not been rerun
  end-to-end after staging was separated; its scripts pass syntax checks.
- Human controls and visual presentation remain unverified. There is no foreign backend
  yet. Next: the first foreign idle/movement/jump slice with native behavior regression.

### Repository publication

- User configured `origin` as `https://github.com/jerezereh/universal-fighter.git` and
  authorized committing and pushing completed work throughout the plan. Recorded this
  project workflow in `AGENTS.md`.
- Initial publication groups the architecture foundation and Windows dependency/baseline
  tooling into separate commits. Local toolchains, upstream checkouts and runtime assets
  remain ignored; their pinned manifests and setup scripts are versioned.
