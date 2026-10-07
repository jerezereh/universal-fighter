# SIGN background detection and autonomous UI

The user authorized autonomous offline source UI on 2026-10-07. This supersedes the
earlier manual-menu preference. Keep source work offline; scripts do not select online
routes or make account/configuration changes.

`tools/xrd-source-window.ps1` fingerprints the exact source EXE and requires one matching
process/window. `status` reports minimization, foreground and desktop idle. `restore`
uses [SW_SHOWNOACTIVATE](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-showwindow)
to restore rendering without activation. It was verified on the minimized training
window: the game resumed rendering while Codex remained foreground. Native memory/state
and GPU detection can run with the game covered. Minimized rendering is not supported;
the script restores the window first rather than treating absent frames as evidence.

`tools/xrd-source-ui.py` writes GPU screenshots, native observations and receipts under
ignored `artifacts/xrd-source-ui`. It reuses installed FFmpeg, the verified source profile
and the pinned Universal Modder WinDrive for foreground keys. No new package, OCR engine
or system-wide execution-policy setting is installed. The shell invocation uses a
process-local execution-policy flag, as existing project control scripts do, and prefers
the installed PowerShell 7 runtime.

```powershell
$probe = 'artifacts/xrd-sign-native/<current-session-probe>'
python tools/xrd-source-ui.py $probe
python tools/xrd-source-ui.py $probe --action key --key escape --mode foreground --wait-idle 120
python tools/xrd-source-ui.py $probe --action menu-check --mode foreground --wait-idle 120 --boundary '<clean same-session boundary trace>'
```

Observation is the default and does not activate the window.
FFmpeg is located in existing PATH, project cache or the installed WinGet package and
checked for `gfxcapture`; `--ffmpeg` can override its path. Nothing is downloaded.

`key` performs one bounded action and captures the result; message/input delivery alone is never an accepted UI
effect. The agent must inspect the screenshot before choosing another action. Available
keys are Escape, Enter, four arrows and the user's J/Punch mapping. This is a scriptable
observe/action loop, not a blind startup-to-training macro.

Background `post-key` uses targeted key-down/up messages without global SendInput.
The live Escape test left training running and did not open its menu; this route is
unaccepted for SIGN menu control. The controller stops on an unverified result rather
than silently switching to foreground input or sending a blind second key.

Foreground mode only takes focus when the desktop has been idle for at least 60 seconds,
or when the game is already foreground. A bounded `--wait-idle` can defer the check while
the user is working. The driver refuses keys if another app becomes foreground. It uses
scan codes, removes its temporary topmost flag and returns focus to the earlier window
only if the game still owns foreground. It does not restore focus over a later user
window switch. Receipts preserve failures and unknown outcomes.

`menu-check` starts from the observed Sol/Ky scene, requires an advancing original source
clock, sends Escape and samples the clock. Only a verified pause allows the second Escape
and resume check. An unexpected menu/key result stops for screenshot inspection. This
check does not install native hooks or advance source updates artificially. Full menu
navigation and native menu-pause semantics must be accepted from live results separately.

Exit codes: 0 for observation/verified menu check or a delivered single key (effect still
requires inspection), 1 for a failure/unverified menu check, 2 for desktop-activity
deferral. Source snapshots, UI photos and native addresses are not committed.
