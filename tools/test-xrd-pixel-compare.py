"""Verify the actual ia32 Windows byte comparator on an owned helper, never a game."""
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'local-cache/xrd-tools/frida/python'))
import frida
spec=importlib.util.spec_from_file_location('boundary',ROOT/'tools/xrd-sign-boundary.py')
boundary=importlib.util.module_from_spec(spec);spec.loader.exec_module(boundary)
child=subprocess.Popen(['C:/Windows/SysWOW64/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-Command','Start-Sleep -Seconds 30'],
    creationflags=subprocess.CREATE_NO_WINDOW)
session=script=None
try:
    session=boundary.bounded_call(frida,lambda:frida.attach(child.pid))
    source=(ROOT/'tools/xrd-sign-layer.js').read_text()+'''\n
rpc.exports={check(){
    if(Process.arch!=='ia32') throw Error('requires ia32 helper');
    const n=640*768*4, a=new Uint8Array(n+1),b=new Uint8Array(n+1);
    a.fill(7);b.fill(7);b[0]=99;
    const metadata={width:640,height:768,state_size:1};
    const left={metadata,data:a.buffer},right={metadata,data:b.buffer};
    const started=Date.now();
    for(let i=0;i<12;++i) if(!equalPixels(left,right)) throw Error('state prefix affected comparison');
    b[n]=8;if(equalPixels(left,right)) throw Error('last alpha byte ignored');
    return {comparisons:13,bytes:n,elapsed_ms:Date.now()-started,self_checked:true};
}};
'''
    script=session.create_script(source);boundary.bounded_call(frida,script.load)
    result=boundary.bounded_call(frida,script.exports_sync.check)
    assert result['self_checked'] and result['comparisons']==13
    print('Native ia32 comparator:',result)
finally:
    try:
        if script is not None: boundary.bounded_call(frida,script.unload)
    finally:
        try:
            if session is not None: boundary.bounded_call(frida,session.detach)
        finally: child.terminate();child.wait(timeout=5)
