"""Prepare fresh offline SIGN render evidence; never enable live producer capabilities."""
import argparse
import json
from pathlib import Path
import runpy
import struct

from xrd_native import ReadOnlyProcess
from xrd_state import observe

ROOT=Path(__file__).resolve().parent.parent
EXE=Path('C:/Program Files (x86)/Steam/steamapps/common/GUILTY GEAR Xrd -SIGN-/Binaries/Win32/GuiltyGearXrd.exe')


def load(name):
    return runpy.run_path(str(ROOT/'tools'/name))


def scene_identity(probe):
    state=json.loads((probe/'state-profile.json').read_text())
    with ReadOnlyProcess(state['pid'],EXE) as process:
        base,_=process.module_base()
        if base!=state['module_base']: raise ValueError('source module changed')
        global_address=base+state['engine_global_rva']
        root=int.from_bytes(process.read(global_address,4),'little')
        if not root: raise ValueError('offline battle is absent')
        slots=list(struct.unpack('<2I',process.read(root+state['fields']['slots'],8)))
        current=observe(process,state)
        if not all(any(p['value'].startswith(prefix) for p in f['pose_candidates']) for f,prefix in zip(current['fighters'],('sol','kyk'))):
            raise ValueError('requires offline Sol versus Ky')
        if int.from_bytes(process.read(global_address,4),'little')!=root or list(struct.unpack('<2I',process.read(root+state['fields']['slots'],8)))!=slots:
            raise ValueError('source scene changed during observation')
        return dict(pid=state['pid'],module_base=base,root=root,slots=slots)


def prepare(pid,candidate,combat,meshes):
    recon=load('xrd-sign-probe.py');_,probe=recon['inspect'](recon['GAME'],pid)
    receipt=dict(prepared=False,source_capabilities_enabled=False,automatic_live_rebind_verified=False,stages={})
    report=probe/'render-preparation.json'
    try:
        load('xrd-sign-observe.py')['capture'](probe,1,0)
        identity=scene_identity(probe);receipt['scene']=identity
        trace=load('xrd-sign-boundary.py')['trace']
        def stage(name,seconds,**options):
            if scene_identity(probe)!=identity: raise ValueError('source scene changed; discard prepared bindings')
            print('Preparing:',name,flush=True)
            folder=trace(probe,candidate,seconds,**options)
            receipt['stages'][name]=folder.name
            if scene_identity(probe)!=identity: raise ValueError('source scene changed during preparation')
            return folder
        # Keep the existing 100-sample evidence guard at reduced background frame rates.
        owner=stage('owner',5)
        draws=stage('draws',4.5,gate_receipt=owner,capture=True,trace_draws=True)
        load('xrd-sign-draw-identity.py')['derive'](draws,meshes)
        buffers=draws/'draw-identity.json'
        mesh=stage('mesh',4.5,gate_receipt=owner,capture=True,trace_draws=True,suppress_path=buffers,inspect_shaders=True)
        screen=stage('screen',8,gate_receipt=owner,capture=True,trace_draws=True,capture_passes=True,
            inspect_screen=True,capture_screen_stages=True)
        stage('verification',28,gate_receipt=owner,combat_path=combat,capture=True,trace_draws=True,
            suppress_path=buffers,layer_path=mesh,normalize=True,settle=True,grade_path=screen,
            post_color_path=screen,smaa=True,transactions=True)
        receipt['prepared']=True
    except Exception as error:
        receipt['error']=repr(error);raise
    finally:
        report.write_text(json.dumps(receipt,indent=2))
    print('Prepared bounded render evidence:',report,flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pid',type=int,required=True)
    p.add_argument('--candidate',type=Path,required=True,help='ignored local verified update candidate')
    p.add_argument('--combat-candidate',type=Path,required=True,help='ignored local scalar getter/setter candidate')
    p.add_argument('--meshes',type=Path,required=True,help='ignored local Sol mesh metadata directory')
    args=p.parse_args()
    if args.pid<=0:p.error('pid must be positive')
    prepare(args.pid,args.candidate.resolve(),args.combat_candidate.resolve(),args.meshes.resolve())
