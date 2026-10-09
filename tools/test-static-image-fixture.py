"""Authored static image DTO validation; no retail pixels."""
import base64
import copy
import json
import hashlib
from pathlib import Path
import runpy
import tempfile

demo=runpy.run_path(str(Path(__file__).with_name('passthrough-demo.py')))
with tempfile.TemporaryDirectory() as temporary:
    path=Path(temporary)/'image.json'
    image=dict(Width=2,Height=1,Pivot=[1,1],RGBA=base64.b64encode(bytes([0,0,0,255,10,20,30,128])).decode())
    path.write_text(json.dumps(image));assert demo['load_image'](path)==image
    fighter=demo['Fighter']('authored-image','amber',image)
    assert fighter.image(-70,True)==image
    fighter.reset();assert fighter.image(-50,False)==image
    for field,value in [('Width',1025),('Height',True),('Pivot',[0,32768]),('Pivot',[0.0,0]),('RGBA','???')]:
        bad=copy.deepcopy(image);bad[field]=value;path.write_text(json.dumps(bad))
        try:demo['load_image'](path)
        except ValueError:pass
        else:raise AssertionError(field+' accepted')
print('Static fixture dimensions/pivot/base64 bounds and authored reset/image separation passed.')
exporter=runpy.run_path(str(Path(__file__).with_name('xrd-preview-image.py')))['export']
with tempfile.TemporaryDirectory() as temporary:
    folder=Path(temporary);(folder/'layers').mkdir()
    receipt={k:True for k in ('loaded_code_restored','detached','source_unchanged','controlled_update_step_verified','private_layer_state_restored')}
    receipt.update(errors=[],render_cleanup=dict(render_code_restored=True))
    (folder/'inspection.json').write_text(json.dumps(receipt))
    pixels=bytearray(20*20*4);pixels[4*(5*20+5):4*(5*20+5)+4]=bytes([2,4,6,255])
    metadata=dict(width=20,height=20,kind='render-layer',format=21,native_coverage_verified=False,
        source_graphics_state_verified=True,replayed_draws=13,normalized_projection=True,
        canonical_right_facing=True,identical_native_pixels=True,projection_pivot=[10,15],
        raw='render-01.bgra',raw_sha256=hashlib.sha256(pixels).hexdigest())
    (folder/'layers/render-01.bgra').write_bytes(pixels)
    (folder/'layers/render-01.json').write_text(json.dumps(metadata))
    image=demo['load_image'](exporter(folder,1))
    assert image['Pivot']==[5,10] and base64.b64decode(image['RGBA'])==bytes([6,4,2,255])
    (folder/'layers/render-01.bgra').write_bytes(bytes(len(pixels)))
    try:exporter(folder,1)
    except ValueError:pass
    else:raise AssertionError('changed source pixels exported')
print('Review crop preserves origin and RGB channel order; changed native pixel hash rejects.')
