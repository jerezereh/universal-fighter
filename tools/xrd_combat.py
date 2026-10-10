"""Derive local scalar access fields and check native contact/stop observations."""
import struct


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


def contact_check(records,states):
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
