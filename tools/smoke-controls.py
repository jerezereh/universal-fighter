"""Interactive SDL keyboard check: focuses IKEMEN, drives two local matches, saves screenshots.

Uses the pinned Universal Modder WinDrive script. Close other IKEMEN instances first.
No AI or foreign input probe drives P1. Requires an unlocked Windows desktop.
"""
from pathlib import Path
import datetime
import os
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / 'artifacts/host-baseline'
DRIVER = ROOT / 'tools/references/universal-modder/um/ps1/WinDrive.ps1'


def wait_for(predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.05)
    raise RuntimeError('Timed out waiting for the native host; inspect the retained trace.')


def run_scene(name, complete=False, rules=None, defense=False):
    folder = RUNTIME / ('controls-' + name + '-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    (folder / 'screenshots').mkdir(parents=True)
    config = (RUNTIME / 'save/config.ini').read_text(encoding='utf-8-sig')
    config = re.sub(r'(?m)^ScreenshotFolder\s*=.*$', 'ScreenshotFolder = ' + folder.name + '/screenshots/', config)
    config = re.sub(r'(?m)^Rollback.DesyncTest\s*=.*$', 'Rollback.DesyncTest = 0', config)
    config = re.sub(r'(?m)^Rollback.DesyncTestFrames\s*=.*$', 'Rollback.DesyncTestFrames = 0', config)
    (folder / 'config.ini').write_text(config, encoding='utf-8')
    env = dict(os.environ, UF_FOREIGN_TRACE='1', UF_FOREIGN_DEBUG='1', UF_FOREIGN_INPUT_PROBE='', UF_SYNTHETIC_PROBE='')
    p1 = f'uf-synthetic/{rules}.def' if rules else 'kof13/kof13.def'
    p2 = 'uf-synthetic/airdash-test.def' if rules == 'parry-test' else 'uf-probe/idle.def'
    if defense:
        p2 = 'uf-probe/high.def'
    args = ['-config', folder.name + '/config.ini', '-p1', p1, '-p2', p2,
            '-p1.ai', '0', '-p2.ai', '0', '-windowed', '-nosound', '-nojoy', '-rounds', '1', '-time', '30' if complete else '-1',
            '-log', folder.name + '/match.txt']
    if complete:
        args += ['-p2.life', '85']
    game = driver = None
    with (folder / 'trace.txt').open('w') as trace_file:
        try:
            game = subprocess.Popen([str(RUNTIME / 'Ikemen_GO.exe'), *args], cwd=RUNTIME, env=env,
                                    stdout=trace_file, stderr=trace_file, creationflags=subprocess.CREATE_NO_WINDOW)
            driver = subprocess.Popen(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(DRIVER), '-Proc', 'Ikemen_GO'],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            if driver.stdout.readline().strip() != 'ready window':
                wait_for(lambda: '[foreign-frame]' in (folder / 'trace.txt').read_text(), 30)

            def command(value):
                driver.stdin.write(value + '\n')
                driver.stdin.flush()
                reply = driver.stdout.readline().strip()
                if reply != 'ok':
                    raise RuntimeError(f'WinDrive {value}: {reply}; no further input sent')

            def trace():
                return (folder / 'trace.txt').read_text()

            def frame():
                return int(re.findall(r'\[foreign-frame\] frame=(\d+)', trace())[-1])

            def shot(label):
                previous = set((folder / 'screenshots').glob('*.png'))
                command('key 0x7B')
                def saved():
                    return [p for p in set((folder / 'screenshots').glob('*.png')) - previous
                            if p.read_bytes().endswith(b'IEND\xaeB`\x82')]
                wait_for(saved)
                shutil.copyfile(saved()[0], folder / (label + '.png'))

            wait_for(lambda: '[foreign-frame]' in trace(), 30)
            command('focus')
            if rules:
                command('key 0x13')
                time.sleep(.15)
                before = frame()
                time.sleep(.2)
                if frame() != before:
                    raise RuntimeError('Authored clock advanced during Pause')
                if rules == 'parry-test':
                    command('key 0x58 down')
                    try:
                        command('key 0x91')
                        time.sleep(.1)
                    finally:
                        command('key 0x58 up')
                    if not re.search(r'\[ruleset-frame\].*parry:6 ', trace()):
                        raise RuntimeError('Keyboard X did not open the authored parry window')
                    before += 1
                for _ in range(3):
                    command('key 0x91')
                    time.sleep(.1)
                    if frame() != before + 1:
                        raise RuntimeError('Authored single-step did not advance once')
                    before += 1
                shot('paused')
                command('key 0x13')
                if defense:
                    command('key 0x25 down')
                    command('key 0x58 down')
                    try:
                        wait_for(lambda: re.search(r'\[ruleset-frame\].*barriers:1', trace()))
                        command('key 0x13')
                        shot('guard')
                    finally:
                        command('key 0x25 up')
                        command('key 0x58 up')
                    if not re.search(r'\[ruleset-frame\].*meter:90 .*barriers:1', trace()):
                        raise RuntimeError('Keyboard Back+X did not spend exactly one guard cost')
                else:
                    command('hold 0x27 700')
                    command('hold 0x5A 120')
                if rules == 'airdash-test' and not defense:
                    command('hold 0x58 120')
                    time.sleep(.4)
                    command('hold 0x26 140')
                    time.sleep(.08)
                    command('hold 0x58 120')
                    time.sleep(.08)
                    command('key 0x13')
                    shot('dash')
                    if not re.search(r'\[ruleset-frame\].*dashes:1 cancels:1 ', trace()):
                        raise RuntimeError('Keyboard normal-confirm cancel and air dash were not both observed')
                elif not defense:
                    time.sleep(.3)
                    command('key 0x13')
                    shot('normal')
                if 'projectile=false' not in trace():
                    raise RuntimeError('Authored keyboard normal did not contact the native target')
            elif complete:
                command('hold 0x27 700')
                command('hold 0x5A 120')
                time.sleep(.6)
                command('hold 0x58 120')
                time.sleep(.2)
                shot('ko')
                game.wait(timeout=45)
                stats = (folder / 'match.txt').read_text()
                lives = [int(v) for v in re.findall(r'\["Life"\]\s*=>\s*(\d+)', stats)]
                if game.returncode or len(lives) != 2 or lives[0] <= 0 or lives[1] != 0 or not re.search(r'\["WinKO"\]\s*=>\s*true', stats) or not re.search(r'\["LastRound"\]\s*=>\s*1', stats):
                    raise RuntimeError('Keyboard-driven match did not complete by KO')
            else:
                command('key 0x13')
                time.sleep(.15)
                before = frame()
                time.sleep(.3)
                if frame() != before:
                    raise RuntimeError('Pause did not freeze the guest clock')
                shot('startup')
                for _ in range(3):
                    command('key 0x91')
                    time.sleep(.15)
                    if frame() != before + 1:
                        raise RuntimeError('Scroll Lock did not advance exactly one frame')
                    before += 1
                command('key 0x13')
                command('hold 0x27 350')
                command('hold 0x25 200')
                command('hold 0x28 150')
                time.sleep(.45)
                command('hold 0x26 140')
                time.sleep(1.25)
                command('hold 0x27 650')
                command('hold 0x5A 120')
                time.sleep(.6)
                command('hold 0x58 120')
                time.sleep(1.1)
                command('key 0x27 down')
                try:
                    command('hold 0x26 140')
                    command('hold 0x27 1000')
                finally:
                    command('key 0x27 up')
                time.sleep(1.1)
                command('hold 0x27 700')  # Exercise label clamping at the stage edge.
                command('key 0x13')
                shot('crossover')
                for action in (2, 3, 25, 27, 12, 68, 475, 15):
                    if not re.search(rf'action={action} ', trace()):
                        raise RuntimeError(f'Missing keyboard-driven action {action}')
                if 'foreign_facing=-1' not in trace() or 'projectile=true' not in trace() or 'projectile=false' not in trace():
                    raise RuntimeError('Crossover facing or both contact paths were not observed')
            print(f'{name} SDL controls passed: {folder}', flush=True)
            return folder
        finally:
            if driver:
                driver.stdin.close()
                try:
                    driver.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    driver.kill()
                    driver.wait()
            if game and game.poll() is None:
                game.terminate()  # Only the exact process launched by this scene.
                game.wait(timeout=5)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic', action='store_true', help='check both authored rulesets instead of Kyo')
    options = parser.parse_args()
    if os.name != 'nt' or not DRIVER.is_file():
        raise SystemExit('Windows and the pinned Universal Modder checkout are required.')
    existing = subprocess.check_output(['powershell.exe', '-NoProfile', '-Command',
                                        'Get-Process -Name Ikemen_GO -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id; exit 0'], text=True).strip()
    if existing:
        raise SystemExit('Close existing IKEMEN instances before this foreground keyboard check.')
    if options.synthetic:
        run_scene('parry', rules='parry-test')
        run_scene('airdash', rules='airdash-test')
        run_scene('barrier', rules='airdash-test', defense=True)
    else:
        run_scene('practice')
        run_scene('match', complete=True)
    print('All requested SDL scenes passed; screenshots still require visual inspection.')
