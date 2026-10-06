"""Launch two authored passthrough guests in IKEMEN, or run bounded native smoke scenes.

Requires the built host. Guests/fixtures/logs remain under ignored artifacts. This
does not launch, patch or inject SIGN; it proves the shared receiving protocol.
"""
import argparse
from contextlib import ExitStack
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
HOST = ROOT / 'artifacts/host-baseline'
HIDDEN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def stop_process(p):
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=5)


def start_guest(stack, folder, game, variant):
    ready = folder / (variant + '-ready.json')
    log = folder / (variant + '-requests.jsonl')
    stderr = stack.enter_context((folder / (variant + '-stderr.txt')).open('w'))
    p = subprocess.Popen([sys.executable, '-X', 'utf8', str(ROOT / 'tools/passthrough-demo.py'),
                          '--game', game, '--variant', variant, '--ready', str(ready),
                          '--log', str(log)], stderr=stderr, creationflags=HIDDEN)
    stack.callback(stop_process, p)
    deadline = time.monotonic() + 10
    while not ready.exists():
        if p.poll() is not None or time.monotonic() > deadline:
            raise RuntimeError(f'{variant} guest failed to start: {folder}')
        time.sleep(.02)
    receipt = json.loads(ready.read_text())
    fixture = HOST / 'chars' / folder.name
    fixture.mkdir(exist_ok=True)
    name = fixture / (variant + '.def')
    name.write_text(f'''[Info]
name = "UF {game}"
displayname = "{variant} passthrough"
runtime = passthrough
mugenversion = 1.1
localcoord = 320,240
[Files]
cmd = shell.cmd
cns = ../kfm/kfm.cns
sprite = ../kfm/kfm.sff
anim = shell.air
''')
    (fixture / 'shell.cmd').write_text('[Statedef -1]\n')
    (fixture / 'shell.air').write_text('[Begin Action 0]\n0,0,0,0,-1\n')
    receipt.update(timeout_ms=500, buttons=({'a': 'punch', 'b': 'kick', 'c': 'heavy'}
                                          if variant == 'amber' else
                                          {'a': 'light', 'b': 'medium', 'c': 'heavy', 'x': 'special'}))
    Path(str(name) + '.passthrough.json').write_text(json.dumps(receipt))
    return folder.name + '/' + name.name, log


def run_scene(scene, smoke=False, reject=False, debug=True):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    folder = HOST / f'passthrough-{scene}-{stamp}'
    folder.mkdir()
    config = (HOST / 'save/config.ini').read_text(encoding='utf-8-sig')
    config = re.sub(r'(?m)^Rollback.DesyncTest\s*=.*$', 'Rollback.DesyncTest = ' + str(int(reject)), config)
    config = re.sub(r'(?m)^Rollback.DesyncTestFrames\s*=.*$', 'Rollback.DesyncTestFrames = ' + ('8' if reject else '0'), config)
    (folder / 'config.ini').write_text(config)
    with ExitStack() as stack:
        amber, amber_log = start_guest(stack, folder, 'authored-amber', 'amber')
        cyan, cyan_log = start_guest(stack, folder, 'authored-cyan', 'cyan')
        p1, p2 = amber, cyan
        if scene == 'native-in':
            p1 = 'uf-probe/high.def'
        elif scene == 'native-out':
            p2 = 'uf-probe/idle.def'
        env = dict(os.environ, UF_FOREIGN_TRACE='1', UF_FOREIGN_DEBUG=str(int(debug)),
                   UF_FOREIGN_INPUT_PROBE='melee' if smoke else '', UF_SYNTHETIC_PROBE='',
                   UF_MIXED_DIAGNOSTICS='')
        args = [str(HOST / 'Ikemen_GO.exe'), '-config', folder.name + '/config.ini',
                '-p1', p1, '-p2', p2, '-p1.ai', '0' if not smoke else '8', '-p2.ai', '8' if smoke else '0',
                '-rounds', '2' if scene == 'reset' else '1', '-time', '8' if smoke else '-1',
                '-windowed', '-nosound', '-nojoy', '-log', folder.name + '/match.txt']
        if scene == 'reset':
            args += ['-p2.life', '1']
        trace_file = stack.enter_context((folder / 'trace.txt').open('w'))
        host = subprocess.Popen(args, cwd=HOST, env=env, stdout=trace_file, stderr=trace_file,
                                creationflags=HIDDEN if smoke else 0)
        stack.callback(stop_process, host)
        print('Running:', scene, folder, flush=True)
        try:
            host.wait(timeout=150 if smoke else None)
        except KeyboardInterrupt:
            return
        trace = (folder / 'trace.txt').read_text()
        if reject:
            if 'passthrough v1 supports offline matches only' not in trace:
                raise RuntimeError(f'Rollback was not rejected: {folder}')
            print('Rollback rejected before connecting to guests.', flush=True)
            return
        if host.returncode or 'panic:' in trace:
            raise RuntimeError(f'Host failed ({host.returncode}): {folder}')
        if smoke:
            stats = (folder / 'match.txt').read_text()
            if not re.search(r'\["LastRound"\]\s*=>\s*[1-9]', stats):
                raise RuntimeError(f'Match did not complete: {folder}')
            requests = [json.loads(line) for log in (amber_log, cyan_log) for line in log.read_text().splitlines()]
            contacts = [q for q in requests if q['operation'] in ('hit', 'contact')]
            if not contacts:
                raise RuntimeError(f'No passthrough contact: {folder}')
            if scene == 'two-guests':
                for game in ('authored-amber', 'authored-cyan'):
                    if not any(q['game'] == game and q['operation'] == 'contact' for q in requests):
                        raise RuntimeError(f'No outgoing contact for {game}: {folder}')
            if scene == 'reset' and (not re.search(r'\["WinKO"\]\s*=>\s*true', stats) or not re.search(r'\["LastRound"\]\s*=>\s*[2-9]', stats)):
                raise RuntimeError(f'KO/reset not established: {folder}')
            if scene == 'reset' and sum(q['operation'] == 'reset' and q['game'] == 'authored-cyan' for q in requests) < 2:
                raise RuntimeError(f'No guest reset on next round: {folder}')
            # Frame clock, acknowledgments and source contacts remain session/round-owned.
            for log in (amber_log, cyan_log):
                sequence = tick = 0
                session = None
                for q in map(json.loads, log.read_text().splitlines()):
                    if q['operation'] == 'hello':
                        sequence = tick = 0
                        session = q['session']
                    if q['sequence'] != sequence + 1 or q['session'] != session:
                        raise RuntimeError(f'Stale sequence/session: {log}')
                    sequence = q['sequence']
                    tick = 0 if q['operation'] == 'reset' else tick + (q['operation'] == 'step')
                    if q['tick'] != tick:
                        raise RuntimeError(f'Guest clock mismatch: {log}')
            seen = set()
            for line in trace.splitlines():
                if '[foreign-reset]' in line:
                    seen.clear()
                contact = re.search(r'\[mixed-contact\] attacker=(\d+) foreign=true defender=(\d+).*activation=(\d+) projectile=false', line)
                if contact:
                    key = contact.groups()
                    if key in seen:
                        raise RuntimeError(f'Duplicate attack contact {key}: {folder}')
                    seen.add(key)
            print(f'Passed {scene}: guest commits={len(contacts)}', flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--smoke', action='store_true', help='automated matches; no keyboard UI automation')
    p.add_argument('--no-debug', action='store_true', help='hide diagnostic collision overlays')
    p.add_argument('--scene', choices=('two-guests', 'native-in', 'native-out', 'reset', 'rollback-rejection'))
    args = p.parse_args()
    if not (HOST / 'Ikemen_GO.exe').exists():
        p.error('Build the runtime first.')
    scenes = [args.scene] if args.scene else ['two-guests', 'native-in', 'native-out', 'reset', 'rollback-rejection'] if args.smoke else ['two-guests']
    for scene in scenes:
        run_scene(scene, args.smoke, scene == 'rollback-rejection', not args.no_debug)


if __name__ == '__main__':
    main()
