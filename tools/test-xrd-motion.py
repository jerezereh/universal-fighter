"""Authored declared-unit and signed integer quantization checks."""
from xrd_motion import motion_units,host_push_to_recoil,host_vertical_to_source,vertical_fields
import struct


def reject(action):
    try:action()
    except ValueError:return
    raise AssertionError('invalid motion mapping accepted')


def main():
    code=bytearray(b'\xcc'*96);witness={}
    for name,at,field in [('velocity',16,128),('gravity',48,132)]:
        body=bytes.fromhex('8b4424048981')+struct.pack('<I',field)+bytes.fromhex('c20400');code[at:at+13]=body
        witness[name]=dict(rva=8192+at,before=body.hex())
    assert vertical_fields(code,8192,witness)['gravity']['field']==132
    reject(lambda:vertical_fields(code,8192,witness|dict(gravity=witness['velocity'])))
    reject(lambda:vertical_fields(code,8192,witness|dict(velocity=witness['velocity']|dict(before='bad'))))
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
    vertical=host_vertical_to_source(-4,2,units)
    assert vertical['source_velocity']==4000 and vertical['source_gravity']==2000
    assert vertical['represented_host_push_y']==-4 and not vertical['live_vertical_hit_mapping']
    for push_y,gravity in [(4,2),(0,2),(-4,0),(-100,2),(True,2),(-4,float('nan'))]:reject(lambda:host_vertical_to_source(push_y,gravity,units))
    print('Signed declared-unit conversion, quantization bounds and invalid/unaccepted geometry rejection passed.')


if __name__=='__main__':main()
