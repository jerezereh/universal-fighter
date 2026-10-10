"""Observe a local SIGN update candidate, or test a bounded offline freeze/step gate."""
import argparse
from collections import Counter, deque
import datetime
import hashlib
import json
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

from xrd_native import ReadOnlyProcess, SIGN_HASH, fingerprint
from xrd_state import assembly_rows, boundary_candidate, observe, read_clock, unique
from xrd_input import input_candidate, input_mask, input_plan, position_plan, punch_plan, input_check, oracle_passed, input_scene_ready
from xrd_combat import combat_fields, contact_check, contact_observations, dispatch_candidate, dispatch_ownership, suppressed_contact_check, contact_callees, external_contact_check, guard_contact_check, dispatch_result_fields
from xrd_render import render_pixels, save_render, render_check, draw_check, save_pass
from xrd_shader import opaque_alpha_variant, screen_packet
from xrd_layer import layer_pixels, save_layer_preview, save_hdr_layer, capture_steps, capture_presentations, render_oracle, settling_oracle, settled_oracle
from xrd_transform import transform_packet, transform_changes, projection_bindings, vertex_bindings
from xrd_d3d import validate_device_calls
from xrd_stream import RollingAudit,body_geometry
from source_frame_tap import FrameTap

ROOT=Path(__file__).resolve().parent.parent
EXE=Path('C:/Program Files (x86)/Steam/steamapps/common/GUILTY GEAR Xrd -SIGN-/Binaries/Win32/GuiltyGearXrd.exe')


def bounded_call(frida,operation,seconds=5):
    # The pinned shim's synchronous RPC waits are not cancellable; a daemon also bounds them.
    cancellation=frida.Cancellable();finished=threading.Event();outcome={}
    def run():
        try:
            with cancellation: outcome['value']=operation()
        except Exception as error: outcome['error']=error
        finally: finished.set()
    threading.Thread(target=run,daemon=True).start()
    if not finished.wait(seconds):
        cancellation.cancel();raise TimeoutError('native instrumentation operation timed out')
    if 'error' in outcome: raise outcome['error']
    return outcome['value']


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


def render_restored(process,receipt,detached):
    targets=receipt.get('render_targets',[])
    if not isinstance(targets,list) or not 1<=len(targets)<=15:
        raise ValueError('missing/unbounded graphics restoration witnesses')
    addresses=set()
    for t in targets:
        if (type(t.get('address'))!=int or not 0x10000<=t['address']<=0xffffffff-32 or
                not isinstance(t.get('before'),str) or not re.fullmatch('[0-9a-f]{64}',t['before']) or
                t['address'] in addresses):
            raise ValueError('invalid graphics restoration witness')
        addresses.add(t['address'])
    return detached and all(process.read(t['address'],32)==bytes.fromhex(t['before']) for t in targets)


def layer_programs(folder,state,identity,normalize=False):
    evidence=json.loads((folder/'inspection.json').read_text())
    if (evidence['pid']!=state['pid'] or evidence['errors'] or not evidence['detached'] or
            not evidence['loaded_code_restored'] or not evidence['source_unchanged'] or
            not evidence['controlled_update_step_verified'] or
            json.loads((folder/'draw-identity.json').read_text())!=identity):
        raise ValueError('layer requires clean same-session shader inspection')
    inventory=json.loads((folder/'mesh-shaders.json').read_text())
    if not isinstance(inventory,list) or not 2<=len(inventory)<=32: raise ValueError('invalid shader inventory')
    targets=Counter(s['source_target'] for s in inventory)
    color=[target for target,count in targets.items() if count>=2]
    if len(color)!=1: raise ValueError('ambiguous main mesh color target')
    programs={}
    for s in inventory:
        if s['source_target']!=color[0]: continue
        if not re.fullmatch(r'shader-[0-9]{2}\.bin',s['file']): raise ValueError('invalid shader filename')
        data=(folder/s['file']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=s['sha256']: raise ValueError('shader inventory drift')
        variant,_=opaque_alpha_variant(data)
        programs[s['shader']]=dict(original_hex=data.hex(),variant_hex=variant.hex())
    result=dict(target=color[0],programs=programs)
    if normalize:
        vertices=json.loads((folder/'mesh-vertices.json').read_text())
        if not isinstance(vertices,list) or not 1<=len(vertices)<=32: raise ValueError('invalid vertex inventory')
        bindings={};origins={}
        for v in vertices:
            if not re.fullmatch(r'vertex-[0-9]{2}\.bin',v['file']): raise ValueError('invalid vertex filename')
            code=(folder/v['file']).read_bytes()
            if hashlib.sha256(code).hexdigest()!=v['sha256']: raise ValueError('vertex inventory drift')
            table=vertex_bindings(v['assembly'],code)
            if table.get('LocalToWorld',(0,0))[1]!=4: raise ValueError('missing native actor origin binding')
            origins[v['shader']]=dict(local_to_world=table['LocalToWorld'][0],original_hex=code.hex())
            if v['source_target']!=color[0]: continue
            if v['shader'] in bindings: raise ValueError('duplicate vertex program')
            bindings[v['shader']]=projection_bindings(v['assembly'],code)|dict(original_hex=code.hex())
            if 'PreViewTranslation' in table:
                if table['PreViewTranslation'][1]!=1: raise ValueError('invalid pre-view translation binding')
                bindings[v['shader']]['pre_view_translation']=table['PreViewTranslation'][0]
            for name,key in [('CameraWorldPos','camera_world'),('CameraPositionVS','camera_position_vs')]:
                if name in table:
                    if table[name][1]!=1: raise ValueError('invalid native camera binding')
                    reserved=set(range(bindings[v['shader']]['projection'],bindings[v['shader']]['projection']+4))|{bindings[v['shader']]['ortho']}
                    reserved.update(range(table['LocalToWorld'][0],table['LocalToWorld'][0]+4))
                    if table[name][0] in reserved or re.search(r'^\s*def c'+str(table[name][0])+',',v['assembly'],re.M):
                        raise ValueError('aliased/inline native camera binding')
                    bindings[v['shader']][key]=table[name][0]
        if not bindings: raise ValueError('missing native projection programs')
        result['projection']=dict(programs=bindings,origins=origins,width=640,height=768,pivot=[320,700],pixels_per_world_unit=2)
    return result


def grading_programs(folder,state):
    evidence=json.loads((folder/'inspection.json').read_text())
    if (evidence['pid']!=state['pid'] or evidence['errors'] or not evidence['loaded_code_restored'] or
            not evidence['detached'] or not evidence['source_unchanged'] or not evidence['controlled_update_step_verified'] or
            evidence.get('d3d_abi',{}).get('native_header_checked') is not True):
        raise ValueError('grading requires a clean same-session native program inspection')
    inventory=json.loads((folder/'screen-shaders.json').read_text());programs=[]
    for s in inventory:
        if not re.fullmatch('screen-[0-9]{2}\\.bin',s['file']):raise ValueError('invalid grading program file')
        code=(folder/s['file']).read_bytes()
        if screen_packet(s,code)['sha256']!=s['sha256']:raise ValueError('native grading program drift')
        table={}
        for name,kind,register,count in re.findall(r'^//\s+(\w+)\s+([cs])(\d+)\s+(\d+)\s*$',s['assembly'],re.M):
            register,count=int(register),int(count)
            if name in table or not 1<=count<=224 or register+count>(16 if kind=='s' else 224):
                raise ValueError('unsupported grading binding')
            table[name]=(kind,register,count)
        programs.append((s,code,table))
    grade=[p for p in programs if p[0].get('lut_source') is not None]
    copies={p[0]['sha256']:p for p in programs if set(p[2])=={'InTexture','TextureComponentReplicateAlpha'}}
    if len(grade)!=1 or len(copies)!=1:raise ValueError('ambiguous native grading/copy programs')
    s,code,table=grade[0];copy,copy_code,copy_table=next(iter(copies.values()))
    samplers={name:register for name,(kind,register,count) in table.items() if kind=='s' and count==1}
    if (set(samplers)!={'SceneColorTexture','ColorGradingLUT','FilterColor1Texture','LowResPostProcessBuffer'} or
            len(set(samplers.values()))!=4 or copy_table['InTexture'][0]!='s' or copy_table['TextureComponentReplicateAlpha'][0]!='c' or
            copy_table['InTexture'][2]!=1 or copy_table['TextureComponentReplicateAlpha'][2]!=1 or
            re.search(r'^\s*def c'+str(copy_table['TextureComponentReplicateAlpha'][1])+',',copy['assembly'],re.M)):
        raise ValueError('unsupported native grading/copy dependencies')
    return dict(shader=s['shader'],target=s['source_target'],original_hex=code.hex(),samplers=samplers,
        vertex_original_hex=s.get('vertex_program',{}).get('code_hex') if s.get('vertex_program') else None,
        source_quad_observed=s.get('vertex_input') is not None,
        copy_hex=copy_code.hex(),copy_sampler=copy_table['InTexture'][1],copy_constant=copy_table['TextureComponentReplicateAlpha'][1])


def post_color_programs(folder,state,grade,smaa=False,projection=None):
    # Reuse the validated inventory; native shader bytes stay in the ignored capture.
    grading_programs(folder,state)
    inventory=json.loads((folder/'screen-shaders.json').read_text())
    programs={(s['shader'],s['source_target']):s for s in inventory}
    stages=[json.loads((folder/f'pass-{i:02}.json').read_text()) for i in range(1,14 if smaa else 11)]
    first=stages[0]
    if first['screen_shader']!=grade['shader'] or first['surface']!=grade['target']:
        raise ValueError('post-color grading boundary changed')
    outputs={first['surface']};result=[]
    for i,stage in enumerate(stages[1:],2):
        s=programs[(stage['screen_shader'],stage['surface'])]
        if (stage.get('capture_boundary')!='after-screen-draw' or stage.get('diagnostic_pipeline') is not True or
                stage.get('presentation_index')!=1 or stage['counter']!=first['counter'] or
                stage['observation']['fighters']!=first['observation']['fighters'] or
                any(type(stage.get(k))!=int or not 1<=stage[k]<=2048 for k in ('width','height')) or
                stage['format'] not in (21,22,36) or not s.get('vertex_input') or not s.get('vertex_program')):
            raise ValueError('unsupported post-color stage evidence')
        sources=stage.get('texture_sources',[])
        bindings={name:int(slot) for name,slot in re.findall(r'^//\s+(\w+)\s+s(\d+)\s+1\s*$',s['assembly'],re.M)}
        lookups=[bindings[name] for name in ('areaTex','searchTex') if i==12 and name in bindings]
        if not isinstance(sources,list) or not 1<=len(sources)<=16 or any(
                x['surface'] not in outputs and x['slot'] not in lookups for x in sources):
            raise ValueError('post-color dependency is not a prior private output')
        slots=[x['slot'] for x in sources]
        if len(set(slots))!=len(slots) or any(type(x)!=int or not 0<=x<16 for x in slots):
            raise ValueError('invalid post-color sampler slots')
        names=set(re.findall(r'^//\s+(\w+)\s+[cs]\d+\s+\d+\s*$',s['assembly'],re.M))
        allowed=({'InTexture','TextureComponentReplicateAlpha'},{'SceneColorTexture'},
                {'SourceTexture'},{'SceneColorTexture','SourceTexture'})
        smaa_names={11:{'SceneColorTexture','SMAAParamA'},12:{'edgesTex','areaTex','searchTex','SMAAParamA'},
            13:{'SceneColorTexture','blendTex','SMAAParamA'}}
        if names not in allowed and not (smaa and i in smaa_names and names==smaa_names[i]):
            raise ValueError('unexpected post-color program')
        if i>=11 and (names!=smaa_names[i] or stage['format']!=21):raise ValueError('unsupported SMAA stage')
        if i==12 and (len(lookups)!=2 or set(slots)!=set(bindings.values()) or any(
                x['surface'] in outputs for x in sources if x['slot'] in lookups)):
            raise ValueError('SMAA lookup must be distinct from scene outputs')
        if i==9 and names!={'SceneColorTexture','SourceTexture'}:raise ValueError('missing native composite')
        result.append(dict(shader=s['shader'],target=stage['surface'],original_hex=(folder/s['file']).read_bytes().hex(),
            vertex_hex=s['vertex_program']['code_hex'],vertex_shader=s['vertex_program']['shader'],
            width=stage['width'],height=stage['height'],format=stage['format'],
            sources=sources,lookup_slots=lookups))
        if projection:
            v=s['vertex_program'];q=s['vertex_input']
            declaration=bytes.fromhex(q['declaration_hex'])
            if (q['stride'] not in (32,48) or declaration[:16]!=bytes.fromhex('00000000030000000000100001000500')):
                raise ValueError('normalized post-color requires observed float4 position/float2 UV declaration')
            vb={name:(int(r),int(count)) for name,r,count in re.findall(r'^//\s+(\w+)\s+c(\d+)\s+(\d+)\s*$',v['assembly'],re.M)}
            pb={name:(int(r),int(count)) for name,r,count in re.findall(r'^//\s+(\w+)\s+c(\d+)\s+(\d+)\s*$',s['assembly'],re.M)}
            if not set(vb)<={'Transform','PSParam1','RenderTargetSizeRCP','SMAAParamA'}:
                raise ValueError('unknown normalized vertex uniforms')
            if any(count!=(4 if name=='Transform' else 1) for name,(_,count) in vb.items()):
                raise ValueError('unsupported normalized vertex uniform size')
            small=stage['format']==36
            if small and (stage['width']!=first['width']//4+2 or stage['height']!=first['height']//4+2):
                raise ValueError('unverified normalized downsample dimensions')
            result[-1].update(private_width=projection['width']//4+2 if small else projection['width'],
                private_height=projection['height']//4+2 if small else projection['height'],
                declaration_hex=q['declaration_hex'],vertex_uniforms={n:r for n,(r,_) in vb.items()},
                pixel_smaa=pb.get('SMAAParamA',(None,))[0])
        outputs.add(stage['surface'])
    if (not smaa and (result[-1]['width']!=first['width'] or result[-1]['height']!=first['height']) or
            smaa and (result[-1]['width']>first['width'] or result[-1]['height']>first['height'])):
        raise ValueError('post-color output dimensions changed')
    return result


def trace(probe,candidate_path,seconds,gate_receipt=None,expire=False,input_path=None,plan_path=None,oracle='movement',scalar_path=None,combat_path=None,capture=False,trace_draws=False,capture_passes=False,suppress_path=None,inspect_shaders=False,layer_path=None,layer_steps=None,layer_presentations=None,inspect_transforms=False,normalize=False,settle=False,inspect_screen=False,hdr=False,grade_path=None,source_view=False,source_color=False,capture_screen_stages=False,post_color_path=None,smaa=False,renewable=False,transactions=False,transaction_loss=False,transaction_hold=13,reset_observation=False,stream_frames=0,stream_duration=False,frame_tap=False,frame_control=False,observe_contact=False,dispatch_path=None,suppress_contact_path=None,callees_path=None,controlled_slot=0,external_pair_step=0,external_damage=0,external_host_stop=False,external_guard=False,external_pair_control=False,external_guard_commit=False,external_ko=False):
    if type(frame_control)!=bool or frame_control and (not input_path or plan_path):
        raise ValueError('source control requires exclusive native input profile without a local plan')
    if frame_control:frame_tap=True
    if type(frame_tap)!=bool or frame_tap and (not stream_frames or stream_duration or transaction_loss):
        raise ValueError('frame tap requires exclusive fixed-count rolling verification')
    if type(stream_duration)!=bool or stream_duration and (stream_frames or plan_path or input_path or not 28<=seconds<=120):
        raise ValueError('duration stream requires exclusive neutral 28..120 second verification')
    if stream_duration and transaction_loss and seconds<60:
        raise ValueError('duration controller-loss check requires 60..120 seconds')
    if type(external_pair_step)!=int or not 0<=external_pair_step<=85 or external_pair_step and (not suppress_contact_path or controlled_slot!=1):
        raise ValueError('external pair experiment requires bounded suppressed second-player contact')
    if type(external_damage)!=int or not 0<=external_damage<=419 or external_damage and not external_pair_step:
        raise ValueError('external damage requires a bounded requested native pair')
    if type(external_host_stop)!=bool or external_host_stop and not external_pair_step:raise ValueError('host stop experiment requires a requested native pair')
    if type(external_guard)!=bool or external_guard and (controlled_slot!=1 or oracle!='contact' or external_damage or external_pair_step and not external_host_stop):raise ValueError('guard experiment requires second-player contact without damage override')
    if type(external_pair_control)!=bool or external_pair_control and (not external_guard or not external_pair_step):raise ValueError('no-call control requires the guard experiment')
    if type(external_guard_commit)!=bool or external_guard_commit and (not external_guard or not external_pair_step or external_pair_control):raise ValueError('caller commit requires the requested guard experiment')
    if type(external_ko)!=bool or external_ko and (not external_pair_step or not external_host_stop or external_guard or external_damage or external_pair_control):raise ValueError('KO probe requires one unguarded host-freeze native pair without damage override')
    if type(controlled_slot)!=int or controlled_slot not in (0,1):raise ValueError('invalid controlled native slot')
    if controlled_slot and (oracle!='contact' or not plan_path or not combat_path or not gate_receipt or capture or layer_path or stream_frames or stream_duration or suppress_contact_path and not external_pair_step):
        raise ValueError('second-player input requires an exclusive original contact validation scene')
    if suppress_contact_path and (not dispatch_path or not plan_path or oracle!='contact'):
        raise ValueError('source contact suppression requires an original dispatch proof and bounded contact plan')
    if callees_path and suppress_contact_path:raise ValueError('callee observation requires original source contacts')
    if dispatch_path or callees_path:observe_contact=True
    if type(observe_contact)!=bool or observe_contact and (not gate_receipt or not combat_path or stream_frames or stream_duration):
        raise ValueError('contact observation requires a bounded scalar/source gate')
    stream_mode=bool(stream_frames or stream_duration)
    if type(stream_frames)!=int or not 0<=stream_frames<=120:
        raise ValueError('stream check steps must be 0..120')
    if stream_mode and (not transactions or not combat_path or transaction_loss and not stream_duration or capture_passes or capture_screen_stages or inspect_screen or inspect_shaders or inspect_transforms):
        raise ValueError('stream check requires owned transactions with age guard and no inventory capture')
    if renewable and (not expire or not gate_receipt or plan_path or capture or trace_draws or layer_path):
        raise ValueError('renewable trace requires an exclusive gate recovery experiment')
    if transactions and (renewable or expire or not gate_receipt or not layer_path or not normalize or not settle or layer_steps not in (None,'0,1,2,3')):
        raise ValueError('transaction trace requires four consecutive normalized settled frames')
    if transactions and plan_path and (oracle not in (('render-position','render-attack') if stream_frames else ('render-position',)) or not combat_path):
        raise ValueError('non-neutral transactions require age ownership and the positioning oracle')
    if transaction_loss and not transactions: raise ValueError('transaction loss requires transaction control')
    if not 13<=transaction_hold<=45 or transaction_hold!=13 and (not transactions or transaction_loss):
        raise ValueError('extended hold requires a normal transaction check; hold must be 13..45 seconds')
    if reset_observation and (not renewable or not combat_path or seconds!=60):
        raise ValueError('reset observation requires the bounded scalar/renewable experiment')
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
        state['ownership_age_field']=derived['age_candidate']
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
    if (capture or trace_draws) and (not gate_options or expire): raise ValueError('render diagnostics require the bounded stepping experiment')
    if capture_passes and not trace_draws: raise ValueError('render-pass capture requires a draw trace')
    if capture_screen_stages and (not capture_passes or not inspect_screen or layer_path or plan_path or suppress_path):
        raise ValueError('screen-stage capture requires exclusive neutral pass/screen inspection')
    if hdr and (not layer_path or not normalize or settle or plan_path or layer_presentations):
        raise ValueError('HDR diagnostic requires normalized neutral layer without readiness/input-plan claims')
    if source_view and (not grade_path or normalize or settle or plan_path or inspect_transforms or hdr or layer_presentations or layer_steps):
        raise ValueError('source-view comparison requires exclusive neutral graded capture without normalization/readiness claims')
    if source_color and not source_view:raise ValueError('full source color diagnostic requires original-camera comparison')
    if post_color_path and (not (source_view or normalize) or source_color):raise ValueError('private post-color replay requires private original-camera or normalized grading')
    if smaa and not post_color_path:raise ValueError('SMAA requires private post-color replay')
    if grade_path and (not layer_path or not (normalize or source_view) or hdr):raise ValueError('native grading requires normalized or diagnostic source-view A8 output')
    if inspect_screen and (not trace_draws or not capture or suppress_path and not layer_path or plan_path):
        raise ValueError('screen shader observation requires exclusive neutral capture/draw trace')
    identity=None
    if inspect_shaders and not suppress_path: raise ValueError('mesh shader inspection requires local buffer identity')
    if suppress_path:
        identity=json.loads(suppress_path.read_text())
        if (not trace_draws or not capture or capture_passes and not (layer_path and inspect_screen) or (plan_path and (not layer_path or not oracle.startswith('render-'))) or expire or identity.get('pid')!=state['pid'] or
                identity.get('exe_sha256')!=SIGN_HASH or not identity.get('geometry_match_verified') or
                identity.get('actor_identity_verified') is not False or identity.get('isolated_rgba') is not False or
                set(identity.get('parts',{}))!={'body','head','weapon'} or
                not re.fullmatch('0x[0-9a-f]{1,8}',identity.get('device','')) or
                any(set(part)!={'index_buffer','vertex_buffer'} or
                    any(not re.fullmatch('0x[0-9a-f]{1,8}',v) or v=='0x0' for v in part.values())
                    for part in identity['parts'].values())):
            raise ValueError('requires bounded same-session unaccepted mesh identity, capture and draw trace')
    layer=None
    if layer_path:
        if not identity or inspect_shaders: raise ValueError('layer capture requires exclusive mesh identity')
        layer=layer_programs(layer_path,state,identity,normalize)
        layer['hdr']=hdr or bool(grade_path)
        layer['source_view']=source_view
        layer['source_color']=source_color
        if grade_path:layer['grade']=grading_programs(grade_path,state)
        if post_color_path:layer['post_color']=post_color_programs(post_color_path,state,layer['grade'],smaa,layer.get('projection'))
        layer['smaa']=smaa
        if source_color and (not layer['grade']['vertex_original_hex'] or not layer['grade']['source_quad_observed']):
            raise ValueError('source color replay requires inspected native vertex/quad inputs')
        layer['capture_steps']=capture_steps(layer_steps or '0,1,2,3')
        layer['presentations']=capture_presentations(layer_presentations or '3',layer['capture_steps'])
        layer['inspect_transforms']=inspect_transforms
        layer['settle']=settle
        if settle and (not normalize or inspect_transforms or layer_presentations or len(layer['capture_steps'])>4 or oracle=='render-settle'):
            raise ValueError('settled rendering requires normalized projection, up to four steps and no fixed samples/transform inspection')
        if len(layer['presentations'])>1 and oracle!='render-settle': raise ValueError('repeated render captures require the settling oracle')
    elif layer_steps or layer_presentations or oracle.startswith('render-'): raise ValueError('selected render oracle requires a private layer')
    if oracle.startswith('render-') and not plan_path and not frame_control: raise ValueError('render oracle requires a named input plan')
    if inspect_transforms and not layer: raise ValueError('vertex observation requires a private layer')
    if normalize and not layer: raise ValueError('normalized projection requires a private layer')
    if settle and not layer: raise ValueError('settled rendering requires a private layer')
    source_window=None
    if capture or trace_draws:
        # Rendering needs an unminimized window, but never requires desktop keyboard focus.
        shell=shutil.which('pwsh') or 'powershell.exe'
        source_window=json.loads(subprocess.check_output([shell,'-NoProfile','-ExecutionPolicy','Bypass',
            '-File',str(ROOT/'tools/xrd-source-window.ps1'),'-Action','restore','-SourceProcessId',str(state['pid'])],text=True,timeout=10))
        if source_window['pid']!=state['pid'] or source_window['minimized']:
            raise ValueError('source render window/session mismatch')
    plan=None
    if plan_path:
        if not gate_options or not input_profile or expire or plan_path.stat().st_size>16384:
            raise ValueError('bounded input plan requires a native gate and validated input ingress')
        plan=(punch_plan if stream_frames and oracle=='render-attack' else position_plan if stream_frames or oracle=='positioning' else input_plan)(json.loads(plan_path.read_text()),stream_frames or (3 if transactions else None))
        if external_pair_step>len(plan):raise ValueError('external pair step exceeds the bounded input plan')
        if layer and (not oracle.startswith('render-') or not stream_frames and layer['capture_steps'][-1]!=len(plan)):
            raise ValueError('private render plan must use a render oracle and capture its final requested step')
    sys.path.insert(0,str(ROOT/'local-cache/xrd-tools/frida/python'))
    import frida
    if frida.__version__!='17.22.2': raise ValueError('run gather-xrd-instrumentation.py for pinned Frida')
    out=probe/('boundary-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    out.mkdir();(out/'candidate.json').write_text(json.dumps(candidate,indent=2))
    if input_profile: (out/'input-profile.json').write_text(json.dumps(input_profile,indent=2))
    if combat_profile: (out/'combat-profile.json').write_text(json.dumps(combat_profile,indent=2))
    if plan: (out/'input-plan.json').write_text(json.dumps(plan,indent=2))
    messages=queue.Queue(maxsize=256 if stream_duration else 8192);overflow=threading.Event()
    def receive(message,data):
        try: messages.put_nowait((message,data,time.perf_counter()))
        except queue.Full: overflow.set()
    errors=[];records=[];states=[];presents=[];inputs=[];diagnostics=[];captures=[];draws=[];passes=[];shaders=[];vertices=[];screens=[];layers=[];transforms=[];scene_packets=[];layer_packets=[];render_bytes=0;pass_bytes=0;session=script=None;detached=False;requests=0;cleanup_receipt=None;automatic_restore=False
    started=time.perf_counter();started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat();completed=0;next_request=.5 if plan else 1;request_log=[]
    per_step=2 if settle else len(layer['presentations']) if layer else 0
    external_events=[]
    callee_calls=[]
    dispatches=[]
    contacts=[]
    contact=None
    if observe_contact:
        entry=unique([v for v in receipt['loaded_candidates'] if v['name']=='hit_detection'],'native contact signature')
        match=unique(entry['matches'],'native contact entry')
        at=match['candidate_rva']-state['code_rva']
        if not 0<at<at+32<=len(code) or code[at-1]!=0xcc or code[at:at+6]!=bytes.fromhex('81ecdc000000'):
            raise ValueError('native contact prologue disagrees with inspected SIGN code')
        contact=dict(rva=match['candidate_rva'],before=code[at:at+32].hex())
        if callees_path:
            if callees_path.stat().st_size>65536:raise ValueError('contact callee inventory too large')
            contact['callees']=contact_callees(code,state['code_rva'],json.loads(callees_path.read_text()))
        if dispatch_path:
            dispatch_local=json.loads(dispatch_path.read_text())
            contact['dispatch']=dispatch_candidate(code,state['code_rva'],dispatch_local,match['candidate_rva'])
            if external_guard_commit or external_ko:contact['dispatch']['caller_result']=dispatch_result_fields(code,state['code_rva'],dispatch_local)
            if suppress_contact_path:
                proof=json.loads((suppress_contact_path/'inspection.json').read_text())
                if proof.get('pid')!=state['pid']:raise ValueError('source dispatch proof session changed')
                contact['dispatch']['owner']=dispatch_ownership(code,state['code_rva'],contact['dispatch'],proof,gate_options['thread'])
    stream_receipts=[];latest_layer=None;controller_lost_at=None
    audit=RollingAudit() if stream_duration else None
    credit_until=seconds-(19 if transaction_loss else 5)
    if audit:
        records=audit.records;states=audit.states;stream_receipts=audit.frames
        presents=deque(maxlen=64);diagnostics=deque(maxlen=16)
    with ReadOnlyProcess(state['pid'],EXE) as process:
        tap=None
        def unchanged():
            base,size=process.module_base()
            return base==state['module_base'] and size==receipt['image_size'] and hashlib.sha256(process.read(base+state['code_rva'],state['code_size'])).hexdigest()==state['code_sha256']
        if not unchanged(): raise ValueError('source session/code changed; run a fresh probe')
        phase='preflight';native_start_attempted=False;clock_preflight=None;abi=None
        try:
            if frame_tap:
                tap=FrameTap(out/'frame-tap-ready.json','ggxrd-sign',frame_control)
                print('Diagnostic source control:' if frame_control else 'Read-only frame tap:',out/'frame-tap-ready.json',flush=True)
                tap.await_subscriber() # No native gate is installed while awaiting the observer.
            if gate_options:
                clock_preflight=read_clock(process,state,candidate)
                if not clock_preflight['advancing']: raise ValueError('original source clock is held or discontinuous; resume offline training before stepping')
            started=time.perf_counter();phase='attach'
            session=bounded_call(frida,lambda:frida.attach(state['pid']))
            phase='load'
            source=(ROOT/'tools/xrd-sign-boundary.js').read_text()
            if layer or inspect_shaders or inspect_screen: source+='\n'+(ROOT/'tools/xrd-sign-layer.js').read_text()
            if grade_path: source+='\n'+(ROOT/'tools/xrd-sign-grade.js').read_text()
            abi=validate_device_calls([source],(ROOT/'local-cache/msys64/mingw64/include/d3d9.h').read_text())
            script=session.create_script(source)
            script.on('message',receive);bounded_call(frida,script.load)
            settings=dict(external_ko=external_ko,external_guard_commit=external_guard_commit,external_pair_control=external_pair_control,external_guard=external_guard,external_host_stop=external_host_stop,external_damage=external_damage,external_pair_step=external_pair_step,contact=contact,state=state,candidate=candidate,image_size=receipt['image_size'],gate=gate_options,input=input_profile,capture=capture,trace_draws=trace_draws,capture_passes=capture_passes,capture_screen_stages=capture_screen_stages,suppress_draws=identity,inspect_mesh_shaders=inspect_shaders,inspect_screen_shaders=inspect_screen,layer=layer,renewable=renewable or transactions,transactions=transactions,reset_observation=reset_observation)
            settings['streaming']=stream_mode
            phase='start';native_start_attempted=True
            print(bounded_call(frida,lambda:script.exports_sync.start(settings)),flush=True)
            phase='observe'
            started=time.perf_counter()
            next_heartbeat=0
            controller_lost_at=None
            if transactions: next_request=transaction_hold
            with (out/'state.jsonl').open('w',encoding='utf-8') as log:
                while time.perf_counter()-started<seconds:
                    if overflow.is_set(): raise ValueError('instrumentation queue overflow')
                    elapsed=time.perf_counter()-started
                    frames_complete=(completed==stream_frames and len(stream_receipts)==stream_frames+1) if stream_frames else transactions and completed==3 and len(layers)==8 and len(scene_packets)==8
                    if audit:frames_complete=elapsed>=credit_until and requests==completed and audit.frame_count==completed+1
                    if frames_complete and transaction_loss and controller_lost_at is None: controller_lost_at=elapsed
                    if controller_lost_at is None and (transactions or renewable and elapsed<seconds-14) and elapsed>=next_heartbeat:
                        heartbeat=bounded_call(frida,script.exports_sync.heartbeat)
                        if stream_mode:diagnostics.append(dict(elapsed=elapsed,heartbeat=heartbeat))
                        next_heartbeat=elapsed+1
                    if not stream_mode and layer and plan and completed==len(plan) and len(layers)==len(layer['capture_steps'])*per_step and len(scene_packets)==len(layers):
                        break
                    if frames_complete and not transaction_loss: break
                    image_ready=not layer or requests not in layer['capture_steps'] or (
                        sum(c['request_index']==requests for c in layers)==per_step and
                        sum(m['request_index']==requests for m,_,_ in scene_packets)==per_step)
                    image_ready &= not capture_screen_stages or bool(scene_packets)
                    if stream_mode: image_ready=bool(stream_receipts) and stream_receipts[-1]['request_index']==requests
                    if frame_control and requests<stream_frames and requests==completed and image_ready and elapsed>=next_request:
                        packet=tap.poll_step()
                        if packet is not None:
                            allowed={'punch'} if oracle=='render-attack' else {'left','right','forward','back'}
                            if set(packet['input'])-allowed:raise ValueError('source control input is outside the selected oracle')
                            if requests==0 and not input_scene_ready(states[0],'render-position',[packet]):
                                raise ValueError('source control requires grounded idle Sol/opponent at safe spacing')
                            mask=input_mask(packet['input'],states[-1][0]['facing_left'],packet['accept_input'])
                            sol,opponent=states[-1]
                            if oracle=='render-attack' and (sol['y_raw'] or abs(sol['x_raw']-opponent['x_raw'])<350000):
                                raise ValueError('standing normal control requires grounded safe source spacing')
                            inward=bool(mask&(4 if sol['facing_left'] else 8))
                            if inward and abs(sol['x_raw']-opponent['x_raw'])<350000:
                                raise ValueError('source control refuses unverified close-range contact')
                            counter=records[-1]['after']
                            bounded_call(frida,lambda:script.exports_sync.step([mask,0],counter))
                            request_log.append(dict(step=requests+1,mask=mask,input=packet['input'],accept_input=packet['accept_input']))
                            requests+=1;next_request=elapsed+.03
                    elif plan and requests<len(plan) and requests==completed and image_ready and time.perf_counter()-started>=next_request:
                        if requests==0 and (not states or not input_scene_ready(states[0],oracle,plan,controlled_slot)):
                            raise ValueError('input oracle requires grounded idle Sol/opponent within its scene distance bounds')
                        packet=plan[requests];mask=input_mask(packet['input'],states[-1][controlled_slot]['facing_left'],packet['accept_input'])
                        counter=records[-1]['after'] if transactions else None
                        masks=[0,0];masks[controlled_slot]=mask
                        if external_guard and (external_pair_step or 39)-5<=requests<=(external_pair_step or 39)+2:masks[0]=input_mask({'back':True},states[-1][0]['facing_left'])
                        bounded_call(frida,lambda:script.exports_sync.step(masks,counter));request_log.append(dict(step=requests+1,mask=mask,**packet));requests+=1
                        next_request=time.perf_counter()-started+.03+packet['hold_ms']/1000
                    elif not frame_control and not plan and gate_options and not expire and (elapsed<credit_until if audit else requests<(stream_frames or 3)) and requests==completed and image_ready and time.perf_counter()-started>=next_request and (not capture_passes or draws):
                        counter=records[-1]['after'] if transactions else None
                        bounded_call(frida,lambda:script.exports_sync.step([0,0],counter));requests+=1;next_request=time.perf_counter()-started+(.03 if stream_mode else 1)
                    if expire and elapsed>(seconds-1.5 if renewable else 12.5) and not automatic_restore:
                        automatic_restore=unchanged()
                    if controller_lost_at is not None and elapsed-controller_lost_at>12.5 and not automatic_restore:
                        automatic_restore=unchanged()
                    try: message,data,wall=messages.get(timeout=.1)
                    except queue.Empty: continue
                    if message['type']=='send' and message['payload'].get('kind')=='present':
                        presents.append(message['payload']);continue
                    if message['type']=='send' and message['payload'].get('kind')=='input':
                        inputs.append(message['payload']);continue
                    if message['type']=='send' and message['payload'].get('kind')=='external-pair-result':
                        if not external_pair_step or external_events:raise ValueError('unrequested/replayed external native pair result')
                        external_events.append(message['payload']);continue
                    if message['type']=='send' and message['payload'].get('kind')=='native-contact-callee':
                        if not callees_path or len(callee_calls)>=256:raise ValueError('unbounded/unrequested contact callee observation')
                        callee_calls.append(message['payload']);continue
                    if message['type']=='send' and message['payload'].get('kind')=='native-dispatch-observation':
                        if not dispatch_path or len(dispatches)>=256:raise ValueError('unbounded/unrequested native dispatch observation')
                        dispatches.append(message['payload']);continue
                    if message['type']=='send' and message['payload'].get('kind')=='native-contact-observation':
                        if not observe_contact or len(contacts)>=256:raise ValueError('unbounded/unrequested native contact observation')
                        contacts.append(message['payload']);continue
                    if message['type']=='send' and message['payload'].get('kind')=='draw-trace':
                        if len(draws)>=2: raise ValueError('unbounded draw intervals')
                        draws.append(message['payload']);continue
                    if message['type']=='send' and message['payload'].get('kind')=='screen-shader':
                        if not inspect_screen or len(screens)>=32: raise ValueError('screen shader observation limit')
                        native=screen_packet(message['payload'],data)
                        name=f'screen-{len(screens)+1:02}.bin';(out/name).write_bytes(data)
                        screens.append(native|dict(file=name));continue
                    if message['type']=='send' and message['payload'].get('kind')=='layer-color-boundary':
                        native=message['payload']
                        if (not inspect_screen or not layer or len([d for d in diagnostics if d.get('kind')=='layer-color-boundary'])>=8 or
                                native.get('observation_only') is not True or native.get('native_grading_replayed') is not False or
                                type(native.get('private_draws'))!=int or not 1<=native['private_draws']<=8192 or
                                native.get('request_index') not in layer['capture_steps']):
                            raise ValueError('invalid private color boundary observation')
                        diagnostics.append(native);continue
                    if message['type']=='send' and message['payload'].get('kind')=='mesh-shader':
                        native=message['payload']
                        if len(shaders)>=32 or not 8<=len(data)<=65536 or len(data)%4 or native['code_size']!=len(data):
                            raise ValueError('invalid shader readback')
                        name=f'shader-{len(shaders)+1:02}.bin';(out/name).write_bytes(data)
                        shaders.append(native|dict(file=name,sha256=hashlib.sha256(data).hexdigest()));continue
                    if message['type']=='send' and message['payload'].get('kind')=='mesh-vertex-shader':
                        native=message['payload']
                        if (not inspect_shaders or len(vertices)>=32 or not 8<=len(data)<=65536 or len(data)%4 or
                                native['code_size']!=len(data) or native.get('read_only') is not True or
                                not isinstance(native.get('assembly'),str) or not 1<=len(native['assembly'])<=131072):
                            raise ValueError('invalid vertex shader inspection')
                        name=f'vertex-{len(vertices)+1:02}.bin';(out/name).write_bytes(data)
                        vertices.append(native|dict(file=name,sha256=hashlib.sha256(data).hexdigest()));continue
                    if message['type']=='send' and message['payload'].get('kind')=='mesh-layer-skipped':
                        diagnostics.append(message['payload']);continue
                    if message['type']=='send' and message['payload'].get('kind')=='layer-readiness':
                        if stream_mode: continue
                        if not settle or len(diagnostics)>=128: raise ValueError('readiness diagnostic limit')
                        diagnostics.append(message['payload']);continue
                    if message['type']=='send' and message['payload'].get('kind')=='layer-transform':
                        if not inspect_transforms or len(transforms)>=8: raise ValueError('vertex observation limit')
                        native=message['payload'];code,constants,analysis=transform_packet(native,data)
                        transforms.append((native|analysis,code,constants));continue
                    if message['type']=='send' and message['payload'].get('kind')=='render-pass':
                        pass_bytes+=len(data)
                        if len(passes)>=24 or pass_bytes>128<<20: raise ValueError('unbounded intermediate capture')
                        passes.append((message['payload'],data));continue
                    if message['type']=='send' and message['payload'].get('kind') in ('render-layer','render-hdr-layer'):
                        native=message['payload']
                        if stream_mode:
                            pixels,_=render_pixels(native,data)
                            coverage=layer_pixels(native,pixels)
                            observation=observe(CapturedMemory(native['segments'],data[:native['state_size']]),state)
                            matches=[s for r,s in zip(records,states) if r['after']==native['counter']]
                            if (native['request_index']!=(audit.frame_count if audit else len(stream_receipts)) or native['request_index']!=completed or
                                not matches or any(s!=observation['fighters'] for s in matches) or
                                native.get('frame_readiness_candidate') is not True or native.get('identical_native_pixels') is not True or
                                native.get('source_graphics_state_verified') is not True or coverage['touches_target_edge'] or
                                native.get('normalized_projection') is not True or native.get('canonical_right_facing') is not True or
                                native.get('source_facing_left')!=observation['fighters'][0]['facing_left'] or native.get('skipped_draws_total')!=0):
                                raise ValueError('unlinked or unordered streaming frame')
                            frame_receipt=dict(counter=native['counter'],request_index=native['request_index'],
                                settled_pair=native['settled_pair'],raw_sha256=hashlib.sha256(pixels).hexdigest(),
                                coverage_bounds=coverage['native_coverage_bounds'],
                                source_x=observation['fighters'][0]['x_raw'],source_y=observation['fighters'][0]['y_raw'],
                                source_facing_left=observation['fighters'][0]['facing_left'])|body_geometry(native)
                            if audit:audit.frame(frame_receipt)
                            else:stream_receipts.append(frame_receipt)
                            if tap:tap.publish(native,pixels,observation['fighters'])
                            latest_layer=(native,data,observation)
                            continue
                        if native['kind']=='render-hdr-layer':
                            if not hdr or not 1<=native['state_size']<=0x80000: raise ValueError('unexpected/unbounded HDR layer')
                        else: render_pixels(native,data)
                        if len(layers)>=len(layer['capture_steps'])*per_step: raise ValueError('private layer capture limit')
                        render_bytes+=len(data)
                        if render_bytes>128<<20: raise ValueError('render packet byte limit')
                        observation=observe(CapturedMemory(native['segments'],data[:native['state_size']]),state)
                        layer_packets.append((native,data,observation))
                        layers.append(dict(request_index=native['request_index']));continue
                    if message['type']=='send' and message['payload'].get('kind')=='render':
                        native=message['payload'];render_pixels(native,data)
                        render_bytes+=len(data)
                        if len(scene_packets)>=8 or render_bytes>128<<20: raise ValueError('source render packet limit')
                        observation=observe(CapturedMemory(native['segments'],data[:native['state_size']]),state)
                        scene_packets.append((native,data,observation));continue
                    if (expire or transaction_loss) and message['type']=='send' and message['payload'].get('phase')=='watchdog':
                        diagnostics.append(message['payload']);continue
                    if message['type']!='send' or message['payload'].get('kind')!='frame':
                        errors.append(message)
                        raise ValueError('native instrumentation error; stopping before more steps')
                    native=message['payload']
                    observation=observe(CapturedMemory(native.pop('segments'),data),state)
                    observation.update(boundary=native,wall_seconds=wall-started,boundary_aligned=True)
                    if audit:audit.record(native,observation['fighters'])
                    else:
                        log.write(json.dumps(observation,separators=(',',':'))+'\n')
                        records.append(native);states.append(observation['fighters'])
                    if native['executed']: completed+=1
        except Exception as error:
            # RPC rejection can arrive before the loop reads its queued native diagnostic.
            while True:
                try: message,_,_=messages.get_nowait()
                except queue.Empty: break
                if message.get('type')=='send' and message.get('payload',{}).get('kind')=='error':
                    errors.append(message)
            errors.append(dict(controller_error=repr(error),controller_phase=phase))
        finally:
            if tap:tap.close()
            # A failed RPC must not prevent script/session teardown from removing the hook.
            if script is not None:
                if source_window:
                    try:
                        status=json.loads(subprocess.check_output([shell,'-NoProfile','-ExecutionPolicy','Bypass',
                            '-File',str(ROOT/'tools/xrd-source-window.ps1'),'-Action','restore','-SourceProcessId',str(state['pid'])],text=True,timeout=10))
                        if status['pid']!=state['pid']: raise ValueError('cleanup source window/session changed')
                        diagnostics.append(dict(phase='cleanup-window',**status))
                    except Exception as error: errors.append(dict(cleanup_window_error=str(error)))
                try:
                    for _ in range(20):
                        cleanup_receipt=bounded_call(frida,script.exports_sync.stop)
                        if not cleanup_receipt.get('pending_renderer_stop'): break
                        time.sleep(.05)
                    else: raise ValueError('renderer did not complete scheduled teardown')
                except Exception as error: errors.append(dict(cleanup_error=repr(error)))
                try: bounded_call(frida,script.unload)
                except Exception as error: errors.append(dict(cleanup_error=repr(error)))
            try:
                if session is not None: bounded_call(frida,session.detach)
                detached=True
            except Exception as error: errors.append(dict(cleanup_error=repr(error)))
        try: restored=unchanged()
        except (OSError,ValueError) as error:
            restored=False;errors.append(dict(cleanup_error='source memory unavailable after teardown: '+str(error)))
        if cleanup_receipt and gate_options:
            cleanup_receipt['render_code_restored_inside_rpc']=cleanup_receipt.get('render_code_restored',False)
            try: cleanup_receipt['render_code_restored']=render_restored(process,cleanup_receipt,detached)
            except (ValueError,OSError) as error:
                cleanup_receipt['render_code_restored']=False
                errors.append(dict(cleanup_error=str(error)))
            cleanup_receipt['render_verification_after_detach']=detached
    if not restored: errors.append(dict(cleanup_error='loaded source code was not restored'))
    if fingerprint(EXE)!=SIGN_HASH: errors.append(dict(source_error='source executable fingerprint changed'))
    if stream_mode:
        gaps=audit.gaps if audit else sum(b['before']!=a['after'] for a,b in zip(records,records[1:]))
        frames_received=audit.frame_count if audit else len(stream_receipts)
        counts_verified=requests==completed and frames_received==completed+1 and (completed>=4 if audit else completed==stream_frames)
        if not counts_verified:
            errors.append(dict(stream_error='bounded check ended without all requested state/image transactions'))
        if tap and tap.sequence!=frames_received:
            errors.append(dict(stream_error='frame tap delivery was not acknowledged'))
        recovery=None
        if audit and transaction_loss:
            recovery=lease_check(records,presents,diagnostics,automatic_restore)
            if not all(recovery[k] for k in ('lease_resumed','hard_lifetime_removed_hook')):
                errors.append(dict(stream_error='duration stream controller-loss recovery not verified'))
        stream_input=None
        if plan or frame_control:
            stream_input=input_check(records,states,inputs,request_log)
            executed=[r for r in records if r['executed']]
            stream_input['requested_masks_linked']=len(executed)==len(request_log)==stream_frames and all(
                r['requested_inputs']==[q['mask'],0] for r,q in zip(executed,request_log))
            stream_input['directions_verified']=all(not any(q['mask']&bit for q in request_log) or stream_input[key]
                for bit,key in ((4,'walk_left'),(8,'walk_right')))
            linked=all(stream_input[k] for k in ('source_history_linked','requested_masks_linked','directions_verified','opponent_neutral','grounded_at_end'))
            if oracle=='render-attack':
                health=lambda f:f['scalar_observations']['health_candidate']
                stream_input['source_health_unchanged']=all([health(f) for f in s]==[health(f) for f in states[0]] for s in states)
                stream_input['passed']=linked and stream_input['standing_punch_activations']>0 and stream_input['active_normal_steps']>0 and stream_input['source_health_unchanged'] and all(f[0]['y_raw']==0 for f in states)
            else:
                stream_input['passed']=linked and (stream_input['walk_left'] or stream_input['walk_right']) and all(f[0]['y_raw']==0 and f[0]['hit_count']==0 for f in states)
            (out/'requests.json').write_text(json.dumps(request_log,indent=2))
            (out/'input.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in inputs))
            if not stream_input['passed']:errors.append(dict(stream_error='rolling input oracle/history not verified'))
        passed=counts_verified and gaps==0 and not errors and detached and restored and bool(cleanup_receipt and cleanup_receipt.get('render_code_restored'))
        result=dict(passed=passed,requested_steps=requests,completed_steps=completed,frames=list(stream_receipts),frames_received=frames_received,
            continuity_gaps=gaps,errors=errors,detached=detached,loaded_code_restored=restored,native_start_attempted=native_start_attempted,
            cleanup=cleanup_receipt,diagnostics=list(diagnostics),seconds=seconds,elapsed=time.perf_counter()-started,
            source_capabilities_enabled=False,live_host_producer=False,
            rolling_image_retention=True,bounded_verification=True,input_check=stream_input,duration_check=stream_duration,
            retained_state_samples=len(records),total_state_samples=audit.samples if audit else len(records),
            controller_loss_recovery=recovery,controller_lost_at=controller_lost_at)
        if tap:result['frame_tap']=tap.receipt()
        if latest_layer:
            folder=out/'latest-layer';folder.mkdir()
            save_render(folder,*latest_layer)
        (out/'stream-check.json').write_text(json.dumps(result,indent=2))
        print('Rolling stream check:',passed,'steps',completed,'frames',frames_received,'retained states',len(records),';',out,flush=True)
        if not passed: raise RuntimeError('rolling stream check failed; see preserved receipt')
        return out
    # Encode RGB previews/histograms only after native hooks and session have been removed.
    captures=[save_render(out,native,data,observation) for native,data,observation in scene_packets]
    layers=[]
    if layer_packets:
        folder=out/'layers';folder.mkdir(exist_ok=True)
        layers=[(save_hdr_layer if hdr else save_render)(folder,native,data,observation) for native,data,observation in layer_packets]
    deltas=Counter(r['counter_delta'] for r in records)
    gaps=sum(b['before']!=a['after'] for a,b in zip(records,records[1:]))
    result=dict(schema=1,pid=state['pid'],samples=len(records),seconds=seconds,started_utc=started_utc,
        counter_deltas=dict(deltas),continuity_gaps=gaps,threads=sorted(set(r['thread'] for r in records)),
        this_deltas=sorted(set(r['this_delta'] for r in records)),depths=sorted(set(r['depth'] for r in records)),
        return_addresses=sorted(set(r['return_address'] for r in records)),errors=errors,
        observations_only=not bool(gate_options),boundary_experiment=bool(gate_options),boundary_aligned=True,temporary_code_interception=True,
        native_start_attempted=native_start_attempted,
        clock_preflight=clock_preflight,
        d3d_abi=abi,
        detached=detached,loaded_code_restored=restored,source_unchanged=fingerprint(EXE)==SIGN_HASH,
        native_tick_verified=False,atomic_native_frame=False,host_step=False,isolated_rgba=False,universal_contact=False)
    if source_window: result['source_window']=source_window
    if inspect_transforms:
        folder=out/'transforms';folder.mkdir()
        for i,(m,code,constants) in enumerate(transforms,1):
            name=f'transform-{i:02}'
            (folder/(name+'.vsbin')).write_bytes(code);(folder/(name+'.constants.bin')).write_bytes(constants)
            (folder/(name+'.asm')).write_text(m['assembly']);(folder/(name+'.json')).write_text(json.dumps(m,indent=2))
        try: result['transform_observation']=transform_changes(transforms)
        except ValueError as error:
            result['transform_observation']=dict(error=str(error),observations_only=True,transform_semantics_verified=False)
            errors.append(dict(transform_error=str(error)))
        if [(m['counter'],m['request_index'],m['presentation_index']) for m,_,_ in transforms]!=[(c['counter'],c['request_index'],c['presentation_index']) for c in layers]:
            errors.append(dict(transform_error='missing/unpaired body transform observation'))
        (folder/'inspection.json').write_text(json.dumps(result['transform_observation'],indent=2))
    if identity:
        (out/'draw-identity.json').write_text(json.dumps(identity,indent=2))
        result['diagnostic_mesh_suppression']=not inspect_shaders and not layer
        if not inspect_shaders and not layer and (not cleanup_receipt or cleanup_receipt.get('diagnostic_mesh_draws_skipped',0)<=0):
            errors.append(dict(filter_error='no matching mesh draws suppressed'))
        if inspect_shaders:
            (out/'mesh-shaders.json').write_text(json.dumps(shaders,indent=2));result['mesh_shaders']=len(shaders)
            (out/'mesh-vertices.json').write_text(json.dumps(vertices,indent=2));result['mesh_vertex_shaders']=len(vertices)
            if not shaders or not vertices: errors.append(dict(shader_error='missing matching mesh shaders'))
    if inspect_screen:
        (out/'screen-shaders.json').write_text(json.dumps(screens,indent=2))
        result['screen_shader_observations']=len(screens)
        if not screens: errors.append(dict(shader_error='missing screen shader observations'))
    if layer:
        for image in layers:
            try:
                if not hdr: image.update(save_layer_preview(out/'layers',image))
                (out/'layers'/Path(image['image']).with_suffix('.json')).write_text(json.dumps(image,indent=2))
            except ValueError as error: errors.append(dict(layer_pixels_error=str(error)))
        result['private_layer_captures']=len(layers)
        result['private_layer_complete']=False
        result['layer_check']=render_check(layers,records,states)
        result['private_layer_state_restored']=bool(layers) and all(c['source_graphics_state_verified'] for c in layers)
        if len(layers)<2 or not result['layer_check']['held_counter_state_linked'] or not result['private_layer_state_restored']:
            errors.append(dict(layer_error='missing/unlinked private layer or graphics-state restoration'))
    if observe_contact:
        result['external_pair_events']=external_events
        result['native_contact_observations']=contacts
        result['native_dispatch_observations']=dispatches
        result['native_contact_callee_observations']=callee_calls
        result['native_contact_observer_restored']=bool(cleanup_receipt and cleanup_receipt.get('contact_observer_code_restored'))
        if not result['native_contact_observer_restored']:errors.append(dict(contact_error='contact observer restoration failed'))
        try:
            result['native_contact_pair_check']=(external_contact_check(records,states,dispatches,contacts,external_events,external_pair_step,external_damage,external_host_stop,external_guard,external_ko) if external_pair_step else suppressed_contact_check(records,states,dispatches,contacts) if suppress_contact_path else guard_contact_check(records,states,contacts) if external_guard else contact_observations(records,states,contacts))
            if not result['native_contact_pair_check']['passed']:errors.append(dict(contact_error='native pair health change not verified'))
        except ValueError as error:errors.append(dict(contact_error=str(error)))
    if gate_options:
        result['gate_check']=gate_check(records,states,presents,len(plan) if plan else 3)
        result['controlled_update_step_verified']=not expire and all(result['gate_check'][k] for k in ('exact_steps','frozen_counter','frozen_observed_state','rendering_while_frozen')) and gaps==0 and not errors
        if expire: result['lease_check']=lease_check(records,presents,diagnostics,automatic_restore)
        if renewable:
            result['lease_check']['held_beyond_original_lifetime']=bool(records) and any(
                not r['executed'] and r['entered_ms']-records[0]['entered_ms']>=13000 for r in records)
            result['renewable_control_experiment']=True
        if transactions:
            result['transaction_check']=dict(
                exact_three_steps=requests==completed==3 and result['controlled_update_step_verified'],
                four_paired_frames=len(layers)==len(captures)==8,
                held_before_first_step=bool(records) and any(not r['executed'] and r['entered_ms']-records[0]['entered_ms']>=(transaction_hold-1)*1000 for r in records if r['after']==records[0]['after']),
                source_capabilities_enabled=False)
            if transaction_loss:
                recovery=lease_check(records,presents,diagnostics,automatic_restore)
                result['transaction_check'].update(controller_loss_resumed=recovery['lease_resumed'],
                    controller_loss_removed_hooks=recovery['hard_lifetime_removed_hook'])
        result['diagnostics']=diagnostics
        result['render_cleanup']=cleanup_receipt
        (out/'present.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in presents))
        if native_start_attempted and (not cleanup_receipt or not cleanup_receipt['render_code_restored']):
            errors.append(dict(cleanup_error='Direct3D presentation code restoration not verified'))
    if input_profile:
        (out/'input.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in inputs))
        result['input_observations']=len(inputs)
        result['input_slots']=dict(Counter(r['slot'] for r in inputs))
        result['input_values']=sorted(set(r['incoming'] for r in inputs))
        if gate_options and not expire:
            result['controlled_input_slot']=controlled_slot
            result['input_check']=input_check(records,states,inputs,request_log,controlled_slot)
            result['source_input_routing_verified']=result['controlled_update_step_verified'] and result['input_check']['source_history_linked'] and not errors
    if capture:
        result['render_check']=render_check(captures,records,states)
        if len(captures)<2 or not result['render_check']['held_counter_state_linked']:
            errors.append(dict(check_error='missing/unlinked native full-scene readback'))
    if settle and not plan:
        try: result['render_oracle']=settled_oracle('render-neutral',layers,captures,layer['capture_steps'])
        except ValueError as error: errors.append(dict(check_error=str(error)))
    if trace_draws:
        (out/'draw-trace.json').write_text(json.dumps(draws,indent=2))
        try: result['draw_check']=draw_check(draws)
        except ValueError as error:
            result['draw_check']=dict(passed=False,error=str(error));errors.append(dict(check_error=str(error)))
        (out/'draw-summary.json').write_text(json.dumps(result['draw_check'],indent=2))
    if capture_passes or source_view:
        pass_results=[]
        for native,data in passes:
            try:
                observation=observe(CapturedMemory(native['segments'],data[:native['state_size']]),state)
                pass_results.append(save_pass(out,native,data,observation))
            except ValueError as error: errors.append(dict(pass_error=str(error)))
        result['pass_captures']=len(pass_results)
        result['pass_bytes']=pass_bytes
        if not pass_results: errors.append(dict(pass_error='missing intermediate readbacks'))
    if plan:
        result['named_input_steps']=len(request_log)
        result['input_oracle']=oracle
        result['input_oracle_passed']=oracle_passed(oracle,result['input_check']) if oracle in ('positioning','movement','crossover') else False
        if oracle.startswith('render-'):
            try:
                result['render_oracle']=(settled_oracle(oracle,layers,captures,layer['capture_steps']) if settle else
                    settling_oracle(layers,captures,layer['capture_steps'],layer['presentations']) if oracle=='render-settle'
                    else render_oracle(oracle,layers,captures,layer['capture_steps']))
            except ValueError as error:
                result['render_oracle']=dict(passed=False,error=str(error));errors.append(dict(check_error=str(error)))
            result['input_oracle_passed']=result['render_oracle']['passed']
        if oracle=='contact' and combat_profile:
            try: result['contact_check']=(external_contact_check(records,states,dispatches,contacts,external_events,external_pair_step,external_damage,external_host_stop,external_guard,external_ko) if external_pair_step else suppressed_contact_check(records,states,dispatches,contacts) if suppress_contact_path else guard_contact_check(records,states,contacts) if external_guard else contact_check(records,states,controlled_slot))
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
    if capture: print('Render checks:',result['render_check'],flush=True)
    if trace_draws: print('Draw checks:',{k:v for k,v in result['draw_check'].items() if k not in ('groups','targets')},flush=True)
    if capture_passes: print('Intermediate captures:',result['pass_captures'],'bytes:',pass_bytes,flush=True)
    if errors or not records or not restored or not detached: raise RuntimeError('boundary trace failed; inspect local receipt')
    if expire and not all(result['lease_check'].values()): raise RuntimeError('gate lease recovery failed')
    if transactions and not all(result['transaction_check'][k] for k in ('exact_three_steps','four_paired_frames','held_before_first_step')):
        raise RuntimeError('source transaction experiment failed')
    if transaction_loss and not all(result['transaction_check'][k] for k in ('controller_loss_resumed','controller_loss_removed_hooks')):
        raise RuntimeError('rendering transaction controller-loss recovery failed')
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
    p.add_argument('--renewable-check',action='store_true',help='with --gate: renew without steps for 14 seconds, then verify controller-loss recovery; no private rendering')
    p.add_argument('--reset-observation',action='store_true',help='with --gate and --combat-candidate: 46-second no-credit renewable hold for a manual reset, followed by recovery; no private rendering')
    p.add_argument('--transaction-check',action='store_true',help='renew ownership across an initial hold, then three counter-bound steps with settled frames; optional three-frame positioning plan requires combat profile')
    p.add_argument('--transaction-loss-check',action='store_true',help='run transaction check, then cease renewal and verify automatic source/renderer-hook recovery')
    p.add_argument('--stream-check-steps',type=int,default=0,help='1..120 rolling credits; optional exact-count horizontal render-position plan, no live host producer')
    p.add_argument('--stream-duration-check',action='store_true',help='neutral rolling capture for --seconds (28..120), bounded recent metadata, no fixed credit count')
    p.add_argument('--frame-tap',action='store_true',help='fixed-count rolling check: read-only loopback source observation subscriber; no playable capabilities')
    p.add_argument('--frame-control',action='store_true',help='fixed-count rolling check: request-driven horizontal diagnostic control; requires input candidate, no local plan')
    p.add_argument('--transaction-hold-seconds',type=float,default=13,help='13..45 seconds for the initial normal transaction hold, allowing a synchronized manual reset test')
    p.add_argument('--input-candidate',type=Path,help='ignored local sampler/writer/ingress discovery JSON')
    p.add_argument('--input-plan',type=Path,help='bounded named-input oracle plan, with --gate and --input-candidate')
    p.add_argument('--oracle',choices=('positioning','movement','crossover','contact','render-motion','render-attack','render-settle','render-framing','render-facing','render-position'),default='movement',help='required input-plan evidence; native render oracles require --capture-layer')
    p.add_argument('--scalar-fields',type=Path,help='ignored bounded field hypotheses to observe without semantic promotion')
    p.add_argument('--external-pair-step',type=int,default=0,help='bounded diagnostic original native pair invocation after one owned step')
    p.add_argument('--external-ko',action='store_true',help='diagnostic lethal normal: stage one source health before native damage')
    p.add_argument('--external-guard-commit',action='store_true',help='apply locally witnessed native caller pending result bit')
    p.add_argument('--external-pair-control',action='store_true',help='negative guard control: skip native pair invocation')
    p.add_argument('--external-guard',action='store_true',help='diagnostic defender back input around one requested normal')
    p.add_argument('--external-host-stop',action='store_true',help='diagnostic host-owned freeze: clear native stops after requested reaction')
    p.add_argument('--external-damage',type=int,default=0,help='1..419 requested nonfatal damage; native Punch reaction remains unchanged')
    p.add_argument('--input-slot',type=int,choices=(0,1),default=0,help='original contact validation control slot; rendered guest stays Sol/slot zero')
    p.add_argument('--contact-callees',type=Path,help='ignored static direct-callee inventory for original contact observation')
    p.add_argument('--suppress-source-contact',type=Path,help='bounded dispatch suppression; requires clean original dispatch proof folder')
    p.add_argument('--contact-dispatch-candidate',type=Path,help='ignored enclosing native dispatch candidate; original calls remain unchanged')
    p.add_argument('--observe-native-contact',action='store_true',help='observe native pair contact calls without suppressing source combat')
    p.add_argument('--combat-candidate',type=Path,help='ignored local scalar getter/setter discoveries for the native contact check')
    p.add_argument('--capture-render',action='store_true',help='with --gate: capture up to eight full-scene D3D9 backbuffers and held source states; no isolated-layer claim')
    p.add_argument('--trace-draws',action='store_true',help='with --gate: observe two Present intervals of D3D9 draw/target/shader bindings; no draw suppression')
    p.add_argument('--capture-passes',action='store_true',help='with --trace-draws: capture first completed target bindings, up to 24/128 MiB, for native layer investigation')
    p.add_argument('--capture-screen-stages',action='store_true',help='with pass/screen inspection: read original screen outputs from grading through SMAA blend in one held presentation, plus its final backbuffer')
    p.add_argument('--suppress-draws',type=Path,help='with --capture-render and --trace-draws: briefly suppress locally derived mesh-buffer candidates for visual identity proof')
    p.add_argument('--inspect-mesh-shaders',action='store_true',help='with --suppress-draws: read matching mesh pixel shader programs while preserving every original draw')
    p.add_argument('--inspect-screen-shaders',action='store_true',help='with neutral capture/draw trace: read up to 32 two-triangle draw programs, constants and sampler bindings; no replay')
    p.add_argument('--capture-layer',type=Path,help='with --suppress-draws: clean shader inspection folder for bounded private opaque mesh replay')
    p.add_argument('--layer-steps',help='with --capture-layer: 2..8 ordered selected request indices starting at 0 (default 0,1,2,3)')
    p.add_argument('--layer-presentations',help='with --oracle render-settle: ordered held-counter presentations, starting at 3 and ending by 24')
    p.add_argument('--inspect-layer-transforms',action='store_true',help='with --capture-layer: read original body vertex program/constants/viewport on each selected render')
    p.add_argument('--normalize-layer',action='store_true',help='diagnostic private projection/depth centered on the native render origin, with canonical right-facing pixels')
    p.add_argument('--settle-layer',action='store_true',help='with --normalize-layer: wait for two consecutive identical native layers at one held source counter, bounded through presentation 24')
    p.add_argument('--hdr-layer',action='store_true',help='normalized neutral diagnostic: preserve native float16 RGB/opaque alpha; no settling/publication claim')
    p.add_argument('--grade-layer',type=Path,help='clean same-session screen program inspection: native private HDR grading and coverage into A8 output')
    p.add_argument('--source-view-layer',action='store_true',help='neutral grading diagnostic: retain original camera/pixel coordinates for source comparison; no readiness claim')
    p.add_argument('--source-color-layer',action='store_true',help='with source-view: repeat original full-scene color draw into private target, masked by Sol coverage; never an isolated color layer')
    p.add_argument('--post-color-layer',type=Path,help='with private source-view grading: clean stage inventory for private blur/composite replay; --smaa-layer extends it through SMAA')
    p.add_argument('--smaa-layer',action='store_true',help='extend private post-color replay through native SMAA; terminal alpha retains binary mesh coverage')
    a=p.parse_args()
    if not 0<=a.stream_check_steps<=120:p.error('--stream-check-steps must be 0..120')
    if a.stream_duration_check:
        if a.stream_check_steps or not 28<=a.seconds<=120:p.error('duration check requires exclusive --seconds 28..120')
        a.transaction_check=True
    if a.stream_check_steps:a.transaction_check=True
    if a.reset_observation:
        if not a.combat_candidate or a.renewable_check or a.transaction_check or a.transaction_loss_check:
            p.error('--reset-observation requires exclusive --combat-candidate observation')
        a.renewable_check=True
    if a.transaction_loss_check: a.transaction_check=True
    if not 13<=a.transaction_hold_seconds<=45 or a.transaction_hold_seconds!=13 and (not a.transaction_check or a.transaction_loss_check):
        p.error('extended transaction hold requires --transaction-check; hold must be 13..45 seconds')
    if not 0<a.seconds<=120: p.error('seconds must be 0..120')
    if a.lease_check and not a.gate: p.error('--lease-check requires --gate')
    if a.renewable_check and (not a.gate or a.lease_check or a.input_plan or a.capture_render or a.trace_draws or a.capture_layer):
        p.error('--renewable-check requires an exclusive gate recovery experiment')
    trace(a.probe.resolve(),a.candidate.resolve(),a.seconds if a.stream_duration_check else 60 if a.reset_observation or a.stream_check_steps else 34 if a.transaction_loss_check else a.transaction_hold_seconds+15 if a.transaction_check else 28 if a.renewable_check else 13 if a.lease_check else 10 if a.capture_layer and a.input_plan else 8 if a.capture_passes or a.capture_layer else 7 if a.input_plan else 4.5 if a.gate else a.seconds,
          a.gate.resolve() if a.gate else None,a.lease_check or a.renewable_check,a.input_candidate.resolve() if a.input_candidate else None,
          a.input_plan.resolve() if a.input_plan else None,a.oracle,a.scalar_fields.resolve() if a.scalar_fields else None,
          a.combat_candidate.resolve() if a.combat_candidate else None,a.capture_render,a.trace_draws,a.capture_passes,
          a.suppress_draws.resolve() if a.suppress_draws else None,a.inspect_mesh_shaders,a.capture_layer.resolve() if a.capture_layer else None,a.layer_steps,a.layer_presentations,a.inspect_layer_transforms,a.normalize_layer,a.settle_layer,a.inspect_screen_shaders,a.hdr_layer,a.grade_layer.resolve() if a.grade_layer else None,a.source_view_layer,a.source_color_layer,a.capture_screen_stages,a.post_color_layer.resolve() if a.post_color_layer else None,a.smaa_layer,a.renewable_check,a.transaction_check,a.transaction_loss_check,a.transaction_hold_seconds,a.reset_observation,a.stream_check_steps,a.stream_duration_check,a.frame_tap,a.frame_control,a.observe_native_contact,a.contact_dispatch_candidate.resolve() if a.contact_dispatch_candidate else None,a.suppress_source_contact.resolve() if a.suppress_source_contact else None,a.contact_callees.resolve() if a.contact_callees else None,a.input_slot,a.external_pair_step,a.external_damage,a.external_host_stop,a.external_guard,a.external_pair_control,a.external_guard_commit,a.external_ko)
