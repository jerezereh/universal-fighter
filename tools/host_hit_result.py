"""Game-independent HitResult validation; no source simulation or transport authority."""
import json
import math

FLAGS=('Accepted','Guarded','Knockdown','Parried','Barrier')
INTEGERS=('ResourceCost','Damage','Stun')
VECTORS=('PushX','PushY','Gravity')
FIELDS=set(FLAGS+INTEGERS+VECTORS+('Hitstop',))


def validate_result(value):
    if type(value)!=dict or set(value)!=FIELDS:raise ValueError('HitResult fields differ from the host schema')
    if any(type(value[k])!=bool for k in FLAGS):raise ValueError('HitResult flags must be booleans')
    if any(type(value[k])!=int or not 0<=value[k]<=2147483647 for k in INTEGERS):raise ValueError('invalid HitResult integer')
    stop=value['Hitstop']
    if type(stop)!=list or len(stop)!=2 or any(type(v)!=int or not 0<=v<=2147483647 for v in stop):raise ValueError('invalid HitResult hitstop')
    if any(type(value[k]) not in (int,float) or abs(value[k])>3.4028234663852886e38 or not math.isfinite(value[k]) for k in VECTORS):raise ValueError('invalid HitResult motion')
    return value


def read_result(path):
    if not 0<path.stat().st_size<=16384:raise ValueError('HitResult file exceeds bounds')
    def unique(pairs):
        value=dict(pairs)
        if len(value)!=len(pairs):raise ValueError('duplicate HitResult field')
        return value
    return validate_result(json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique))


def damage_probe(value,allow_stun=False,allow_guard=False,allow_push_x=False,allow_vertical=False,allow_knockdown=False):
    """Explicit partial diagnostic. Never advertise full typed result application."""
    validate_result(value)
    if type(allow_knockdown)!=bool or allow_knockdown and (not allow_vertical or not value['Knockdown']):raise ValueError('grounded knockdown requires witnessed vertical launch')
    if type(allow_guard)!=bool or not value['Accepted'] or any(value[k] for k in FLAGS[3:]) or value['Knockdown'] and not allow_knockdown:raise ValueError('reaction probe requires an accepted normal result')
    if value['Guarded']:
        if not allow_guard or not allow_stun or not 5<=value['Stun']<=30 or not 0<=value['Damage']<=419:raise ValueError('guard probe requires witnessed 5..30 frame blockstun and nonfatal chip')
    elif not 1<=value['Damage']<=419:raise ValueError('damage probe requires nonfatal damage')
    if type(allow_stun)!=bool or value['Stun']>(30 if allow_stun else 0):raise ValueError('stun requires a witnessed bounded reaction probe')
    if type(allow_push_x)!=bool or not allow_push_x and value['PushX']:raise ValueError('horizontal motion requires declared calibrated units')
    if type(allow_vertical)!=bool or allow_vertical and (value['Guarded'] or value['Stun'] or value['PushX'] or value['PushY']>=0 or value['Gravity']<=0):raise ValueError('vertical probe requires unguarded airborne motion without a stun or horizontal override')
    if not allow_vertical and (value['PushY'] or value['Gravity']):raise ValueError('vertical motion requires witnessed airborne reaction and declared units')
    if value['ResourceCost'] or value['Hitstop']!=[0,0]:
        raise ValueError('damage probe cannot map resource or nonzero hitstop values')
    return value['Damage']
