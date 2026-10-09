"""Classify an interrupted transaction as reset invalidation; preserve the raw failure."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from xrd_native import ReadOnlyProcess, SIGN_HASH, fingerprint
from xrd_state import observe, read_clock

ROOT=Path(__file__).resolve().parent.parent
EXE=Path('C:/Program Files (x86)/Steam/steamapps/common/GUILTY GEAR Xrd -SIGN-/Binaries/Win32/GuiltyGearXrd.exe')
MESSAGE='Error: transaction source changed outside owned update; original execution resumed'


def reset_check(receipt, observations, recovered):
    expected=[dict(type='send',payload=dict(kind='error',phase='gate',message=MESSAGE)),
        dict(controller_error="ValueError('native instrumentation error; stopping before more steps')",controller_phase='observe'),
        dict(check_error='missing settled pairs')]
    clean=all(receipt.get(k) is True for k in ('detached','loaded_code_restored','source_unchanged'))
    clean &= receipt.get('render_cleanup',{}).get('render_code_restored') is True
    unchanged=receipt.get('gate_check',{}).get('frozen_observed_state') is True
    boundaries=[v['boundary'] for v in observations]
    no_credits=bool(boundaries) and all(v['executed'] is False and v['counter_delta']==0 for v in boundaries)
    before=observations[-1]['fighters'] if observations else []
    after=recovered.get('fighters',[])
    errors=copy.deepcopy(receipt.get('errors',[]))
    changes=errors[0].get('payload',{}).pop('ownership_changes',None) if errors else None
    fields=dict(x='x_raw',y='y_raw',facing='facing_left')
    def valid_change(c):
        if not isinstance(c,dict) or set(c)!={'fighter','field','before','after'} or type(c['fighter'])!=int or c['fighter'] not in (0,1) or len(before)!=2:
            return False
        if c['field'] not in (*fields,'age') or any(type(c[k])!=int or not -0x80000000<=c[k]<=0x7fffffff for k in ('before','after')):
            return False
        fighter=before[c['fighter']]
        prior=fighter.get('scalar_observations',{}).get('age_candidate') if c['field']=='age' else int(fighter[fields[c['field']]])
        return c['before']==prior and c['before']!=c['after']
    valid_changes=changes is None or isinstance(changes,list) and 1<=len(changes)<=8 and all(valid_change(c) for c in changes)
    age_reset=valid_changes and changes is not None and len(changes)==2 and {c['fighter'] for c in changes}=={0,1} and all(
        c['field']=='age' and c['before']>0 and c['after']==0 for c in changes)
    changed=len(before)==len(after)==2 and any(
        (a['x_raw'],a['y_raw'],a['facing_left'])!=(b['x_raw'],b['y_raw'],b['facing_left']) for a,b in zip(before,after))
    checks=dict(expected_guard_rejection=valid_changes and errors in (expected,expected[:2]),held_state_unchanged=unchanged,
        no_credits_granted=no_credits,reset_state_observed=changed or age_reset,clean_restoration=clean,
        source_clock_resumed=recovered.get('clock',{}).get('advancing') is True)
    return dict(checks=checks,passed=all(checks.values()),age_reset_diagnostic=bool(age_reset),source_capabilities_enabled=False,
        same_observation_reset_verified=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('trace',type=Path)
    folder=p.parse_args().trace.resolve()
    if not folder.is_relative_to(ROOT/'artifacts/xrd-sign-native'): raise ValueError('requires ignored local SIGN evidence')
    paths=[folder/'inspection.json',folder/'state.jsonl',folder.parent/'state-profile.json',folder/'candidate.json']
    if any(v.stat().st_size>16<<20 for v in paths): raise ValueError('unbounded reset evidence')
    receipt=json.loads(paths[0].read_text());observations=[json.loads(v) for v in paths[1].read_text().splitlines()]
    state=json.loads(paths[2].read_text());candidate=json.loads(paths[3].read_text())
    if receipt['pid']!=state['pid'] or fingerprint(EXE)!=SIGN_HASH: raise ValueError('source identity changed')
    with ReadOnlyProcess(state['pid'],EXE) as process:
        base,size=process.module_base()
        if base!=state['module_base'] or hashlib.sha256(process.read(base+state['code_rva'],state['code_size'])).hexdigest()!=state['code_sha256']:
            raise ValueError('source session or loaded code changed')
        recovered=observe(process,state)|dict(clock=read_clock(process,state,candidate))
    result=reset_check(receipt,observations,recovered)|dict(recovered=recovered,raw_trace=folder.name)
    (folder/'reset-invalidation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result['checks'],indent=2))
    if not result['passed']: raise ValueError('reset invalidation not verified; raw failure remains unchanged')


if __name__=='__main__': main()
