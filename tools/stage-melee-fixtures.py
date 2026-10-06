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
for mode in ('projectile', 'idle', 'guard', 'miss', 'pause'):
    definition = (source / 'probe.def').read_text().replace('@LEVEL@', mode)
    (output / (mode + '.def')).write_text(definition)
    states = (source / ('projectile.cns' if mode in ('projectile', 'pause') else 'idle.cns')).read_text()
    if mode == 'guard':
        states += '\n[Statedef -2]\n[State -2, Guard]\ntype = AssertSpecial\ntrigger1 = 1\nflag = autoguard\n'
    if mode == 'miss':
        states += '\n[Statedef -2]\n[State -2, Invulnerable]\ntype = NotHitBy\ntrigger1 = 1\nvalue = SCA, SP\ntime = 1\n'
    if mode == 'pause':
        states += '\n[Statedef -2]\n[State -2, Pause probe]\ntype = Pause\ntriggerall = RoundState = 2\ntrigger1 = Time % 120 = 60\ntime = 4\n'
    (output / (mode + '.cns')).write_text(states)
(output / 'probe.cmd').write_bytes((source / 'probe.cmd').read_bytes())
(output / 'probe.air').write_bytes((runtime / 'kfm/kfm.air').read_bytes() + b'\n' + (source / 'probe.air').read_bytes())
print('Authored native melee probes staged')
