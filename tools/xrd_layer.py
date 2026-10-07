"""Inspect the native alpha channel of a diagnostic private mesh layer."""
import hashlib


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


def render_oracle(kind,layers,scenes,steps):
    if kind not in ('render-motion','render-attack'): raise ValueError('unknown native render oracle')
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
    passed=(left and right and jump if kind=='render-motion' else bool(normal) and active) and changed
    return dict(passed=passed,selected_steps=steps,paired_source_states=True,image_moves_left=left,
        image_moves_right=right,image_rises_with_jump=jump,normal_render_samples=len(normal),
        active_normal_rendered=active,mesh_images_changed=changed,
        clipped_render_steps=[c['request_index'] for c in layers if c.get('touches_target_edge')],
        native_render_latency_verified=False,atomic_native_frame=False,isolated_rgba=False)
