"""Experimental D3D9On12 launch for the pinned SIGN build; offline checks only.

Start SIGN through its required BootGGXrd executable and intercept the exact child
before it creates a D3D9 device. Keep this process open while testing the game.
No game, Steam, registry, or driver files are changed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sign-producer'))
from sign.attach import pins, process_image  # noqa: E402

BOOT_SHA256 = '998ece44b49fd9f4442304ade6ab71ba14a4f6dca5b0e000d668fe934ba8f59b'
FRIDA = ROOT / 'local-cache/xrd-tools/frida/python'
RECEIPT = ROOT / 'local-cache/xrd-tools/oracle-dependencies.json'
REDIRECT = r'''
'use strict';
let replacement = null;
let redirected = false;
let deviceProbe = null;
let deviceHooked = false;
function guid(text) {
    const h = text.replace(/-/g, ''), p = Memory.alloc(16);
    p.writeU32(parseInt(h.slice(0, 8), 16)); p.add(4).writeU16(parseInt(h.slice(8, 12), 16));
    p.add(6).writeU16(parseInt(h.slice(12, 16), 16));
    for (let i = 0; i < 8; ++i) p.add(8 + i).writeU8(parseInt(h.slice(16 + 2*i, 18 + 2*i), 16));
    return p;
}
function call(object, slot, ret, types) {
    return new NativeFunction(object.readPointer().add(slot * 4).readPointer(), ret, ['pointer', ...types], 'stdcall');
}
function probeDevice(device) {
    const on12 = Memory.alloc(4), native12 = Memory.alloc(4);
    on12.writePointer(ptr(0)); native12.writePointer(ptr(0));
    const on12Guid = guid('e7fda234-b589-4049-940d-8878977531c8');
    const deviceGuid = guid('189819f1-1db6-4b57-be54-1821339b85f7');
    try {
        const qi = call(device, 0, 'int', ['pointer','pointer'])(device, on12Guid, on12);
        if (qi !== 0 || on12.readPointer().isNull()) return {on12_interface:false, qi};
        const iface = on12.readPointer();
        const get12 = call(iface, 3, 'int', ['pointer','pointer'])(iface, deviceGuid, native12);
        return {on12_interface:true, d3d12_device:get12 === 0 && !native12.readPointer().isNull(), get12};
    } finally {
        if (!native12.readPointer().isNull()) call(native12.readPointer(), 2, 'uint', [])(native12.readPointer());
        if (!on12.readPointer().isNull()) call(on12.readPointer(), 2, 'uint', [])(on12.readPointer());
    }
}
function watchDevice(d3d9) {
    if (deviceHooked) return;
    deviceHooked = true;
    const create = d3d9.readPointer().add(16 * 4).readPointer();
    Interceptor.attach(create, {
        onEnter(a) { this.output = a[6]; },
        onLeave(result) {
            if (result.toInt32() !== 0 || this.output.isNull() || this.output.readPointer().isNull()) return;
            try { deviceProbe = probeDevice(this.output.readPointer()); }
            catch (error) { deviceProbe = {error:String(error)}; }
            send({kind:'device-probe', ...deviceProbe});
        }
    });
}
function install(module) {
    if (replacement !== null) return;
    const original = module.getExportByName('Direct3DCreate9');
    const target = module.findExportByName('Direct3DCreate9On12');
    if (target === null) { send({kind:'error', message:'Direct3DCreate9On12 unavailable'}); return; }
    const create12 = new NativeFunction(target, 'pointer', ['uint','pointer','uint'], 'stdcall');
    const args = Memory.alloc(24);
    args.writeU32(1); // Enable9On12; let Windows create its device and queues.
    replacement = new NativeCallback(function (sdk) {
        const device = create12(sdk, args, 1);
        redirected = !device.isNull();
        if (redirected) watchDevice(device);
        send({kind:'redirected', sdk, success:redirected});
        return device;
    }, 'pointer', ['uint'], 'stdcall');
    Interceptor.replace(original, replacement);
    send({kind:'hooked'});
}
const loaded = Process.findModuleByName('d3d9.dll');
if (loaded !== null) install(loaded);
else Process.attachModuleObserver({onAdded(module) {
    if (module.name.toLowerCase() === 'd3d9.dll') install(module);
}});
rpc.exports = {status() { return {redirected, on12_module:Process.findModuleByName('d3d9on12.dll') !== null,
    device_probe:deviceProbe}; }};
'''


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def verified_paths(install):
    game = pins()['game']
    binary = install / 'Binaries/Win32'
    exe, boot = binary / 'GuiltyGearXrd.exe', binary / 'BootGGXrd.exe'
    if exe.stat().st_size != game['exe_size'] or digest(exe) != game['exe_sha256']:
        raise ValueError('SIGN game executable differs from pinned build')
    if digest(boot) != BOOT_SHA256:
        raise ValueError('SIGN bootstrap differs from pinned build')
    receipt = json.loads(RECEIPT.read_text(encoding='utf-8'))
    if receipt.get('complete') is not True or len(receipt.get('dlls', [])) != 3:
        raise ValueError('run tools/gather-xrd-oracle.ps1 first')
    library_dir = Path(receipt['directory'])
    for entry in receipt['dlls']:
        if digest(library_dir / entry['name']) != entry['sha256'].lower():
            raise ValueError('cached DirectX library fingerprint changed')
    return exe.resolve(), boot.resolve(), library_dir.resolve()


def load_frida():
    sys.path.insert(0, str(FRIDA))
    import frida
    if frida.__version__ != '17.22.2':
        raise ValueError('run tools/gather-xrd-instrumentation.py for pinned Frida')
    return frida


def same_image(pid, exe):
    try:
        return str(process_image(pid)).casefold() == str(exe).casefold()
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', type=Path, default=Path(pins()['game']['default_install']))
    parser.add_argument('--check', action='store_true', help='verify local inputs without launching')
    parser.add_argument('--seconds', type=int, default=30, help='observe the redirected child for 1..300 seconds')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 300:
        parser.error('--seconds must be 1..300')
    exe, boot, libraries = verified_paths(args.install)
    frida = load_frida()
    device = frida.get_local_device()
    running = [p.pid for p in device.enumerate_processes()
               if p.name.casefold() == exe.name.casefold() and same_image(p.pid, exe)]
    print(json.dumps(dict(game=str(exe), bootstrap=str(boot), existing_sign=running,
                          frida=frida.__version__, verified=True)), flush=True)
    if args.check:
        return
    if running:
        raise SystemExit('close the existing SIGN instance before the D3D9On12 launch check')

    children = queue.Queue()
    device.on('child-added', lambda child: children.put(child))
    env = dict(os.environ, PATH=str(libraries) + os.pathsep + os.environ.get('PATH', ''),
               SteamAppId='376300', SteamGameId='376300')
    boot_pid = device.spawn([str(boot)], cwd=str(boot.parent), env=env)
    boot_session = child_session = script = None
    pending = set()
    try:
        boot_session = device.attach(boot_pid)
        boot_session.enable_child_gating()
        device.resume(boot_pid)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            try:
                child = children.get(timeout=min(1, max(.01, deadline - time.monotonic())))
            except queue.Empty:
                continue
            pending.add(child.pid)
            if not same_image(child.pid, exe):
                device.resume(child.pid)
                pending.remove(child.pid)
                continue
            child_session = device.attach(child.pid)
            events = queue.Queue()
            script = child_session.create_script(REDIRECT)
            script.on('message', lambda message, data: events.put(message))
            script.load()
            device.resume(child.pid)
            pending.remove(child.pid)
            print('SIGN child resumed with D3D9On12 redirect, PID', child.pid, flush=True)
            observe_until = time.monotonic() + args.seconds
            while time.monotonic() < observe_until:
                try:
                    message = events.get(timeout=min(1, max(.01, observe_until - time.monotonic())))
                    print('redirect:', message, flush=True)
                    if message.get('type') == 'send' and message['payload'].get('kind') == 'redirected':
                        print('D3D9On12 status:', script.exports_sync.status(), flush=True)
                    if message.get('type') == 'send' and message['payload'].get('kind') == 'error':
                        raise RuntimeError(message['payload']['message'])
                    if message.get('type') == 'error':
                        raise RuntimeError(message.get('description', str(message)))
                except queue.Empty:
                    if child_session.is_detached:
                        raise RuntimeError('SIGN exited during D3D9On12 check')
            status = script.exports_sync.status()
            if not (status['redirected'] and status['on12_module'] and
                    status['device_probe'] and status['device_probe'].get('d3d12_device')):
                raise RuntimeError('SIGN D3D9On12 device check failed: ' + str(status))
            print('D3D9On12 launch check passed for SIGN PID', child.pid, status, flush=True)
            return
        raise TimeoutError('bootstrap did not create the pinned SIGN child in 45 seconds')
    finally:
        for pid in pending:
            try:
                device.resume(pid)
            except Exception:
                pass
        if boot_session is not None:
            try:
                boot_session.disable_child_gating()
                boot_session.detach()
            except Exception:
                pass
        if child_session is not None:
            try:
                if script is not None:
                    script.unload()
                child_session.detach()
            except Exception:
                pass


if __name__ == '__main__':
    main()
