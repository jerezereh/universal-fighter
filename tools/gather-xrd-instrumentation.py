"""Cache a pinned Frida wheel for development-only offline SIGN instrumentation."""
import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import urllib.request

VERSION='17.22.2'
SHA256='e77725a08b5f87d7f626ece5b7a6f404ad9504e13082aa1ff3e4457ba5417910'
URL='https://files.pythonhosted.org/packages/6c/2c/4ca2ffcc6c8a40fb228307c554e0e7c92dc6fa767ab37524af194d6e1c47/frida-17.22.2-cp37-abi3-win_amd64.whl'
CACHE=Path(__file__).resolve().parent.parent/'local-cache/xrd-tools/frida'


if __name__=='__main__':
    if sys.platform!='win32' or struct.calcsize('P')!=8:
        raise SystemExit('This pinned wheel requires 64-bit Windows Python (the guest may be x86).')
    CACHE.mkdir(parents=True,exist_ok=True)
    wheel=CACHE/URL.rsplit('/',1)[1]
    if not wheel.exists():
        temporary=wheel.with_suffix('.download')
        with urllib.request.urlopen(URL,timeout=60) as source,temporary.open('wb') as target:
            while block:=source.read(1<<20): target.write(block)
        if hashlib.sha256(temporary.read_bytes()).hexdigest()!=SHA256:
            raise SystemExit('Frida download checksum mismatch; not installed.')
        temporary.replace(wheel)
    if hashlib.sha256(wheel.read_bytes()).hexdigest()!=SHA256:
        raise SystemExit('Cached Frida wheel checksum mismatch; not installed.')
    subprocess.run([sys.executable,'-m','pip','install','--no-deps','--no-index','--upgrade',
                    '--target',str(CACHE/'python'),str(wheel)],check=True)
    sys.path.insert(0,str(CACHE/'python'))
    import frida
    if frida.__version__!=VERSION: raise SystemExit('Frida version mismatch.')
    print('Verified local Frida',VERSION,'in',CACHE)
