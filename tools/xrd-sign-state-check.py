"""Compare observed Sol boxes with the user's imported collision data; no tick claims."""
import argparse
import json
from pathlib import Path

from xrd_package import collision_archive


def check(folder,collision):
    receipt=json.loads((folder/'inspection.json').read_text())
    if not receipt.get('observations_only') or any(receipt.get(k) for k in ('native_tick_verified','host_step','isolated_rgba','universal_contact')):
        raise ValueError('requires an observation-only capture receipt')
    frames=collision_archive(collision.read_bytes())
    matched=unmapped=mismatched=0;active=[];x=[];y=[];facing=set();poses=set()
    with (folder/'state.jsonl').open() as log:
        for line in log:
            r=json.loads(line);s=r['fighters'][0]
            if r['atomic_native_frame']:raise ValueError('unverified atomic native frame claim')
            x.append(s['x_raw']);y.append(s['y_raw']);facing.add(s['facing_left'])
            names=s['pose_candidates']
            if len(names)!=1 or names[0]['value'] not in frames:
                unmapped+=1;continue
            name=names[0]['value'];poses.add(name);source=frames[name]
            if source['hurt']+source['hit']==s['boxes']:matched+=1
            else:mismatched+=1
            if s['hit_count']:
                active.append(dict(wall_seconds=r['wall_seconds'],pose=name,state_candidates=s['state_candidates']))
    if len(x)!=receipt['samples'] or not x or not matched:raise ValueError('capture count/data incomplete')
    result=dict(schema=1,samples=len(x),matched=matched,mismatched=mismatched,unmapped=unmapped,
                x_range=[min(x),max(x)],y_range=[min(y),max(y)],facings=sorted(facing),
                movement_observed=min(x)!=max(x),airborne_observed=max(y)>0,
                active_samples=active,poses=sorted(poses),native_tick_verified=False,
                timing_accepted=False,atomic_frames=False)
    (folder/'collision-check.json').write_text(json.dumps(result,indent=2))
    print('Source collision comparison:',matched,'matched;',mismatched,'mismatched;',unmapped,'unmapped')
    print('Movement:',result['movement_observed'],'airborne:',result['airborne_observed'],'facings:',result['facings'],'active samples:',len(active))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture',type=Path)
    p.add_argument('--collision',type=Path,required=True,help='local imported COL_SOL.bin')
    a=p.parse_args();check(a.capture,a.collision)
