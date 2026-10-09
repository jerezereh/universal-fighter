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
aged=copy.deepcopy(observations)
for f in aged[0]['fighters']: f['scalar_observations']={'age_candidate':10}
age_receipt=copy.deepcopy(receipt);age_receipt['errors']=age_receipt['errors'][:2]
changes=[dict(fighter=i,field='age',before=10,after=0) for i in range(2)]
age_receipt['errors'][0]['payload']['ownership_changes']=changes
same=recovered|dict(fighters=[fighter,fighter])
assert check(age_receipt,aged,same)['passed'] and check(age_receipt,aged,same)['age_reset_diagnostic']
assert len(age_receipt['errors'][0]['payload']['ownership_changes'])==2 # classifier leaves raw receipt intact
for changes in ([dict(fighter=0,field='age',before=10,after=0)],
        [dict(fighter=i,field='invented',before=10,after=0)for i in range(2)],
        [dict(fighter=i,field='age',before=11,after=0)for i in range(2)]):
    wrong=copy.deepcopy(age_receipt);wrong['errors'][0]['payload']['ownership_changes']=changes
    assert not check(wrong,aged,same)['passed']
print('Reset classification requires guard rejection, zero credits, changed transform or matched shared age reset, resumed clock and clean restoration.')
scene=module['scene_exit_check'];scene_receipt=copy.deepcopy(receipt)
scene_receipt['errors']=[dict(type='send',payload=dict(kind='error',phase='gate',message='Error: transaction scene changed; original execution resumed')),
    dict(controller_phase='observe',controller_error="RPCException('transaction scene changed', 'Error', 'authored stack')")]
assert scene(scene_receipt,observations,0)['passed']
for root in (1,False,None): assert not scene(scene_receipt,observations,root)['passed']
assert not scene(scene_receipt,[],0)['passed']
assert not scene(scene_receipt,bad,0)['passed']
assert not scene(scene_receipt|dict(loaded_code_restored=False),observations,0)['passed']
assert not scene(scene_receipt|dict(errors=scene_receipt['errors']+[dict(unexpected=True)]),observations,0)['passed']
assert not scene(receipt,observations,0)['passed']
print('Scene-exit classification requires exact root-loss RPC rejection, zero credits, absent battle and restoration.')
