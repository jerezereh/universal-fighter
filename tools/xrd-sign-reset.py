"""Reset offline SIGN through its witnessed Escape path and verify native recovery."""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

from xrd_combat import combat_fields
from xrd_native import ReadOnlyProcess, SIGN_HASH, fingerprint
from xrd_state import observe

ROOT = Path(__file__).resolve().parent.parent
EXE = Path('C:/Program Files (x86)/Steam/steamapps/common/GUILTY GEAR Xrd -SIGN-/Binaries/Win32/GuiltyGearXrd.exe')


def reset_check(before, after, expected):
    a, b = before['fighters'], after['fighters']
    if len(a) != 2 or len(b) != 2 or len(expected) != 2:
        return False
    return all(x['slot'] == y['slot'] == i and
        x['scalar_observations']['age_candidate'] > y['scalar_observations']['age_candidate'] + 2 and
        0 <= y['scalar_observations']['age_candidate'] <= 180 and
        y['scalar_observations']['health_candidate'] == e['health'] and
        y['scalar_observations']['hitstop_candidate'] == 0 and
        (y['x_raw'], y['y_raw']) == (e['x_raw'], e['y_raw']) and not y['hit_count']
        for i, (x, y, e) in enumerate(zip(a, b, expected)))


def candidate_check(c, p, code):
    if c.get('schema') != 1 or c.get('manual_reset_verified') is not True or any(
            c.get(k) != p[k] for k in ('pid', 'module_base', 'exe_sha256', 'code_sha256')):
        raise ValueError('requires same-session witnessed manual reset candidate')
    if len(code) != p['code_size'] or hashlib.sha256(code).hexdigest() != p['code_sha256']:
        raise ValueError('private loaded-code capture changed')
    if type(c.get('hwnd_offset')) != int or not 0 <= c['hwnd_offset'] <= 4096:
        raise ValueError('invalid private viewport field')
    for name in ('poll_return', 'window_handler'):
        rva = c.get(name + '_rva'); witness = bytes.fromhex(c.get(name + '_hex', ''))
        if type(rva) != int or len(witness) != 32 or not p['code_rva'] <= rva <= p['code_rva'] + len(code) - 32 or code[rva-p['code_rva']:rva-p['code_rva']+32] != witness:
            raise ValueError('reset code witness mismatch')
    e = c.get('expected_fighters')
    if type(e) != list or len(e) != 2 or any(type(f) != dict or set(f) != {'x_raw', 'y_raw', 'health'} or any(type(v) != int for v in f.values()) or f['y_raw'] != 0 or not 1 <= f['health'] <= 10000 for f in e):
        raise ValueError('invalid witnessed reset state')


def reset(probe, candidate, combat):
    p = json.loads((probe/'state-profile.json').read_text())
    c = json.loads(candidate.read_text()); code = (probe/'text-loaded.bin').read_bytes()
    candidate_check(c, p, code)
    if p['exe_sha256'] != SIGN_HASH or fingerprint(EXE) != SIGN_HASH:
        raise ValueError('unverified SIGN executable')
    p['scalar_fields'] = combat_fields(code, p['code_rva'], json.loads(combat.read_text()))
    spec = importlib.util.spec_from_file_location('xrd_boundary', ROOT/'tools/xrd-sign-boundary.py')
    boundary = importlib.util.module_from_spec(spec); spec.loader.exec_module(boundary)
    sys.path.insert(0, str(ROOT/'local-cache/xrd-tools/frida/python'))
    import frida
    call = lambda operation: boundary.bounded_call(frida, operation)
    out = probe/('reset-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    out.mkdir(); session = script = None
    receipt = dict(schema=1, reset_verified=False, detached=False,
                   host_round_reset_verified=False, live_reset_transport=False)
    try:
        with ReadOnlyProcess(p['pid'], EXE) as process:
            base, _ = process.module_base()
            def source_clean():
                return base == p['module_base'] and hashlib.sha256(process.read(base+p['code_rva'], p['code_size'])).hexdigest() == p['code_sha256']
            if not source_clean(): raise ValueError('loaded source code/session changed')
            before = observe(process, p); time.sleep(.1); running = observe(process, p)
            if len(before['fighters']) != 2 or len(running['fighters']) != 2 or any(
                    f['y_raw'] or f['hit_count'] or f['scalar_observations']['hitstop_candidate'] or
                    f['scalar_observations']['age_candidate'] <= old['scalar_observations']['age_candidate']
                    for old, f in zip(before['fighters'], running['fighters'])):
                raise ValueError('requires running grounded offline training with idle inputs')
            before = running
            session = call(lambda: frida.attach(p['pid']))
            script = call(lambda: session.create_script((ROOT/'tools/xrd-reset-agent.js').read_text()))
            call(script.load); call(lambda: script.exports_sync.start(c))
            deadline = time.monotonic() + 3; states = []
            while time.monotonic() < deadline:
                states.append(observe(process, p))
                status = call(script.exports_sync.status)
                if status['phase'] >= 10 and reset_check(before, states[-1], c['expected_fighters']): break
                time.sleep(.05)
            stopped = call(script.exports_sync.stop)
            call(script.unload); script = None; call(session.detach); session = None
            receipt.update(stopped, detached=True, source_code_unchanged=source_clean(), before=before, after=states[-1])
            receipt['reset_verified'] = (stopped['phase'] == 10 and len(stopped['events']) == 2 and
                len({e['thread'] for e in stopped['events']}) == 1 and stopped['code_restored'] and
                stopped['foreground_unchanged'] and receipt['source_code_unchanged'] and
                reset_check(before, states[-1], c['expected_fighters']))
            (out/'states.json').write_text(json.dumps(states, indent=2))
            if not receipt['reset_verified']: raise RuntimeError('Escape delivered but native reset not verified')
    except Exception as error:
        receipt['error'] = str(error); raise
    finally:
        cleanup_errors = []
        if script:
            for label, operation in [('stop', script.exports_sync.stop), ('unload', script.unload)]:
                try:
                    result = call(operation)
                    if label == 'stop': receipt['cleanup'] = result
                except Exception as error: cleanup_errors.append(dict(operation=label, error=str(error)))
        if session:
            try: call(session.detach); receipt['detached'] = True
            except Exception as error: cleanup_errors.append(dict(operation='detach', error=str(error)))
        if cleanup_errors: receipt['cleanup_errors'] = cleanup_errors
        (out/'inspection.json').write_text(json.dumps(receipt, indent=2))
        print(json.dumps(dict(evidence=str(out), reset_verified=receipt['reset_verified'], detached=receipt['detached'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('probe', type=Path)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--combat-candidate', type=Path, required=True)
    args = parser.parse_args()
    reset(args.probe.resolve(), args.candidate.resolve(), args.combat_candidate.resolve())
