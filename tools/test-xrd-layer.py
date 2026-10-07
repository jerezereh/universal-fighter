"""Authored native-alpha bounds and rejection checks; no source assets."""
import copy
from xrd_layer import layer_pixels, capture_steps, render_oracle

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
