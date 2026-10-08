// Development-only opaque mesh/color-product replay. No source targets retained.
let meshLayer = null;
let layerDrawing = false;
let layerCaptures = 0;
let layerDraws = 0;
let layerStopping = false;
let layerFailed = false;
let layerSkipped = 0;
let layerColorBlends = 0;
const layerSkipSeen = new Set();
const layerCapturedSteps = new Set();

function releaseLayer() {
    if (meshLayer === null) return;
    const current = meshLayer; meshLayer = null;
    let failure = null;
    for (const resource of [...current.shaders.values(), current.target]) {
        try { com(resource, 2, 'uint', [])(resource); }
        catch (error) { failure = error; }
    }
    if (failure) throw failure;
}

function renderState(device, id) {
    const output = Memory.alloc(4);
    succeeded(com(device, 58, 'int', ['uint','pointer'])(device, id, output), 'GetRenderState');
    return output.readU32();
}

function createLayer(device, counter, sourceTarget) {
    const desc = Memory.alloc(32), output = Memory.alloc(4); output.writePointer(ptr(0));
    succeeded(com(sourceTarget, 12, 'int', ['pointer'])(sourceTarget, desc), 'GetDesc');
    const width = desc.add(24).readU32(), height = desc.add(28).readU32();
    if (width < 1 || height < 1 || width > 2048 || height > 2048 || desc.add(16).readU32() !== 0)
        throw new Error('unsupported private target dimensions/multisampling');
    succeeded(com(device, 28, 'int', ['uint','uint','uint','uint','uint','uint','pointer','pointer'])(
        device, width, height, 21, 0, 0, 0, output, ptr(0)), 'CreateRenderTarget');
    meshLayer = {target: output.readPointer(), counter, shaders: new Map(), draws: 0, cleared: false, state_verified: true};
}

function layerShader(device, sourceShader, program) {
    const id = sourceShader.toString();
    if (meshLayer.shaders.has(id)) return meshLayer.shaders.get(id);
    const size = Memory.alloc(4); size.writeU32(0);
    succeeded(com(sourceShader, 4, 'int', ['pointer','pointer'])(sourceShader, ptr(0), size), 'GetFunction size');
    if (size.readU32() * 2 !== program.original_hex.length) throw new Error('layer shader size drift');
    const data = Memory.alloc(size.readU32());
    succeeded(com(sourceShader, 4, 'int', ['pointer','pointer'])(sourceShader, data, size), 'GetFunction');
    if (hex(bytes(data, size.readU32())) !== program.original_hex) throw new Error('layer shader bytes drift');
    const variant = Memory.alloc(program.variant_hex.length / 2);
    variant.writeByteArray(program.variant_hex.match(/../g).map(x => parseInt(x, 16)));
    const output = Memory.alloc(4); output.writePointer(ptr(0));
    succeeded(com(device, 106, 'int', ['pointer','pointer'])(device, variant, output), 'CreatePixelShader');
    const shader = output.readPointer(); meshLayer.shaders.set(id, shader); return shader;
}

function inspectLayerTransform(device,d,counter,viewport) {
    if (!config.layer.inspect_transforms || meshLayer.transform_captured ||
        d.indexBuffer !== config.suppress_draws.parts.body.index_buffer ||
        d.vertexBuffer !== config.suppress_draws.parts.body.vertex_buffer) return;
    const output = Memory.alloc(4); output.writePointer(ptr(0));
    let shader = ptr(0), assembly = ptr(0);
    try {
        succeeded(com(device,93,'int',['pointer'])(device,output),'GetVertexShader');
        shader=output.readPointer();
        if (shader.isNull()) throw new Error('missing body vertex shader');
        const size=Memory.alloc(4);size.writeU32(0);
        succeeded(com(shader,4,'int',['pointer','pointer'])(shader,ptr(0),size),'vertex GetFunction size');
        const length=size.readU32();
        if (length<8 || length>65536 || length%4) throw new Error('invalid vertex program bounds');
        const code=Memory.alloc(length);
        succeeded(com(shader,4,'int',['pointer','pointer'])(shader,code,size),'vertex GetFunction');
        if (size.readU32()!==length) throw new Error('vertex program size drift');
        const constants=Memory.alloc(4096);
        succeeded(com(device,95,'int',['uint','pointer','uint'])(device,0,constants,256),'GetVertexShaderConstantF');
        const sdk=Process.getModuleByName('d3dx9_43.dll');
        const entry=sdk.enumerateExports().find(e=>e.name==='D3DXDisassembleShader');
        if (!entry) throw new Error('missing native shader disassembler');
        const disassemble=new NativeFunction(entry.address,'int',['pointer','int','pointer','pointer'],
            {abi:'stdcall',exceptions:'propagate'});
        output.writePointer(ptr(0));
        succeeded(disassemble(code,0,ptr(0),output),'D3DXDisassembleShader');assembly=output.readPointer();
        const textSize=com(assembly,4,'uint',[])(assembly);
        if (textSize<1 || textSize>131072) throw new Error('unbounded vertex assembly');
        const textAddress=com(assembly,3,'pointer',[])(assembly);
        const data=new Uint8Array(length+4096);
        data.set(bytes(code,length));data.set(bytes(constants,4096),length);
        send({kind:'layer-transform',counter,request_index:(counter-gate.initialCounter)>>>0,
            presentation_index:renderCapture.presentations+1,shader:shader.toString(),bytecode_size:length,
            constants:256,assembly:textAddress.readUtf8String(textSize-1),
            viewport_hex:hex(bytes(viewport,24)),read_only:true},data.buffer);
        meshLayer.transform_captured=true;
    } finally {
        try {if(!assembly.isNull()) com(assembly,2,'uint',[])(assembly);}
        finally {if(!shader.isNull()) com(shader,2,'uint',[])(shader);}
    }
}

function replayMeshDraw(device, original, values, d) {
    const g = gate, p = config.layer;
    if (layerDrawing || layerFailed || layerStopping || g === null || g.resumed || g.executing || Date.now() > g.deadline || layerCaptures >= p.capture_steps.length * p.presentations.length ||
        d.currentTarget !== p.target || !p.presentations.includes(renderCapture.presentations + 1) || !p.programs[d.pixelShader]) return;
    const root = Process.mainModule.base.add(config.state.engine_global_rva).readPointer();
    const counter = root.add(4 + config.candidate.counter_field).readU32();
    const requestIndex = (counter - g.initialCounter) >>> 0;
    if (g.initialCounter === null || renderCapture.counter !== counter ||
        !p.capture_steps.includes(requestIndex) || layerCapturedSteps.has(requestIndex + ':' + (renderCapture.presentations + 1))) return;
    let block = ptr(0), sourceShader = ptr(0);
    const targets = [], viewport = Memory.alloc(24);
    const before = [14,15,19,20,23,27,52,168,171,206,207,208,209].map(id => [id, renderState(device, id)]);
    const state = new Map(before);
    // A destination/source-color product uses no shader alpha in its RGB equation.
    // Alpha-tested/translucent materials still need their original coverage semantics.
    const colorProduct = state.get(27) === 1 && state.get(19) === 9 && state.get(20) === 3 && state.get(171) === 1;
    if (state.get(15) !== 0 || (state.get(27) !== 0 && !colorProduct)) {
        ++layerSkipped;
        const key = d.pixelShader + ':' + before.map(x => x.join('=')).join(',');
        if (!layerSkipSeen.has(key)) {
            layerSkipSeen.add(key);
            send({kind: 'mesh-layer-skipped', reason: 'alpha-tested/blended draw', shader: d.pixelShader,
                values, source_target: d.currentTarget, index_buffer: d.indexBuffer, vertex_buffer: d.vertexBuffer,
                render_states: [...before, ...[24,25].map(id => [id, renderState(device,id)])]});
        }
        return;
    }
    const constants = Memory.alloc(16);
    succeeded(com(device, 110, 'int', ['uint','pointer','uint'])(device, 223, constants, 1), 'GetPixelShaderConstantF');
    const oldPixel = d.pixelShader, oldTarget = d.currentTarget;
    layerDrawing = true;
    try {
        for (let index = 0; index < 4; ++index) {
            const output = Memory.alloc(4); output.writePointer(ptr(0));
            const hr = com(device, 38, 'int', ['uint','pointer'])(device, index, output);
            if (hr === 0) targets.push([index, output.readPointer()]);
            else if (hr === (0x88760866 | 0)) targets.push([index, ptr(0)]);
            else if (index === 0 || hr !== (0x8876086c | 0)) succeeded(hr, 'GetRenderTarget');
        }
        const shaderOut = Memory.alloc(4), blockOut = Memory.alloc(4);
        succeeded(com(device, 108, 'int', ['pointer'])(device, shaderOut), 'GetPixelShader'); sourceShader = shaderOut.readPointer();
        succeeded(com(device, 48, 'int', ['pointer'])(device, viewport), 'GetViewport');
        succeeded(com(device, 59, 'int', ['uint','pointer'])(device, 1, blockOut), 'CreateStateBlock'); block = blockOut.readPointer();
        if (meshLayer === null) createLayer(device, counter, targets[0][1]);
        if (meshLayer.counter !== counter) throw new Error('source advanced during private replay');
        inspectLayerTransform(device,d,counter,viewport);
        const shader = layerShader(device, sourceShader, p.programs[oldPixel]);
        for (const [index] of targets) if (index !== 0)
            succeeded(com(device, 37, 'int', ['uint','pointer'])(device, index, ptr(0)), 'disable extra target');
        succeeded(com(device, 37, 'int', ['uint','pointer'])(device, 0, meshLayer.target), 'private target');
        succeeded(com(device, 47, 'int', ['pointer'])(device, viewport), 'private viewport');
        if (!meshLayer.cleared) {
            succeeded(com(device, 43, 'int', ['uint','pointer','uint','uint','float','uint'])(device, 0, ptr(0), 1, 0, 1, 0), 'private clear');
            meshLayer.cleared = true;
        }
        for (const [id, value] of [[14,0],[23,4],[27,state.get(27)],[52,0],[168,15],[206,1],[207,1],[208,2],[209,1]])
            succeeded(com(device, 57, 'int', ['uint','uint'])(device, id, value), 'private render state');
        // ZERO/ONE separate-alpha blending preserves opaque coverage beneath a color-product overlay.
        const one = Memory.alloc(16); for (let i = 0; i < 4; ++i) one.add(i * 4).writeFloat(1);
        succeeded(com(device, 109, 'int', ['uint','pointer','uint'])(device, 223, one, 1), 'private alpha constant');
        succeeded(com(device, 107, 'int', ['pointer'])(device, shader), 'private shader');
        succeeded(original(device, ...values), 'private mesh draw');
        ++meshLayer.draws; ++layerDraws;
        if (colorProduct) ++layerColorBlends;
    } finally {
        let failure = null;
        for (const [index, target] of targets) {
            try { succeeded(com(device, 37, 'int', ['uint','pointer'])(device, index, target), 'restore source target'); }
            catch (error) { failure = error; }
        }
        try { if (!block.isNull()) succeeded(com(block, 5, 'int', [])(block), 'restore source state block'); }
        catch (error) { failure = error; }
        for (const resource of [...targets.map(t => t[1]), sourceShader, block]) {
            try { if (!resource.isNull()) com(resource, 2, 'uint', [])(resource); }
            catch (error) { failure = error; }
        }
        d.pixelShader = oldPixel; d.currentTarget = oldTarget; layerDrawing = false;
        if (failure) throw failure;
    }
    const restored = Memory.alloc(16), restoredViewport = Memory.alloc(24);
    succeeded(com(device, 110, 'int', ['uint','pointer','uint'])(device, 223, restored, 1), 'verify alpha constant');
    succeeded(com(device, 48, 'int', ['pointer'])(device, restoredViewport), 'verify viewport');
    if (hex(bytes(constants, 16)) !== hex(bytes(restored, 16)) || hex(bytes(viewport, 24)) !== hex(bytes(restoredViewport, 24)) ||
        before.some(([id, value]) => renderState(device, id) !== value)) throw new Error('source graphics state did not restore');
}

function finishMeshLayer(device) {
    if (meshLayer === null) return;
    const current = meshLayer;
    try {
        const root = Process.mainModule.base.add(config.state.engine_global_rva).readPointer();
        const captured = captureBackBuffer(device, root, current.counter, false, current.target);
        send({...captured.metadata, kind: 'render-layer', presentation_index: renderCapture.presentations + 1,
            diagnostic_settling: config.layer.presentations.length > 1, native_coverage_verified: false,
            request_index: (current.counter - gate.initialCounter) >>> 0,
            replayed_draws: current.draws, skipped_draws_total: layerSkipped,
            color_product_draws_total: layerColorBlends,
            source_graphics_state_verified: current.state_verified, hresult: 0}, captured.data);
        ++layerCaptures;
        layerCapturedSteps.add(((current.counter - gate.initialCounter) >>> 0) + ':' + (renderCapture.presentations + 1));
    } finally { releaseLayer(); }
}
