"""Authored wire-schema and explicit partial-result rejection checks."""
import tempfile
from pathlib import Path
from host_hit_result import validate_result,read_result,damage_probe


def reject(action):
    try:action()
    except ValueError:return
    raise AssertionError('accepted invalid or unsupported typed result')


def main():
    result=dict(Accepted=True,Guarded=False,Knockdown=False,Parried=False,Barrier=False,
        ResourceCost=0,Damage=17,Stun=0,Hitstop=[0,0],PushX=0,PushY=0,Gravity=0)
    assert validate_result(result)==result and damage_probe(result)==17
    for patch in (dict(extra=1),dict(Accepted=1),dict(Damage=True),dict(Stun=-1),
                  dict(Hitstop=[0]),dict(Hitstop=[False,0]),dict(PushX=float('nan')),dict(Gravity=float('inf'))):
        reject(lambda:validate_result(result|patch))
    for patch in (dict(Accepted=False),dict(Guarded=True),dict(Parried=True),dict(Damage=420),
                  dict(Stun=15),dict(Hitstop=[3,3]),dict(PushX=2.4),dict(ResourceCost=1)):
        reject(lambda:damage_probe(result|patch))
    # Generic validation accepts an arbiter result even when this partial probe rejects it.
    assert validate_result(result|dict(Stun=15,PushX=2.4))['Stun']==15
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'result.json';path.write_text('{"Damage":17,"Damage":18}')
        reject(lambda:read_result(path))
        path.write_text(' '*16385);reject(lambda:read_result(path))
    print('Host HitResult schema, type/range/duplicate rejection and explicit partial-damage bounds passed.')


if __name__=='__main__':main()
