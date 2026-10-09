"""Classify reset or scene-exit invalidation; preserve the raw interrupted capture."""
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


def scene_exit_check(receipt, observations, root):
    errors=receipt.get('errors',[])
    expected=dict(type='send',payload=dict(kind='error',phase='gate',
        message='Error: transaction scene changed; original execution resumed'))
    rejection=len(errors)==2 and errors[0]==expected and errors[1].get('controller_phase')=='observe' and errors[1].get(
        'controller_error','').startswith("RPCException('transaction scene changed', 'Error', ")
    checks=dict(expected_scene_rejection=rejection,
        no_credits_granted=bool(observations) and all(v['boundary']['executed'] is False and v['boundary']['counter_delta']==0 for v in observations),
        held_state_unchanged=receipt.get('gate_check',{}).get('frozen_observed_state') is True,
        battle_absent=type(root)==int and root==0,
        clean_restoration=all(receipt.get(k) is True for k in ('detached','loaded_code_restored','source_unchanged')) and
            receipt.get('render_cleanup',{}).get('render_code_restored') is True)
    return dict(checks=checks,passed=all(checks.values()),source_capabilities_enabled=False,automatic_rebind_verified=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('trace',type=Path)
    p.add_argument('--scene-exit',action='store_true',help='require absent battle engine instead of a resumed battle clock')
    args=p.parse_args();folder=args.trace.resolve()
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
        if args.scene_exit:
            recovered=dict(battle_root=int.from_bytes(process.read(base+state['engine_global_rva'],4),'little'))
        else: recovered=observe(process,state)|dict(clock=read_clock(process,state,candidate))
    result=(scene_exit_check(receipt,observations,recovered['battle_root']) if args.scene_exit else reset_check(receipt,observations,recovered))|dict(recovered=recovered,raw_trace=folder.name)
    (folder/('scene-exit-invalidation.json' if args.scene_exit else 'reset-invalidation.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps(result['checks'],indent=2))
    if not result['passed']: raise ValueError('reset invalidation not verified; raw failure remains unchanged')


if __name__=='__main__': main()
