"""Read-only native recoil evidence; no host units or memory writes."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct


def recoil_getter(code,code_rva,local):
    if type(local)!=dict or set(local)!={'rva','before','caller_rva'}:raise ValueError('invalid recoil witness')
    rva=local['rva'];before=local['before']
    if type(rva)!=int or type(before)!=str or len(before)!=60:raise ValueError('invalid recoil getter bounds')
    at=rva-code_rva;body=code[at:at+30]
    if at<3 or rva%16 or code[at-3:at] not in (b'\xcc\xcc\xcc',b'\xc2\x04\x00') or body.hex()!=before or body[:2]!=b'\x8b\x89' or body[6:8]!=b'\x69\xc9' or body[12:]!=bytes.fromhex('b867666666f7e9c1fa028bc2c1e81f03c2c3'):raise ValueError('recoil getter arithmetic changed')
    field=struct.unpack_from('<I',body,2)[0];numerator=struct.unpack_from('<i',body,8)[0]
    if not 0<field<=0x10000-4 or field%4 or not 1<=numerator<=1000:raise ValueError('unbounded recoil field/scale')
    caller=local['caller_rva']
    if type(caller)!=int:raise ValueError('invalid recoil caller')
    call=caller-code_rva
    if not 2<=call<=len(code)-11 or code[call-2:call]!=b'\x8b\xce' or code[call]!=0xe8 or caller+5+struct.unpack_from('<i',code,call+1)[0]!=rva or code[call+5:call+7]!=b'\x89\x86':raise ValueError('recoil getter is not linked to movement output')
    sink=struct.unpack_from('<I',code,call+7)[0]
    if not 0<sink<=0x10000-4 or sink%4 or sink==field:raise ValueError('invalid recoil movement output')
    return dict(rva=rva,before=before,field=field,numerator=numerator,denominator=10,sink=sink)


def audit(probe,boundary,candidate):
    profile=json.loads((probe/'state-profile.json').read_text());code=(probe/'text-loaded.bin').read_bytes()
    if hashlib.sha256(code).hexdigest()!=profile['code_sha256']:raise ValueError('loaded code receipt changed')
    getter=recoil_getter(code,profile['code_rva'],json.loads(candidate.read_text()))
    receipt=json.loads((boundary/'inspection.json').read_text())
    if receipt.get('pid')!=profile['pid'] or receipt.get('errors') or not all(receipt.get(k) is True for k in ('controlled_update_step_verified','detached','loaded_code_restored','native_contact_observer_restored')):raise ValueError('requires a complete restored native contact receipt')
    states=[json.loads(line) for line in (boundary/'state.jsonl').read_text().splitlines()]
    states=[row for row in states if row.get('boundary',{}).get('executed')]
    samples=[];previous=None
    for step,row in enumerate(states,1):
        raw=(boundary/('reaction-%03d.bin'%step)).read_bytes()
        if max(getter['field'],getter['sink'])+4>len(raw):raise ValueError('recoil field outside retained snapshot')
        push=struct.unpack_from('<i',raw,getter['field'])[0];fighter=row['fighters'][0]
        hurt=any(re.fullmatch(r'sol05[012]_[0-9]{2}',pose['value']) for pose in fighter['pose_candidates'])
        if previous and previous[0] and push and previous[2] and hurt:
            product=push*getter['numerator']
            if not -(1<<31)<=product<(1<<31):raise ValueError('recoil arithmetic overflow')
            expected=(abs(product)//getter['denominator'])*(-1 if product<0 else 1)
            samples.append(dict(step=step,recoil=push,native_output=struct.unpack_from('<i',raw,getter['sink'])[0],expected_delta=expected,actual_delta=fighter['x_raw']-previous[1]))
        previous=(push,fighter['x_raw'],hurt)
    result=dict(read_only=True,samples=samples,source_recoil_trajectory_verified=len(samples)>=6 and all(s['actual_delta']==s['expected_delta']==s['native_output'] for s in samples),host_units_verified=False,live_motion_mapping=False)
    (boundary/'recoil-trajectory-check.json').write_text(json.dumps(result,indent=2))
    print({k:v for k,v in result.items() if k!='samples'}|dict(sample_count=len(samples)))
    return result




def motion_units(calibration,display_scale):
    """Declared display-scale conversion; anatomical pivot/live rendering stay pending."""
    if type(calibration)!=dict:raise ValueError('invalid unit calibration')
    if calibration.get('body_origin_mapping_verified') is not True or type(calibration.get('samples'))!=int or not 3<=calibration['samples']<=16:raise ValueError('requires verified body-origin calibration')
    axes=calibration.get('axes');pixels=calibration.get('pixels_per_source_logical_unit')
    valid=lambda v:type(v) in (int,float) and math.isfinite(v)
    if type(axes)!=list or len(axes)!=2 or not valid(pixels) or not 0<pixels<=160 or not valid(display_scale) or not 0<display_scale<=1:raise ValueError('invalid motion unit geometry')
    slopes=[]
    for axis in axes:
        if type(axis)!=dict:raise ValueError('invalid unit axis')
        slope=axis.get('world_per_source_logical_unit');residual=axis.get('max_world_residual');origin=axis.get('intercept')
        if not all(valid(v) for v in (slope,residual,origin)) or not 0<slope<=10 or not 0<=residual<=.001 or abs(origin)>.001:raise ValueError('invalid source axis fit')
        slopes.append(slope)
    if abs(slopes[0]/slopes[1]-1)>.001:raise ValueError('inconsistent source axis units')
    coefficient=pixels*display_scale/1000
    if not 1e-9<=coefficient<=1:raise ValueError('unit scale exceeds diagnostic precision')
    return dict(host_per_source_raw=coefficient,display_scale=display_scale,body_origin_mapping_verified=True,foot_pivot_verified=False,live_host_units_verified=False)


def host_push_to_recoil(push,units,getter):
    if type(push) not in (int,float) or not math.isfinite(push):raise ValueError('invalid host push')
    quantum=units['host_per_source_raw']*getter['numerator']/getter['denominator']
    recoil=round(push/quantum)
    if not -5000<=recoil<=5000:raise ValueError('host push exceeds native diagnostic range')
    product=recoil*getter['numerator'];raw=(abs(product)//getter['denominator'])*(-1 if product<0 else 1)
    represented=raw*units['host_per_source_raw'];error=abs(represented-push)
    if error>quantum/2+units['host_per_source_raw']+1e-9:raise ValueError('host push conversion exceeds quantization error')
    return dict(source_recoil=recoil,requested_host_push=push,represented_host_push=represented,max_quantization_error=quantum/2+units['host_per_source_raw'],actual_error=error,native_decay_before_displacement=True,live_motion_mapping=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('probe',type=Path);p.add_argument('boundary',type=Path);p.add_argument('candidate',type=Path);a=p.parse_args()
    audit(a.probe,a.boundary,a.candidate)
