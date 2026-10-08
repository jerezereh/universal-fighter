"""Authored native grading dependency tables and stale-ABI evidence rejection."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile

spec=importlib.util.spec_from_file_location('boundary',Path(__file__).with_name('xrd-sign-boundary.py'))
boundary=importlib.util.module_from_spec(spec);spec.loader.exec_module(boundary)
code=struct.pack('<5I',0xffff0300,0x02000001,0x800f0800,0x80e40000,0xffff)
with tempfile.TemporaryDirectory() as temporary:
    folder=Path(temporary)
    evidence=dict(pid=123,errors=[],loaded_code_restored=True,detached=True,source_unchanged=True,
        controlled_update_step_verified=True,d3d_abi=dict(native_header_checked=True))
    (folder/'inspection.json').write_text(json.dumps(evidence))
    def packet(index,assembly,lut=None):
        filename=f'screen-{index:02}.bin';(folder/filename).write_bytes(code)
        samplers=[dict(slot=i,texture=None,srgb=0) for i in range(16)]
        if lut:samplers[lut['slot']]['texture']=lut['texture']
        return dict(file=filename,kind='screen-shader',code_size=len(code),read_only=True,shader=f'0x{index}000',
            source_target='0x2000',constants_hex='00'*(224*16),assembly=assembly,srgb_write=0,samplers=samplers,
            counter=10,trace_frame=1,trace_event=1,lut_source=lut,sha256=hashlib.sha256(code).hexdigest())
    grade=packet(1,'// SceneColorTexture s0 1\n// FilterColor1Texture s1 1\n// ColorGradingLUT s2 1\n// LowResPostProcessBuffer s3 1\n',
        dict(slot=2,texture='0x3000',surface='0x4000',format=21,width=256,height=16))
    copy=packet(2,'// InTexture s0 1\n// TextureComponentReplicateAlpha c7 1\n')
    (folder/'screen-shaders.json').write_text(json.dumps([grade,copy]))
    result=boundary.grading_programs(folder,dict(pid=123))
    assert result['copy_constant']==7 and result['samplers']['ColorGradingLUT']==2
    for changed in [dict(pid=124),dict(d3d_abi={}),dict(errors=['failed']),dict(detached=False)]:
        (folder/'inspection.json').write_text(json.dumps(evidence|changed))
        try: boundary.grading_programs(folder,dict(pid=123))
        except ValueError: continue
        raise AssertionError('stale/failed native grading inventory accepted')
    (folder/'inspection.json').write_text(json.dumps(evidence))
    bad=grade|dict(assembly=grade['assembly'].replace('FilterColor1Texture s1','FilterColor1Texture s2'))
    (folder/'screen-shaders.json').write_text(json.dumps([bad,copy]))
    try: boundary.grading_programs(folder,dict(pid=123))
    except ValueError: pass
    else: raise AssertionError('aliased native grading samplers accepted')
print('Authored native grading/copy tables, sampler alias and stale/failed ABI evidence guards passed.')
