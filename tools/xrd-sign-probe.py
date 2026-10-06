"""Read-only SIGN native-hook reconnaissance. Outputs stay under ignored artifacts.

Without --pid, inspect disk code. With --pid, read the normally launched Steam module.
Candidate matches are not verified hooks; this tool never publishes host-step capability.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

from xrd_native import PE, SIGN_HASH, ReadOnlyProcess, fingerprint, legacy_patterns, scan_patterns

ROOT = Path(__file__).resolve().parent.parent
GAME = Path('C:/Program Files (x86)/Steam/steamapps/common/GUILTY GEAR Xrd -SIGN-')


def inspect(game, pid=None):
    exe = game/'Binaries/Win32/GuiltyGearXrd.exe'
    before = fingerprint(exe)
    if before != SIGN_HASH or (game/'Binaries/Win32/steam_appid.txt').read_text().strip() != '376300':
        raise ValueError('unverified SIGN executable/app identity')
    pe = PE(exe.read_bytes())
    refs = json.loads((ROOT/'tools/upstreams.json').read_text())
    entry = refs['xrdLegacyOverlay']
    reference = ROOT/entry['path']
    actual = subprocess.check_output(['git','-C',str(reference),'rev-parse','HEAD'],text=True).strip()
    if actual != entry['commit']:
        raise ValueError('legacy reference revision drift')
    source = reference/'ggxrd_hitbox_overlay.cpp'
    patterns = legacy_patterns(source.read_text())
    disk = [(s,pe.data[s['raw']:s['raw']+s['size']]) for s in pe.executable_sections()]
    report = dict(schema=1,appid=376300,exe_sha256=before,reference_revision=actual,
                  reference_sha256=fingerprint(source),mode='loaded-module' if pid else 'disk',
                  sections=pe.sections,disk_candidates=scan_patterns(disk,patterns),
                  hook_semantics_verified=False,host_step=False,isolated_rgba=False,universal_contact=False)
    folder = ROOT/'artifacts/xrd-sign-native'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    folder.mkdir(parents=True)
    if pid:
        with ReadOnlyProcess(pid,exe) as process:
            if fingerprint(process.executable) != SIGN_HASH:
                raise ValueError('live target executable fingerprint drift')
            base, size = process.module_base()
            if size != pe.image_size:
                raise ValueError('loaded image bounds differ from verified PE')
            loaded = []
            loaded_hashes = {}
            for s in pe.executable_sections():
                data = process.read(base+s['rva'],s['size'])
                loaded.append((s,data))
                (folder/(s['name'].strip('.')+'-loaded.bin')).write_bytes(data)
                loaded_hashes[s['name']] = hashlib.sha256(data).hexdigest()
            report.update(pid=pid,module_base=base,image_size=size,loaded_hashes=loaded_hashes,
                          loaded_candidates=scan_patterns(loaded,patterns))
    if fingerprint(exe) != before:
        raise ValueError('source executable changed during probe')
    report['source_unchanged'] = True
    (folder/'inspection.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    selected = report.get('loaded_candidates',report['disk_candidates'])
    print('Probe:',folder)
    for row in selected:
        print(row['name']+':',len(row['matches']),'candidate(s); semantics unverified')
    return report,folder


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game',type=Path,default=GAME)
    p.add_argument('--pid',type=int,help='normally launched SIGN PID; read access only')
    a = p.parse_args()
    inspect(a.game,a.pid)
