"""Exercise pinned Frida timeout/unload recovery on an owned helper, never a game."""
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'local-cache/xrd-tools/frida/python'))
import frida

spec=importlib.util.spec_from_file_location('boundary',ROOT/'tools/xrd-sign-boundary.py')
boundary=importlib.util.module_from_spec(spec);spec.loader.exec_module(boundary)
if frida.__version__!='17.22.2': raise RuntimeError('requires pinned local instrumentation')

child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],creationflags=subprocess.CREATE_NO_WINDOW)
session=script=None
try:
    session=boundary.bounded_call(frida,lambda:frida.attach(child.pid))
    script=session.create_script('rpc.exports = {ping(){return 7;}, wait(){return new Promise(()=>{});}};')
    boundary.bounded_call(frida,script.load)
    assert boundary.bounded_call(frida,script.exports_sync.ping)==7
    try: boundary.bounded_call(frida,script.exports_sync.wait,.1)
    except TimeoutError: pass
    else: raise AssertionError('never-resolving RPC did not time out')
    boundary.bounded_call(frida,script.unload);script=None
    boundary.bounded_call(frida,session.detach);session=None
    assert child.poll() is None
    print('Pinned native helper RPC timeout, subsequent unload/detach and surviving target verified.')
finally:
    if script is not None: boundary.bounded_call(frida,script.unload)
    if session is not None: boundary.bounded_call(frida,session.detach)
    child.terminate();child.wait(timeout=5)
