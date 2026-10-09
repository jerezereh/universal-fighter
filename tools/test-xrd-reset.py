"""Authored reset classification rejection checks; no native layouts or assets."""
import copy
import runpy
from pathlib import Path

module=runpy.run_path(str(Path(__file__).with_name('xrd-sign-reset-check.py')))
check=module['reset_check'];message=module['MESSAGE']
receipt=dict(detached=True,loaded_code_restored=True,source_unchanged=True,
    render_cleanup=dict(render_code_restored=True),gate_check=dict(frozen_observed_state=True),
    errors=[dict(type='send',payload=dict(kind='error',phase='gate',message=message)),
        dict(controller_error="ValueError('native instrumentation error; stopping before more steps')",controller_phase='observe'),
        dict(check_error='missing settled pairs')])
fighter=dict(x_raw=20,y_raw=0,facing_left=False)
observations=[dict(boundary=dict(executed=False,counter_delta=0),fighters=[fighter,fighter])]
recovered=dict(fighters=[fighter|dict(x_raw=0),fighter],clock=dict(advancing=True))
assert check(receipt,observations,recovered)['passed']
for key in ('detached','loaded_code_restored','source_unchanged'):
    assert not check(receipt|{key:False},observations,recovered)['passed']
for patch in (dict(errors=[]),dict(errors=receipt['errors']+[dict(unexpected='failure')]),
        dict(render_cleanup=dict(render_code_restored=False))):
    assert not check(receipt|patch,observations,recovered)['passed']
assert not check(receipt,[],recovered)['passed']
assert not check(receipt,observations,recovered|dict(fighters=[fighter,fighter]))['passed']
assert not check(receipt,observations,recovered|dict(clock=dict(advancing=False)))['passed']
bad=copy.deepcopy(observations);bad[0]['boundary']['executed']=True
assert not check(receipt,bad,recovered)['passed']
print('Reset classification requires guard rejection, zero credits, changed transform, resumed clock and clean restoration.')
