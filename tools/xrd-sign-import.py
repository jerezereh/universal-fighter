"""Fingerprint and inspect a bounded copy of local SIGN data; optional graphics export.

Run gather-xrd-tools.ps1 first. Outputs remain under ignored extracted/xrd-sign.
No hooks, save/config changes, script execution or host binding are performed.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from xrd_package import collision_archive, lzo_decoder, package, raw_asset
from xrd_script import command_sizes, instructions, linear_poses

ROOT = Path(__file__).resolve().parent.parent
EXE_HASH = 'f7a2e990b664f882bf16eafa94433ff0460f0b630c083fd0760a0d7949e08b78'


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def command(args, folder, label):
    result = subprocess.run([str(x) for x in args], cwd=folder, capture_output=True, timeout=180)
    (folder / (label + '.log')).write_bytes(result.stdout + result.stderr)
    if result.returncode or b'*** ERROR' in result.stdout + result.stderr:
        raise RuntimeError(f'{label} failed; inspect {folder / (label + ".log")}')
    return result.stdout.decode('utf-8', errors='replace')


def inspect(game, graphics):
    exe = game / 'Binaries/Win32/GuiltyGearXrd.exe'
    executable = exe.read_bytes()
    fingerprint = hashlib.sha256(executable).hexdigest()
    if fingerprint != EXE_HASH or (game / 'Binaries/Win32/steam_appid.txt').read_text().strip() != '376300':
        raise ValueError('unverified SIGN edition/build; inspect the new build before adapting it')
    sizes = command_sizes(executable)
    references = json.loads((ROOT / 'tools/upstreams.json').read_text())
    for key in ('xrdDecrypt', 'ueViewer'):
        entry = references[key]
        head = subprocess.check_output(['git', '-C', str(ROOT/entry['path']), 'rev-parse', 'HEAD'], text=True).strip()
        if head != entry['commit']:
            raise ValueError(f'upstream revision drift: {key}')
    decoder = ROOT / 'local-cache/xrd-tools/GGXrdRevelator.exe'
    lzo = ROOT / 'local-cache/xrd-tools/lzo.dll'
    viewer = ROOT / references['ueViewer']['path'] / 'umodel.exe'
    decompress = lzo_decoder(lzo)
    folder = ROOT / 'extracted/xrd-sign' / datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    folder.mkdir(parents=True)
    report = {'schema': 1, 'backend': 'xrd-sign-inspection', 'appid': 376300, 'exe_sha256': fingerprint,
              'complete': False, 'behavior_decoded': False, 'visual_accepted': False,
              'instruction_boundaries_verified': True,
              'tools': {key: references[key]['commit'] for key in ('xrdDecrypt', 'ueViewer')},
              'tool_hashes': {p.name: digest(p) for p in (decoder, lzo, viewer)}, 'packages': {}}
    selected = ['SOL_DAT_SF.upk', 'CMN_DAT_SF.upk']
    if graphics:
        selected += ['SOL_MSH_01_SF.upk', 'SOL_ANM_BTL_01_SF.upk', 'SOL_MAT_0100_SF.upk']
    for name in selected:
        source = game / 'REDGame/CookedPCConsole' / name
        before = digest(source)
        copied = folder / name
        shutil.copyfile(source, copied)
        command([decoder, '-sign', copied], folder, name + '-decode')
        decoded = copied.with_suffix('.upk.dec')
        listing = command([viewer, '-list', '-game=guilty', decoded], folder, name + '-list')
        virtual, names, exports = package(decoded.read_bytes(), decompress)
        # Independent reader agrees with the official viewer's actual export table.
        listed = re.findall(r'(?m)^\s*(\d+)\s+([0-9A-F]+)\s+([0-9A-F]+)\s+(\S+)\s+(\S+)\s*$', listing)
        if len(listed) != len(exports):
            raise ValueError(f'export-count disagreement: {name}')
        for index, (entry, row) in enumerate(zip(exports, listed)):
            expected = (index, entry['offset'], entry['size'], entry['class'], entry['name'])
            actual = (int(row[0]), int(row[1], 16), int(row[2], 16), row[3], row[4])
            if actual != expected:
                raise ValueError(f'export-table disagreement: {name}/{entry["name"]}')
            if entry['class'] in ('REDAssetCharaScript', 'REDAssetCollision'):
                payload = raw_asset(virtual, names, entry)
                (folder / (entry['name'] + '.bin')).write_bytes(payload)
                parsed = instructions(payload, sizes) if entry['class'] == 'REDAssetCharaScript' else collision_archive(payload)
                (folder / (entry['name'] + '.json')).write_text(json.dumps(parsed, indent=2), encoding='utf-8')
                if entry['name'] == 'BBS_SOL':
                    poses = linear_poses(parsed, 'NmlAtk5A')
                    (folder/'NmlAtk5A.poses.json').write_text(json.dumps(poses, indent=2), encoding='utf-8')
        if graphics and '_DAT_' not in name:
            mode = '-gltf' if '_MSH_' in name else '-png' if '_MAT_' in name else '-psk'
            command([viewer, '-export', '-game=guilty', mode, '-out=' + str(folder/'graphics'), decoded], folder, name + '-export')
            if not any((folder/'graphics'/name.removesuffix('.upk')).rglob('*')):
                raise ValueError(f'no exported graphics: {name}')
        if digest(source) != before or digest(copied) != before:
            raise ValueError(f'source/copy fingerprint changed: {name}')
        report['packages'][name] = {'source_sha256': before, 'decoded_sha256': digest(decoded),
                                    'virtual_sha256': hashlib.sha256(virtual).hexdigest(), 'exports': exports}
        print(f'{name}: {len(exports)} exports verified; source unchanged', flush=True)
    if digest(exe) != fingerprint:
        raise ValueError('source executable changed during inspection')
    report['complete'] = True
    (folder/'inspection.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'Inspection complete: {folder}. Behavior and presentation acceptance remain pending.')
    return folder


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, default=Path('C:/Program Files (x86)/Steam/steamapps/common/GUILTY GEAR Xrd -SIGN-'))
    parser.add_argument('--graphics', action='store_true', help='also export Sol mesh, animation and default-color packages')
    args = parser.parse_args()
    inspect(args.game.resolve(), args.graphics)
