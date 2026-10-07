"""Authored native-alpha bounds and rejection checks; no source assets."""
from xrd_layer import layer_pixels

metadata=dict(width=3,height=2,kind='render-layer',format=21,native_coverage_verified=False,
    source_graphics_state_verified=True,replayed_draws=2)
pixels=bytes([0,0,0,0, 0,0,0,255, 1,2,3,255, 0,0,0,0, 0,0,0,0, 0,0,0,0])
result=layer_pixels(metadata,pixels)
assert result['native_coverage_bounds']==[1,0,3,1] and result['covered_pixels']==2
assert result['native_alpha_values']=={'0':4,'255':2} and not result['isolated_rgba']
for changed,data in ((dict(format=22),pixels),(dict(native_coverage_verified=True),pixels),
        (dict(source_graphics_state_verified=False),pixels),({},pixels[:-1]),({},bytes(24)),
        ({},bytes([0,0,0,255])*6),({},bytes([1])+pixels[1:])):
    try: layer_pixels(metadata|changed,data)
    except ValueError: continue
    raise AssertionError('invalid/native-alpha claim accepted')
print('Native alpha preserves black material coverage; X8/promoted/unrestored/empty/full/leaking layers reject.')
