// Development-only entry/return observation. No replacement, input or native calls.
let listener = null;
let config = null;
let sequence = 0;

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

rpc.exports = {
    start(p) {
        if (listener) throw new Error('already observing');
        const module = Process.mainModule;
        if (Process.arch !== 'ia32' || Process.pointerSize !== 4 || Process.id !== p.state.pid ||
            !module.base.equals(ptr(p.state.module_base)) || module.size !== p.image_size ||
            module.name.toLowerCase() !== 'guiltygearxrd.exe') throw new Error('source session mismatch');
        const target = module.base.add(p.candidate.rva);
        const actual = Array.from(bytes(target, p.candidate.code_size), x => x.toString(16).padStart(2, '0')).join('');
        if (actual !== p.candidate.function_hex) throw new Error('native function bytes changed');
        config = p;
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
                    const captured = snapshot(s.root);
                    // This boundary is under investigation; renderer/tick atomicity is not accepted.
                    send({kind: 'frame',sequence: ++sequence, before: s.before, after,
                        counter_delta: (after - s.before) >>> 0, thread: s.thread, depth: s.depth,
                        return_address: s.return_address, this_delta: s.this_delta,
                        entered_ms: s.entered_ms, returned_ms: Date.now(), segments: captured.segments}, captured.data);
                } catch (error) { send({kind: 'error',phase: 'return',message: String(error)}); }
            }
        });
        return {installed: true, mutation: 'temporary Frida entry interception; original routine runs unchanged'};
    },
    stop() {
        if (listener) { listener.detach(); listener = null; Interceptor.flush(); }
        return {detached: true, samples: sequence};
    }
};
