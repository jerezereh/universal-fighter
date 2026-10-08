"""Inspect the native alpha channel of a diagnostic private mesh layer."""
import hashlib
import math


def layer_pixels(metadata,pixels):
    import numpy as np
    width,height=metadata['width'],metadata['height']
    if (any(type(n)!=int or not 1<=n<=2048 for n in (width,height)) or
            metadata.get('kind')!='render-layer' or metadata.get('format')!=21 or
            metadata.get('native_coverage_verified') is not False or
            metadata.get('source_graphics_state_verified') is not True or
            type(metadata.get('replayed_draws'))!=int or not 1<=metadata['replayed_draws']<=8192 or len(pixels)!=width*height*4):
        raise ValueError('requires bounded restored-state diagnostic A8 layer')
    bgra=np.frombuffer(pixels,dtype='u1').reshape(height,width,4)
    alpha=bgra[:,:,3];covered=alpha!=0
    if not covered.any() or covered.all(): raise ValueError('missing/full-target coverage')
    y,x=np.nonzero(covered);bounds=[int(x.min()),int(y.min()),int(x.max())+1,int(y.max())+1]
    if np.any(bgra[~covered,:3]): raise ValueError('RGB outside native coverage')
    values,counts=np.unique(alpha,return_counts=True)
    return dict(native_alpha_values={str(int(v)):int(n) for v,n in zip(values,counts)},
        native_coverage_bounds=bounds,covered_pixels=int(covered.sum()),
        native_coverage_center=[float(x.mean()),float(y.mean())],
        touches_target_edge=bounds[0]==0 or bounds[1]==0 or bounds[2]==width or bounds[3]==height,
        alpha_sha256=hashlib.sha256(alpha.tobytes()).hexdigest(),transparent_rgb_zero=True,
        native_coverage_verified=False,isolated_rgba=False)


def save_layer_preview(folder,metadata):
    """RGBA crop and checker preview use the actual GPU alpha, including black material pixels."""
    import numpy as np
    from PIL import Image
    pixels=(folder/metadata['raw']).read_bytes();analysis=layer_pixels(metadata,pixels)
    rgba=np.frombuffer(pixels,dtype='u1').reshape(metadata['height'],metadata['width'],4)[:,:,[2,1,0,3]]
    image=Image.fromarray(rgba).crop(tuple(analysis['native_coverage_bounds']))
    name=metadata['image'].removesuffix('.png')
    image.save(folder/(name+'-rgba.png'))
    y,x=np.indices((image.height,image.width));gray=np.where(((x//16+y//16)%2)==0,180,220).astype('u1')
    check=Image.fromarray(np.repeat(gray[:,:,None],3,axis=2)).convert('RGBA')
    check.alpha_composite(image);check.convert('RGB').save(folder/(name+'-checker.png'))
    return analysis|dict(rgba_preview=name+'-rgba.png',checker_preview=name+'-checker.png',
        crop_is_diagnostic=True,pivot_verified=False,color_verified=False)


def capture_steps(text):
    try: steps=[int(n) for n in text.split(',')]
    except (TypeError,ValueError): raise ValueError('invalid selected layer steps')
    if not 2<=len(steps)<=8 or steps[0]!=0 or steps!=sorted(set(steps)) or steps[-1]>160:
        raise ValueError('requires 2..8 ordered distinct layer steps starting at zero, ending by 160')
    return steps


def capture_presentations(text,steps):
    try: values=[int(n) for n in text.split(',')]
    except (TypeError,ValueError): raise ValueError('invalid selected presentations')
    if not values or values[0]!=3 or values!=sorted(set(values)) or values[-1]>24 or len(values)*len(steps)>8:
        raise ValueError('requires ordered presentations starting at 3, ending by 24, at most eight step/presentation pairs')
    return values


def settling_oracle(layers,scenes,steps,presentations):
    expected=[(step,p) for step in steps for p in presentations]
    if ([(c.get('request_index'),c.get('presentation_index')) for c in layers]!=expected or
            [(c.get('request_index'),c.get('presentation_index')) for c in scenes]!=expected):
        raise ValueError('missing/out-of-order settling pairs')
    stable=[]
    for step in steps:
        images=[c for c in layers if c['request_index']==step]
        source=[c for c in scenes if c['request_index']==step]
        if any(((c['counter']-layers[0]['counter'])&0xffffffff)!=step or
                c['counter']!=s['counter'] or c['observation']['fighters']!=s['observation']['fighters'] or
                c['observation']['fighters']!=images[0]['observation']['fighters'] or
                c.get('skipped_draws_total')!=0 or c.get('source_graphics_state_verified') is not True
                for c,s in zip(images,source)):
            raise ValueError('source advanced/state changed/incomplete layer during settling')
        tail=next((c['presentation_index'] for i,c in enumerate(images[:-1])
            if len({later['raw_sha256'] for later in images[i:]})==1),None)
        stable.append(dict(request_index=step,identical_mesh_pixels=len({c['raw_sha256'] for c in images})==1,
            identical_mesh_alpha=len({c['alpha_sha256'] for c in images})==1,
            distinct_mesh_images=len({c['raw_sha256'] for c in images}),earliest_tested_stable_tail=tail,
            first_to_final_center_delta=[b-a for a,b in zip(images[0]['native_coverage_center'],images[-1]['native_coverage_center'])]))
    return dict(passed=all(s['identical_mesh_pixels'] for s in stable),held_state_verified=True,
        selected_steps=steps,presentations=presentations,stability=stable,
        native_render_latency_verified=False,atomic_native_frame=False,isolated_rgba=False)


def render_oracle(kind,layers,scenes,steps):
    if kind not in ('render-motion','render-attack','render-framing','render-facing','render-neutral'): raise ValueError('unknown native render oracle')
    if ([c.get('request_index') for c in layers]!=steps or [c.get('request_index') for c in scenes]!=steps or
            any(c.get('counter')!=s.get('counter') or c['observation']['fighters']!=s['observation']['fighters']
                for c,s in zip(layers,scenes))):
        raise ValueError('missing/out-of-order/unpaired source render steps')
    if any(((c['counter']-layers[0]['counter'])&0xffffffff)!=c['request_index'] for c in layers):
        raise ValueError('native counter does not identify requested render step')
    if any(c.get('skipped_draws_total')!=0 or not c.get('source_graphics_state_verified') for c in layers):
        raise ValueError('incomplete/restoration-failed native mesh layer')
    left=right=jump=False
    for a,b in zip(layers,layers[1:]):
        fa,fb=(c['observation']['fighters'][0] for c in (a,b))
        ca,cb=(c['native_coverage_center'] for c in (a,b))
        dx,dy=fb['x_raw']-fa['x_raw'],fb['y_raw']-fa['y_raw']
        left |= dx<0 and cb[0]<ca[0]-.5
        right |= dx>0 and cb[0]>ca[0]+.5
        jump |= dy>10000 and cb[1]<ca[1]-1
    normal=[c for c in layers if any(n['value']=='NmlAtk5A' for n in c['observation']['fighters'][0]['state_candidates'])]
    active=any(c['observation']['fighters'][0]['hit_count']>0 for c in normal)
    changed=len({c['alpha_sha256'] for c in layers})>1 and len({c['rgb_sha256'] for c in layers})>1
    if kind in ('render-framing','render-facing','render-neutral'):
        if any(c.get('normalized_projection') is not True or c.get('canonical_right_facing') is not True or
                c.get('source_facing_left')!=c['observation']['fighters'][0]['facing_left'] or
                c.get('projection_pivot')!=layers[0].get('projection_pivot') or c.get('touches_target_edge') is not False
                for c in layers): raise ValueError('missing/cropped/noncanonical private projection')
        native=[c['observation']['fighters'][0] for c in layers]
        walked_left=any(b['x_raw']<a['x_raw'] for a,b in zip(native,native[1:]))
        walked_right=any(b['x_raw']>a['x_raw'] for a,b in zip(native,native[1:]))
        risen=any(b['y_raw']>a['y_raw']+10000 for a,b in zip(native,native[1:]))
        # Canonicalizing the same idle pose across a crossover can preserve its silhouette.
        if kind=='render-neutral': passed=True
        elif kind=='render-framing': passed=walked_left and walked_right and risen and changed
        else: passed={f['facing_left'] for f in native}=={False,True}
    else: passed=(left and right and jump if kind=='render-motion' else bool(normal) and active) and changed
    result=dict(passed=passed,selected_steps=steps,paired_source_states=True,image_moves_left=left,
        image_moves_right=right,image_rises_with_jump=jump,normal_render_samples=len(normal),
        active_normal_rendered=active,mesh_images_changed=changed,
        clipped_render_steps=[c['request_index'] for c in layers if c.get('touches_target_edge')],
        native_render_latency_verified=False,atomic_native_frame=False,isolated_rgba=False)
    if kind in ('render-framing','render-facing','render-neutral'):
        result.update(camera_independent_projection=True,native_walk_left=walked_left,
            native_walk_right=walked_right,native_rise=risen,source_facings=sorted({f['facing_left'] for f in native}))
    return result


def settled_oracle(kind,layers,scenes,steps):
    if len(layers)!=2*len(steps) or len(scenes)!=len(layers): raise ValueError('missing settled pairs')
    for i,step in enumerate(steps):
        a,b=layers[i*2:i*2+2];sa,sb=scenes[i*2:i*2+2];pair=[a.get('presentation_index'),b.get('presentation_index')]
        for c in (a,b):
            origin=c.get('source_render_origin',[]);pivot=c.get('projection_pivot',[])
            if (c.get('normalized_projection') is not True or c.get('canonical_right_facing') is not True or
                    c.get('touches_target_edge') is not False or c.get('source_facing_left')!=c['observation']['fighters'][0]['facing_left'] or
                    len(origin)!=4 or not all(type(v) in (int,float) and math.isfinite(v) and abs(v)<=1e6 for v in origin) or origin[3]!=1 or
                    len(pivot)!=2 or not all(type(v)==int and 0<=v<bound for v,bound in zip(pivot,[c['width'],c['height']]))):
                raise ValueError('invalid/unaccepted settled projection geometry')
        if (not all(type(v)==int for v in pair) or not 3<=pair[0]<pair[1]<=24 or pair[1]!=pair[0]+1 or
                any(c.get('request_index')!=step or c.get('settled_pair')!=pair or
                    c.get('identical_native_pixels') is not True or c.get('frame_readiness_candidate') is not True
                    for c in (a,b,sa,sb)) or a['raw_sha256']!=b['raw_sha256'] or a['alpha_sha256']!=b['alpha_sha256'] or
                any(c['counter']!=a['counter'] or c['observation']['fighters']!=a['observation']['fighters'] for c in (b,sa,sb))):
            raise ValueError('changing/unpaired native readiness images')
    result=render_oracle(kind,layers[1::2],scenes[1::2],steps)
    return result|dict(identical_consecutive_native_images=True,
        readiness_presentations=[c['settled_pair'] for c in layers[1::2]],native_render_latency_verified=False)


def unit_calibration(layers):
    """Fit observed body-world X/Z to source logical X/Y, without a retail scale constant."""
    if not 3<=len(layers)<=16: raise ValueError('requires 3..16 selected native samples')
    geometry={(c['width'],c['height'],tuple(c['projection_pivot']),c['pixels_per_world_unit']) for c in layers}
    if len(geometry)!=1: raise ValueError('inconsistent private projection scale/pivot')
    width,height,pivot,pixels_per_world=geometry.pop()
    if (any(type(n)!=int or not 1<=n<=1024 for n in (width,height)) or len(pivot)!=2 or
            any(type(n)!=int or not 0<=n<bound for n,bound in zip(pivot,(width,height))) or
            type(pixels_per_world) not in (int,float) or not math.isfinite(pixels_per_world) or not 0<pixels_per_world<=16):
        raise ValueError('invalid private projection geometry')
    samples=[]
    for c in layers:
        f=c['observation']['fighters'][0];world=c.get('native_absolute_body_origin',[])
        if (c.get('normalized_projection') is not True or c.get('canonical_right_facing') is not True or
                c.get('source_graphics_state_verified') is not True or c.get('identical_native_pixels') is not True or
                c.get('touches_target_edge') is not False or len(world)!=3 or
                any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e6 for v in world) or
                abs(world[1])>.001 or any(type(f.get(k))!=int or abs(f[k])>1e9 for k in ('x_raw','y_raw'))):
            raise ValueError('invalid/unsettled body-world sample')
        samples.append(([f['x_raw']/1000,f['y_raw']/1000],[world[0],world[2]]))
    fits=[]
    for axis in range(2):
        pairs=[(s[axis],w[axis]) for s,w in samples]
        if len({s for s,_ in pairs})<3 or max(s for s,_ in pairs)-min(s for s,_ in pairs)<10:
            raise ValueError('requires three distinct positions spanning ten logical units per axis')
        x=sum(s for s,_ in pairs)/len(pairs);y=sum(w for _,w in pairs)/len(pairs)
        slope=sum((s-x)*(w-y) for s,w in pairs)/sum((s-x)**2 for s,_ in pairs)
        intercept=y-slope*x;residual=max(abs(w-(slope*s+intercept)) for s,w in pairs)
        if not 0<slope<=10 or abs(intercept)>.001 or residual>.001:
            raise ValueError('body origin does not follow source logical position')
        fits.append(dict(world_per_source_logical_unit=slope,intercept=intercept,max_world_residual=residual))
    if abs(fits[0]['world_per_source_logical_unit']/fits[1]['world_per_source_logical_unit']-1)>.001:
        raise ValueError('horizontal/vertical source unit scales disagree')
    scale=sum(f['world_per_source_logical_unit'] for f in fits)/2
    return dict(samples=len(samples),axes=fits,world_per_source_logical_unit=scale,
        pixels_per_source_logical_unit=scale*pixels_per_world,projection_pivot=list(pivot),
        body_origin_mapping_verified=True,foot_pivot_verified=False,color_verified=False,
        isolated_rgba=False,host_publishable=False)


if __name__=='__main__':
    import argparse
    import json
    from pathlib import Path
    parser=argparse.ArgumentParser(description='Recheck retained paired native pixels and fit body/source units offline.')
    parser.add_argument('traces',type=Path,nargs='+')
    args=parser.parse_args();samples=[];checks=[]
    for folder in args.traces:
        receipt=json.loads((folder/'inspection.json').read_text())
        if (receipt['errors'] or not receipt['loaded_code_restored'] or not receipt['detached'] or
                not receipt['source_unchanged'] or not receipt['render_cleanup']['render_code_restored'] or
                not receipt['controlled_update_step_verified'] or not receipt['source_input_routing_verified']):
            raise ValueError('requires clean native source/state/restoration evidence')
        layers=[json.loads(p.read_text()) for p in sorted((folder/'layers').glob('render-[0-9][0-9].json'))]
        scenes=[json.loads(p.read_text()) for p in sorted(folder.glob('render-[0-9][0-9].json'))]
        if not 2<=len(layers)==len(scenes)<=8: raise ValueError('unbounded/missing native image pairs')
        for c in layers+scenes:
            raw=Path(c['raw'])
            if raw.name!=c['raw']: raise ValueError('invalid raw capture path')
            pixels=((folder/'layers' if c['kind']=='render-layer' else folder)/raw).read_bytes()
            if hashlib.sha256(pixels).hexdigest()!=c['raw_sha256']: raise ValueError('native pixels changed')
            rgb=bytearray(len(pixels)//4*3);rgb[0::3],rgb[1::3],rgb[2::3]=pixels[2::4],pixels[1::4],pixels[0::4]
            if hashlib.sha256(rgb).hexdigest()!=c['rgb_sha256']: raise ValueError('native RGB receipt changed')
            if c['kind']=='render-layer': c.update(layer_pixels(c,pixels))
        steps=[c['request_index'] for c in layers[1::2]]
        result=settled_oracle(receipt['input_oracle'],layers,scenes,steps)
        if not result['passed']: raise ValueError('paired native render oracle failed')
        (folder/'render-reassessment.json').write_text(json.dumps(result,indent=2))
        checks.append(dict(trace=str(folder.resolve()),render_oracle=result));samples.extend(layers[1::2])
    result=unit_calibration(samples)|dict(traces=checks)
    destination=args.traces[0]/'unit-calibration.json';destination.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2));print('Saved',destination)
