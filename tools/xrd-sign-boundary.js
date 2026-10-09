// Development-only return observation or bounded offline gate; no desktop input.
let listener = null;
let config = null;
let sequence = 0;
let gate = null;
let renderHooks = [];
let inputHooks = [];
const pendingInputs = new Map();
let renderCapture = {attempts: 0, counter: null, presentations: 0};
let drawTrace = null;
let drawFilter = null;
const comMethods = new Map();
let stopRequested = false;
let stopReceipt = null;

function removeDrawFilter() {
    if (drawFilter !== null) {
        Interceptor.revert(drawFilter.target); Interceptor.flush(); drawFilter = null;
    }
}

function installDrawFilter(device, identity) {
    if (!device.equals(ptr(identity.device))) throw new Error('draw identity device changed');
    const pairs = Object.values(identity.parts);
    const target = device.readPointer().add(82 * 4).readPointer();
    const original = new NativeFunction(target, 'int', ['pointer','uint','int','uint','uint','uint','uint'],
        {abi: 'stdcall', exceptions: 'propagate'});
    const replacement = new NativeCallback(function(object, type, base, min, vertices, start, primitives) {
        if (config.layer && layerDrawing) return original(object, type, base, min, vertices, start, primitives);
        const d = drawTrace, g = gate, filter = drawFilter;
        if (filter !== null && d !== null && object.equals(d.device) && g !== null && !g.resumed &&
            Date.now() <= g.deadline && pairs.some(p => p.index_buffer === d.indexBuffer && p.vertex_buffer === d.vertexBuffer)) {
            if (config.layer) {
                const result = original(object, type, base, min, vertices, start, primitives);
                if (result === 0) try {
                    observeBodyAnchor(object,d);
                    replayMeshDraw(object, original, [type,base,min,vertices,start,primitives], d);
                }
                catch (error) {
                    layerFailed = true;
                    if (meshLayer !== null) meshLayer.state_verified = false;
                    send({kind: 'error',phase: 'mesh-layer',message: String(error)});
                }
                return result;
            }
            if (config.inspect_mesh_shaders) {
                try { inspectMeshVertexShader(object, d, filter); inspectMeshShader(object, d, filter); }
                catch (error) { send({kind: 'error',phase: 'mesh-shader',message: String(error)}); }
                return original(object, type, base, min, vertices, start, primitives);
            }
            ++filter.skipped;
            return 0; // Diagnostic mesh suppression only; original source simulation stays intact.
        }
        return original(object, type, base, min, vertices, start, primitives);
    }, 'int', ['pointer','uint','int','uint','uint','uint','uint'], 'stdcall');
    drawFilter = {target, replacement, skipped: 0, shaders: new Set(), vertices: new Set()};
    Interceptor.replace(target, replacement); Interceptor.flush();
}

function inspectMeshShader(device, d, filter) {
    if (d.pixelShader && filter.shaders.has(d.pixelShader)) return;
    const output = Memory.alloc(4); output.writePointer(ptr(0));
    let shader = ptr(0);
    try {
        succeeded(com(device, 108, 'int', ['pointer'])(device, output), 'GetPixelShader');
        shader = output.readPointer();
        if (shader.isNull()) throw new Error('missing mesh pixel shader');
        const id = shader.toString();
        d.pixelShader = id;
        if (filter.shaders.has(id)) return;
        if (filter.shaders.size >= 32) throw new Error('mesh shader limit');
        const size = Memory.alloc(4); size.writeU32(0);
        succeeded(com(shader, 4, 'int', ['pointer','pointer'])(shader, ptr(0), size), 'GetFunction size');
        const length = size.readU32();
        if (length < 8 || length > 65536 || length % 4) throw new Error('invalid shader bytecode bounds');
        const data = Memory.alloc(length);
        succeeded(com(shader, 4, 'int', ['pointer','pointer'])(shader, data, size), 'GetFunction');
        if (size.readU32() !== length) throw new Error('shader size changed');
        filter.shaders.add(id);
        send({kind: 'mesh-shader', shader: id, code_size: length, source_target: d.currentTarget,
            index_buffer: d.indexBuffer, vertex_buffer: d.vertexBuffer}, data.readByteArray(length));
    } finally { if (!shader.isNull()) com(shader, 2, 'uint', [])(shader); }
}

function twoTriangleDraw(method,args) {
    const count={DrawPrimitive:3,DrawPrimitiveUP:2,DrawIndexedPrimitiveUP:4}[method];
    return count!==undefined && [4,5].includes(args[1].toUInt32()) && args[count].toUInt32()===2;
}

function installDrawTrace(device) {
    drawTrace = {device, active: false, frames: 0, events: [], counter: null, surfaces: new Map(),
        currentTarget: null, passSeen: new Set(), passBytes: 0, passIndex: 0,screenShaders:new Set(),
        lutShaders:new Set(),colorBoundarySteps:new Set(),screenPrograms:new Map()};
    drawTrace.screenStagesStarted=false;
    drawTrace.screenStagesDone=false;
    // D3D9 interface slots, not source-game offsets. Capture two complete Present intervals.
    const methods = [[37, 'SetRenderTarget', ['u', 'p']], [43, 'Clear', ['u', 'p', 'u', 'u', 'u', 'u']],
        [65, 'SetTexture', ['u', 'p']], [81, 'DrawPrimitive', ['u', 'u', 'u']],
        [82, 'DrawIndexedPrimitive', ['u', 'i', 'u', 'u', 'u', 'u']],
        [83, 'DrawPrimitiveUP', ['u', 'u', 'p', 'u']],
        [84, 'DrawIndexedPrimitiveUP', ['u', 'u', 'u', 'u', 'p', 'u', 'p', 'u']],
        [92, 'SetVertexShader', ['p']], [100, 'SetStreamSource', ['u', 'p', 'u', 'u']],
        [104, 'SetIndices', ['p']], [107, 'SetPixelShader', ['p']]];
    const targets = new Set();
    // Snapshot every prefix before installing any hook: nearby methods can share a 32-byte window.
    const resolved = methods.map(([slot, method, types]) => {
        const target = device.readPointer().add(slot * 4).readPointer();
        const range = Process.findRangeByAddress(target);
        if (range === null || !range.protection.includes('x') || targets.has(target.toString()))
            throw new Error('invalid/aliased draw-trace method');
        targets.add(target.toString());
        return {target, slot, method, types, before: hex(bytes(target, 32))};
    });
    for (const {target, slot, method, types, before} of resolved) {
        const listener = Interceptor.attach(target, {
            onEnter(args) {
                this.event = null;
                this.binding = null;
                this.targetBinding = null;
                this.gradeDevice=null;
                this.gradeReplay=null;
                this.postReplay=null;
                this.screenStage=null;
                if (config.layer && layerDrawing) return;
                const d = drawTrace;
                if (d === null || !args[0].equals(d.device)) return;
                if (method === 'SetIndices') this.binding = ['indexBuffer', args[1].toString()];
                if (method === 'SetVertexShader') this.binding = ['vertexShader', args[1].toString()];
                if (method === 'SetPixelShader') this.binding = ['pixelShader', args[1].toString()];
                if (method === 'SetTexture' && args[1].toUInt32()<16) this.binding=['texture'+args[1].toUInt32(),args[2].toString()];
                if (method === 'SetStreamSource' && args[1].toUInt32() === 0)
                    this.binding = ['vertexBuffer', args[2].toString()];
                if (method === 'SetRenderTarget' && args[1].toUInt32() === 0) this.targetBinding = args[2].toString();
                if(config.layer?.grade && twoTriangleDraw(method,args) && d.pixelShader===config.layer.grade.shader &&
                        d.currentTarget===config.layer.grade.target) {
                    this.gradeDevice=args[0];
                    if(config.layer.source_color && method==='DrawIndexedPrimitiveUP') {
                        const device=args[0],signature=types.map(t=>t==='p'?'pointer':t==='i'?'int':'uint');
                        const values=types.map((t,i)=>t==='p'?args[i+1]:t==='i'?args[i+1].toInt32():args[i+1].toUInt32());
                        this.gradeReplay=()=>com(device,slot,'int',signature)(device,...values);
                    }
                }
                if(config.layer?.post_color && meshLayer?.post && !meshLayer.post.complete && twoTriangleDraw(method,args)) {
                    const expected=config.layer.post_color[meshLayer.post.index];
                    if(d.pixelShader===expected.shader && d.currentTarget===expected.target) {
                        if(method!=='DrawIndexedPrimitiveUP')throw new Error('post-color replay requires indexed CPU quad');
                        inspectScreenInput(args[0],args);
                        const dev=args[0],signature=types.map(t=>t==='p'?'pointer':t==='i'?'int':'uint');
                        const values=types.map((t,i)=>t==='p'?args[i+1]:t==='i'?args[i+1].toInt32():args[i+1].toUInt32());
                        this.postReplay={device:dev,draw:()=>com(dev,slot,'int',signature)(dev,...values)};
                    }
                }
                if(config.inspect_screen_shaders && config.layer && twoTriangleDraw(method,args)) {
                    try {observeLayerColorBoundary(d);}
                    catch(error) {send({kind:'error',phase:'layer-color-boundary',message:String(error)});}
                }
                if (!d.active) return;
                if(config.inspect_screen_shaders && gate!==null && !gate.resumed && !gate.executing &&
                    twoTriangleDraw(method,args)) {
                    try { inspectScreenShader(device,d,method,args); }
                    catch(error) {send({kind:'error',phase:'screen-shader',message:String(error)});}
                }
                if(config.capture_screen_stages && d.frames===0 && !d.screenStagesDone && twoTriangleDraw(method,args)) {
                    if(d.lutShaders.has(d.pixelShader))d.screenStagesStarted=true;
                    if(d.screenStagesStarted) {
                        if(d.passIndex>=24)throw new Error('screen-stage count limit');
                        this.screenStage={shader:d.pixelShader,event:d.events.length,device:args[0]};
                        if(/^\/\/\s+blendTex\s+s\d+\s+1\s*$/m.test(d.screenPrograms.get(d.pixelShader)??''))d.screenStagesDone=true;
                    }
                }
                if (d.events.length >= 8192) {
                    d.active = false;
                    send({kind: 'error',phase: 'draw-trace',message: 'draw interval overflow'}); return;
                }
                const main = Process.mainModule, caller = this.returnAddress;
                this.event = {method, values: types.map((type, i) => type === 'p' ? args[i + 1].toString() :
                    type === 'i' ? args[i + 1].toInt32() : args[i + 1].toUInt32()), thread: this.threadId,
                    caller_rva: caller.compare(main.base) >= 0 && caller.compare(main.base.add(main.size)) < 0 ?
                        caller.sub(main.base).toUInt32() : null};
                if (method === 'SetRenderTarget' && !args[2].isNull()) {
                    const id = args[2].toString();
                    try {
                        if (!d.surfaces.has(id)) {
                            if (d.surfaces.size >= 32) throw new Error('surface description limit');
                            const desc = Memory.alloc(32);
                            succeeded(com(args[2], 12, 'int', ['pointer'])(args[2], desc), 'GetDesc');
                            d.surfaces.set(id, {format: desc.readU32(), type: desc.add(4).readU32(),
                                usage: desc.add(8).readU32(), pool: desc.add(12).readU32(),
                                multisample: desc.add(16).readU32(), width: desc.add(24).readU32(), height: desc.add(28).readU32()});
                        }
                        this.event.surface = d.surfaces.get(id);
                    } catch (error) { send({kind: 'error',phase: 'draw-surface',message: String(error)}); }
                }
                if (config.capture_passes && !config.capture_screen_stages && method === 'SetRenderTarget' && args[1].toUInt32() === 0 &&
                    d.frames === 0 && d.passSeen.size < 24 && d.passBytes < 128 * 1024 * 1024 &&
                    !d.passSeen.has(d.currentTarget) && gate !== null && !gate.executing && !gate.resumed) {
                    try {
                        const root = Process.mainModule.base.add(config.state.engine_global_rva).readPointer();
                        const captured = captureBackBuffer(device, root, d.counter, true);
                        if (!d.passSeen.has(captured.metadata.surface)) {
                            if (d.passBytes + captured.data.byteLength > 128 * 1024 * 1024)
                                throw new Error('render-pass byte limit exceeded');
                            d.passSeen.add(captured.metadata.surface); d.passBytes += captured.data.byteLength;
                            send({...captured.metadata, pass_index: ++d.passIndex, trace_event: d.events.length,
                                capture_boundary: 'before-target-switch', hresult: 0}, captured.data);
                        }
                    } catch (error) {
                        d.passSeen.add(d.currentTarget); // One diagnostic attempt per target, including failures.
                        send({kind: 'error',phase: 'render-pass',message: String(error)});
                    }
                }
            },
            onLeave(result) {
                if(this.screenStage && result.toInt32()===0) {
                    try {
                        const d=drawTrace,s=this.screenStage;
                        const root=Process.mainModule.base.add(config.state.engine_global_rva).readPointer();
                        const captured=captureBackBuffer(s.device,root,d.counter,true);
                        const textureSources=screenTextureSources(s.device,d.screenPrograms.get(s.shader));
                        if(d.passBytes+captured.data.byteLength>128*1024*1024)throw new Error('screen-stage byte limit');
                        d.passBytes+=captured.data.byteLength;
                        send({...captured.metadata,pass_index:++d.passIndex,trace_event:s.event,
                            presentation_index:1,screen_shader:s.shader,capture_boundary:'after-screen-draw',
                            texture_sources:textureSources,diagnostic_pipeline:true,hresult:0},captured.data);
                    }catch(error){send({kind:'error',phase:'screen-stage',message:String(error)});}
                }
                if(this.gradeDevice!==null && result.toInt32()===0) {
                    try {gradeLayer(this.gradeDevice,drawTrace,this.gradeReplay);}
                    catch(error){layerFailed=true;if(meshLayer!==null)meshLayer.state_verified=false;
                        send({kind:'error',phase:'native-private-grading',message:String(error)});}
                }
                if(this.postReplay && result.toInt32()===0) {
                    try {postColorLayer(this.postReplay.device,drawTrace,this.postReplay.draw);}
                    catch(error){layerFailed=true;if(meshLayer!==null)meshLayer.state_verified=false;
                        send({kind:'error',phase:'private-post-color',message:String(error)});}
                }
                if (this.binding && drawTrace !== null && result.toInt32() === 0)
                    drawTrace[this.binding[0]] = this.binding[1];
                if (this.targetBinding && drawTrace !== null && result.toInt32() === 0)
                    drawTrace.currentTarget = this.targetBinding;
                if (this.event && drawTrace !== null && drawTrace.active) {
                    if (result.toInt32() === 0 && this.event.method === 'SetRenderTarget' && this.event.values[0] === 0)
                        drawTrace.currentTarget = this.event.values[1];
                    drawTrace.events.push({...this.event, hresult: result.toInt32()});
                }
            }
        });
        renderHooks.push({listener, target, before});
    }
    Interceptor.flush();
}

function drawInterval(device, counter, entering, hresult = 0) {
    const d = drawTrace;
    if (d === null || !device.equals(d.device)) return;
    if (entering && d.active) {
        d.active = false;
        send({kind: 'draw-trace', frame: ++d.frames, counter_before: d.counter, counter_after: counter,
            device: device.toString(), events: d.events, isolated_rgba: false});
        d.events = [];
    } else if (!entering && hresult === 0 && d.frames < 2 && gate !== null && !gate.resumed) {
        d.counter = counter; d.active = true;
    }
}

function com(object, slot, result, arguments_) {
    const target = object.readPointer().add(slot * 4).readPointer();
    const key = target.toString() + ':' + result + ':' + arguments_.join(',');
    if (comMethods.has(key)) return comMethods.get(key);
    const range = Process.findRangeByAddress(target);
    if (range === null || !range.protection.includes('x')) throw new Error('invalid COM method');
    if (comMethods.size >= 256) throw new Error('COM method cache limit');
    const method = new NativeFunction(target, result, ['pointer', ...arguments_],
        {abi: 'stdcall', exceptions: 'propagate'});
    comMethods.set(key, method); return method;
}

function succeeded(hr, name) {
    if (hr < 0) throw new Error(name + ' failed: ' + hr);
}

function captureBackBuffer(device, root, counter, intermediate = false, privateSurface = null) {
    // Diagnostic full-scene capture only. No render-state changes or fabricated alpha.
    const buffer = Memory.alloc(4), staging = Memory.alloc(4), desc = Memory.alloc(32);
    buffer.writePointer(ptr(0)); staging.writePointer(ptr(0));
    let surface = ptr(0), destination = ptr(0), locked = false;
    try {
        if (privateSurface !== null) {
            com(privateSurface, 1, 'uint', [])(privateSurface); buffer.writePointer(privateSurface);
        } else if (intermediate) succeeded(com(device, 38, 'int', ['uint', 'pointer'])(device, 0, buffer), 'GetRenderTarget');
        else succeeded(com(device, 18, 'int', ['uint', 'uint', 'uint', 'pointer'])(device, 0, 0, 0, buffer), 'GetBackBuffer');
        surface = buffer.readPointer();
        succeeded(com(surface, 12, 'int', ['pointer'])(surface, desc), 'GetDesc');
        const format = desc.readU32(), multisample = desc.add(16).readU32();
        const width = desc.add(24).readU32(), height = desc.add(28).readU32();
        const pixelBytes = [36, 113].includes(format) ? 8 : 4;
        const formats=intermediate?[21,22,36,113,114]:privateSurface!==null && config.layer?.hdr?[21,113]:[21,22];
        if (!formats.includes(format) || multisample !== 0 || width < 1 || height < 1 ||
            width > 2048 || height > 2048) throw new Error('unsupported/bounded backbuffer description');
        succeeded(com(device, 36, 'int', ['uint', 'uint', 'uint', 'uint', 'pointer', 'pointer'])(
            device, width, height, format, 2, staging, ptr(0)), 'CreateOffscreenPlainSurface');
        destination = staging.readPointer();
        succeeded(com(device, 32, 'int', ['pointer', 'pointer'])(device, surface, destination), 'GetRenderTargetData');
        const rect = Memory.alloc(8);
        succeeded(com(destination, 13, 'int', ['pointer', 'pointer', 'uint'])(destination, rect, ptr(0), 0x10), 'LockRect');
        locked = true;
        const pitch = rect.readS32(), pixels = rect.add(4).readPointer();
        if (pitch < width * pixelBytes || pitch > 65536 || pixels.isNull()) throw new Error('invalid locked pitch/pixels');
        const state = snapshot(root);
        const output = new Uint8Array(state.data.byteLength + width * height * pixelBytes);
        output.set(new Uint8Array(state.data));
        if (pitch === width * pixelBytes) output.set(bytes(pixels, width * height * pixelBytes), state.data.byteLength);
        else for (let y = 0; y < height; ++y)
            output.set(bytes(pixels.add(y * pitch), width * pixelBytes), state.data.byteLength + y * width * pixelBytes);
        const global = Process.mainModule.base.add(config.state.engine_global_rva);
        if (!global.readPointer().equals(root) || root.add(4 + config.candidate.counter_field).readU32() !== counter ||
            gate === null || gate.resumed || gate.executing) throw new Error('source advanced during readback');
        return {metadata: {kind: intermediate ? 'render-pass' : 'render', counter, width, height, format, multisample, pitch,
            surface: surface.toString(), pixel_bytes: pixelBytes,
            state_size: state.data.byteLength, segments: state.segments, device: device.toString(),
            presentation_index: intermediate ? null : renderCapture.presentations, atomic_native_frame: false,
            isolated_rgba: false, native_render_latency_verified: false}, data: output.buffer};
    } finally {
        // Independently release both references even if unlock or an earlier operation fails.
        try { if (locked) succeeded(com(destination, 14, 'int', [])(destination), 'UnlockRect'); }
        finally {
            try { if (!destination.isNull()) com(destination, 2, 'uint', [])(destination); }
            finally { if (!surface.isNull()) com(surface, 2, 'uint', [])(surface); }
        }
    }
}

function installInput(p) {
    const input = p.input;
    for (const label of ['sampler', 'writer']) {
        const address = Process.mainModule.base.add(input[label + '_rva']);
        if (hex(bytes(address, input[label + '_size'])) !== input[label + '_hex'])
            throw new Error('native input function bytes changed');
    }
    const writer = Process.mainModule.base.add(input.writer_rva);
    const writerListener = Interceptor.attach(writer, {
        onEnter() {
            this.sample = null;
            try {
                const root = Process.mainModule.base.add(p.state.engine_global_rva).readPointer();
                const ring = this.context.ecx;
                const delta = ring.sub(root.add(4 + input.ring_field)).toInt32();
                if (delta !== 0 && delta !== input.stride) return;
                const incoming = this.context.esp.add(4).readU32() & 0xffff;
                if (p.gate) {
                    // The instruction hook relocates the CALL's return address into a trampoline.
                    const event = pendingInputs.get(this.threadId);
                    pendingInputs.delete(this.threadId);
                    if (!event || event.slot !== delta / input.stride || event.incoming !== incoming)
                        throw new Error('source input did not follow validated ingress');
                } else if (!this.returnAddress.equals(Process.mainModule.base.add(input.ingress_rva + 8)))
                    throw new Error('unexpected source input caller');
                this.sample = {ring, slot: delta / input.stride,
                    incoming,
                    previous: ring.add(input.current).readU16(),
                    counter: root.add(4 + p.candidate.counter_field).readU32(),thread: this.threadId};
            } catch (error) { send({kind: 'error',phase: 'input-enter',message: String(error)}); }
        },
        onLeave() {
            if (this.sample === null) return;
            try {
                const s = this.sample;
                const index = s.ring.add(input.index).readU16();
                if (index >= input.capacity) throw new Error('invalid native input history index');
                const current = s.ring.add(input.current).readU16();
                const last = s.ring.readU16();
                const entry = s.ring.add(input.inputs + index * 2).readU16();
                const held = s.ring.add(input.held + index * 2).readU16();
                if (current !== s.incoming || last !== s.previous || entry !== current || held === 0)
                    throw new Error('native input history disagrees with call');
                send({kind: 'input',slot: s.slot,counter: s.counter,incoming: s.incoming,
                    previous: s.previous,current,last,entry,held,index,thread: s.thread,
                    injected: gate !== null && gate.executing});
            } catch (error) { send({kind: 'error',phase: 'input-return',message: String(error)}); }
        }
    });
    inputHooks.push(writerListener);
    if (!p.gate) return;
    const ingress = Process.mainModule.base.add(input.ingress_rva);
    const ingressListener = Interceptor.attach(ingress, function() {
        const g = gate;
        try {
            const slot = this.context.ebp.toUInt32();
            const root = Process.mainModule.base.add(p.state.engine_global_rva).readPointer();
            if (slot > 1 || !this.context.edi.equals(root.add(4 + input.ring_field + slot * input.stride)))
                throw new Error('native input player/receiver mismatch');
            // Original instructions push ESI into history and subsequently record it.
            if (g !== null && g.executing && !g.resumed) this.context.esi = ptr(g.inputs[slot]);
            pendingInputs.set(this.threadId, {slot, incoming: this.context.esi.toUInt32() & 0xffff});
        } catch (error) {
            if (g !== null) g.resumed = true;
            send({kind: 'error',phase: 'input-ingress',message: String(error)});
        }
    });
    inputHooks.push(ingressListener);
}

function removeInputHooks() {
    for (const h of inputHooks) h.detach();
    inputHooks = []; pendingInputs.clear(); Interceptor.flush();
}

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
                this.capture = null;
                try {
                    const table = args[0].readPointer();
                    const method = methods.find(c => table.add(c.slot * 4).readPointer().equals(target));
                    if (!method) return;
                    this.device = args[0].toString(); this.method = method.method;
                    this.stopping = stopRequested;
                    if (this.stopping) { this.valid = true; return; }
                    const root = Process.mainModule.base.add(config.state.engine_global_rva).readPointer();
                    this.counter = root.add(4 + config.candidate.counter_field).readU32();
                    this.device = args[0].toString(); this.method = method.method; this.valid = true;
                    if (config.trace_draws && this.method === 'Present' && gate !== null && !gate.resumed) {
                        if (drawTrace === null) installDrawTrace(args[0]);
                        if (config.suppress_draws && drawFilter === null) installDrawFilter(args[0], config.suppress_draws);
                        drawInterval(args[0], this.counter, true);
                    }
                    if (config.capture && this.method === 'Present' && gate !== null && !gate.resumed && !gate.executing) {
                        if (renderCapture.counter !== this.counter) {
                            renderCapture.counter = this.counter; renderCapture.presentations = 0;
                        }
                        // Default third presentation, or explicitly requested settling samples; no delay acceptance.
                        ++renderCapture.presentations;
                        if (config.layer && config.layer.settle) {
                            if (pendingLayer!==null) {
                                this.capture=captureBackBuffer(args[0],root,this.counter);
                                this.capture.metadata.request_index=(this.counter-gate.initialCounter)>>>0;
                            }
                        } else if ((config.layer ? config.layer.presentations.includes(renderCapture.presentations) : renderCapture.presentations === (config.capture_screen_stages?1:3)) && renderCapture.attempts < 8 &&
                            (!config.layer || (gate.initialCounter !== null && config.layer.capture_steps.includes((this.counter - gate.initialCounter) >>> 0)))) {
                            ++renderCapture.attempts;
                            this.capture = captureBackBuffer(args[0], root, this.counter);
                            if(config.capture_screen_stages)this.capture.metadata.diagnostic_pipeline=true;
                            if (config.layer) this.capture.metadata.diagnostic_settling = config.layer.presentations.length > 1;
                            if (config.layer) this.capture.metadata.request_index = (this.counter - gate.initialCounter) >>> 0;
                        }
                    }
                } catch (error) { send({kind: 'error',phase: 'present',message: String(error)}); }
            },
            onLeave(result) {
                if (this.valid && this.stopping) {
                    try {
                        if (this.method === 'EndScene' && config.layer && meshLayer !== null) releaseLayer();
                        if (this.method === 'Present' && (!config.layer || meshLayer === null)) stopReceipt = finishStop();
                    } catch (error) { send({kind: 'error',phase: 'renderer-stop',message: String(error)}); }
                    return;
                }
                if (this.valid && this.method === 'EndScene' && result.toInt32() === 0 && config.layer && meshLayer !== null) {
                    try {
                        if (layerStopping) releaseLayer();
                        else finishMeshLayer(ptr(this.device));
                    } catch (error) { send({kind: 'error',phase: 'layer-end',message: String(error)}); }
                }
                if (this.valid) send({kind: 'present',counter: this.counter,device: this.device,
                    method: this.method,target: target.toString(),thread: this.threadId,hresult: result.toInt32(),wall_ms: Date.now()});
                if (this.capture && result.toInt32() === 0) {
                    this.capture.metadata.thread=this.threadId;this.capture.metadata.hresult=0;
                    if (config.layer && config.layer.settle) {
                        try {finishSettledPair(this.capture);}
                        catch (error) {send({kind:'error',phase:'layer-settling',message:String(error)});}
                    } else send(this.capture.metadata,this.capture.data);
                }
                if (this.valid && this.method === 'Present' && config.trace_draws)
                    drawInterval(ptr(this.device), this.counter, false, result.toInt32());
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
        requested_inputs: executed && gate !== null && config.input ? gate.inputs : null,
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
    gate = {target, root, credits: 0, pending: false, deadline: Date.now() + 8000, resumed: false, timer: null,
        executing: false, inputs: [0, 0], initialCounter: null};
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
        if (g.initialCounter === null) g.initialCounter = s.before;
        if (execute) {
            g.credits = 0; g.executing = true;
            try { original(object); } finally { g.executing = false; }
        }
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
            Interceptor.revert(target); removeInputHooks(); removeDrawFilter(); Interceptor.flush(); gate = null;
            send({kind: 'error',phase: 'watchdog',message: 'hard gate lifetime expired; hook removed'});
        }
    }, 12000);
    return {installed: true, thiscall_oracle: true, mutation: 'bounded native update gate', lifetime_seconds: 12, render};
}

function finishStop() {
    const skipped = drawFilter === null ? 0 : drawFilter.skipped;
    removeDrawFilter();
    removeInputHooks();
    for (const h of renderHooks) h.listener.detach();
    Interceptor.flush();
    const renderRestored = renderHooks.every(h => hex(bytes(h.target, 32)) === h.before);
    const renderTargets = renderHooks.map(h => ({address: h.target.toUInt32(), before: h.before}));
    renderHooks = []; drawTrace = null;
    if (listener) { listener.detach(); listener = null; Interceptor.flush(); }
    // Resume ordinary native updates after graphics/input hooks have been removed.
    if (gate) {
        clearTimeout(gate.timer);
        Interceptor.revert(gate.target); Interceptor.flush(); gate = null;
    }
    stopRequested = false;
    return {detached: true, samples: sequence, render_code_restored: renderRestored, render_targets: renderTargets,
        diagnostic_mesh_draws_skipped: skipped};
}

rpc.exports = {
    start(p) {
        if (listener || gate) throw new Error('already observing');
        if (p.capture && !p.gate) throw new Error('render capture requires a controlled source gate');
        if (p.trace_draws && !p.gate) throw new Error('draw trace requires a controlled source gate');
        if (p.capture_passes && !p.trace_draws) throw new Error('render-pass capture requires a draw trace');
        if (p.suppress_draws && !p.trace_draws) throw new Error('mesh suppression requires a draw trace');
        if (p.inspect_mesh_shaders && !p.suppress_draws) throw new Error('mesh shader inspection requires buffer identity');
        if (p.layer && (!p.suppress_draws || p.inspect_mesh_shaders)) throw new Error('private layer requires exclusive buffer identity');
        renderCapture = {attempts: 0, counter: null, presentations: 0};
        drawTrace = null;
        const module = Process.mainModule;
        if (Process.arch !== 'ia32' || Process.pointerSize !== 4 || Process.id !== p.state.pid ||
            !module.base.equals(ptr(p.state.module_base)) || module.size !== p.image_size ||
            module.name.toLowerCase() !== 'guiltygearxrd.exe') throw new Error('source session mismatch');
        const target = module.base.add(p.candidate.rva);
        const actual = hex(bytes(target, p.candidate.code_size));
        if (actual !== p.candidate.function_hex) throw new Error('native function bytes changed');
        config = p;
        if (p.input) installInput(p);
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
    step(inputs) {
        if (gate === null || gate.resumed || gate.pending || gate.credits !== 0)
            throw new Error('gate unavailable or step already pending');
        if (!Array.isArray(inputs) || inputs.length !== 2 || inputs.some(x => !Number.isInteger(x) || x < 0 || x > 0x3ff))
            throw new Error('invalid core input masks');
        if (!config.input && inputs.some(x => x !== 0)) throw new Error('native input ingress is not installed');
        gate.deadline = Date.now() + 8000;
        gate.inputs = inputs.slice();
        gate.pending = true; gate.credits = 1;
        return {accepted: true};
    },
    stop() {
        if (stopReceipt !== null) return stopReceipt;
        if (renderHooks.length) {
            stopRequested = true;
            if (config.layer) layerStopping = true;
            return {pending_renderer_stop: true,
                render_targets: renderHooks.map(h => ({address:h.target.toUInt32(),before:h.before}))};
        }
        stopReceipt = finishStop(); return stopReceipt;
    }
};
