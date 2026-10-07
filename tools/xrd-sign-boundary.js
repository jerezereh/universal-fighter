// Development-only return observation or bounded offline gate; no input injection.
let listener = null;
let config = null;
let sequence = 0;
let gate = null;
let renderHooks = [];

function hex(data) {
    return Array.from(data, x => x.toString(16).padStart(2, '0')).join('');
}

function observePresent() {
    const module = Process.getModuleByName('d3d9.dll');
    const candidates = [];
    // Device constructor pattern from the pinned legacy reference, for the OS DLL only.
    for (const range of module.enumerateRanges('r-x')) {
        for (const hit of Memory.scanSync(range.base, range.size, 'c7 06 ?? ?? ?? ?? 89 86 ?? ?? ?? ?? 89 86')) {
            const table = hit.address.add(2).readPointer();
            if (table.compare(module.base) < 0 || table.add(43 * 4).compare(module.base.add(module.size)) > 0)
                throw new Error('invalid device-table candidate');
            for (const [slot, method] of [[17, 'Present'], [42, 'EndScene']]) {
                const target = table.add(slot * 4).readPointer();
                const executable = Process.findRangeByAddress(target);
                if (target.compare(module.base) < 0 || target.compare(module.base.add(module.size)) >= 0 ||
                    executable === null || !executable.protection.includes('x')) throw new Error('invalid device method candidate');
                candidates.push({table, target, slot, method});
            }
        }
    }
    if (candidates.length === 0 || candidates.length > 8) throw new Error('missing/unbounded Direct3D device candidates');
    // Observe every bounded candidate; only a real call whose device owns that table counts.
    for (const target of new Map(candidates.map(c => [c.target.toString(), c.target])).values()) {
        const methods = candidates.filter(c => c.target.equals(target));
        const before = hex(bytes(target, 32));
        const listener = Interceptor.attach(target, {
            onEnter(args) {
                this.valid = false;
                try {
                    const table = args[0].readPointer();
                    const method = methods.find(c => table.add(c.slot * 4).readPointer().equals(target));
                    if (!method) return;
                    const root = Process.mainModule.base.add(config.state.engine_global_rva).readPointer();
                    this.counter = root.add(4 + config.candidate.counter_field).readU32();
                    this.device = args[0].toString(); this.method = method.method; this.valid = true;
                } catch (error) { send({kind: 'error',phase: 'present',message: String(error)}); }
            },
            onLeave(result) {
                if (this.valid) send({kind: 'present',counter: this.counter,device: this.device,
                    method: this.method,target: target.toString(),thread: this.threadId,hresult: result.toInt32(),wall_ms: Date.now()});
            }
        });
        renderHooks.push({listener,target,before});
    }
    return {candidates: candidates.length, targets: renderHooks.length};
}

function bytes(address, size) {
    return new Uint8Array(address.readByteArray(size));
}

function snapshot(root) {
    const f = config.state.fields;
    const segments = [];
    let length = 0;
    function add(address, size) {
        const data = bytes(address, size);
        segments.push({address: address.toUInt32(), offset: length, size, data});
        length += size;
    }
    const global = Process.mainModule.base.add(config.state.engine_global_rva);
    add(global, 4);
    const headerSize = Math.max(f.slots + 8, f.count + 4);
    add(root, headerSize);
    const count = root.add(f.count).readS32();
    const slots = [root.add(f.slots).readPointer(), root.add(f.slots + 4).readPointer()];
    if (count < 2 || count > 256 || slots.some(x => x.isNull()) || slots[0].equals(slots[1]))
        throw new Error('invalid training slots/count');
    for (const actor of slots) {
        // One actor block contains both scalar fields and candidate pose/state names.
        const data = bytes(actor, 0x2600);
        const view = new DataView(data.buffer);
        const hurt = view.getInt32(f.hurt_count, true);
        const hit = view.getInt32(f.hit_count, true);
        if (hurt < 0 || hurt > 64 || hit < 0 || hit > 64)
            throw new Error('invalid collision count');
        segments.push({address: actor.toUInt32(), offset: length, size: data.length, data});
        length += data.length;
        if (hurt + hit) add(ptr(view.getUint32(f.boxes, true)), 20 * (hurt + hit));
    }
    if (!global.readPointer().equals(root) || !slots.every((s, i) => root.add(f.slots + 4 * i).readPointer().equals(s)))
        throw new Error('source scene changed');
    const output = new Uint8Array(length);
    for (const s of segments) output.set(s.data, s.offset);
    return {segments: segments.map(({address, offset, size}) => ({address, offset, size})), data: output.buffer};
}

function publish(s, after, executed) {
    const captured = snapshot(s.root);
    send({kind: 'frame',sequence: ++sequence, before: s.before, after,
        counter_delta: (after - s.before) >>> 0, thread: s.thread, depth: s.depth,
        return_address: s.return_address, this_delta: s.this_delta,
        entered_ms: s.entered_ms, returned_ms: Date.now(), executed,
        segments: captured.segments}, captured.data);
}

function thiscallOracle() {
    // Authored scratch code: increment the argument's uint32, return it, no stack arguments.
    const code = Memory.alloc(Process.pageSize);
    Memory.protect(code, Process.pageSize, 'rwx');
    code.writeByteArray([0xff, 0x01, 0x8b, 0x01, 0xc3]);
    const value = Memory.alloc(4);
    value.writeU32(0);
    const call = new NativeFunction(code, 'uint', ['pointer'], 'thiscall');
    let allow = false;
    const replacement = new NativeCallback(function(object) {
        if (!object.equals(value) || !this.context.ecx.equals(value)) throw new Error('thiscall ABI mismatch');
        return allow ? call(object) : object.readU32();
    }, 'uint', ['pointer'], 'thiscall');
    try {
        Interceptor.replace(code, replacement);
        Interceptor.flush();
        if (call(value) !== 0) throw new Error('authored call did not block');
        allow = true;
        if (call(value) !== 1 || value.readU32() !== 1) throw new Error('authored original-call bypass failed');
    } finally { Interceptor.revert(code); Interceptor.flush(); }
    if (call(value) !== 2) throw new Error('authored code restoration failed');
    return true;
}

function installGate(target, p) {
    thiscallOracle();
    const render = observePresent();
    const root = Process.mainModule.base.add(p.state.engine_global_rva).readPointer();
    const original = new NativeFunction(target, 'void', ['pointer'], {abi: 'thiscall', exceptions: 'propagate'});
    gate = {target, root, credits: 0, pending: false, deadline: Date.now() + 8000, resumed: false, timer: null};
    const replacement = new NativeCallback(function(object) {
        const g = gate;
        if (g === null || g.resumed) { original(object); return; }
        if (Date.now() > g.deadline) {
            g.resumed = true;
            send({kind: 'error', phase: 'watchdog', message: 'gate lease expired; original execution resumed'});
            original(object); return;
        }
        let s;
        try {
            const currentRoot = Process.mainModule.base.add(p.state.engine_global_rva).readPointer();
            if (!currentRoot.equals(g.root) || !object.equals(g.root.add(4)) ||
                !this.context.ecx.equals(object) || this.threadId !== p.gate.thread ||
                this.returnAddress.toString() !== p.gate.return_address || this.depth !== 0)
                throw new Error('source caller/scene changed');
            s = {root: g.root, before: object.add(p.candidate.counter_field).readU32(),
                thread: this.threadId, depth: this.depth, return_address: this.returnAddress.toString(),
                this_delta: 4, entered_ms: Date.now()};
        } catch (error) {
            g.resumed = true;
            send({kind: 'error',phase: 'gate',message: String(error) + '; original execution resumed'});
            original(object); return;
        }
        const execute = g.credits === 1;
        if (execute) { g.credits = 0; original(object); }
        try {
            publish(s, object.add(p.candidate.counter_field).readU32(), execute);
        } catch (error) {
            g.resumed = true;
            send({kind: 'error',phase: 'gate-snapshot',message: String(error)});
        } finally { if (execute) g.pending = false; }
    }, 'void', ['pointer'], 'thiscall');
    gate.replacement = replacement;
    Interceptor.replace(target, replacement);
    // A disconnected controller cannot leave this development gate installed indefinitely.
    gate.timer = setTimeout(() => {
        if (gate !== null) {
            Interceptor.revert(target); Interceptor.flush(); gate = null;
            send({kind: 'error',phase: 'watchdog',message: 'hard gate lifetime expired; hook removed'});
        }
    }, 12000);
    return {installed: true, thiscall_oracle: true, mutation: 'bounded native update gate', lifetime_seconds: 12, render};
}

rpc.exports = {
    start(p) {
        if (listener || gate) throw new Error('already observing');
        const module = Process.mainModule;
        if (Process.arch !== 'ia32' || Process.pointerSize !== 4 || Process.id !== p.state.pid ||
            !module.base.equals(ptr(p.state.module_base)) || module.size !== p.image_size ||
            module.name.toLowerCase() !== 'guiltygearxrd.exe') throw new Error('source session mismatch');
        const target = module.base.add(p.candidate.rva);
        const actual = hex(bytes(target, p.candidate.code_size));
        if (actual !== p.candidate.function_hex) throw new Error('native function bytes changed');
        config = p;
        if (p.gate) return installGate(target, p);
        listener = Interceptor.attach(target, {
            onEnter() {
                this.sample = null;
                try {
                    const root = module.base.add(p.state.engine_global_rva).readPointer();
                    const object = this.context.ecx;
                    if (root.isNull() || (!object.equals(root) && !object.equals(root.add(4))))
                        throw new Error('unexpected thiscall object');
                    this.sample = {root, object, before: object.add(p.candidate.counter_field).readU32(),
                        thread: this.threadId, depth: this.depth, return_address: this.returnAddress.toString(),
                        this_delta: object.sub(root).toInt32(), entered_ms: Date.now()};
                } catch (error) { send({kind: 'error',phase: 'enter',message: String(error)}); }
            },
            onLeave() {
                if (this.sample === null) return;
                try {
                    const s = this.sample;
                    const after = s.object.add(p.candidate.counter_field).readU32();
                    // This boundary is under investigation; renderer/tick atomicity is not accepted.
                    publish(s, after, true);
                } catch (error) { send({kind: 'error',phase: 'return',message: String(error)}); }
            }
        });
        return {installed: true, mutation: 'temporary Frida entry interception; original routine runs unchanged'};
    },
    step() {
        if (gate === null || gate.resumed || gate.pending || gate.credits !== 0)
            throw new Error('gate unavailable or step already pending');
        gate.deadline = Date.now() + 8000;
        gate.pending = true; gate.credits = 1;
        return {accepted: true};
    },
    stop() {
        if (listener) { listener.detach(); listener = null; Interceptor.flush(); }
        if (gate) {
            clearTimeout(gate.timer);
            Interceptor.revert(gate.target); Interceptor.flush(); gate = null;
        }
        for (const h of renderHooks) h.listener.detach();
        Interceptor.flush();
        const renderRestored = renderHooks.every(h => hex(bytes(h.target, 32)) === h.before);
        renderHooks = [];
        return {detached: true, samples: sequence, render_code_restored: renderRestored};
    }
};
