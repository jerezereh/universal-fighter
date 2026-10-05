"""Apply versioned host patches and copy the project runtime; refuse source drift."""
from pathlib import Path
import json
import shutil
import subprocess

root = Path(__file__).resolve().parent.parent
host = root / 'backends/ikemen'
expected = json.loads((root / 'tools/upstreams.json').read_text())['ikemen']['commit']
actual = subprocess.check_output(['git', '-C', str(host), 'rev-parse', 'HEAD'], text=True).strip()
if actual != expected:
    raise SystemExit(f'Host revision drift: expected {expected}, found {actual}')
for patch in sorted((root / 'patches').glob('*.patch')):
    args = ['git', '-C', str(host), 'apply']
    if subprocess.run(args + ['--reverse', '--check', str(patch)], capture_output=True).returncode == 0:
        print(f'Already applied: {patch.name}')
    else:
        subprocess.run(args + ['--check', str(patch)], check=True)
        subprocess.run(args + [str(patch)], check=True)
        print(f'Applied: {patch.name}')
for name in ('kof13.go', 'host.go'):
    shutil.copyfile(root / 'runtime' / name, host / 'src' / ('foreign_' + name))
print('Project runtime copied to pinned host')
