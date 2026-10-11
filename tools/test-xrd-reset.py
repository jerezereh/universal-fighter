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


"""Small authored checks for reset evidence; no retail bytes or live process."""
import copy
import hashlib
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('reset', Path(__file__).with_name('xrd-sign-reset.py'))
reset = importlib.util.module_from_spec(spec); spec.loader.exec_module(reset)
expected = [dict(x_raw=-100, y_raw=0, health=100), dict(x_raw=100, y_raw=0, health=100)]
before = dict(fighters=[dict(slot=i, x_raw=0, y_raw=0, hit_count=0,
    scalar_observations=dict(age_candidate=500, health_candidate=50, hitstop_candidate=0)) for i in range(2)])
after = dict(fighters=[dict(slot=i, x_raw=e['x_raw'], y_raw=0, hit_count=0,
    scalar_observations=dict(age_candidate=10, health_candidate=100, hitstop_candidate=0)) for i,e in enumerate(expected)])
assert reset.reset_check(before, after, expected)
for field, value in [('age_candidate', 510), ('age_candidate', 200), ('health_candidate', 50), ('hitstop_candidate', 1)]:
    bad = copy.deepcopy(after); bad['fighters'][1]['scalar_observations'][field] = value
    assert not reset.reset_check(before, bad, expected)
for field, value in [('slot', 0), ('x_raw', 0), ('y_raw', 1), ('hit_count', 1)]:
    bad = copy.deepcopy(after); bad['fighters'][1][field] = value
    assert not reset.reset_check(before, bad, expected)
assert not reset.reset_check(before, dict(fighters=after['fighters'][:1]), expected)
p = dict(pid=123, module_base=4096, exe_sha256='hash', code_sha256=hashlib.sha256(bytes(64)).hexdigest(), code_rva=4096, code_size=64)
c = dict(p, schema=1, manual_reset_verified=True, hwnd_offset=112, expected_fighters=expected,
    poll_return_rva=4096, window_handler_rva=4128, poll_return_hex='00'*32, window_handler_hex='00'*32)
reset.candidate_check(c, p, bytes(64))
try: reset.candidate_check(c, p, bytes(63))
except ValueError: pass
else: raise AssertionError('changed code capture')
for field, value in [('pid', 124), ('manual_reset_verified', False), ('hwnd_offset', -1),
                     ('poll_return_hex', '01'*32), ('window_handler_rva', 8192)]:
    bad = dict(c); bad[field] = value
    try: reset.candidate_check(bad, p, bytes(64))
    except ValueError: pass
    else: raise AssertionError(field)
print('reset evidence checks passed')
