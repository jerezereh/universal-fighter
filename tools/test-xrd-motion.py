"""Authored declared-unit and signed integer quantization checks."""
from xrd_motion import motion_units,host_push_to_recoil


def reject(action):
    try:action()
    except ValueError:return
    raise AssertionError('invalid motion mapping accepted')


def main():
    axis=dict(world_per_source_logical_unit=1,intercept=0,max_world_residual=0)
    calibration=dict(body_origin_mapping_verified=True,samples=4,axes=[axis,axis],pixels_per_source_logical_unit=2)
    units=motion_units(calibration,.5);getter=dict(numerator=20,denominator=10)
    for push,raw in [(2.4,1200),(-2.4,-1200),(0,0)]:
        mapped=host_push_to_recoil(push,units,getter)
        assert mapped['source_recoil']==raw and abs(mapped['represented_host_push']-push)<1e-9
        assert not mapped['live_motion_mapping'] and not units['foot_pivot_verified']
    for push in [2.401,-2.401]:
        mapped=host_push_to_recoil(push,units,getter);assert mapped['actual_error']<=mapped['max_quantization_error']
    for scale in [0,True,float('nan'),1e-300]:reject(lambda:motion_units(calibration,scale))
    for patch in [dict(body_origin_mapping_verified=False),dict(samples=2),dict(axes=[axis,axis|dict(world_per_source_logical_unit=2)]),dict(pixels_per_source_logical_unit=float('inf'))]:reject(lambda:motion_units(calibration|patch,.5))
    for push in [float('nan'),True,20]:reject(lambda:host_push_to_recoil(push,units,getter))
    print('Signed declared-unit conversion, quantization bounds and invalid/unaccepted geometry rejection passed.')


if __name__=='__main__':main()
