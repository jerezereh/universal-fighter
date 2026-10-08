"""Authored native-alpha bounds and rejection checks; no source assets."""
import copy
from xrd_layer import layer_pixels, capture_steps, capture_presentations, render_oracle, settling_oracle, settled_oracle, unit_calibration

metadata=dict(width=3,height=2,kind='render-layer',format=21,native_coverage_verified=False,
    source_graphics_state_verified=True,replayed_draws=2)
pixels=bytes([0,0,0,0, 0,0,0,255, 1,2,3,255, 0,0,0,0, 0,0,0,0, 0,0,0,0])
result=layer_pixels(metadata,pixels)
assert result['native_coverage_bounds']==[1,0,3,1] and result['covered_pixels']==2
assert result['native_alpha_values']=={'0':4,'255':2} and not result['isolated_rgba']
assert result['touches_target_edge']
for changed,data in ((dict(format=22),pixels),(dict(native_coverage_verified=True),pixels),
        (dict(source_graphics_state_verified=False),pixels),({},pixels[:-1]),({},bytes(24)),
        ({},bytes([0,0,0,255])*6),({},bytes([1])+pixels[1:])):
    try: layer_pixels(metadata|changed,data)
    except ValueError: continue
    raise AssertionError('invalid/native-alpha claim accepted')
print('Native alpha preserves black material coverage; X8/promoted/unrestored/empty/full/leaking layers reject.')

assert capture_steps('0,4,8,12')==[0,4,8,12]
for bad in ('', '0', '1,2', '0,0', '0,3,2', '0,161', '0,1,2,3,4,5,6,7,8', '0,no'):
    try: capture_steps(bad)
    except ValueError: continue
    raise AssertionError('invalid selected capture steps accepted')
steps=[0,4,8,12];layers=[]
for step,x,y,cx,cy in zip(steps,[0,-20,20,20],[0,0,0,20000],[10,8,12,12],[10,10,10,8]):
    layers.append(dict(request_index=step,counter=100+step,skipped_draws_total=0,source_graphics_state_verified=True,
        native_coverage_center=[cx,cy],alpha_sha256=str(step),rgb_sha256=str(step),
        observation=dict(fighters=[dict(x_raw=x,y_raw=y,hit_count=0,state_candidates=[])])))
scenes=copy.deepcopy(layers)
assert render_oracle('render-motion',layers,scenes,steps)['passed']
wrong=copy.deepcopy(layers);wrong[1]['native_coverage_center']=[12,10]
assert not render_oracle('render-motion',wrong,scenes,steps)['passed']
same=copy.deepcopy(layers)
for c in same: c['alpha_sha256']='unchanged'
assert not render_oracle('render-motion',same,scenes,steps)['passed']
for bad_layers,bad_scenes in ((layers[:-1],scenes),(layers,list(reversed(scenes))),
        (layers,[dict(s, counter=0) for s in scenes]),([dict(c, skipped_draws_total=1) for c in layers],scenes)):
    try: render_oracle('render-motion',bad_layers,bad_scenes,steps)
    except ValueError: continue
    raise AssertionError('invalid render association accepted')
wrong_counter=[dict(c,counter=100) for c in layers]
try: render_oracle('render-motion',wrong_counter,copy.deepcopy(wrong_counter),steps)
except ValueError: pass
else: raise AssertionError('unadvanced native counter accepted')
attack=copy.deepcopy(layers)
attack[1]['observation']['fighters'][0].update(state_candidates=[dict(value='NmlAtk5A')],hit_count=1)
assert render_oracle('render-attack',attack,copy.deepcopy(attack),steps)['passed']
assert not render_oracle('render-attack',layers,scenes,steps)['passed']
print('Selected capture bounds, paired source states, motion direction, changed mesh and active normal oracles passed.')

assert capture_presentations('3,6,12,24',[0,1])==[3,6,12,24]
for bad in ('','2','3,3','3,24,6','3,25','3,4,5,6,7'):
    try: capture_presentations(bad,[0,1])
    except ValueError: continue
    raise AssertionError('invalid repeated presentations accepted')
held=[]
for step in (0,1):
    for presentation in (3,6,12,24):
        c=copy.deepcopy(layers[step]);c.update(request_index=step,counter=100+step,
            presentation_index=presentation,raw_sha256=str(step),alpha_sha256=str(step));held.append(c)
assert settling_oracle(held,copy.deepcopy(held),[0,1],[3,6,12,24])['passed']
later=copy.deepcopy(held);later[4]['raw_sha256']='early'
assert settling_oracle(later,copy.deepcopy(held),[0,1],[3,6,12,24])['stability'][1]['earliest_tested_stable_tail']==6
unstable=copy.deepcopy(held);unstable[-1]['raw_sha256']='different'
assert not settling_oracle(unstable,copy.deepcopy(held),[0,1],[3,6,12,24])['passed']
bad=copy.deepcopy(held);bad[-1]['observation']['fighters'][0]['x_raw']+=1
try: settling_oracle(bad,copy.deepcopy(bad),[0,1],[3,6,12,24])
except ValueError: pass
else: raise AssertionError('changed held source state accepted')
print('Repeated presentation bounds, complete held-state pairs and changing mesh rejection passed.')

normalized=copy.deepcopy(layers)
for c in normalized:
    c['observation']['fighters'][0]['facing_left']=False
    c.update(normalized_projection=True,canonical_right_facing=True,source_facing_left=False,
        projection_pivot=[10,15],source_render_origin=[0,0,0,1],touches_target_edge=False,width=20,height=20)
assert render_oracle('render-framing',normalized,copy.deepcopy(normalized),steps)['passed']
pairs=[]
for c in normalized:
    for p in (4,5):
        pairs.append(copy.deepcopy(c)|dict(presentation_index=p,settled_pair=[4,5],raw_sha256=str(c['request_index']),
            identical_native_pixels=True,frame_readiness_candidate=True))
assert settled_oracle('render-framing',pairs,copy.deepcopy(pairs),steps)['passed']
for key,value in [('raw_sha256','different'),('source_render_origin',[float('nan'),0,0,1]),
        ('presentation_index',7),('canonical_right_facing',False),('touches_target_edge',True)]:
    bad=copy.deepcopy(pairs);bad[1][key]=value
    try: settled_oracle('render-framing',bad,copy.deepcopy(bad),steps)
    except ValueError: pass
    else: raise AssertionError('unready native frame accepted')
print('Normalized framing and consecutive native-pixel/state evidence checks passed.')

facing=copy.deepcopy(pairs)
for c in facing:
    left=c['request_index']>0
    c['observation']['fighters'][0]['facing_left']=left;c['source_facing_left']=left
    c['raw_sha256']=c['rgb_sha256']=c['alpha_sha256']='same-canonical-idle'
assert settled_oracle('render-facing',facing,copy.deepcopy(facing),steps)['passed']
one_side=copy.deepcopy(facing)
for c in one_side:
    c['source_facing_left']=False;c['observation']['fighters'][0]['facing_left']=False
assert not settled_oracle('render-facing',one_side,copy.deepcopy(one_side),steps)['passed']
assert not settled_oracle('render-framing',facing,copy.deepcopy(facing),steps)['passed']
print('Facing normalization accepts identical canonical idle pixels; missing facing and unchanged motion still reject.')

units=[]
for x,y in [(0,0),(10000,10000),(-10000,20000),(30000,30000)]:
    c=copy.deepcopy(pairs[0]);c['observation']['fighters'][0].update(x_raw=x,y_raw=y)
    c.update(pixels_per_world_unit=2,native_absolute_body_origin=[x/2000,0,y/2000]);units.append(c)
fit=unit_calibration(units)
assert fit['world_per_source_logical_unit']==.5 and fit['pixels_per_source_logical_unit']==1
assert fit['projection_pivot']==[10,15] and fit['body_origin_mapping_verified']
assert not fit['foot_pivot_verified'] and not fit['host_publishable']
for change in [dict(native_absolute_body_origin=[float('nan'),0,0]),dict(native_absolute_body_origin=[0,1,0]),
        dict(native_absolute_body_origin=[2,0,0]),dict(projection_pivot=[11,15]),dict(identical_native_pixels=False)]:
    bad=copy.deepcopy(units);bad[0].update(change)
    try: unit_calibration(bad)
    except ValueError: pass
    else: raise AssertionError('unverified/mismatched unit sample accepted')
bad=copy.deepcopy(units)
for c in bad: c['native_absolute_body_origin'][2]*=2
try: unit_calibration(bad)
except ValueError: pass
else: raise AssertionError('unequal native axis scale accepted')
try: unit_calibration([units[0]]*3)
except ValueError: pass
else: raise AssertionError('grounded-only unit samples accepted')
print('Observed unit fit, zero origin, axis agreement and unsupported foot/color publication checks passed.')
