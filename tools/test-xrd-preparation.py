"""Authored orchestration checks, not native evidence; no retail data or injection."""
import json
from pathlib import Path
import runpy
import tempfile

prepare=runpy.run_path(str(Path(__file__).with_name('prepare-xrd-sign-render.py')))['prepare']
namespace=prepare.__globals__
with tempfile.TemporaryDirectory() as folder:
    probe=Path(folder);calls=[];scene={'root':1};failure=None
    def trace(*args,**kwargs):
        calls.append(kwargs)
        if failure=='trace':raise RuntimeError('authored stage failure')
        result=probe/str(len(calls));result.mkdir(exist_ok=True)
        if failure=='scene':scene['root']=2
        return result
    modules={'xrd-sign-probe.py':{'GAME':None,'inspect':lambda *args:(None,probe)},
        'xrd-sign-observe.py':{'capture':lambda *args:None},'xrd-sign-boundary.py':{'trace':trace},
        'xrd-sign-draw-identity.py':{'derive':lambda *args:None}}
    namespace['load']=lambda name:modules[name]
    namespace['scene_identity']=lambda _:dict(scene)
    report=prepare(1,Path('candidate'),Path('combat'),Path('meshes'))
    receipt=json.loads(report.read_text())
    assert receipt['prepared'] and not receipt['source_capabilities_enabled']
    assert len(calls)==5 and calls[-1]['transactions'] and calls[-1]['smaa']
    assert calls[-1]['layer_path']==probe/'3' and calls[-1]['grade_path']==probe/'4'
    for failure in ('trace','scene'):
        calls.clear();scene['root']=1
        try:prepare(1,Path('candidate'),Path('combat'),Path('meshes'))
        except (RuntimeError,ValueError):pass
        else:raise AssertionError('preparation failure was hidden')
        receipt=json.loads(report.read_text())
        assert not receipt['prepared'] and 'error' in receipt and len(calls)==1
print('Preparation composes bounded stages, keeps capabilities off and stops on stage/scene failure.')
