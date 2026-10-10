"""Validate session-local SIGN input ingress and compile named receiver inputs."""
import re
import struct

from xrd_state import unique

# Core bits agree with the inspected SIGN mapper and pinned public input declarations.
# Macros and training/menu controls are deliberately excluded from this first slice.
INPUT_BITS=dict(up=1,down=2,left=4,right=8,punch=16,kick=32,slash=64,heavy_slash=128,dust=256,taunt=512)


def input_mask(named,facing_left=False,accept_input=True):
    if type(named)!=dict or any(k not in INPUT_BITS and k not in ('forward','back') or type(v)!=bool for k,v in named.items()):
        raise ValueError('unknown/non-boolean SIGN input')
    if type(facing_left)!=bool or type(accept_input)!=bool: raise ValueError('invalid facing/input acceptance')
    if not accept_input: return 0
    values=dict(named)
    if 'left' not in named and 'right' not in named:
        values['left']=named.get('forward' if facing_left else 'back',False)
        values['right']=named.get('back' if facing_left else 'forward',False)
    # ponytail: neutral opposing directions; no game-specific SOCD policy until its oracle exists.
    for a,b in (('left','right'),('up','down')):
        if values.get(a) and values.get(b): values[a]=values[b]=False
    return sum(bit for name,bit in INPUT_BITS.items() if values.get(name))


def input_plan(data,expected_frames=None):
    if type(data)!=list or not 1<=len(data)<=32: raise ValueError('input plan must have 1..32 segments')
    frames=[]
    for segment in data:
        if type(segment)!=dict or set(segment)-{'frames','input','label','accept_input','hold_ms'}:
            raise ValueError('invalid input segment')
        count=segment.get('frames',1);label=segment.get('label','input')
        if type(count)!=int or not 1<=count<=160 or type(label)!=str or not 1<=len(label)<=32:
            raise ValueError('invalid input frame count/label')
        named=segment.get('input',{});accept=segment.get('accept_input',True)
        hold=segment.get('hold_ms',0)
        if type(hold)!=int or not 0<=hold<=500: raise ValueError('invalid bounded input hold')
        input_mask(named,False,accept)
        frames.extend(dict(input=dict(named),label=label,accept_input=accept,hold_ms=hold) for _ in range(count))
        if len(frames)>160: raise ValueError('input plan exceeds bounded gate capacity')
    if expected_frames is not None and (type(expected_frames)!=int or not 1<=expected_frames<=160 or len(frames)!=expected_frames):
        raise ValueError('input plan does not match expected source credit count')
    return frames


def position_plan(data,expected_frames):
    frames=input_plan(data,expected_frames)
    if any(set(q['input'])-{'left','right','forward','back'} for q in frames):
        raise ValueError('rolling positioning excludes attacks and vertical inputs')
    if not any(input_mask(q['input'],False,q['accept_input']) for q in frames):
        raise ValueError('positioning requires a non-neutral request')
    return frames


def input_scene_ready(fighters,oracle,requests):
    if len(fighters)!=2 or any(f['y_raw'] or f['hit_count'] for f in fighters):return False
    if not any(re.fullmatch(r'sol00[01]_[0-9]{2}',n['value']) for n in fighters[0]['pose_candidates']):return False
    distance=abs(fighters[0]['x_raw']-fighters[1]['x_raw'])
    if oracle=='contact':return distance<=350000
    # A pure retreat can safely create spacing without a guessed position write.
    if oracle=='render-position' and requests and all(q['accept_input'] and q['input'] in ({},{'back':True}) for q in requests) and any(q['input'].get('back') for q in requests):return True
    if oracle=='render-facing':
        from xrd_combat import world_boxes
        left,right=sorted(fighters,key=lambda f:f['x_raw'])
        a,b=world_boxes(left,0),world_boxes(right,0)
        return bool(a and b) and max(box[2] for box in a)<min(box[0] for box in b)
    return distance>=350000


def input_check(records,states,inputs,requests=()):
    executed=[(r,s) for r,s in zip(records,states) if r['executed']]
    by_counter={}
    for i in inputs:
        if i['injected']: by_counter.setdefault(i['counter'],[]).append(i)
    linked=bool(executed)
    for r,s in executed:
        calls=by_counter.get(r['before'],[])
        linked &= len(calls)==2 and sorted(i['slot'] for i in calls)==[0,1] and all(i['incoming']==r['requested_inputs'][i['slot']] for i in calls)
    walk_left=walk_right=airborne=False;normal_activations=0;was_normal=False
    for index,(r,s) in enumerate(executed):
        sol=s[0];normal=any(n['value']=='NmlAtk5A' for n in sol['state_candidates']) and any(n['value'].startswith('sol200_') for n in sol['pose_candidates'])
        if normal and not was_normal: normal_activations+=1
        was_normal=normal
        airborne |= sol['y_raw']>0
        if index:
            delta=sol['x_raw']-executed[index-1][1][0]['x_raw']
            mask=r['requested_inputs'][0]
            walk_left |= bool(mask&4) and delta<0
            walk_right |= bool(mask&8) and delta>0
    cross=False;grounded_facings=set();relative_left=relative_right=False
    for index,(r,s) in enumerate(executed):
        sol,opponent=s
        if index:
            before=executed[index-1][1]
            cross |= (sol['x_raw']>opponent['x_raw'])!=(before[0]['x_raw']>before[1]['x_raw'])
            if index<len(requests) and sol['y_raw']==0 and before[0]['y_raw']==0:
                packet=requests[index];named=packet['input'];facing=before[0]['facing_left']
                expected=input_mask(named,facing,packet['accept_input'])
                delta=sol['x_raw']-before[0]['x_raw']
                if ('forward' in named or 'back' in named) and expected==r['requested_inputs'][0] and delta:
                    relative_left |= bool(expected&4) and delta<0
                    relative_right |= bool(expected&8) and delta>0
        if sol['y_raw']==0 and abs(sol['x_raw']-opponent['x_raw'])>50000 and sol['facing_left']==(sol['x_raw']>opponent['x_raw']):
            grounded_facings.add(sol['facing_left'])
    return dict(source_history_linked=bool(linked),executed_steps=len(executed),
        walk_left=bool(walk_left),walk_right=bool(walk_right),airborne=bool(airborne),
        grounded_at_end=bool(executed) and executed[-1][1][0]['y_raw']==0,
        standing_punch_activations=normal_activations,
        active_normal_steps=sum(s[0]['hit_count']>0 for r,s in executed),
        opponent_neutral=bool(executed) and all(r['requested_inputs'][1]==0 for r,s in executed),
        crossed_opponent=bool(cross),grounded_inward_facings=sorted(grounded_facings),
        relative_walk_left=bool(relative_left),relative_walk_right=bool(relative_right))


def oracle_passed(kind,result):
    if kind=='movement':
        return all(result[k] for k in ('walk_left','walk_right','airborne','grounded_at_end','opponent_neutral')) and result['standing_punch_activations']>=2 and result['active_normal_steps']>0
    if kind=='crossover':
        return all(result[k] for k in ('crossed_opponent','airborne','grounded_at_end','opponent_neutral','relative_walk_left','relative_walk_right')) and result['grounded_inward_facings']==[False,True]
    raise ValueError('unknown input oracle')


def input_candidate(code,code_rva,local,owner_rows,sampler_rows,writer_rows):
    """Derive the native ring layout and callsite from bounded actual instructions."""
    for label,rows,ending in (('sampler',sampler_rows,b'\xc3'),('writer',writer_rows,b'\xc2\x04\x00')):
        rva,size=(local[label+'_'+k] for k in ('rva','size'))
        if type(rva)!=int or type(size)!=int: raise ValueError('non-integer native input candidate')
        at=rva-code_rva
        if not 0<at<at+size<=len(code) or not 16<=size<=4096 or code[at-1]!=0xcc or not code[at:at+size].endswith(ending):
            raise ValueError('invalid bounded native input '+label)
        if not rows or rows[0]['address']!=rva or rows[-1]['op']!='ret' or rows[-1]['address']+len(ending)!=rva+size:
            raise ValueError('input disassembly extent mismatch')
    sampler,writer,ingress=(local[k] for k in ('sampler_rva','writer_rva','ingress_rva'))
    if not any(r['op']=='call' and r['args']==hex(sampler) for r in owner_rows):
        raise ValueError('sampler is not called by the validated update owner')
    fields=unique([int(m[1],16) for r in sampler_rows if r['op']=='lea' and (m:=re.fullmatch(r'ecx,\[eax\+0x([0-9a-f]+)\]',r['args']))],'native input ring origin')
    i=unique([i for i,r in enumerate(sampler_rows) if r['address']==ingress],'input ingress instruction')
    strides=unique([int(m[1],16) for r in sampler_rows[i+3:i+24] if r['op']=='add' and (m:=re.fullmatch(r'edi,0x([0-9a-f]+)',r['args']))],'native input ring stride')
    if i+2>=len(sampler_rows) or [(r['op'],r['args']) for r in sampler_rows[i:i+3]]!=[('push','esi'),('mov','ecx,edi'),('call',hex(writer))]:
        raise ValueError('input ingress is not the native ring write')
    at=ingress-code_rva
    if code[at:at+4]!=b'\x56\x8b\xcf\xe8' or ingress+8+struct.unpack_from('<i',code,at+4)[0]!=writer:
        raise ValueError('input ingress instruction bytes disagree')
    if not any(r['op']=='inc' and r['args']=='ebp' for r in sampler_rows) or not any(r['op']=='push' and r['args']=='ebp' for r in sampler_rows[i+3:i+7]):
        raise ValueError('missing native player-index loop')
    current=unique([int(m[1],16) for r in writer_rows if r['op']=='mov' and (m:=re.fullmatch(r'WORD PTR \[ecx\+0x([0-9a-f]+)\],si',r['args']))],'current input field')
    index=unique(sorted(set(int(m[1],16) for r in writer_rows if r['op']=='movzx' and (m:=re.fullmatch(r'(?:eax|edx),WORD PTR \[ecx\+0x([0-9a-f]+)\]',r['args'])))),'ring index field')
    inputs=unique([int(m[1],16) for r in writer_rows if r['op']=='cmp' and (m:=re.fullmatch(r'si,WORD PTR \[ecx\+eax\*2\+0x([0-9a-f]+)\]',r['args']))],'ring entries')
    held=unique([int(m[1],16) for r in writer_rows if r['op']=='lea' and (m:=re.fullmatch(r'eax,\[ecx\+eax\*2\+0x([0-9a-f]+)\]',r['args']))],'ring held durations')
    capacity=unique([int(m[1],16) for r in writer_rows if r['op']=='cmp' and (m:=re.fullmatch(r'ax,0x([0-9a-f]+)',r['args']))],'ring capacity')
    if not 0<fields<4<<20 or fields%4 or not 2<=capacity<=64 or strides!=index+2 or not 0<current<inputs<held<index or inputs+2*capacity!=held or held+2*capacity!=index:
        raise ValueError('invalid bounded native input layout')
    result=dict(local,ring_field=fields,stride=strides,current=current,index=index,inputs=inputs,held=held,capacity=capacity,validated_semantics=False)
    for label in ('sampler','writer'):
        at=local[label+'_rva']-code_rva
        result[label+'_hex']=code[at:at+local[label+'_size']].hex()
    return result
