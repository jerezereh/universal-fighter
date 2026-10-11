"""Validate private, counter-aligned attack metadata for an idle proxy diagnostic."""
import hashlib
import json
from pathlib import Path
import re
import struct


def pair_steps(values, first, frames):
    if type(values)!=list or not 2<=len(values)<=4 or any(type(v)!=int for v in values) or values[0]!=first or first<2 or values!=sorted(set(values)) or values[-1]>frames-20 or any(b-a<20 for a,b in zip(values,values[1:])):
        raise ValueError('multiple contacts require 2..4 ordered steps with bounded recovery windows')
    return values


def pair_result(event, steps, received):
    if type(received)!=int or not 0<=received<len(steps) or type(event.get('request_index'))!=int or type(event.get('request_ordinal'))!=int or event.get('request_index')!=steps[received] or event.get('request_ordinal')!=received+1:
        raise ValueError('unrequested/replayed/out-of-order native pair result')


def attack_region(code, code_rva, local):
    caller, entry, size = (local.get(k) for k in ('caller_rva', 'initializer_rva', 'initializer_size'))
    if any(type(v) != int for v in (caller, entry, size)) or not 32 <= size <= 4096:
        raise ValueError('invalid initializer witness')
    at, start = caller-code_rva, entry-code_rva
    body = code[at:at+17]
    if not 0 <= at <= len(code)-17 or body[:2] != b'\x8d\x8e' or body[6] != 0xe8 or body[11:13] != b'\x8d\x8e' or caller+11+struct.unpack_from('<i', body, 7)[0] != entry:
        raise ValueError('attack initializer caller changed')
    field, end = struct.unpack_from('<I', body, 2)[0], struct.unpack_from('<I', body, 13)[0]
    if field % 4 or end % 4 or not 0 < field < end <= 0x2600 or not 32 <= end-field <= 4096:
        raise ValueError('unbounded attack metadata region')
    if not 0 < start <= len(code)-size or code[start-1] != 0xcc or code[start+size-1] != 0xc3 or hashlib.sha256(code[start:start+size]).hexdigest() != local.get('initializer_sha256'):
        raise ValueError('complete initializer witness changed')
    return field, end-field


def template(code, code_rva, state, path):
    local = json.loads(path.read_text()); field, size = attack_region(code, code_rva, local)
    if local.get('pid') != state['pid'] or local.get('source_code_sha256') != state['code_sha256']:
        raise ValueError('proxy template session changed')
    folder = Path(local['capture']); proof = json.loads((folder/'inspection.json').read_text())
    if proof.get('pid') != state['pid'] or proof.get('errors') or not all(proof.get(k) for k in ('detached', 'source_unchanged', 'loaded_code_restored', 'controlled_update_step_verified')) or not proof.get('contact_check', {}).get('passed') or proof.get('input_check', {}).get('standing_punch_activations') != 1:
        raise ValueError('proxy template requires clean native contact capture')
    records = [json.loads(s) for s in (folder/'state.jsonl').read_text().splitlines()]
    frames = [s['fighters'] for s in records if s['boundary']['executed']]
    blocks = []
    for key, active in [('active_step', True), ('idle_step', False)]:
        step = local.get(key)
        if type(step) != int or not 1 <= step <= min(85, len(frames)):
            raise ValueError('invalid proxy template counter')
        fighter = frames[step-1][1]; data = (folder/('proxy-%03d.bin'%step)).read_bytes()
        if len(data) != 0x2600 or struct.unpack_from('<i', data, state['fields']['hit_count'])[0] != fighter['hit_count'] or fighter['y_raw'] or not fighter.get('pose_candidates') or any(not re.fullmatch('kyk200_[0-9]{2}' if active else 'kyk00[01]_[0-9]{2}', p['value']) for p in fighter['pose_candidates']) or (fighter['hit_count'] <= 0 if active else fighter['hit_count'] != 0):
            raise ValueError('proxy template pose/count mismatch')
        block = data[field:field+size]
        if hashlib.sha256(block).hexdigest() != local.get('active_sha256' if active else 'idle_sha256'):
            raise ValueError('proxy metadata capture changed')
        blocks.append(block)
    changes = [i for i in range(0, size, 4) if blocks[0][i:i+4] != blocks[1][i:i+4]]
    if not 1 <= len(changes) <= 8:
        raise ValueError('proxy template exceeds narrow metadata scope')
    return dict(field=field, active=blocks[0].hex(), idle=blocks[1].hex())


def idle_check(records, states, event):
    return bool(records and len(records) == len(states) and
        event.get('proxy_metadata_restored') is True and event.get('proxy_hit_count_before') == 0 and
        all(r.get('requested_inputs') == [0, 0] for r in records if r['executed']) and
        all(s[1]['hit_count'] == 0 and s[1]['y_raw'] == 0 and s[1].get('pose_candidates') and
            all(re.fullmatch('kyk00[01]_[0-9]{2}', p['value']) for p in s[1]['pose_candidates']) for s in states))
