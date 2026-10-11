"""Authored proxy scope/ownership rejection checks; no source code or process."""
import copy
import hashlib
import struct
from xrd_proxy import attack_region, idle_check, pair_steps, pair_result
from xrd_combat import multiple_contact_check


def reject(action):
    try: action()
    except ValueError: return
    raise AssertionError('invalid proxy witness accepted')


code = bytearray(b'\xcc'*512)
code[16:33] = b'\x8d\x8e'+struct.pack('<I',128)+b'\xe8'+struct.pack('<i',128-27)+b'\x8d\x8e'+struct.pack('<I',192)
code[128:160] = b'\x90'*31+b'\xc3'
local = dict(caller_rva=4112, initializer_rva=4224, initializer_size=32,
    initializer_sha256=hashlib.sha256(code[128:160]).hexdigest())
assert attack_region(code,4096,local) == (128,64)
for change in [dict(caller_rva=True),dict(initializer_rva=4225),dict(initializer_size=33),dict(initializer_sha256='wrong')]:
    reject(lambda:attack_region(code,4096,local|change))
bad = bytearray(code);bad[27]=0
reject(lambda:attack_region(bad,4096,local))
records=[dict(executed=True,requested_inputs=[0,0]),dict(executed=False,requested_inputs=None)]
states=[[{},dict(hit_count=0,y_raw=0,pose_candidates=[dict(value='kyk000_01')])] for _ in records]
event=dict(proxy_metadata_restored=True,proxy_hit_count_before=0)
assert idle_check(records,states,event)
alt=copy.deepcopy(states);alt[0][1]['pose_candidates']=[dict(value='kyk001_06')]
assert idle_check(records,alt,event)
assert not idle_check(records,states,event|dict(proxy_metadata_restored=False))
assert not idle_check(records,states,event|dict(proxy_hit_count_before=1))
for field,value in [('hit_count',1),('y_raw',1),('pose_candidates',[dict(value='kyk200_01')]),('pose_candidates',[])]:
    bad=copy.deepcopy(states);bad[0][1][field]=value
    assert not idle_check(records,bad,event)
bad=copy.deepcopy(records);bad[0]['requested_inputs']=[0,16]
assert not idle_check(bad,states,event)
assert not idle_check(records,states[:1],event)
print('Proxy initializer, neutral input, idle pose and restoration rejection checks passed.')

assert pair_steps([5,45],5,85)==[5,45]
pair_result(dict(request_index=5,request_ordinal=1),[5,45],0)
pair_result(dict(request_index=45,request_ordinal=2),[5,45],1)
for event,n in [(dict(request_index=5,request_ordinal=1),1),(dict(request_index=45,request_ordinal=2),0),
                (dict(request_index=45,request_ordinal=2),2),(dict(request_index=45,request_ordinal=1),1)]:
    reject(lambda:pair_result(event,[5,45],n))
reject(lambda:pair_result(dict(request_index=5,request_ordinal=True),[5,45],0))
for values in ([5,5],[45,5],[5,10],[5,80],[True,45],[],[5]):
    reject(lambda:pair_steps(values,5,85))
records=[];states=[];dispatches=[]
for step in range(1,43):
    hp=420-10*(step>=2)-10*(step>=22)
    hurt=2<=step<8 or 22<=step<28
    actors=[dict(x_raw=0,y_raw=0,hit_count=0,rotation_raw=0,scale_raw=[1000,1000],
        facing_left=False,boxes=[[0,-10,-10,20,20]],
        scalar_observations=dict(health_candidate=hp if slot==0 else 420,hitstop_candidate=0,age_candidate=step),
        state_candidates=[dict(value='CmnActNokezoriHighLv1' if hurt and slot==0 else 'CmnActStand')],
        pose_candidates=[dict(value='sol052_00' if hurt and slot==0 else ('sol','kyk')[slot]+'000_00')]) for slot in (0,1)]
    r=dict(before=step-1,after=step,executed=True,thread=9,requested_inputs=[0,0])
    records.append(r);states.append(actors)
    dispatches.extend(dict(counter=step,argument=i,thread=9,this_delta=4,suppressed=True,original_called=False) for i in range(3))
    if step in (2,22):
        for _ in range(5):records.append(r|dict(before=step,executed=False));states.append(copy.deepcopy(actors))
events=[dict(request_index=step,request_ordinal=i+1,counter=step,thread=9,attacker=1,defender=0,
    before=[420-i*10,420],after=[410-i*10,420],native_pair_called=True,source_collision_suppressed=True,
    hitstop_owner='host',requested_damage=10,proxy_metadata_restored=True,proxy_hit_count_before=0) for i,step in enumerate((2,22))]
assert multiple_contact_check(records,states,dispatches,[],events,[2,22],10)['passed']
reject(lambda:multiple_contact_check(records,states[:-1],dispatches,[],events,[2,22],10))
for bad in (events[::-1],events[:1],[events[0],events[1]|dict(request_ordinal=1)],
            [events[0],events[1]|dict(before=[409,420])]):
    reject(lambda:multiple_contact_check(records,states,dispatches,[],bad,[2,22],10))
bad=copy.deepcopy(states);bad[-1][0]['pose_candidates']=[dict(value='sol052_00')]
reject(lambda:multiple_contact_check(records,bad,dispatches,[],events,[2,22],10))
print('Multi-contact ordering, replay/missing event, health continuity and recovery checks passed.')
