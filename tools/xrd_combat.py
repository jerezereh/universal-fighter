"""Derive local scalar access fields and check native contact/stop observations."""
import struct
import hashlib
import re


def dispatch_candidate(code,code_rva,local,pair_rva):
    """Check an inspected enclosing thiscall entry and its witnessed pair call."""
    rva=local.get('rva');size=local.get('size');returned=local.get('pair_return_rva')
    if any(type(v)!=int for v in (rva,size,returned)) or not 32<=size<=8192:
        raise ValueError('invalid contact-dispatch candidate bounds')
    at=rva-code_rva;call=returned-code_rva-5
    if (not 2<=at<at+size<=len(code) or code[at-2:at]!=b'\xcc\xcc' or rva%16 or
            not at<=call<call+5<=at+size or code[call]!=0xe8 or
            returned+struct.unpack_from('<i',code,call+1)[0]!=pair_rva):
        raise ValueError('dispatch does not enclose witnessed native pair call')
    body=code[at:at+size]
    if (hashlib.sha256(body).hexdigest()!=local.get('sha256') or body[:3]!=b'\x83\xec\x50' or
            not body.rstrip(b'\xcc').endswith(b'\xc2\x04\x00')):
        raise ValueError('dispatch body/thiscall stack cleanup changed')
    return dict(rva=rva,before=body[:32].hex())


def contact_callees(code,code_rva,local):
    if type(local)!=list or not 1<=len(local)<=16:raise ValueError('contact callee observation requires 1..16 selected entries')
    seen=set()
    for c in local:
        if type(c)!=dict or set(c)!={'rva','before','return_rvas'} or type(c['rva'])!=int:
            raise ValueError('invalid contact callee candidate')
        at=c['rva']-code_rva
        if not 0<at<at+32<=len(code) or code[at-1]!=0xcc or code[at]==0xcc or code[at:at+32].hex()!=c['before'] or c['rva'] in seen:
            raise ValueError('contact callee entry changed/aliased')
        seen.add(c['rva'])
        if type(c['return_rvas'])!=list or not 1<=len(c['return_rvas'])<=64:raise ValueError('invalid contact callee callers')
        for returned in c['return_rvas']:
            if type(returned)!=int:raise ValueError('invalid contact callee caller')
            call=returned-code_rva-5
            if not 0<=call<call+5<=len(code) or code[call]!=0xe8 or returned+struct.unpack_from('<i',code,call+1)[0]!=c['rva']:
                raise ValueError('contact callee caller code changed')
    return local


def dispatch_result_fields(code,code_rva,local):
    """Derive the witnessed caller's defender result load and pending-bit write."""
    returned=local.get('pair_return_rva');pending=local.get('pending_rva')
    if any(type(v)!=int for v in (returned,pending)):raise ValueError('missing caller-result witnesses')
    start=local['rva'];end=start+local['size'];load=returned-code_rva;write=pending-code_rva
    if not start<=returned<returned+6<=pending<pending+10<=end or not 0<=load<write+10<=len(code):raise ValueError('unbounded caller result')
    if code[load:load+2]!=b'\x8b\x87' or code[write:write+2]!=b'\x81\x8f':raise ValueError('caller result operands changed')
    kind=struct.unpack_from('<I',code,load+2)[0];field,mask=struct.unpack_from('<II',code,write+2)
    if any(v%4 or not 0<=v<=0x2600-4 for v in (kind,field)) or kind==field or not mask or mask&(mask-1):raise ValueError('invalid caller result fields')
    # The local witness still supplies branch locations; both operands are the defender (EDI).
    return dict(kind_field=kind,pending_field=field,pending_mask=mask,rva=pending,before=code[write:write+10].hex())


def fatal_global_field(code,code_rva,local,global_address):
    rva=local.get('rva')
    if type(rva)!=int:raise ValueError('invalid fatal global witness')
    at=rva-code_rva;body=code[at:at+9]
    if not 0<=at<at+9<=len(code) or body.hex()!=local.get('before') or body[:1]!=b'\xa1' or body[5:7]!=b'\x83\x48' or struct.unpack_from('<I',body,1)[0]!=global_address:
        raise ValueError('fatal global load/write changed')
    field,mask=body[7:9]
    if field%4 or not 0<field<128 or not 0<mask<128 or mask&(mask-1):raise ValueError('invalid fatal global operand')
    return dict(rva=rva,before=body.hex(),field=field,mask=mask)


def state_transition_candidate(code,code_rva,local,module_base,image_size):
    rva=local.get('rva');size=local.get('size');returned=local.get('return_rva');state=local.get('state_rva');name=local.get('name')
    if any(type(v)!=int for v in (rva,size,returned,state)) or not 32<=size<=256 or type(name)!=str or not re.fullmatch('[A-Za-z0-9_]{1,31}',name):raise ValueError('invalid state transition witness')
    at=rva-code_rva;caller=returned-code_rva-12
    if not 0<at<at+size<=len(code) or code[at-1]!=0xcc or code[at:at+32].hex()!=local.get('before') or code[at+size-3:at+size]!=b'\xc2\x04\x00' or not 0<=state<state+32<=image_size:
        raise ValueError('state transition entry/data bounds changed')
    if not 0<=caller<caller+12<=len(code) or code[caller]!=0x68 or code[caller+5:caller+8]!=b'\x8b\xce\xe8' or struct.unpack_from('<I',code,caller+1)[0]!=module_base+state or returned+struct.unpack_from('<i',code,caller+8)[0]!=rva:
        raise ValueError('state transition caller disagrees with entry or name')
    return dict(rva=rva,before=local['before'],state_rva=state,name=name)


def dispatch_ownership(code,code_rva,dispatch,proof,thread):
    if (proof.get('errors') or not all(proof.get(k) for k in ('source_unchanged','detached',
            'loaded_code_restored','controlled_update_step_verified','native_contact_observer_restored')) or
            not proof.get('contact_check',{}).get('passed') or not proof.get('native_contact_pair_check',{}).get('passed')):
        raise ValueError('requires clean original native contact evidence')
    calls=proof.get('native_dispatch_observations',[]);count=proof['gate_check']['executed']
    if not 20<=count<=85 or len(calls)!=3*count:raise ValueError('missing bounded three-stage dispatch proof')
    returns={}
    for index in range(count):
        group=calls[index*3:index*3+3]
        if ([c['argument'] for c in group]!=[0,1,2] or len({c['counter'] for c in group})!=1 or
                any(c['this_delta']!=4 or c['thread']!=thread or c['result']!=0 or c['original_called'] is not True for c in group)):
            raise ValueError('dispatch ownership/stage ordering changed')
        for c in group:
            returned=c['return_rva'];at=returned-code_rva-5
            if not 0<=at<at+5<=len(code) or code[at]!=0xe8 or returned+struct.unpack_from('<i',code,at+1)[0]!=dispatch['rva']:
                raise ValueError('dispatch caller bytes disagree with observed entry')
            stage=c['argument']
            if stage in returns and returns[stage]!=returned:raise ValueError('dispatch stage caller changed')
            returns[stage]=returned
    return dict(thread=thread,return_rvas=[returns[i] for i in range(3)])


def suppressed_contact_check(records,states,dispatches,contacts):
    executed=[(r,s) for r,s in zip(records,states) if r['executed']]
    if not 20<=len(executed)<=85:raise ValueError('suppressed contact check is unbounded/too short')
    health=lambda s:[f['scalar_observations']['health_candidate'] for f in s]
    overlap_steps=sum(any(overlap(a,b) for a in world_boxes(s[0],1) for b in world_boxes(s[1],0)) for _,s in executed)
    defender=states[0][1]
    idle=lambda f:bool(f['pose_candidates']) and all(re.fullmatch(r'kyk00[01]_[0-9]{2}',n['value']) for n in f['pose_candidates'])
    clean=idle(defender) and all(health(s)==health(states[0]) and
        all(f['scalar_observations']['hitstop_candidate']==0 for f in s) and
        s[1]['state_candidates']==defender['state_candidates'] and idle(s[1]) for s in states)
    phases=set()
    for i,(r,_) in enumerate(executed):
        group=dispatches[i*3:i*3+3]
        if group and all(c['counter']==r['before'] for c in group):phases.add('before')
        elif group and all(c['counter']==r['after'] for c in group):phases.add('after')
        else:phases.add('unlinked')
    ordered=len(dispatches)==3*len(executed) and all(
        [c['argument'] for c in dispatches[i*3:i*3+3]]==[0,1,2] and all(
            c.get('suppressed') is True and c['original_called'] is False and
            c['thread']==r['thread'] and c['this_delta']==4 for c in dispatches[i*3:i*3+3])
        for i,(r,_) in enumerate(executed)) and len(phases)==1 and 'unlinked' not in phases
    return dict(passed=bool(overlap_steps and clean and ordered and not contacts),overlapping_active_steps=overlap_steps,
        native_health_stop_reaction_unchanged=clean,owned_dispatch_suppressed=ordered,native_pair_calls=len(contacts),
        observed_counter_phase=sorted(phases),universal_contact=False,external_results_applied=False)


def external_contact_check(records,states,dispatches,contacts,events,step,damage=0,host_stop=False,guard=False,ko=False,isolate_ko=False):
    executed=[r for r in records if r['executed']]
    native=contact_check(records,states,1)
    if len(records)!=len(states) or len(events)!=1 or type(step)!=int or not 1<=step<=len(executed):raise ValueError('external native contact requires exactly one requested result')
    event=events[0];frame=executed[step-1]
    if any(type(event.get(k))!=list or len(event[k])!=2 or any(type(v)!=int or v<0 for v in event[k]) for k in ('before','after')):
        raise ValueError('invalid external native health evidence')
    linked=(event['request_index']==step and event['counter']==frame['after'] and event['thread']==frame['thread'] and
        event.get('native_pair_called',True) is True and
        event['attacker']==1 and event['defender']==0 and event['source_collision_suppressed'] is True and
        (event['before']==event['after'] if guard else event['before'][0]>=event['after'][0] if ko and isolate_ko else event['before'][0]>event['after'][0]) and event['before'][1]==event['after'][1])
    if type(damage)!=int or not 0<=damage<=419:raise ValueError('invalid requested damage')
    damage_mapped=(not damage and event.get('requested_damage') is None or damage>0 and
        event.get('requested_damage')==damage and event['before'][0]-event['after'][0]==damage and event['after'][0]>0 and
        len(native['damage_events'])==1 and native['damage_events'][0]['before']==event['before'][0] and
        native['damage_events'][0]['after']==event['after'][0])
    if type(host_stop)!=bool:raise ValueError('invalid hitstop owner')
    if type(guard)!=bool or guard and (damage or not host_stop):raise ValueError('invalid guard experiment')
    if type(ko)!=bool or ko and (damage or guard or not host_stop):raise ValueError('invalid KO experiment')
    if type(isolate_ko)!=bool or isolate_ko and not ko:raise ValueError('invalid source KO isolation')
    host_freeze=False
    if host_stop:
        held=[s for r,s in zip(records,states) if not r['executed'] and r['after']==frame['after']]
        scalar=lambda s:[[f['scalar_observations'][k+'_candidate'] for k in ('health','hitstop','age')] for f in s]
        reacting=[s for r,s in zip(records,states) if r['executed'] and r['after']>frame['after'] and
            s[0].get('pose_candidates') and all(not re.fullmatch(r'sol00[01]_[0-9]{2}',n['value']) for n in s[0]['pose_candidates']) and
            any(('Guard' if guard else 'Hizakuzure' if ko else 'Nokezori') in n['value'] for n in s[0]['state_candidates'])]
        host_freeze=(event.get('hitstop_owner')=='host' and native['max_stop']==[0,0] and len(held)>=5 and
            all(scalar(s)==scalar(held[0]) for s in held) and len(reacting)>=2 and
            any(b[0]['scalar_observations']['age_candidate']>a[0]['scalar_observations']['age_candidate'] for a,b in zip(reacting,reacting[1:])) and
            (not native['damage_events'] and all(s[0]['scalar_observations']['health_candidate']==event['before'][0] for s in states)
                if guard else not native['damage_events'] and event['before'][0]==event['after'][0]==1
                if ko and isolate_ko and not native['damage_events'] else len(native['damage_events'])==1 and native['damage_events'][0]['mirrored_box_overlap']))
    suppressed=len(dispatches)==3*len(executed) and all(
        [c['argument'] for c in dispatches[i*3:i*3+3]]==[0,1,2] and all(
            c.get('suppressed') is True and c['original_called'] is False and c['thread']==r['thread'] and
            c['this_delta']==4 and c['counter']==r['after'] for c in dispatches[i*3:i*3+3])
        for i,r in enumerate(executed))
    requested=all(c.get('externally_requested') is True for c in contacts)
    guard_applied=guard and event.get('caller_result_committed') is True and sum(
        r['executed'] and r['after']>frame['after'] and any(n['value']=='sol040_03' for n in s[0].get('pose_candidates',[]))
        for r,s in zip(records,states))>=5 and all(re.fullmatch(r'sol00[01]_[0-9]{2}',n['value']) for n in states[-1][0].get('pose_candidates',[]))
    expected_health=1 if isolate_ko else 0
    isolation_matches=not isolate_ko or event.get('source_ko_isolated') is True and event.get('native_fatal_health')==0
    ko_candidate=ko and isolation_matches and event.get('requested_ko') is True and event.get('caller_result_committed') is True and event['after'][0]==expected_health and all(
        s[0]['scalar_observations']['health_candidate']==expected_health for r,s in zip(records,states) if r['after']>=frame['after'])
    lethal=ko and linked and isolation_matches and event.get('requested_ko') is True and event['after'][0]==expected_health and (not native['damage_events'] and isolate_ko and event['before'][0]==1 or len(native['damage_events'])==1 and native['damage_events'][0]['step']==step and native['damage_events'][0]['after']==expected_health)
    lifecycle_changed=ko and any(s[0]['scalar_observations']['health_candidate']!=expected_health for r,s in zip(records,states) if r['after']>=frame['after'])
    defeat_pose=isolate_ko and event.get('native_reaction_requested')=='CmnActHizakuzure' and sum(
        r['executed'] and r['after']>frame['after'] and any(n['value'].startswith('sol085_') for n in s[0].get('pose_candidates',[])) for r,s in zip(records,states))>=5
    # Proximity guard alone is insufficient; require the original block's hit pose and caller commit.
    return native|dict(passed=bool((guard_applied if guard else ko_candidate and (not isolate_ko or defeat_pose) if ko else True) and (host_freeze if host_stop else native['passed']) and linked and suppressed and requested and damage_mapped),external_result_linked=linked,
        native_ko_candidate=bool(ko_candidate),native_lethal_result_verified=bool(lethal),
        source_ko_lifecycle_changed=bool(lifecycle_changed),defeat_semantics_verified=False,
        native_defeat_pose_observed=bool(defeat_pose),
        source_ko_isolation_verified=bool(isolate_ko and defeat_pose and ko_candidate and host_freeze and linked and suppressed and requested),
        source_lifecycle_isolated=bool(isolate_ko and lethal and not lifecycle_changed and suppressed and requested),
        host_freeze_verified=host_freeze,
        native_guard_reaction_candidate=bool(guard and host_freeze),guard_semantics_verified=bool(guard_applied and host_freeze and linked and suppressed and requested),
        requested_damage_verified=bool(damage and damage_mapped),
        source_dispatch_suppressed=suppressed,automatic_pair_calls=sum(c.get('externally_requested') is not True for c in contacts),
        universal_contact=False,typed_host_result_applied=False)


def guard_contact_check(records,states,contacts):
    """Original native block baseline; anticipatory guarding alone must fail."""
    native=contact_check(records,states,1)
    executed={r['before']:r for r in records if r['executed']}
    linked=len(contacts)==1 and all(c.get('original_called') is True and not c.get('externally_requested') and
        c.get('attacker')==1 and c.get('defender')==0 and c.get('counter') in executed and
        c.get('thread')==executed[c['counter']]['thread'] and c.get('before')==c.get('after') for c in contacts)
    health=[[f['scalar_observations']['health_candidate'] for f in s] for s in states]
    guarded=any(any('Guard' in n['value'] for n in s[0]['state_candidates']) for s in states)
    recovered=bool(states[-1][0].get('pose_candidates')) and all(re.fullmatch(r'sol00[01]_[0-9]{2}',n['value']) for n in states[-1][0]['pose_candidates'])
    passed=linked and all(h==health[0] for h in health) and guarded and recovered and all(native['max_stop']) and all(n>=3 for n in native['countdown_steps']) and all(n>=3 for n in native['held_animation_age_steps']) and native['frozen_stop_samples']>=5 and native['frozen_scalar_changes']==0 and native['stop_recovered'] and native['animation_age_resumed']
    return native|dict(passed=bool(passed),original_guard_verified=bool(passed),original_pair_linked=linked,
        universal_contact=False,typed_host_result_applied=False)


def combat_fields(code,code_rva,local):
    fields={}
    for name,kind in (('health_candidate','health_getter'),('hitstop_candidate','stop_setter'),('age_candidate','age_getter')):
        rva=local[kind+'_rva']
        if type(rva)!=int: raise ValueError('non-integer combat candidate')
        at=rva-code_rva;size=13 if kind=='stop_setter' else 7
        if not 0<at<at+size<=len(code) or code[at-1]!=0xcc:
            raise ValueError('invalid bounded scalar function')
        data=code[at:at+size]
        if kind=='stop_setter':
            if data[:6]!=b'\x8b\x44\x24\x04\x89\x81' or data[10:]!=b'\xc2\x04\x00':
                raise ValueError('not a scalar thiscall setter')
            field=struct.unpack_from('<I',data,6)[0]
        else:
            if data[:2]!=b'\x8b\x81' or data[6:]!=b'\xc3': raise ValueError('not a scalar thiscall getter')
            field=struct.unpack_from('<I',data,2)[0]
        if not 0<=field<=0x2600-4 or field%4: raise ValueError('unbounded scalar field')
        fields[name]=field
    if len(set(fields.values()))!=3: raise ValueError('aliased combat fields')
    return fields


def world_boxes(fighter,kind):
    if fighter.get('rotation_raw')!=0: raise ValueError('source rotation is unverified or unsupported')
    sx,sy=(v/1000 for v in fighter['scale_raw'])
    if not 0<sx<=10 or not 0<sy<=10: raise ValueError('invalid source collision scale')
    x=fighter['x_raw']/1000;y=-fighter['y_raw']/1000;flip=1 if fighter['facing_left'] else -1
    result=[]
    for k,bx,by,w,h in fighter['boxes']:
        if k==kind:
            a=x+bx*sx*flip;b=x+(bx+w)*sx*flip
            result.append([min(a,b),y+by*sy,max(a,b),y+(by+h)*sy])
    return result


def overlap(a,b):
    return max(a[0],b[0])<min(a[2],b[2]) and max(a[1],b[1])<min(a[3],b[3])


def contact_observations(records,states,contacts):
    """Associate original pair-handler health changes with the enclosing owned tick."""
    if not 1<=len(contacts)<=256:raise ValueError('missing/unbounded native pair observations')
    executed={r['before']:(r,s) for r,s in zip(records,states) if r['executed']}
    changes=[]
    for c in contacts:
        if (c.get('original_called') is not True or c.get('attacker') not in (0,1) or
                c.get('defender')!=1-c['attacker'] or type(c.get('argument'))!=int or
                not 0<=c['argument']<=16 or c.get('counter') not in executed or
                any(type(v)!=int or not 0<=v<=100000 for v in c.get('before',[])+c.get('after',[])) or
                len(c.get('before',[]))!=2 or len(c.get('after',[]))!=2):
            raise ValueError('invalid/unowned native pair observation')
        r,s=executed[c['counter']]
        if c.get('thread')!=r['thread']:raise ValueError('native pair thread differs from owned tick')
        if c['before']!=c['after']:
            if c['after']!=[f['scalar_observations']['health_candidate'] for f in s]:
                raise ValueError('pair health change disagrees with owned post-state')
            changes.append(c)
    return dict(passed=len(changes)==1,observed_calls=len(contacts),health_changes=len(changes),
        original_source_combat_preserved=True,source_contact_suppressed=False,universal_contact=False)


def contact_check(records,states,attacker_slot=0):
    if type(attacker_slot)!=int or attacker_slot not in (0,1):raise ValueError('invalid native attacker slot')
    if attacker_slot==1:states=[s[::-1] for s in states]
    executed=[(r,s) for r,s in zip(records,states) if r['executed']]
    if len(executed)<20: raise ValueError('native contact capture is too short')
    scalar=lambda s,slot,name:s[slot]['scalar_observations'][name+'_candidate']
    damage=[];max_stop=[0,0];countdown=[0,0];held_age=[0,0];frozen_samples=0;frozen_changes=0
    before=None
    for r,s in zip(records,states):
        if before is not None and not r['executed'] and any(scalar(s,slot,'hitstop')>0 for slot in (0,1)):
            frozen_samples+=1
            if any(scalar(s,slot,k)!=scalar(before,slot,k) for slot in (0,1) for k in ('health','hitstop','age')): frozen_changes+=1
        before=s
    for index,(r,s) in enumerate(executed):
        for slot in (0,1):
            stop=scalar(s,slot,'hitstop');hp=scalar(s,slot,'health')
            if not 0<=stop<=600 or not 0<=hp<=100000: raise ValueError('invalid contact scalar range')
            max_stop[slot]=max(max_stop[slot],stop)
            if index:
                previous=executed[index-1][1];old=scalar(previous,slot,'hitstop')
                if stop>0 and old>0 and stop==old-1: countdown[slot]+=1
                if stop>0 and old>0 and scalar(s,slot,'age')==scalar(previous,slot,'age'): held_age[slot]+=1
                if slot==1 and hp<scalar(previous,1,'health'):
                    intersect=any(overlap(a,b) for a in world_boxes(s[0],1) for b in world_boxes(s[1],0))
                    damage.append(dict(step=index+1,before=scalar(previous,1,'health'),after=hp,mirrored_box_overlap=intersect))
    recovered=all(scalar(executed[-1][1],slot,'hitstop')==0 for slot in (0,1))
    reaction=any('Nokezori' in n['value'] for _,s in executed for n in s[1]['state_candidates'])
    age_resumed=all(any(scalar(b,slot,'hitstop')==0 and scalar(a,slot,'hitstop')>0 and scalar(b,slot,'age')>scalar(a,slot,'age') for (_,a),(_,b) in zip(executed,executed[1:])) for slot in (0,1))
    passed=len(damage)==1 and all(d['mirrored_box_overlap'] for d in damage) and all(max_stop) and all(n>=3 for n in countdown) and all(n>=3 for n in held_age) and frozen_samples>=5 and frozen_changes==0 and recovered and reaction and age_resumed
    return dict(passed=bool(passed),damage_events=damage,max_stop=max_stop,countdown_steps=countdown,
        held_animation_age_steps=held_age,frozen_stop_samples=frozen_samples,frozen_scalar_changes=frozen_changes,
        native_hit_reaction=bool(reaction),stop_recovered=recovered,animation_age_resumed=age_resumed)


def reaction_timer_field(code,code_rva,local):
    """Derive a private timer field from its inspected decrement/load/store witness."""
    if type(local)!=dict or set(local)!={'rva','before'}:raise ValueError('invalid reaction timer profile')
    rva=local.get('rva');before=local.get('before')
    if type(rva)!=int or type(before)!=str or len(before)!=34:raise ValueError('invalid reaction timer witness')
    at=rva-code_rva;body=code[at:at+17]
    if at<0 or len(body)!=17 or body.hex()!=before or body[:2]!=b'\x8b\x86' or body[6:9]!=b'\x3b\xc3\x7e' or not 7<=body[9]<=32 or body[10]!=0x48 or body[11:13]!=b'\x89\x86' or body[2:6]!=body[13:17]:raise ValueError('reaction timer decrement witness changed')
    field=struct.unpack_from('<I',body,2)[0]
    if not 0<field<0x10000 or field%4:raise ValueError('unbounded reaction timer field')
    return dict(rva=rva,before=before,field=field)
