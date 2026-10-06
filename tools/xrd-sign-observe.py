"""Collect read-only SIGN training state, not a synchronized passthrough producer."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import time

from xrd_native import ReadOnlyProcess, SIGN_HASH, fingerprint
from xrd_state import observe, profile

ROOT=Path(__file__).resolve().parent.parent
EXE=Path('C:/Program Files (x86)/Steam/steamapps/common/GUILTY GEAR Xrd -SIGN-/Binaries/Win32/GuiltyGearXrd.exe')


def capture(probe,seconds,delay):
    receipt=json.loads((probe/'inspection.json').read_text())
    if receipt.get('mode')!='loaded-module' or receipt['exe_sha256']!=SIGN_HASH or fingerprint(EXE)!=SIGN_HASH:
        raise ValueError('requires a verified live SIGN probe receipt')
    refs=json.loads((ROOT/'tools/upstreams.json').read_text());entry=refs['xrdLegacyOverlay'];ref=ROOT/entry['path']
    if subprocess.check_output(['git','-C',str(ref),'rev-parse','HEAD'],text=True).strip()!=entry['commit']:
        raise ValueError('native reference revision drift')
    source=ref/'ggxrd_hitbox_overlay.cpp'
    if fingerprint(source)!=receipt['reference_sha256']: raise ValueError('reference content drift')
    p=profile(receipt,probe,source.read_text(),ROOT/'local-cache/msys64/mingw64/bin/objdump.exe')
    (probe/'state-profile.json').write_text(json.dumps(p,indent=2))
    out=probe/('observe-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    out.mkdir()
    with ReadOnlyProcess(p['pid'],EXE) as process:
        base,size=process.module_base()
        if base!=p['module_base'] or size!=receipt['image_size'] or hashlib.sha256(process.read(base+p['code_rva'],p['code_size'])).hexdigest()!=p['code_sha256']:
            raise ValueError('loaded source session/code changed; run a fresh probe')
        print('Ready for manual training observation:',out,flush=True)
        time.sleep(delay)
        start=time.perf_counter();started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat();samples=0
        with (out/'state.jsonl').open('w',encoding='utf-8') as log:
            while time.perf_counter()-start<seconds:
                record=observe(process,p);record['wall_seconds']=time.perf_counter()-start
                log.write(json.dumps(record,separators=(',',':'))+'\n');log.flush();samples+=1
                time.sleep(1/120)
    if fingerprint(EXE)!=SIGN_HASH: raise ValueError('source executable changed during capture')
    result=dict(schema=1,pid=p['pid'],samples=samples,seconds=seconds,started_utc=started_utc,source_unchanged=True,
                observations_only=True,native_tick_verified=False,host_step=False,isolated_rgba=False,universal_contact=False)
    (out/'inspection.json').write_text(json.dumps(result,indent=2))
    print('Read-only observation complete:',samples,'samples;',out,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('probe',type=Path)
    parser.add_argument('--seconds',type=float,default=5)
    parser.add_argument('--delay',type=float,default=0)
    args=parser.parse_args()
    if not 0<args.seconds<=120 or not 0<=args.delay<=60: parser.error('seconds must be 0..120 and delay 0..60')
    capture(args.probe.resolve(),args.seconds,args.delay)
