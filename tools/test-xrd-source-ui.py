"""Authored desktop/input gates and offline UI transaction checks; no desktop input."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('ui',Path(__file__).with_name('xrd-source-ui.py'))
ui=importlib.util.module_from_spec(spec);spec.loader.exec_module(ui)


def main():
    assert not ui.focus_allowed(dict(foreground=False,idle_seconds=59.99))
    assert ui.focus_allowed(dict(foreground=False,idle_seconds=60))
    assert ui.focus_allowed(dict(foreground=True,idle_seconds=0))
    state=dict(fighters=[dict(pose_candidates=[dict(value='sol000_00')]),dict(pose_candidates=[dict(value='kyk000_00')])])
    assert ui.training_pair(state) and not ui.training_pair(None)
    assert not ui.training_pair(state|dict(fighters=list(reversed(state['fighters']))))
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);probe=root/'probe';probe.mkdir();boundary=root/'boundary';boundary.mkdir()
        (probe/'state-profile.json').write_text(json.dumps(dict(pid=123,exe_sha256=ui.SIGN_HASH)))
        (boundary/'candidate.json').write_text('{}')
        (boundary/'inspection.json').write_text(json.dumps(dict(pid=123,observations_only=True,loaded_code_restored=True)))
        ffmpeg=root/'ffmpeg.exe';ffmpeg.write_bytes(b'authored')
        with patch.object(ui.subprocess,'check_output',lambda *a,**k:'Filter gfxcapture hwnd'):
            assert ui.find_ffmpeg(ffmpeg)==ffmpeg
        with patch.object(ui.subprocess,'check_output',lambda *a,**k:'Filter gfxcapture window_exe'):
            try: ui.find_ffmpeg(ffmpeg)
            except ValueError: pass
            else: raise AssertionError('unsupported capture runtime accepted')
        preview=root/'capture.png'
        def capture(command,**kwargs):
            assert 'gfxcapture=hwnd=10:' in command[command.index('-i')+1]
            assert 'window_exe' not in ' '.join(command)
            preview.write_bytes(b'\x89PNG\r\n\x1a\n')
        with patch.object(ui.subprocess,'run',capture): ui.screenshot(ffmpeg,preview,10)
        calls=[]
        def window(action='status',key='escape',previous=0,source_pid=0):
            assert source_pid==123
            calls.append((action,key))
            return dict(pid=123,hwnd=10,foreground=False,idle_seconds=0,foreground_hwnd=20)
        def shot(ffmpeg,path,hwnd):
            assert hwnd==10;path.write_bytes(b'authored preview')
        args=SimpleNamespace(probe=probe,boundary=boundary,ffmpeg=ffmpeg,action='menu-check',mode='background',key='escape',wait_idle=0)
        with patch.object(ui,'ROOT',root),patch.object(ui,'window',window),patch.object(ui,'native_state',lambda p:state),\
             patch.object(ui,'fingerprint',lambda p:ui.SIGN_HASH),patch.object(ui,'screenshot',shot),\
             patch.object(ui.time,'sleep',lambda _:None),contextlib.redirect_stdout(io.StringIO()):
            clocks=iter([dict(advancing=True),dict(paused=True),dict(advancing=True)])
            with patch.object(ui,'source_clock',lambda p,c:next(clocks)):
                out=ui.run(args);r=json.loads((out/'inspection.json').read_text())
                assert r['success'] and r['background_menu_input_verified']
                assert calls.count(('post-key','escape'))==2
            calls.clear();clocks=iter([dict(advancing=True),dict(paused=False)])
            with patch.object(ui,'source_clock',lambda p,c:next(clocks)):
                out=ui.run(args);r=json.loads((out/'inspection.json').read_text())
                assert not r['success'] and 'unverified' in r and calls.count(('post-key','escape'))==1
            calls.clear();args.mode='foreground'
            with patch.object(ui,'window',lambda *a,**k:window(*a,**k)|dict(matching_processes=2)),\
                 patch.object(ui.subprocess,'Popen',side_effect=AssertionError('ambiguous driver started')):
                out=ui.run(args);r=json.loads((out/'inspection.json').read_text())
                assert 'edition' in r['error'] and not any(a=='post-key' for a,k in calls)
            with patch.object(ui.subprocess,'Popen',side_effect=AssertionError('driver started on active desktop')):
                out=ui.run(args);r=json.loads((out/'inspection.json').read_text())
                assert 'deferred' in r and not any(a=='post-key' for a,k in calls)
            (root/'tools').mkdir()
            (root/'tools/upstreams.json').write_text(json.dumps(dict(universalModder=dict(path='reference',commit='pin'))))
            focused=[False];commands=[];lose_focus=[False]
            def foreground_window(action='status',key='escape',previous=0,source_pid=0):
                assert source_pid==123
                calls.append((action,key))
                if action=='return-focus': assert previous==20;focused[0]=False
                return dict(pid=123,hwnd=10,foreground=focused[0] and not lose_focus[0],
                            idle_seconds=60,foreground_hwnd=10 if focused[0] else 20)
            def command(driver,value):
                commands.append(value)
                if value=='focus': focused[0]=True
            def make_driver(*a,**k):
                return SimpleNamespace(stdin=io.StringIO(),stdout=io.StringIO('ready window\n'),wait=lambda **k:0)
            with patch.object(ui,'window',foreground_window),patch.object(ui,'driver_command',command),\
                 patch.object(ui.subprocess,'Popen',make_driver),patch.object(ui.subprocess,'check_output',lambda *a,**k:'pin\n'):
                clocks=iter([dict(advancing=True),dict(paused=True),dict(advancing=True)])
                with patch.object(ui,'source_clock',lambda p,c:next(clocks)):
                    out=ui.run(args);r=json.loads((out/'inspection.json').read_text())
                    assert r['success'] and commands.count('key 0x1b')==2 and not focused[0]
                    assert 'untop' in commands and r['focus_return']['foreground'] is False
                commands.clear();focused[0]=False
                def lose_after_focus(driver,value):
                    command(driver,value)
                    if value=='focus': lose_focus[0]=True
                with patch.object(ui,'driver_command',lose_after_focus),patch.object(ui,'source_clock',lambda p,c:dict(advancing=True)):
                    out=ui.run(args);r=json.loads((out/'inspection.json').read_text())
                    assert 'focus/identity changed' in r['error'] and not any(c.startswith('key ') for c in commands)
    print('Idle/focus gates, known pair, background pause/resume, unverified-action stop and busy-desktop deferral passed.')


if __name__=='__main__': main()
