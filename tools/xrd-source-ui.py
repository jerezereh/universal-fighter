"""Background SIGN observation and bounded, verified offline UI actions. No online navigation."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from xrd_native import ReadOnlyProcess, SIGN_HASH, fingerprint
from xrd_state import observe

ROOT=Path(__file__).resolve().parent.parent
EXE=Path('C:/Program Files (x86)/Steam/steamapps/common/GUILTY GEAR Xrd -SIGN-/Binaries/Win32/GuiltyGearXrd.exe')
KEYS=dict(escape=0x1b,enter=0x0d,up=0x26,down=0x28,left=0x25,right=0x27,punch=0x4a)
POWERSHELL=shutil.which('pwsh') or 'powershell.exe'


def find_ffmpeg(requested=None):
    if requested: candidates=[requested]
    else:
        local=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))
        candidates=[shutil.which('ffmpeg'),ROOT/'local-cache/xrd-tools/ffmpeg/bin/ffmpeg.exe']
        candidates.extend((local/'Microsoft/WinGet/Packages').glob('Gyan.FFmpeg_*/ffmpeg*/bin/ffmpeg.exe'))
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file(): continue
        help_text=subprocess.check_output([str(candidate),'-hide_banner','-h','filter=gfxcapture'],
            text=True,stderr=subprocess.STDOUT,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
        if 'window_exe' in help_text: return Path(candidate).resolve()
    raise ValueError('no installed gfxcapture-capable FFmpeg; pass --ffmpeg explicitly')


def window(action='status',key='escape',previous=0):
    command=[POWERSHELL,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/xrd-source-window.ps1'),
        '-Action',action,'-Key',key,'-PreviousForeground',str(previous)]
    return json.loads(subprocess.check_output(command,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW))


def focus_allowed(status):
    return status['foreground'] or status['idle_seconds']>=60


def native_state(profile):
    with ReadOnlyProcess(profile['pid'],EXE) as process:
        base,size=process.module_base()
        if base!=profile['module_base'] or hashlib.sha256(process.read(base+profile['code_rva'],profile['code_size'])).hexdigest()!=profile['code_sha256']:
            raise ValueError('source profile/session changed; run a fresh probe')
        root=int.from_bytes(process.read(base+profile['engine_global_rva'],4),'little')
        return observe(process,profile) if root else None


def source_clock(profile,candidate):
    values=[]
    with ReadOnlyProcess(profile['pid'],EXE) as process:
        for _ in range(6):
            root=int.from_bytes(process.read(profile['module_base']+profile['engine_global_rva'],4),'little')
            if not root: raise ValueError('source battle is unavailable')
            values.append(int.from_bytes(process.read(root+4+candidate['counter_field'],4),'little'))
            time.sleep(.06)
    return dict(samples=values,paused=len(set(values))==1,advancing=all(b>a for a,b in zip(values,values[1:])))


def training_pair(state):
    return state is not None and len(state['fighters'])==2 and all(
        any(p['value'].startswith(prefix) for p in f['pose_candidates'])
        for f,prefix in zip(state['fighters'],('sol','kyk')))


def screenshot(ffmpeg,path):
    subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-y','-f','lavfi','-i',
        'gfxcapture=window_exe=GuiltyGearXrd.exe:capture_cursor=0:max_framerate=30,hwdownload,format=bgra',
        '-frames:v','1',str(path)],check=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
    if path.read_bytes()[:8]!=b'\x89PNG\r\n\x1a\n': raise ValueError('invalid GPU screenshot')


def driver_command(driver,command):
    driver.stdin.write(command+'\n');driver.stdin.flush()
    reply=driver.stdout.readline().strip()
    if reply!='ok': raise RuntimeError('WinDrive '+command+': '+reply+'; reobserve before more input')


def run(args):
    if args.wait_idle<0 or args.wait_idle>120: raise ValueError('idle wait must be 0..120 seconds')
    if not args.ffmpeg.is_file(): raise ValueError('pass the installed gfxcapture-capable --ffmpeg path')
    folder=ROOT/'artifacts/xrd-source-ui'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    folder.mkdir(parents=True)
    result=dict(action=args.action,mode=args.mode,steps=[],success=False,background_menu_input_verified=False)
    driver=None;previous=0
    try:
        status=window('restore');result['window_before']=status;previous=status['foreground_hwnd']
        profile=json.loads((args.probe/'state-profile.json').read_text())
        if profile['pid']!=status['pid'] or profile['exe_sha256']!=SIGN_HASH or fingerprint(EXE)!=SIGN_HASH:
            raise ValueError('source session/fingerprint mismatch')
        state=native_state(profile);result['native_before']=state
        screenshot(args.ffmpeg,folder/'before.png')
        if args.action=='observe': result['success']=True;return folder
        if args.action=='menu-check' and not training_pair(state): raise ValueError('menu check requires the known offline Sol/Ky scene')
        if args.mode=='foreground':
            deadline=time.monotonic()+args.wait_idle
            while not focus_allowed(status):
                if time.monotonic()>=deadline:
                    result['deferred']='desktop active; no focus/input sent';return folder
                time.sleep(1);status=window()
            if status['pid']!=profile['pid']: raise ValueError('source process changed before input')
            if args.action=='menu-check' and not training_pair(native_state(profile)):
                raise ValueError('source scene changed during idle wait; no input sent')
            driver_path=ROOT/'tools/references/universal-modder/um/ps1/WinDrive.ps1'
            refs=json.loads((ROOT/'tools/upstreams.json').read_text())['universalModder']
            if subprocess.check_output(['git','-C',str(ROOT/refs['path']),'rev-parse','HEAD'],text=True).strip()!=refs['commit']:
                raise ValueError('input driver reference revision changed')
            driver=subprocess.Popen([POWERSHELL,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(driver_path),'-Proc','GuiltyGearXrd'],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
            if driver.stdout.readline().strip()!='ready window': raise RuntimeError('source input driver not ready')
            # Recheck immediately before activating: the user may have resumed typing during setup.
            if not focus_allowed(window()): result['deferred']='desktop activity resumed before focus';return folder
            driver_command(driver,'focus');driver_command(driver,'scanmode on')
        def key(name,label):
            if driver:
                current=window()
                if current['pid']!=profile['pid'] or not current['foreground']:
                    raise ValueError('source focus/identity changed; no key sent')
                driver_command(driver,'key '+hex(KEYS[name]))
            else: result['steps'].append(window('post-key',name))
            time.sleep(.25);screenshot(args.ffmpeg,folder/(label+'.png'))
        if args.action=='key': key(args.key,'after');result['input_sent']=True;result['key_effect_verified']=False
        else:
            candidate=json.loads((args.boundary/'candidate.json').read_text())
            evidence=json.loads((args.boundary/'inspection.json').read_text())
            if evidence['pid']!=profile['pid'] or not evidence['observations_only'] or not evidence['loaded_code_restored']:
                raise ValueError('menu clock requires a clean same-session native observation')
            result['clock_before']=source_clock(profile,candidate)
            if not result['clock_before']['advancing']: raise ValueError('menu check requires an advancing training scene')
            key('escape','menu');result['clock_menu']=source_clock(profile,candidate)
            if not result['clock_menu']['paused']:
                result['unverified']='Escape did not freeze the observed source clock; inspect menu.png before another action';return folder
            key('escape','resumed');result['clock_after']=source_clock(profile,candidate)
            result['success']=result['clock_after']['advancing']
            result['background_menu_input_verified']=args.mode=='background' and result['success']
        result['native_after']=native_state(profile)
    except Exception as error: result['error']=str(error)
    finally:
        if driver:
            try: driver_command(driver,'untop')
            except Exception as error: result['cleanup_error']=str(error)
            driver.stdin.close()
            try: driver.wait(timeout=3)
            except subprocess.TimeoutExpired: driver.terminate();driver.wait(timeout=3)
            if previous and previous!=result['window_before']['hwnd']:
                try: result['focus_return']=window('return-focus',previous=previous)
                except Exception as error: result['focus_return_error']=str(error)
        try: result['window_after']=window()
        except Exception as error: result['status_error']=str(error)
        (folder/'inspection.json').write_text(json.dumps(result,indent=2))
        print(json.dumps({k:v for k,v in result.items() if k not in ('native_before','native_after','steps')},indent=2))
        print('UI evidence:',folder,flush=True)
    return folder


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('probe',type=Path,help='verified current-session native probe')
    p.add_argument('--ffmpeg',type=Path,help='installed FFmpeg with gfxcapture; defaults to existing PATH/local cache/WinGet installation')
    p.add_argument('--action',choices=('observe','key','menu-check'),default='observe')
    p.add_argument('--key',choices=KEYS,default='escape')
    p.add_argument('--mode',choices=('background','foreground'),default='background')
    p.add_argument('--boundary',type=Path,help='clean same-session boundary trace for --action menu-check')
    p.add_argument('--wait-idle',type=float,default=0,help='bounded wait for 60 seconds idle before taking focus')
    a=p.parse_args()
    a.ffmpeg=find_ffmpeg(a.ffmpeg)
    if a.action=='menu-check' and not a.boundary: p.error('menu-check requires --boundary')
    folder=run(a)
    receipt=json.loads((folder/'inspection.json').read_text())
    if receipt.get('deferred'): raise SystemExit(2)
    if receipt.get('error') or not (receipt['success'] or receipt.get('input_sent')): raise SystemExit(1)
