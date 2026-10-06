"""Temporarily instrument a local SIGN update candidate; never freeze or call it."""
import argparse
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import sys
import time

from xrd_native import ReadOnlyProcess, SIGN_HASH, fingerprint
from xrd_state import assembly_rows, boundary_candidate, observe

ROOT=Path(__file__).resolve().parent.parent
EXE=Path('C:/Program Files (x86)/Steam/steamapps/common/GUILTY GEAR Xrd -SIGN-/Binaries/Win32/GuiltyGearXrd.exe')


class CapturedMemory:
    def __init__(self,segments,data):
        self.parts=[]
        offset=0
        for s in segments:
            if s['offset']!=offset or not 0<s['size']<=0x10000 or not 0<s['address']<=0xffffffff-s['size']:
                raise ValueError('invalid captured memory segment')
            self.parts.append((s['address'],data[offset:offset+s['size']]))
            offset+=s['size']
        if offset!=len(data) or len(segments)>8: raise ValueError('incomplete captured memory')

    def read(self,address,size):
        for base,data in self.parts:
            if base<=address and address+size<=base+len(data): return data[address-base:address-base+size]
        raise ValueError('read outside captured native snapshot')


def trace(probe,candidate_path,seconds):
    receipt=json.loads((probe/'inspection.json').read_text())
    state=json.loads((probe/'state-profile.json').read_text())
    if receipt.get('mode')!='loaded-module' or state['exe_sha256']!=SIGN_HASH or fingerprint(EXE)!=SIGN_HASH or state['pid']!=receipt['pid']:
        raise ValueError('requires a verified live SIGN state profile/receipt')
    code=(probe/'text-loaded.bin').read_bytes()
    if hashlib.sha256(code).hexdigest()!=state['code_sha256'] or state['code_sha256']!=receipt['loaded_hashes']['.text']:
        raise ValueError('loaded code receipt drift')
    local=json.loads(candidate_path.read_text())
    objdump=ROOT/'local-cache/msys64/mingw64/bin/objdump.exe'
    text=subprocess.check_output([str(objdump),'-D','-b','binary','-m','i386','-Mintel',
        '--adjust-vma='+hex(state['code_rva']),'--start-address='+hex(local['rva']),
        '--stop-address='+hex(local['rva']+local['code_size']),str(probe/'text-loaded.bin')],text=True)
    candidate=boundary_candidate(code,state['code_rva'],local,assembly_rows(text))
    sys.path.insert(0,str(ROOT/'local-cache/xrd-tools/frida/python'))
    import frida
    if frida.__version__!='17.22.2': raise ValueError('run gather-xrd-instrumentation.py for pinned Frida')
    out=probe/('boundary-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    out.mkdir();(out/'candidate.json').write_text(json.dumps(candidate,indent=2))
    messages=queue.Queue(maxsize=8192);overflow=[]
    def receive(message,data):
        try: messages.put_nowait((message,data,time.perf_counter()))
        except queue.Full: overflow.append(True)
    errors=[];records=[];session=script=None;detached=False
    started=time.perf_counter();started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with ReadOnlyProcess(state['pid'],EXE) as process:
        def unchanged():
            base,size=process.module_base()
            return base==state['module_base'] and size==receipt['image_size'] and hashlib.sha256(process.read(base+state['code_rva'],state['code_size'])).hexdigest()==state['code_sha256']
        if not unchanged(): raise ValueError('source session/code changed; run a fresh probe')
        try:
            session=frida.attach(state['pid'])
            script=session.create_script((ROOT/'tools/xrd-sign-boundary.js').read_text())
            script.on('message',receive);script.load()
            print(script.exports_sync.start(dict(state=state,candidate=candidate,image_size=receipt['image_size'])),flush=True)
            started=time.perf_counter()
            with (out/'state.jsonl').open('w',encoding='utf-8') as log:
                while time.perf_counter()-started<seconds:
                    if overflow: raise ValueError('instrumentation queue overflow')
                    try: message,data,wall=messages.get(timeout=.1)
                    except queue.Empty: continue
                    if message['type']!='send' or message['payload'].get('kind')!='frame':
                        errors.append(message);continue
                    native=message['payload']
                    observation=observe(CapturedMemory(native.pop('segments'),data),state)
                    observation.update(boundary=native,wall_seconds=wall-started,boundary_aligned=True)
                    log.write(json.dumps(observation,separators=(',',':'))+'\n')
                    records.append(native)
        except Exception as error:
            errors.append(dict(controller_error=repr(error)))
        finally:
            # A failed RPC must not prevent script/session teardown from removing the hook.
            if script is not None:
                for cleanup in (script.exports_sync.stop,script.unload):
                    try: cleanup()
                    except Exception as error: errors.append(dict(cleanup_error=repr(error)))
            try:
                if session is not None: session.detach()
                detached=True
            except Exception as error: errors.append(dict(cleanup_error=repr(error)))
        restored=unchanged()
    if not restored: errors.append(dict(cleanup_error='loaded source code was not restored'))
    if fingerprint(EXE)!=SIGN_HASH: errors.append(dict(source_error='source executable fingerprint changed'))
    deltas=Counter(r['counter_delta'] for r in records)
    gaps=sum(b['before']!=a['after'] for a,b in zip(records,records[1:]))
    result=dict(schema=1,pid=state['pid'],samples=len(records),seconds=seconds,started_utc=started_utc,
        counter_deltas=dict(deltas),continuity_gaps=gaps,threads=sorted(set(r['thread'] for r in records)),
        this_deltas=sorted(set(r['this_delta'] for r in records)),depths=sorted(set(r['depth'] for r in records)),
        return_addresses=sorted(set(r['return_address'] for r in records)),errors=errors,
        observations_only=True,boundary_aligned=True,temporary_code_interception=True,
        detached=detached,loaded_code_restored=restored,source_unchanged=fingerprint(EXE)==SIGN_HASH,
        native_tick_verified=False,atomic_native_frame=False,host_step=False,isolated_rgba=False,universal_contact=False)
    (out/'inspection.json').write_text(json.dumps(result,indent=2))
    print('Boundary trace:',len(records),'samples; counter deltas',dict(deltas),'gaps',gaps,'errors',len(errors),';',out,flush=True)
    if errors or not records or not restored or not detached: raise RuntimeError('boundary trace failed; inspect local receipt')
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('probe',type=Path)
    p.add_argument('--candidate',type=Path,required=True,help='ignored local enclosing-function/counter-writer discovery JSON')
    p.add_argument('--seconds',type=float,default=10)
    a=p.parse_args()
    if not 0<a.seconds<=120: p.error('seconds must be 0..120')
    trace(a.probe.resolve(),a.candidate.resolve(),a.seconds)
