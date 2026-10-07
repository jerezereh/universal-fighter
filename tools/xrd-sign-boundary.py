"""Observe a local SIGN update candidate, or test a bounded offline freeze/step gate."""
import argparse
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import queue
import re
import subprocess
import sys
import time

from xrd_native import ReadOnlyProcess, SIGN_HASH, fingerprint
from xrd_state import assembly_rows, boundary_candidate, observe
from xrd_input import input_candidate, input_mask, input_plan, input_check, oracle_passed
from xrd_combat import combat_fields, contact_check

ROOT=Path(__file__).resolve().parent.parent
EXE=Path('C:/Program Files (x86)/Steam/steamapps/common/GUILTY GEAR Xrd -SIGN-/Binaries/Win32/GuiltyGearXrd.exe')


class CapturedMemory:
    def __init__(self,segments,data):
        self.parts=[]
        offset=0
        for s in segments:
            if s['offset']!=offset or not 0<s['size']<=0x10000 or not 0<s['address']<=0xffffffff-s['size']:
                raise ValueError('invalid captured memory segment')
            self.parts.append((s['address'],data[offset:offset+s['size']]))
            offset+=s['size']
        if offset!=len(data) or len(segments)>8: raise ValueError('incomplete captured memory')

    def read(self,address,size):
        for base,data in self.parts:
            if base<=address and address+size<=base+len(data): return data[address-base:address-base+size]
        raise ValueError('read outside captured native snapshot')


def gate_evidence(folder,candidate,state):
    evidence=json.loads((folder/'inspection.json').read_text())
    previous=json.loads((folder/'candidate.json').read_text())
    if previous!=candidate or evidence['pid']!=state['pid'] or evidence['samples']<100 or evidence['errors'] or evidence['continuity_gaps'] or evidence['counter_deltas']!={'1':evidence['samples']} or evidence['this_deltas']!=[4] or evidence['depths']!=[0] or len(evidence['threads'])!=1 or len(evidence['return_addresses'])!=1 or not evidence['observations_only'] or not evidence['loaded_code_restored'] or not evidence['detached']:
        raise ValueError('gate requires a clean same-session entry/return trace')
    return dict(thread=evidence['threads'][0],return_address=evidence['return_addresses'][0])


def gate_check(records,states,presents=(),expected_steps=3):
    executed=[r for r in records if r['executed']]
    blocked=[r for r in records if not r['executed']]
    changed=0;previous=None
    for r,s in zip(records,states):
        verified=[{k:v for k,v in f.items() if k!='scalar_observations'} for f in s]
        if not r['executed'] and previous is not None and verified!=previous: changed+=1
        previous=verified
    successful=Counter(r['counter'] for r in presents if r['hresult']==0)
    held=set(r['before'] for r in blocked)
    return dict(executed=len(executed),blocked=len(blocked),
        exact_steps=len(executed)==expected_steps and all(r['counter_delta']==1 for r in executed),
        frozen_counter=bool(blocked) and all(r['counter_delta']==0 for r in blocked),
        frozen_state_changes=changed,frozen_observed_state=bool(blocked) and changed==0,
        successful_presentations=sum(r['hresult']==0 and r.get('method')=='Present' for r in presents),
        successful_scene_ends=sum(r['hresult']==0 and r.get('method')=='EndScene' for r in presents),
        graphics_completions_per_held_counter={str(k):v for k,v in successful.items() if k in held},
        rendering_while_frozen=sum(v>=10 for k,v in successful.items() if k in held)>=2)


def lease_check(records,presents,diagnostics,automatic_restore):
    held=[r for r in records if not r['executed']]
    progressed=bool(held) and any(r['hresult']==0 and r['counter']>held[-1]['after'] for r in presents)
    return dict(no_requested_steps=bool(held) and all(not r['executed'] and r['counter_delta']==0 for r in records),
        lease_resumed=any('lease expired' in r.get('message','') for r in diagnostics) and progressed,
        hard_lifetime_removed_hook=any('hard gate lifetime' in r.get('message','') for r in diagnostics) and automatic_restore)


def trace(probe,candidate_path,seconds,gate_receipt=None,expire=False,input_path=None,plan_path=None,oracle='movement',scalar_path=None,combat_path=None):
    receipt=json.loads((probe/'inspection.json').read_text())
    state=json.loads((probe/'state-profile.json').read_text())
    if scalar_path:
        fields=json.loads(scalar_path.read_text())
        if type(fields)!=dict or not 1<=len(fields)<=128 or any(type(k)!=str or not re.fullmatch('[a-zA-Z_][a-zA-Z0-9_]{0,31}',k) or type(v)!=int or not 0<=v<=0x2600-4 or v%4 for k,v in fields.items()):
            raise ValueError('invalid bounded scalar observations')
        state['scalar_fields']=fields
    if receipt.get('mode')!='loaded-module' or state['exe_sha256']!=SIGN_HASH or fingerprint(EXE)!=SIGN_HASH or state['pid']!=receipt['pid']:
        raise ValueError('requires a verified live SIGN state profile/receipt')
    code=(probe/'text-loaded.bin').read_bytes()
    if hashlib.sha256(code).hexdigest()!=state['code_sha256'] or state['code_sha256']!=receipt['loaded_hashes']['.text']:
        raise ValueError('loaded code receipt drift')
    combat_profile=None
    if combat_path:
        local_combat=json.loads(combat_path.read_text())
        derived=combat_fields(code,state['code_rva'],local_combat)
        state.setdefault('scalar_fields',{}).update(derived)
        combat_profile=dict(candidates=local_combat,fields=derived,validated_semantics=False)
    local=json.loads(candidate_path.read_text())
    objdump=ROOT/'local-cache/msys64/mingw64/bin/objdump.exe'
    text=subprocess.check_output([str(objdump),'-D','-b','binary','-m','i386','-Mintel',
        '--adjust-vma='+hex(state['code_rva']),'--start-address='+hex(local['rva']),
        '--stop-address='+hex(local['rva']+local['code_size']),str(probe/'text-loaded.bin')],text=True)
    candidate=boundary_candidate(code,state['code_rva'],local,assembly_rows(text))
    input_profile=None
    if input_path:
        input_local=json.loads(input_path.read_text())
        rows=[]
        for label in ('sampler','writer'):
            disassembly=subprocess.check_output([str(objdump),'-D','-b','binary','-m','i386','-Mintel',
                '--adjust-vma='+hex(state['code_rva']),'--start-address='+hex(input_local[label+'_rva']),
                '--stop-address='+hex(input_local[label+'_rva']+input_local[label+'_size']),str(probe/'text-loaded.bin')],text=True)
            rows.append(assembly_rows(disassembly))
        input_profile=input_candidate(code,state['code_rva'],input_local,assembly_rows(text),*rows)
    gate_options=gate_evidence(gate_receipt,candidate,state) if gate_receipt else None
    plan=None
    if plan_path:
        if not gate_options or not input_profile or expire or plan_path.stat().st_size>16384:
            raise ValueError('bounded input plan requires a native gate and validated input ingress')
        plan=input_plan(json.loads(plan_path.read_text()))
    sys.path.insert(0,str(ROOT/'local-cache/xrd-tools/frida/python'))
    import frida
    if frida.__version__!='17.22.2': raise ValueError('run gather-xrd-instrumentation.py for pinned Frida')
    out=probe/('boundary-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    out.mkdir();(out/'candidate.json').write_text(json.dumps(candidate,indent=2))
    if input_profile: (out/'input-profile.json').write_text(json.dumps(input_profile,indent=2))
    if combat_profile: (out/'combat-profile.json').write_text(json.dumps(combat_profile,indent=2))
    if plan: (out/'input-plan.json').write_text(json.dumps(plan,indent=2))
    messages=queue.Queue(maxsize=8192);overflow=[]
    def receive(message,data):
        try: messages.put_nowait((message,data,time.perf_counter()))
        except queue.Full: overflow.append(True)
    errors=[];records=[];states=[];presents=[];inputs=[];diagnostics=[];session=script=None;detached=False;requests=0;cleanup_receipt=None;automatic_restore=False
    started=time.perf_counter();started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat();completed=0;next_request=.5;request_log=[]
    with ReadOnlyProcess(state['pid'],EXE) as process:
        def unchanged():
            base,size=process.module_base()
            return base==state['module_base'] and size==receipt['image_size'] and hashlib.sha256(process.read(base+state['code_rva'],state['code_size'])).hexdigest()==state['code_sha256']
        if not unchanged(): raise ValueError('source session/code changed; run a fresh probe')
        try:
            session=frida.attach(state['pid'])
            script=session.create_script((ROOT/'tools/xrd-sign-boundary.js').read_text())
            script.on('message',receive);script.load()
            print(script.exports_sync.start(dict(state=state,candidate=candidate,image_size=receipt['image_size'],gate=gate_options,input=input_profile)),flush=True)
            started=time.perf_counter()
            with (out/'state.jsonl').open('w',encoding='utf-8') as log:
                while time.perf_counter()-started<seconds:
                    if overflow: raise ValueError('instrumentation queue overflow')
                    if plan and requests<len(plan) and requests==completed and time.perf_counter()-started>=next_request:
                        if requests==0 and (not states or any(s['y_raw'] or s['hit_count'] for s in states[0]) or not any(re.fullmatch(r'sol00[01]_[0-9]{2}',n['value']) for n in states[0][0]['pose_candidates']) or
                            (abs(states[0][0]['x_raw']-states[0][1]['x_raw'])>350000 if oracle=='contact' else abs(states[0][0]['x_raw']-states[0][1]['x_raw'])<350000)):
                            raise ValueError('input oracle requires grounded idle Sol/opponent within its scene distance bounds')
                        packet=plan[requests];mask=input_mask(packet['input'],states[-1][0]['facing_left'],packet['accept_input'])
                        script.exports_sync.step([mask,0]);request_log.append(dict(step=requests+1,mask=mask,**packet));requests+=1
                        next_request=time.perf_counter()-started+.03+packet['hold_ms']/1000
                    elif not plan and gate_options and not expire and requests<3 and time.perf_counter()-started>=requests+1:
                        script.exports_sync.step([0,0]);requests+=1
                    if expire and time.perf_counter()-started>12.5 and not automatic_restore:
                        automatic_restore=unchanged()
                    try: message,data,wall=messages.get(timeout=.1)
                    except queue.Empty: continue
                    if message['type']=='send' and message['payload'].get('kind')=='present':
                        presents.append(message['payload']);continue
                    if message['type']=='send' and message['payload'].get('kind')=='input':
                        inputs.append(message['payload']);continue
                    if expire and message['type']=='send' and message['payload'].get('phase')=='watchdog':
                        diagnostics.append(message['payload']);continue
                    if message['type']!='send' or message['payload'].get('kind')!='frame':
                        errors.append(message);continue
                    native=message['payload']
                    observation=observe(CapturedMemory(native.pop('segments'),data),state)
                    observation.update(boundary=native,wall_seconds=wall-started,boundary_aligned=True)
                    log.write(json.dumps(observation,separators=(',',':'))+'\n')
                    records.append(native)
                    states.append(observation['fighters'])
                    if native['executed']: completed+=1
        except Exception as error:
            errors.append(dict(controller_error=repr(error)))
        finally:
            # A failed RPC must not prevent script/session teardown from removing the hook.
            if script is not None:
                try: cleanup_receipt=script.exports_sync.stop()
                except Exception as error: errors.append(dict(cleanup_error=repr(error)))
                try: script.unload()
                except Exception as error: errors.append(dict(cleanup_error=repr(error)))
            try:
                if session is not None: session.detach()
                detached=True
            except Exception as error: errors.append(dict(cleanup_error=repr(error)))
        restored=unchanged()
    if not restored: errors.append(dict(cleanup_error='loaded source code was not restored'))
    if fingerprint(EXE)!=SIGN_HASH: errors.append(dict(source_error='source executable fingerprint changed'))
    deltas=Counter(r['counter_delta'] for r in records)
    gaps=sum(b['before']!=a['after'] for a,b in zip(records,records[1:]))
    result=dict(schema=1,pid=state['pid'],samples=len(records),seconds=seconds,started_utc=started_utc,
        counter_deltas=dict(deltas),continuity_gaps=gaps,threads=sorted(set(r['thread'] for r in records)),
        this_deltas=sorted(set(r['this_delta'] for r in records)),depths=sorted(set(r['depth'] for r in records)),
        return_addresses=sorted(set(r['return_address'] for r in records)),errors=errors,
        observations_only=not bool(gate_options),boundary_experiment=bool(gate_options),boundary_aligned=True,temporary_code_interception=True,
        detached=detached,loaded_code_restored=restored,source_unchanged=fingerprint(EXE)==SIGN_HASH,
        native_tick_verified=False,atomic_native_frame=False,host_step=False,isolated_rgba=False,universal_contact=False)
    if gate_options:
        result['gate_check']=gate_check(records,states,presents,len(plan) if plan else 3)
        result['controlled_update_step_verified']=not expire and all(result['gate_check'][k] for k in ('exact_steps','frozen_counter','frozen_observed_state','rendering_while_frozen')) and gaps==0 and not errors
        if expire: result['lease_check']=lease_check(records,presents,diagnostics,automatic_restore)
        result['diagnostics']=diagnostics
        result['render_cleanup']=cleanup_receipt
        (out/'present.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in presents))
        if not cleanup_receipt or not cleanup_receipt['render_code_restored']:
            errors.append(dict(cleanup_error='Direct3D presentation code not restored'))
    if input_profile:
        (out/'input.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in inputs))
        result['input_observations']=len(inputs)
        result['input_slots']=dict(Counter(r['slot'] for r in inputs))
        result['input_values']=sorted(set(r['incoming'] for r in inputs))
        if gate_options and not expire:
            result['input_check']=input_check(records,states,inputs,request_log)
            result['source_input_routing_verified']=result['controlled_update_step_verified'] and result['input_check']['source_history_linked'] and not errors
    if plan:
        result['named_input_steps']=len(request_log)
        result['input_oracle']=oracle
        result['input_oracle_passed']=oracle_passed(oracle,result['input_check']) if oracle!='contact' else False
        if oracle=='contact' and combat_profile:
            try: result['contact_check']=contact_check(records,states)
            except ValueError as error:
                result['contact_check']=dict(passed=False,error=str(error))
                errors.append(dict(check_error=str(error)))
            result['input_oracle_passed']=result['contact_check']['passed']
        (out/'requests.json').write_text(json.dumps(request_log,indent=2))
    (out/'inspection.json').write_text(json.dumps(result,indent=2))
    print('Boundary trace:',len(records),'samples; counter deltas',dict(deltas),'gaps',gaps,'errors',len(errors),';',out,flush=True)
    if gate_options: print('Gate checks:',{k:v for k,v in result['gate_check'].items() if k!='graphics_completions_per_held_counter'},flush=True)
    if expire: print('Lease checks:',result['lease_check'],flush=True)
    if 'input_check' in result: print('Input checks:',result['input_check'],flush=True)
    if 'contact_check' in result: print('Contact checks:',result['contact_check'],flush=True)
    if errors or not records or not restored or not detached: raise RuntimeError('boundary trace failed; inspect local receipt')
    if expire and not all(result['lease_check'].values()): raise RuntimeError('gate lease recovery failed')
    if gate_options and not expire and not result['controlled_update_step_verified']:
        raise RuntimeError('native gate experiment failed; no host-step capability accepted')
    if input_profile and gate_options and not expire and not result['input_check']['source_history_linked']:
        raise RuntimeError('source input does not match requested native steps')
    if plan and (oracle!='contact' or combat_profile) and not result['input_oracle_passed']:
        raise RuntimeError('source '+oracle+' input oracle failed')
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('probe',type=Path)
    p.add_argument('--candidate',type=Path,required=True,help='ignored local enclosing-function/counter-writer discovery JSON')
    p.add_argument('--seconds',type=float,default=10)
    p.add_argument('--gate',type=Path,help='clean same-session boundary trace: run a bounded 4.5-second freeze/three-step experiment')
    p.add_argument('--lease-check',action='store_true',help='with --gate: omit steps and verify automatic resume/removal over 13 seconds')
    p.add_argument('--input-candidate',type=Path,help='ignored local sampler/writer/ingress discovery JSON')
    p.add_argument('--input-plan',type=Path,help='bounded named-input oracle plan, with --gate and --input-candidate')
    p.add_argument('--oracle',choices=('movement','crossover','contact'),default='movement',help='required input-plan evidence; contact without --combat-candidate records discovery only')
    p.add_argument('--scalar-fields',type=Path,help='ignored bounded field hypotheses to observe without semantic promotion')
    p.add_argument('--combat-candidate',type=Path,help='ignored local scalar getter/setter discoveries for the native contact check')
    a=p.parse_args()
    if not 0<a.seconds<=120: p.error('seconds must be 0..120')
    if a.lease_check and not a.gate: p.error('--lease-check requires --gate')
    trace(a.probe.resolve(),a.candidate.resolve(),13 if a.lease_check else 7 if a.input_plan else 4.5 if a.gate else a.seconds,
          a.gate.resolve() if a.gate else None,a.lease_check,a.input_candidate.resolve() if a.input_candidate else None,
          a.input_plan.resolve() if a.input_plan else None,a.oracle,a.scalar_fields.resolve() if a.scalar_fields else None,
          a.combat_candidate.resolve() if a.combat_candidate else None)
