"""Stage authored native collision probes using the baseline's existing KFM art."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
source = root / 'tools/fixtures/melee-native'
runtime = root / 'artifacts/host-baseline/chars'
output = runtime / 'uf-probe'
output.mkdir(parents=True, exist_ok=True)
for level, guard, fall, yvel in (('high', 'H', '0', '0'), ('low', 'L', '0', '0'), ('down', 'M', '1', '-4')):
    replacements = {'LEVEL': level, 'GUARD': guard, 'FALL': fall, 'YVEL': yvel}
    for extension in ('def', 'cns'):
        text = (source / ('probe.' + extension)).read_text()
        for key, value in replacements.items():
            text = text.replace('@' + key + '@', value)
        (output / (level + '.' + extension)).write_text(text)
(output / 'probe.cmd').write_bytes((source / 'probe.cmd').read_bytes())
(output / 'probe.air').write_bytes((runtime / 'kfm/kfm.air').read_bytes() + b'\n' + (source / 'probe.air').read_bytes())
print('Authored native melee probes staged')
