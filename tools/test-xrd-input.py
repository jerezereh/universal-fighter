"""Authored named-input, native-layout and source-step association checks."""
import struct

from xrd_input import input_mask, input_plan, position_plan, input_candidate, input_check, oracle_passed, input_scene_ready


def reject(action):
    try: action()
    except ValueError: return
    raise AssertionError('accepted invalid input/layout')


def main():
    assert input_mask({'forward':True,'punch':True})==24
    assert input_mask({'forward':True,'punch':True},True)==20
    assert input_mask({'back':True},True)==8
    assert input_mask({'forward':True,'left':False,'right':True},True)==8
    assert input_mask({'forward':True,'left':False,'right':False})==0
    assert input_mask({'left':True,'right':True,'up':True,'down':True,'dust':True})==256
    assert input_mask({'punch':True},accept_input=False)==0
    for named in ({'record':True},{'menu':True},{'punch':1},{'unknown':False}): reject(lambda:input_mask(named))
    reject(lambda:input_mask({},facing_left=1))
    assert len(input_plan([dict(frames=2,input={'punch':True})]))==2
    assert len(input_plan([dict(frames=3,input={'forward':True})],3))==3
    for count in (2,4,0,True,161): reject(lambda:input_plan([dict(frames=3,input={'forward':True})],count))
    fighter=lambda x,flip:dict(x_raw=x,y_raw=0,hit_count=0,facing_left=flip,rotation_raw=0,
        scale_raw=[1000,1000],boxes=[[0,-50,-100,100,100]],pose_candidates=[dict(value='sol000_00')])
    actors=[fighter(0,False),fighter(200000,True)]
    retreat=input_plan([dict(frames=5,input={'back':True})]);forward=input_plan([dict(input={'forward':True})])
    assert input_scene_ready(actors,'render-facing',forward)
    assert not input_scene_ready(actors,'render-framing',forward)
    assert input_scene_ready(actors,'render-position',retreat)
    assert not input_scene_ready(actors,'render-position',forward)
    actors[1]['x_raw']=90000
    assert not input_scene_ready(actors,'render-facing',forward)
    assert input_scene_ready(actors,'render-position',retreat)
    actors[1]['hit_count']=1
    assert not input_scene_ready(actors,'render-position',retreat)
    actors[1]['hit_count']=0;actors[0]['y_raw']=1
    assert not input_scene_ready(actors,'render-facing',forward)
    for plan in ([],[dict(frames=True)],[dict(frames=161)],[dict(frames=100),dict(frames=100)],[dict(extra=1)],[dict(accept_input=0)],[dict(hold_ms=501)],[dict(hold_ms=True)]):
        reject(lambda:input_plan(plan))
    # Invented fields/code locations; no source game bytes or layout profile in this test.
    code=bytearray(b'\xcc'*0x500)
    code[0x100:0x140]=b'\x90'*63+b'\xc3'
    code[0x110:0x118]=b'\x56\x8b\xcf\xe8'+struct.pack('<i',0x1300-0x1118)
    code[0x300:0x318]=b'\x90'*21+b'\xc2\x04\x00'
    row=lambda address,op,args:dict(address=address,op=op,args=args)
    sampler=[row(0x1100,'lea','ecx,[eax+0x200]'),row(0x1110,'push','esi'),
        row(0x1111,'mov','ecx,edi'),row(0x1113,'call','0x1300'),row(0x1118,'push','esi'),
        row(0x1119,'push','ebp'),row(0x111a,'add','edi,0x16'),row(0x111d,'inc','ebp'),row(0x113f,'ret','')]
    writer=[row(0x1300,'mov','WORD PTR [ecx+0x2],si'),row(0x1304,'movzx','eax,WORD PTR [ecx+0x14]'),
        row(0x1308,'cmp','si,WORD PTR [ecx+eax*2+0x4]'),row(0x130c,'lea','eax,[ecx+eax*2+0xc]'),
        row(0x1310,'cmp','ax,0x4'),row(0x1315,'ret','0x4')]
    local=dict(sampler_rva=0x1100,sampler_size=64,writer_rva=0x1300,writer_size=24,ingress_rva=0x1110)
    owner=[row(0x1000,'call','0x1100')]
    p=input_candidate(code,0x1000,local,owner,sampler,writer)
    assert p['ring_field']==0x200 and p['capacity']==4 and p['stride']==22 and not p['validated_semantics']
    reject(lambda:input_candidate(code,0x1000,local,[],sampler,writer))
    reject(lambda:input_candidate(code,0x1000,local|dict(ingress_rva=0x1111),owner,sampler,writer))
    reject(lambda:input_candidate(code,0x1000,local,owner,sampler[:6]+[sampler[6]|dict(args='edi,0x18')]+sampler[7:],writer))
    bad=bytearray(code);bad[0x110]=0x90
    reject(lambda:input_candidate(bad,0x1000,local,owner,sampler,writer))
    records=[dict(executed=True,before=10,requested_inputs=[16,0])]
    states=[[dict(x_raw=0,y_raw=0,facing_left=False,hit_count=1,state_candidates=[dict(value='NmlAtk5A')],pose_candidates=[dict(value='sol200_02')]),dict(x_raw=100000)]]
    calls=[dict(injected=True,counter=10,slot=i,incoming=mask) for i,mask in enumerate([16,0])]
    checked=input_check(records,states,calls)
    assert checked['source_history_linked'] and checked['standing_punch_activations']==1 and checked['active_normal_steps']==1
    assert not input_check(records,states,calls[:-1])['source_history_linked']
    assert not input_check(records,states,[calls[0]|dict(incoming=0),calls[1]])['source_history_linked']
    fighter=lambda x,y,left:dict(x_raw=x,y_raw=y,facing_left=left,hit_count=0,state_candidates=[],pose_candidates=[])
    states=[[fighter(x,y,left),dict(x_raw=0)] for x,y,left in [(-100000,0,False),(200000,100000,False),(200000,0,True),(210000,0,True),(205000,0,True)]]
    packets=[dict(input=n,accept_input=True) for n in ({},{'right':True},{},{'back':True},{'forward':True})]
    records=[dict(executed=True,before=i,requested_inputs=[m,0]) for i,m in enumerate((0,8,0,8,4))]
    calls=[dict(injected=True,counter=i,slot=j,incoming=m) for i,r in enumerate(records) for j,m in enumerate(r['requested_inputs'])]
    crossed=input_check(records,states,calls,packets)
    assert oracle_passed('crossover',crossed)
    assert not oracle_passed('crossover',crossed|dict(grounded_inward_facings=[True]))
    reject(lambda:oracle_passed('unsupported',crossed))
    print('Named input/facing/SOCD, bounded plans, native layout/caller/byte rejection and per-step history association passed.')


if __name__=='__main__': main()

rolling=position_plan([dict(frames=8,input={'back':True}),dict(frames=8,input={'forward':True}),dict(frames=4,input={})],20)
assert len(rolling)==20
assert input_mask(rolling[0]['input'],False)==4 and input_mask(rolling[0]['input'],True)==8
assert input_mask(rolling[8]['input'],False)==8 and input_mask(rolling[8]['input'],True)==4
for data,count in (([dict(frames=19,input={'back':True})],20),([dict(input={})],1),
                   ([dict(input={'punch':True})],1),([dict(input={'up':True})],1),
                   ([dict(input={'forward':True},accept_input=False)],1),
                   ([dict(input={'left':True,'right':True})],1)):
    reject(lambda:position_plan(data,count))
