"""Authored scalar-body and native stop/contact association checks."""
import copy
import struct

from xrd_combat import combat_fields, contact_check, contact_observations, world_boxes, dispatch_candidate, dispatch_ownership, suppressed_contact_check, contact_callees, external_contact_check, guard_contact_check, dispatch_result_fields
import hashlib


def reject(action):
    try: action()
    except ValueError: return
    raise AssertionError('accepted invalid combat profile')


def main():
    caller=bytearray(b'\xcc'*128);caller[32:38]=b'\x8b\x87'+struct.pack('<I',128)
    caller[48:58]=b'\x81\x8f'+struct.pack('<II',132,256)
    witness=dict(rva=8192,size=128,pair_return_rva=8224,pending_rva=8240)
    assert dispatch_result_fields(caller,8192,witness)['pending_mask']==256
    reject(lambda:dispatch_result_fields(caller,8192,witness|dict(pending_rva=True)))
    bad=bytearray(caller);bad[48]=0x80;reject(lambda:dispatch_result_fields(bad,8192,witness))
    bad=bytearray(caller);struct.pack_into('<I',bad,54,3);reject(lambda:dispatch_result_fields(bad,8192,witness))
    bad=bytearray(caller);struct.pack_into('<I',bad,50,128);reject(lambda:dispatch_result_fields(bad,8192,witness))
    candidate_code=bytearray(b'\xcc'*512);base=4096;entry=base+32;pair=base+400
    candidate_code[32:96]=b'\x90'*64;candidate_code[32:35]=b'\x83\xec\x50'
    candidate_code[48:53]=b'\xe8'+struct.pack('<i',pair-(base+53));candidate_code[93:96]=b'\xc2\x04\x00'
    local=dict(rva=entry,size=64,pair_return_rva=base+53,sha256=hashlib.sha256(candidate_code[32:96]).hexdigest())
    dispatch=dispatch_candidate(candidate_code,base,local,pair)
    returns=[base+201,base+225,base+249]
    for returned in returns:candidate_code[returned-base-5:returned-base]=b'\xe8'+struct.pack('<i',entry-returned)
    calls=[dict(argument=stage,this_delta=4,thread=9,result=0,original_called=True,counter=index,return_rva=returns[stage]) for index in range(20) for stage in range(3)]
    proof=dict(errors=[],source_unchanged=True,detached=True,loaded_code_restored=True,controlled_update_step_verified=True,
        native_contact_observer_restored=True,contact_check=dict(passed=True),native_contact_pair_check=dict(passed=True),
        native_dispatch_observations=calls,gate_check=dict(executed=20))
    assert dispatch_ownership(candidate_code,base,dispatch,proof,9)['return_rvas']==returns
    selected=dict(rva=entry,before=bytes(candidate_code[32:64]).hex(),return_rvas=returns)
    assert contact_callees(candidate_code,base,[selected])==[selected]
    reject(lambda:contact_callees(candidate_code,base,[selected]*17))
    reject(lambda:contact_callees(candidate_code,base,[selected,selected]))
    reject(lambda:contact_callees(candidate_code,base,[selected|dict(before='bad')]))
    reject(lambda:contact_callees(candidate_code,base,[selected|dict(return_rvas=[base+5])]))
    reject(lambda:dispatch_ownership(candidate_code,base,dispatch,proof,8))
    reject(lambda:dispatch_candidate(candidate_code,base,local|dict(sha256='bad'),pair))
    bad=copy.deepcopy(proof);bad['native_dispatch_observations'][3]['argument']=2
    reject(lambda:dispatch_ownership(candidate_code,base,dispatch,bad,9))
    frame=dict(x_raw=0,y_raw=0,rotation_raw=0,scale_raw=[1000,1000],facing_left=False,
        scalar_observations=dict(health_candidate=420,hitstop_candidate=0),boxes=[[1,0,-10,20,20]],
        state_candidates=[dict(value='CmnActStand')],pose_candidates=[dict(value='sol000_00')])
    defender=copy.deepcopy(frame);defender.update(facing_left=True,boxes=[[0,-10,-10,20,20]],
        state_candidates=[dict(value='CmnActNokezoriHighLv1'),dict(value='CmnActStand')],pose_candidates=[dict(value='kyk000_00')])
    source_states=[copy.deepcopy([frame,defender]) for _ in range(20)]
    ticks=[dict(before=i,after=i+1,thread=9,executed=True) for i in range(20)]
    blocked=[c|dict(counter=c['counter']+1,original_called=False,suppressed=True) for c in calls]
    assert suppressed_contact_check(ticks,source_states,blocked,[])['passed']
    alternate=copy.deepcopy(source_states);alternate[0][1]['pose_candidates']=[dict(value='kyk001_23')]
    assert suppressed_contact_check(ticks,alternate,blocked,[])['passed']
    mixed=copy.deepcopy(blocked);mixed[0]['counter']=0
    assert not suppressed_contact_check(ticks,source_states,mixed,[])['passed']
    bad=copy.deepcopy(source_states);bad[-1][1]['pose_candidates']=[dict(value='kyk050_00')]
    assert not suppressed_contact_check(ticks,bad,blocked,[])['passed']
    bad=copy.deepcopy(source_states);bad[-1][1]['scalar_observations']['health_candidate']=410
    assert not suppressed_contact_check(ticks,bad,blocked,[])['passed']
    records=[dict(before=5,executed=True,thread=9)]
    states=[[dict(scalar_observations=dict(health_candidate=420)),dict(scalar_observations=dict(health_candidate=410))]]
    c=dict(original_called=True,attacker=0,defender=1,argument=0,counter=5,thread=9,before=[420,420],after=[420,410])
    assert contact_observations(records,states,[c])['passed']
    for patch in (dict(counter=4),dict(thread=8),dict(original_called=False),dict(after=[420,409]),dict(defender=0)):
        reject(lambda:contact_observations(records,states,[c|patch]))
    assert not contact_observations(records,states,[c|dict(before=[420,410])])['passed']
    code=bytearray(b'\xcc'*128)
    code[32:39]=b'\x8b\x81'+struct.pack('<I',0x100)+b'\xc3'
    code[64:77]=b'\x8b\x44\x24\x04\x89\x81'+struct.pack('<I',0x104)+b'\xc2\x04\x00'
    code[96:103]=b'\x8b\x81'+struct.pack('<I',0x108)+b'\xc3'
    local=dict(health_getter_rva=0x1020,stop_setter_rva=0x1040,age_getter_rva=0x1060)
    assert combat_fields(code,0x1000,local)==dict(health_candidate=0x100,hitstop_candidate=0x104,age_candidate=0x108)
    reject(lambda:combat_fields(code,0x1000,local|dict(health_getter_rva=True)))
    reject(lambda:combat_fields(code,0x1000,local|dict(age_getter_rva=0x1020)))
    bad=bytearray(code);bad[32]=0x90;reject(lambda:combat_fields(bad,0x1000,local))
    bad=bytearray(code);struct.pack_into('<I',bad,34,0x2600);reject(lambda:combat_fields(bad,0x1000,local))
    fighter=dict(x_raw=0,y_raw=0,facing_left=False,rotation_raw=0,scale_raw=[1000,1000],boxes=[[1,-30,-20,10,10]])
    assert world_boxes(fighter,1)==[[20,-20,30,-10]]
    assert world_boxes(fighter|dict(facing_left=True),1)==[[-30,-20,-20,-10]]
    reject(lambda:world_boxes(fighter|dict(rotation_raw=1000),1))
    records=[];states=[]
    for step in range(20):
        stop=max(0,6-step) if step else 0
        s=[dict(scalar_observations=dict(health_candidate=420 if slot==0 or step==0 else 410,
            hitstop_candidate=stop,age_candidate=10 if step==0 else 11 if stop else 11+step-5),
            state_candidates=[dict(value='CmnActNokezoriHighLv1')] if slot else [],
            x_raw=0,y_raw=0,facing_left=False,rotation_raw=0,scale_raw=[1000,1000],boxes=[[1 if slot==0 else 0,-30,-20,10,10]]) for slot in (0,1)]
        records.append(dict(executed=True));states.append(s)
        if stop:
            for _ in range(2): records.append(dict(executed=False));states.append(copy.deepcopy(s))
    checked=contact_check(records,states)
    assert checked['passed'] and len(checked['damage_events'])==1 and checked['max_stop']==[5,5]
    reverse=[s[::-1] for s in states]
    assert contact_check(records,reverse,1)['passed']
    owned=copy.deepcopy(records);counter=0
    for r in owned:
        r.update(before=counter,after=counter+int(r['executed']),thread=9)
        counter=r['after']
    suppressed=[dict(argument=stage,counter=r['after'],thread=9,this_delta=4,suppressed=True,original_called=False)
        for r in owned if r['executed'] for stage in range(3)]
    event=dict(request_index=2,counter=2,thread=9,attacker=1,defender=0,source_collision_suppressed=True,before=[420,420],after=[410,420])
    check=lambda events=[event],dispatches=suppressed,contacts=[]:external_contact_check(owned,reverse,dispatches,contacts,events,2)
    assert check()['passed'] and not check()['typed_host_result_applied']
    mapped=event|dict(requested_damage=10)
    assert external_contact_check(owned,reverse,suppressed,[],[mapped],2,10)['requested_damage_verified']
    assert not external_contact_check(owned,reverse,suppressed,[],[mapped],2,17)['passed']
    assert not external_contact_check(owned,reverse,suppressed,[],[mapped],2)['passed']
    reject(lambda:external_contact_check(owned,reverse,suppressed,[],[mapped],2,True))
    zero_records=[];zero_states=[]
    for r,s in zip(owned,reverse):
        s=copy.deepcopy(s)
        for f in s:f['scalar_observations'].update(hitstop_candidate=0,age_candidate=r['after'])
        s[0]['pose_candidates']=[dict(value='sol052_00' if r['after']>1 else 'sol000_00')]
        for _ in range(1 if r['executed'] else 3):zero_records.append(r);zero_states.append(copy.deepcopy(s))
    host_event=mapped|dict(hitstop_owner='host')
    host_check=lambda samples=zero_states,e=host_event:external_contact_check(zero_records,samples,suppressed,[],[e],2,10,True)
    assert host_check()['passed'] and host_check()['host_freeze_verified']
    assert not host_check(e=host_event|dict(hitstop_owner='source'))['passed']
    bad_zero=copy.deepcopy(zero_states);bad_zero[3][0]['scalar_observations']['age_candidate']+=1
    assert not host_check(samples=bad_zero)['passed']
    block_states=copy.deepcopy(reverse)
    for s in block_states:
        s[0]['scalar_observations']['health_candidate']=420
        s[0].update(pose_candidates=[dict(value='sol040_03')],state_candidates=[dict(value='CmnActMidGuardLoop')])
    block_states[-1][0]['pose_candidates']=[dict(value='sol000_00')]
    contact=dict(original_called=True,externally_requested=False,attacker=1,defender=0,counter=1,thread=9,before=[420,420],after=[420,420])
    assert guard_contact_check(owned,block_states,[contact])['passed']
    assert not guard_contact_check(owned,block_states,[])['passed']
    assert not guard_contact_check(owned,block_states,[contact|dict(thread=8)])['passed']
    guard_states=copy.deepcopy(zero_states)
    for s in guard_states:
        s[0]['scalar_observations']['health_candidate']=420
        s[0].update(pose_candidates=[dict(value='sol040_03')],state_candidates=[dict(value='CmnActMidGuardLoop')])
    guard_states[-1][0]['pose_candidates']=[dict(value='sol000_00')]
    guarded=host_event|dict(before=[420,420],after=[420,420],requested_damage=None,caller_result_committed=True,native_pair_called=True)
    guard_check=lambda e=guarded:external_contact_check(zero_records,guard_states,suppressed,[],[e],2,0,True,True)
    assert guard_check()['passed'] and guard_check()['guard_semantics_verified']
    assert not guard_check(e=guarded|dict(native_pair_called=False))['passed']
    assert not guard_check(e=guarded|dict(caller_result_committed=False))['passed']
    bad_zero=copy.deepcopy(zero_states);bad_zero[3][0]['scalar_observations']['hitstop_candidate']=1
    assert not host_check(samples=bad_zero)['passed']
    reject(lambda:check(events=[event,event]))
    reject(lambda:check(events=[event|dict(after=[])]))
    for patch in (dict(counter=3),dict(thread=8),dict(attacker=0),dict(source_collision_suppressed=False)):
        assert not check(events=[event|patch])['passed']
    for patch in (dict(argument=2),dict(counter=0),dict(thread=8),dict(this_delta=0),dict(original_called=True)):
        assert not check(dispatches=[suppressed[0]|patch]+suppressed[1:])['passed']
    assert not check(contacts=[dict(externally_requested=False)])['passed']
    bad=copy.deepcopy(states);bad[2][0]['scalar_observations']['hitstop_candidate']-=1
    assert not contact_check(records,bad)['passed']
    bad=copy.deepcopy(states)
    for s in bad:s[1]['scalar_observations']['health_candidate']=420
    assert not contact_check(records,bad)['passed']
    print('Scalar function bounds/byte/alias rejection and contact/countdown/held-age/freeze/recovery proof passed.')


if __name__=='__main__': main()
