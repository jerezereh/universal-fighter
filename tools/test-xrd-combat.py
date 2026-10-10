"""Authored scalar-body and native stop/contact association checks."""
import copy
import struct

from xrd_combat import combat_fields, contact_check, contact_observations, world_boxes


def reject(action):
    try: action()
    except ValueError: return
    raise AssertionError('accepted invalid combat profile')


def main():
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
    bad=copy.deepcopy(states);bad[2][0]['scalar_observations']['hitstop_candidate']-=1
    assert not contact_check(records,bad)['passed']
    bad=copy.deepcopy(states)
    for s in bad:s[1]['scalar_observations']['health_candidate']=420
    assert not contact_check(records,bad)['passed']
    print('Scalar function bounds/byte/alias rejection and contact/countdown/held-age/freeze/recovery proof passed.')


if __name__=='__main__': main()
