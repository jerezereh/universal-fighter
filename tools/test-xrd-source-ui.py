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
    assert ui.clock_check([7]*6)['paused']
    assert ui.clock_check([0xfffffffe,0xffffffff,0,1,2,3])['advancing']
    assert not ui.clock_check([1,2,1,2,3,4])['advancing']
    assert not ui.clock_check([1,1,2,3,4,5])['paused']
    for bad in ([1],[-1]*6,[True]*6,[0x100000000]*6):
        try: ui.clock_check(bad)
        except ValueError: continue
        raise AssertionError('invalid source clock reads accepted')
    assert not ui.focus_allowed(dict(foreground=False,idle_seconds=59.99))
    assert ui.focus_allowed(dict(foreground=False,idle_seconds=60))
    assert ui.focus_allowed(dict(foreground=True,idle_seconds=0))
    state=dict(fighters=[dict(pose_candidates=[dict(value='sol000_00')]),dict(pose_candidates=[dict(value='kyk000_00')])])
    assert ui.training_pair(state) and not ui.training_pair(None)
    assert not ui.training_pair(state|dict(fighters=list(reversed(state['fighters']))))
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);probe=root/'probe';probe.mkdir();boundary=root/'boundary';boundary.mkdir()
        (probe/'state-profile.json').write_text(json.dumps(dict(pid=123,exe_sha256=ui.SIGN_HASH)))
        (boundary/'candidate.json').write_text(json.dumps(dict(counter_field=20)))
        evidence=dict(pid=123,observations_only=True,loaded_code_restored=True,detached=True,source_unchanged=True,
            errors=[],samples=100,continuity_gaps=0,counter_deltas={'1':100})
        (boundary/'inspection.json').write_text(json.dumps(evidence))
        assert ui.clock_candidate(dict(pid=123),boundary)['counter_field']==20
        for changed in [dict(pid=124),dict(errors=['failure']),dict(detached=False),dict(counter_deltas={'1':99})]:
            (boundary/'inspection.json').write_text(json.dumps(evidence|changed))
            try: ui.clock_candidate(dict(pid=123),boundary)
            except ValueError: continue
            raise AssertionError('unclean clock evidence accepted')
        (boundary/'inspection.json').write_text(json.dumps(evidence))
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
            args.action='clock-check';args.mode='foreground';args.expected_clock='paused'
            with patch.object(ui,'window',lambda *a,**k:window(*a,**k)|dict(matching_processes=2)),\
                 patch.object(ui,'source_clock',lambda p,c:ui.clock_check([7]*6)),\
                 patch.object(ui.subprocess,'Popen',side_effect=AssertionError('read-only check started input driver')):
                out=ui.run(args);r=json.loads((out/'inspection.json').read_text())
                assert r['success'] and r['read_only'] and r['fighters_unchanged']
                assert not any(a in ('post-key','return-focus') for a,k in calls)
            with patch.object(ui,'source_clock',lambda p,c:ui.clock_check([1,2,3,4,5,6])):
                out=ui.run(args);r=json.loads((out/'inspection.json').read_text());assert not r['success']
                args.expected_clock='advancing'
                out=ui.run(args);r=json.loads((out/'inspection.json').read_text());assert r['success']
            changed_state=dict(fighters=[dict(pose_candidates=[dict(value='sol000_01')]),state['fighters'][1]])
            snapshots=iter([state,changed_state]);args.expected_clock='paused'
            with patch.object(ui,'source_clock',lambda p,c:ui.clock_check([7]*6)),\
                 patch.object(ui,'native_state',lambda p:next(snapshots)):
                out=ui.run(args);r=json.loads((out/'inspection.json').read_text());assert not r['success'] and not r['fighters_unchanged']
            calls.clear();args.action='menu-check';args.mode='background'
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
    print('Read-only pause/resume, clock wrap/bounds/evidence, idle/focus/input gates and changed-state rejection passed.')


if __name__=='__main__': main()
