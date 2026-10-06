"""Stage authored executable rulesets; reuse existing baseline art, never retail assets."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
output = root / 'artifacts/host-baseline/chars/uf-synthetic'
output.mkdir(parents=True, exist_ok=True)
for rules in ('parry-test', 'airdash-test'):
    (output / f'{rules}.def').write_text(f'''[Info]
name = "UF {rules}"
displayname = "{rules}"
runtime = {rules}
mugenversion = 1.1
localcoord = 320,240
[Files]
cmd = shell.cmd
cns = ../kfm/kfm.cns
sprite = ../kfm/kfm.sff
anim = synthetic.air
''')
(output / 'shell.cmd').write_text('[Statedef -1]\n')
actions = []
for action in (1, 2, 3, 5, 11, 12, 14, 15, 19, 20, 25, 26, 27, 34, 36, 68, 106, 112, 161):
    crouch = action in (25, 26, 36, 112)
    group, image = (11, 2) if crouch else (0, 0)
    if action == 2:
        group = 20
    elif action == 3:
        group = 21
    actions.append(f'[Begin Action {action}]\nClsn2Default: 1\nClsn2[0] = -15,{-48 if crouch else -85},15,0\nClsn1: 0\n')
    if action == 68:
        actions.append('200,0,0,0,4\nClsn1: 1\nClsn1[0] = 15,-60,55,-20\n200,1,0,0,3\nClsn1: 0\n200,2,0,0,11\n')
    else:
        actions.append(f'{group},{image},0,0,{1 if action in (12,15,20) else 4}\n')
        if action in (12, 15, 20):
            actions.append(f'{group},{image},0,0,600\n')
(output / 'synthetic.air').write_text('\n'.join(actions))
print('Authored parry and air-dash rulesets staged')
