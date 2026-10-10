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


def damage_probe(value,allow_stun=False):
    """Explicit partial diagnostic. Never advertise full typed result application."""
    validate_result(value)
    if not value['Accepted'] or any(value[k] for k in FLAGS[1:]) or not 1<=value['Damage']<=419:
        raise ValueError('damage probe requires an accepted nonfatal unguarded result')
    if type(allow_stun)!=bool or value['Stun']>(30 if allow_stun else 0):raise ValueError('stun requires a witnessed bounded reaction probe')
    if any(value[k] for k in ('ResourceCost',)+VECTORS) or value['Hitstop']!=[0,0]:
        raise ValueError('damage probe cannot map resource, motion or hitstop values')
    return value['Damage']
