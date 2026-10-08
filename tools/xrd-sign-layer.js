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
let bodyAnchor=null;
let pendingLayer=null, previousCandidate=null;
let pixelCompare=null, pixelScratch=null;
let privateViewOffset=null;

function layerPresentationSelected() {
    const p=config.layer, index=renderCapture.presentations+1;
    return p.settle ? index>=3 && index<=24 : p.presentations.includes(index);
}

function equalPixels(a,b) {
    if (a.metadata.width!==b.metadata.width || a.metadata.height!==b.metadata.height) return false;
    const aa=new Uint8Array(a.data,a.metadata.state_size),bb=new Uint8Array(b.data,b.metadata.state_size);
    if (aa.length!==bb.length) return false;
    if (aa.length!==a.metadata.width*a.metadata.height*4 || aa.length>16*1024*1024)
        throw new Error('invalid pixel comparison bounds');
    if (pixelCompare===null) {
        const api=Process.getModuleByName('ntdll.dll').enumerateExports().find(e=>e.name==='RtlCompareMemory');
        if (!api) throw new Error('missing native byte comparator');
        pixelCompare=new NativeFunction(api.address,'uint',['pointer','pointer','uint'],{abi:'stdcall',exceptions:'propagate'});
        const left=Memory.alloc(4),right=Memory.alloc(4);
        left.writeByteArray([1,2,3,4]);right.writeByteArray([1,2,3,5]);
        if (pixelCompare(left,left,4)!==4 || pixelCompare(left,right,4)===4)
            throw new Error('native byte comparator failed self-check');
    }
    // Reuse two CPU buffers; QuickJS byte-by-byte loops consume the native lease budget.
    if (pixelScratch===null || pixelScratch.size!==aa.length)
        pixelScratch={size:aa.length,a:Memory.alloc(aa.length),b:Memory.alloc(aa.length)};
    pixelScratch.a.writeByteArray(aa);pixelScratch.b.writeByteArray(bb);
    return pixelCompare(pixelScratch.a,pixelScratch.b,aa.length)===aa.length;
}

function finishSettledPair(scene) {
    if (pendingLayer===null) return;
    const layer=pendingLayer;pendingLayer=null;
    if (scene.metadata.counter!==layer.metadata.counter || scene.metadata.presentation_index!==layer.metadata.presentation_index)
        throw new Error('unpaired settling candidate');
    const prior=previousCandidate;
    const pixelsMatch=prior!==null && equalPixels(prior.layer,layer);
    const ready=prior!==null && prior.layer.metadata.counter===layer.metadata.counter &&
        prior.layer.metadata.presentation_index+1===layer.metadata.presentation_index &&
        prior.layer.metadata.replayed_draws===layer.metadata.replayed_draws &&
        prior.layer.metadata.source_facing_left===layer.metadata.source_facing_left &&
        pixelsMatch;
    send({kind:'layer-readiness',counter:layer.metadata.counter,request_index:layer.metadata.request_index,
        presentation_index:layer.metadata.presentation_index,pixels_equal:pixelsMatch,
        source_render_origin:layer.metadata.source_render_origin,ready});
    if (ready) {
        const pair=[prior.layer.metadata.presentation_index,layer.metadata.presentation_index];
        for(const candidate of [prior,{layer,scene}]) {
            const proof={settled_pair:pair,identical_native_pixels:true,frame_readiness_candidate:true,diagnostic_settling:true};
            send({...candidate.layer.metadata,...proof},candidate.layer.data);
            send({...candidate.scene.metadata,...proof},candidate.scene.data);
        }
        layerCaptures+=2;layerCapturedSteps.add(layer.metadata.request_index+':settled');previousCandidate=null;
    } else {
        previousCandidate={layer,scene};
        if(layer.metadata.presentation_index>=24) {
            send({...layer.metadata,frame_readiness_candidate:false,settle_failed:true},layer.data);
            send({...scene.metadata,diagnostic_settling:true,frame_readiness_candidate:false,settle_failed:true},scene.data);
            throw new Error('native layer did not settle within bounded presentations');
        }
    }
}

function releaseLayer() {
    if (meshLayer === null) return;
    const current = meshLayer; meshLayer = null;
    let failure = null;
    for (const resource of [...current.shaders.values(), current.target, ...(current.depth ? [current.depth] : [])]) {
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

function createLayer(device, counter, sourceTarget, sourceDepth = null) {
    const desc = Memory.alloc(32), output = Memory.alloc(4); output.writePointer(ptr(0));
    succeeded(com(sourceTarget, 12, 'int', ['pointer'])(sourceTarget, desc), 'GetDesc');
    const projection=config.layer.projection;
    const width = projection ? projection.width : desc.add(24).readU32();
    const height = projection ? projection.height : desc.add(28).readU32();
    if (width < 1 || height < 1 || width > 2048 || height > 2048 || desc.add(16).readU32() !== 0)
        throw new Error('unsupported private target dimensions/multisampling');
    succeeded(com(device, 28, 'int', ['uint','uint','uint','uint','uint','uint','pointer','pointer'])(
        device, width, height, 21, 0, 0, 0, output, ptr(0)), 'CreateRenderTarget');
    meshLayer = {target: output.readPointer(), counter, shaders: new Map(), draws: 0, cleared: false, state_verified: true};
    if (projection) {
        if (sourceDepth===null || sourceDepth.isNull()) throw new Error('missing native depth description');
        succeeded(com(sourceDepth,12,'int',['pointer'])(sourceDepth,desc),'depth GetDesc');
        output.writePointer(ptr(0));
        succeeded(com(device,29,'int',['uint','uint','uint','uint','uint','int','pointer','pointer'])(
            device,width,height,desc.readU32(),0,0,1,output,ptr(0)),'CreateDepthStencilSurface');
        meshLayer.depth=output.readPointer();meshLayer.vertex_seen=new Set();
    }
}

function projectionRows(origin,facingLeft,p) {
    if (origin.length!==4 || origin.some(v=>!Number.isFinite(v)||Math.abs(v)>1e6) || origin[3]!==1)
        throw new Error('invalid native render origin');
    const sx=2*p.pixels_per_world_unit/p.width*(facingLeft?-1:1), sy=2*p.pixels_per_world_unit/p.height;
    const px=2*p.pivot[0]/p.width-1, py=1-2*p.pivot[1]/p.height, w=512, dz=-.001;
    // Keep clip W large enough for the original outline's literal clip-depth bias.
    return {matrix:[sx*w,0,0,0, 0,0,dz*w,0, 0,sy*w,0,0,
        (px-origin[0]*sx)*w,(py-origin[2]*sy)*w,(.5-origin[1]*dz)*w,w],
        ortho:[sx,0,0,px-origin[0]*sx]};
}

function observeBodyAnchor(device,d) {
    const p=config.layer.projection;
    if (!p || layerFailed || !layerPresentationSelected()) return;
    const body=config.suppress_draws.parts.body;
    if (d.indexBuffer!==body.index_buffer || d.vertexBuffer!==body.vertex_buffer) return;
    const root=Process.mainModule.base.add(config.state.engine_global_rva).readPointer();
    const counter=root.add(4+config.candidate.counter_field).readU32(), presentation=renderCapture.presentations+1;
    if (renderCapture.counter!==counter || !config.layer.capture_steps.includes((counter-gate.initialCounter)>>>0) ||
        config.layer.settle && layerCapturedSteps.has(((counter-gate.initialCounter)>>>0)+':settled') ||
        bodyAnchor && bodyAnchor.counter===counter && bodyAnchor.presentation===presentation) return;
    const binding=p.origins[d.vertexShader];
    if (!binding) throw new Error('unverified native body anchor program');
    const program=vertexProgram(device);
    if (program.shader!==d.vertexShader || hex(program.code)!==binding.original_hex) throw new Error('body anchor vertex drift');
    const data=Memory.alloc(16);
    succeeded(com(device,95,'int',['uint','pointer','uint'])(device,binding.local_to_world+3,data,1),'body render origin');
    const origin=Array.from({length:4},(_,i)=>data.add(i*4).readFloat());
    const actor=root.add(config.state.fields.slots).readPointer(),facing=actor.add(config.state.fields.facing).readS32();
    if (facing!==0 && facing!==1) throw new Error('invalid native projection facing');
    projectionRows(origin,facing===1,p);
    bodyAnchor={counter,presentation,origin,source_facing_left:facing===1};
}

function privateProjection(device,d) {
    const p=config.layer.projection;
    if (!p) return null;
    const binding=p.programs[d.vertexShader];
    if (!binding) throw new Error('unverified native vertex projection');
    if (!meshLayer.vertex_seen.has(d.vertexShader)) {
        const program=vertexProgram(device);
        if (program.shader!==d.vertexShader || hex(program.code)!==binding.original_hex)
            throw new Error('native vertex program drift');
        meshLayer.vertex_seen.add(d.vertexShader);
    }
    const constants=Memory.alloc(4096);
    succeeded(com(device,95,'int',['uint','pointer','uint'])(device,0,constants,256),'projection GetVertexShaderConstantF');
    const before=[binding.projection,binding.ortho].map((r,i)=>[r,i===0?4:1,hex(bytes(constants.add(r*16),i===0?64:16))]);
    if (binding.pre_view_translation!==undefined && d.indexBuffer===config.suppress_draws.parts.body.index_buffer &&
            d.vertexBuffer===config.suppress_draws.parts.body.vertex_buffer) {
        const translated=Array.from({length:3},(_,i)=>constants.add((binding.local_to_world+3)*16+i*4).readFloat());
        const preView=Array.from({length:3},(_,i)=>constants.add(binding.pre_view_translation*16+i*4).readFloat());
        if ([...translated,...preView].some(v=>!Number.isFinite(v)||Math.abs(v)>1e6)) throw new Error('invalid native body world observation');
        meshLayer.absolute_body_origin=translated.map((v,i)=>v-preView[i]);
        meshLayer.pre_view_translation=preView;
    }
    if (!meshLayer.origin) {
        if (!bodyAnchor || bodyAnchor.counter!==meshLayer.counter || bodyAnchor.presentation!==renderCapture.presentations+1)
            throw new Error('missing current body render anchor');
        meshLayer.origin=bodyAnchor.origin;meshLayer.source_facing_left=bodyAnchor.source_facing_left;
    }
    const rows=projectionRows(meshLayer.origin,meshLayer.source_facing_left,p);
    for (const [register,values] of [[binding.projection,rows.matrix],[binding.ortho,rows.ortho]]) {
        const data=Memory.alloc(values.length*4);
        values.forEach((v,i)=>data.add(i*4).writeFloat(v));
        succeeded(com(device,94,'int',['uint','pointer','uint'])(device,register,data,values.length/4),'private vertex projection');
    }
    let cameraRegister=null, cameraPosition=null;
    if (binding.camera_world!==undefined) {
        if (binding.pre_view_translation===undefined) throw new Error('camera world binding lacks pre-view translation');
        const pre=Array.from({length:3},(_,i)=>constants.add(binding.pre_view_translation*16+i*4).readFloat());
        const bodyWorld=meshLayer.origin.slice(0,3).map((v,i)=>v-pre[i]);
        const camera=Array.from({length:3},(_,i)=>constants.add(binding.camera_world*16+i*4).readFloat());
        if (privateViewOffset===null) {
            privateViewOffset=[0,camera[1]-bodyWorld[1],camera[2]-bodyWorld[2]];
            if (privateViewOffset.some(v=>!Number.isFinite(v)||Math.abs(v)>10000) || privateViewOffset[1]<=1)
                throw new Error('invalid native private camera baseline');
        }
        cameraRegister=binding.camera_world;cameraPosition=bodyWorld.map((v,i)=>v+privateViewOffset[i]);
    } else if (binding.camera_position_vs!==undefined && privateViewOffset!==null) {
        cameraRegister=binding.camera_position_vs;
        cameraPosition=meshLayer.origin.slice(0,3).map((v,i)=>v+privateViewOffset[i]);
    }
    if(cameraRegister!==null) {
        before.push([cameraRegister,1,hex(bytes(constants.add(cameraRegister*16),16))]);
        const data=Memory.alloc(16);data.writeByteArray(bytes(constants.add(cameraRegister*16),16));
        cameraPosition.forEach((v,i)=>data.add(i*4).writeFloat(v));
        succeeded(com(device,94,'int',['uint','pointer','uint'])(device,cameraRegister,data,1),'private camera constant');
    }
    return before;
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

function shaderProgram(device,kind='vertex') {
    if (!['vertex','pixel'].includes(kind)) throw new Error('invalid shader kind');
    const output = Memory.alloc(4); output.writePointer(ptr(0));
    let shader = ptr(0), assembly = ptr(0);
    try {
        succeeded(com(device,kind==='vertex'?93:108,'int',['pointer'])(device,output),'Get '+kind+' shader');
        shader=output.readPointer();
        if (shader.isNull()) throw new Error('missing '+kind+' shader');
        const size=Memory.alloc(4);size.writeU32(0);
        succeeded(com(shader,4,'int',['pointer','pointer'])(shader,ptr(0),size),'vertex GetFunction size');
        const length=size.readU32();
        if (length<8 || length>65536 || length%4) throw new Error('invalid '+kind+' program bounds');
        const code=Memory.alloc(length);
        succeeded(com(shader,4,'int',['pointer','pointer'])(shader,code,size),'vertex GetFunction');
        if (size.readU32()!==length) throw new Error(kind+' program size drift');
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
        return {shader:shader.toString(),code:bytes(code,length),assembly:textAddress.readUtf8String(textSize-1)};
    } finally {
        try {if(!assembly.isNull()) com(assembly,2,'uint',[])(assembly);}
        finally {if(!shader.isNull()) com(shader,2,'uint',[])(shader);}
    }
}

function vertexProgram(device) { return shaderProgram(device); }

function textureSurface(device,slot) {
    const output=Memory.alloc(4);output.writePointer(ptr(0));
    let texture=ptr(0),surface=ptr(0);
    try {
        succeeded(com(device,64,'int',['uint','pointer'])(device,slot,output),'GetTexture');
        texture=output.readPointer();
        if(texture.isNull() || com(texture,10,'uint',[])(texture)!==3) throw new Error('LUT requires a native 2D texture');
        output.writePointer(ptr(0));
        succeeded(com(texture,18,'int',['uint','pointer'])(texture,0,output),'GetSurfaceLevel');surface=output.readPointer();
        const desc=Memory.alloc(32);
        succeeded(com(surface,12,'int',['pointer'])(surface,desc),'LUT GetDesc');
        return {slot,texture:texture.toString(),surface:surface.toString(),format:desc.readU32(),
            width:desc.add(24).readU32(),height:desc.add(28).readU32()};
    } finally {
        try {if(!surface.isNull())com(surface,2,'uint',[])(surface);}
        finally {if(!texture.isNull())com(texture,2,'uint',[])(texture);}
    }
}

function inspectScreenShader(device,d) {
    const key=d.currentTarget+':'+d.pixelShader;
    if (d.screenShaders.has(key)) return;
    if (d.screenShaders.size>=32) throw new Error('screen shader observation limit');
    const program=shaderProgram(device,'pixel'), constants=Memory.alloc(224*16);
    if (program.shader!==d.pixelShader) throw new Error('screen shader binding drift');
    succeeded(com(device,110,'int',['uint','pointer','uint'])(device,0,constants,224),'GetPixelShaderConstantF');
    const srgb=Memory.alloc(4),samplers=[];
    succeeded(com(device,58,'int',['uint','pointer'])(device,194,srgb),'GetRenderState sRGB');
    for(let slot=0;slot<16;++slot) {
        const state=Memory.alloc(4);
        succeeded(com(device,69,'int',['uint','uint','pointer'])(device,slot,11,state),'GetSamplerState sRGB');
        samplers.push({slot,texture:d['texture'+slot]??null,srgb:state.readU32()});
    }
    const lutBindings=[...program.assembly.matchAll(/^\/\/\s+ColorGradingLUT\s+s(\d+)\s+(\d+)\s*$/gm)];
    if(lutBindings.length>1 || lutBindings.some(m=>Number(m[1])>=16 || Number(m[2])!==1))
        throw new Error('ambiguous LUT sampler binding');
    const lut=lutBindings.length?textureSurface(device,Number(lutBindings[0][1])):null;
    if(lut!==null && samplers[lut.slot].texture!==lut.texture) throw new Error('LUT texture binding drift');
    d.screenShaders.add(key);
    send({kind:'screen-shader',shader:program.shader,code_size:program.code.length,assembly:program.assembly,
        source_target:d.currentTarget,constants_hex:hex(bytes(constants,224*16)),srgb_write:srgb.readU32(),
        samplers,lut_source:lut,counter:d.counter,trace_frame:d.frames+1,trace_event:d.events.length,read_only:true},program.code.buffer);
}

function inspectMeshVertexShader(device,d,filter) {
    if (filter.vertices.has(d.vertexShader)) return;
    if (filter.vertices.size>=32) throw new Error('vertex shader limit');
    const program=vertexProgram(device);
    d.vertexShader=program.shader;
    if (filter.vertices.has(program.shader)) return;
    filter.vertices.add(program.shader);
    send({kind:'mesh-vertex-shader',shader:program.shader,code_size:program.code.length,
        assembly:program.assembly,source_target:d.currentTarget,read_only:true},program.code.buffer);
}

function inspectLayerTransform(device,d,counter,viewport) {
    if (!config.layer.inspect_transforms || meshLayer.transform_captured ||
        d.indexBuffer !== config.suppress_draws.parts.body.index_buffer ||
        d.vertexBuffer !== config.suppress_draws.parts.body.vertex_buffer) return;
    const program=vertexProgram(device), constants=Memory.alloc(4096);
    succeeded(com(device,95,'int',['uint','pointer','uint'])(device,0,constants,256),'GetVertexShaderConstantF');
    const data=new Uint8Array(program.code.length+4096);
    data.set(program.code);data.set(bytes(constants,4096),program.code.length);
    send({kind:'layer-transform',counter,request_index:(counter-gate.initialCounter)>>>0,
        presentation_index:renderCapture.presentations+1,shader:program.shader,bytecode_size:program.code.length,
        constants:256,assembly:program.assembly,viewport_hex:hex(bytes(viewport,24)),read_only:true},data.buffer);
    meshLayer.transform_captured=true;
}

function replayMeshDraw(device, original, values, d) {
    const g = gate, p = config.layer;
    if (layerDrawing || layerFailed || layerStopping || g === null || g.resumed || g.executing || Date.now() > g.deadline || layerCaptures >= p.capture_steps.length * (p.settle?2:p.presentations.length) ||
        d.currentTarget !== p.target || !layerPresentationSelected() || !p.programs[d.pixelShader]) return;
    const root = Process.mainModule.base.add(config.state.engine_global_rva).readPointer();
    const counter = root.add(4 + config.candidate.counter_field).readU32();
    const requestIndex = (counter - g.initialCounter) >>> 0;
    if (g.initialCounter === null || renderCapture.counter !== counter ||
        !p.capture_steps.includes(requestIndex) || layerCapturedSteps.has(requestIndex + ':' + (p.settle?'settled':renderCapture.presentations+1))) return;
    let block = ptr(0), sourceShader = ptr(0), sourceDepth = ptr(0), vertexBefore = null;
    const targets = [], viewport = Memory.alloc(24);
    const before = [...[14,15,19,20,23,27,52,168,171,206,207,208,209],...(p.projection?[7,22]:[])].map(id => [id, renderState(device, id)]);
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
        if (p.projection) {
            const output=Memory.alloc(4);output.writePointer(ptr(0));
            succeeded(com(device,40,'int',['pointer'])(device,output),'GetDepthStencilSurface');sourceDepth=output.readPointer();
        }
        if (meshLayer === null) createLayer(device, counter, targets[0][1],sourceDepth);
        if (meshLayer.counter !== counter) throw new Error('source advanced during private replay');
        inspectLayerTransform(device,d,counter,viewport);
        const shader = layerShader(device, sourceShader, p.programs[oldPixel]);
        vertexBefore=privateProjection(device,d);
        for (const [index] of targets) if (index !== 0)
            succeeded(com(device, 37, 'int', ['uint','pointer'])(device, index, ptr(0)), 'disable extra target');
        succeeded(com(device, 37, 'int', ['uint','pointer'])(device, 0, meshLayer.target), 'private target');
        let privateViewport=viewport;
        if (p.projection) {
            succeeded(com(device,39,'int',['pointer'])(device,meshLayer.depth),'private depth');
            privateViewport=Memory.alloc(24);privateViewport.writeByteArray(bytes(viewport,24));
            privateViewport.writeU32(0);privateViewport.add(4).writeU32(0);
            privateViewport.add(8).writeU32(p.projection.width);privateViewport.add(12).writeU32(p.projection.height);
            privateViewport.add(16).writeFloat(0);privateViewport.add(20).writeFloat(1);
        }
        succeeded(com(device, 47, 'int', ['pointer'])(device, privateViewport), 'private viewport');
        if (!meshLayer.cleared) {
            succeeded(com(device, 43, 'int', ['uint','pointer','uint','uint','float','uint'])(device, 0, ptr(0), p.projection?3:1, 0, 1, 0), 'private clear');
            meshLayer.cleared = true;
        }
        for (const [id, value] of [[14,0],[23,4],[27,state.get(27)],[52,0],[168,15],[206,1],[207,1],[208,2],[209,1]])
            succeeded(com(device, 57, 'int', ['uint','uint'])(device, id, value), 'private render state');
        if (p.projection) {
            const cull=state.get(22), mirrored=meshLayer.source_facing_left && (cull===2 || cull===3);
            for (const [id,value] of [[7,1],[14,colorProduct?0:1],[22,mirrored?5-cull:cull]])
                succeeded(com(device,57,'int',['uint','uint'])(device,id,value),'private depth/culling state');
        }
        // ZERO/ONE separate-alpha blending preserves opaque coverage beneath a color-product overlay.
        const one = Memory.alloc(16); for (let i = 0; i < 4; ++i) one.add(i * 4).writeFloat(1);
        succeeded(com(device, 109, 'int', ['uint','pointer','uint'])(device, 223, one, 1), 'private alpha constant');
        succeeded(com(device, 107, 'int', ['pointer'])(device, shader), 'private shader');
        succeeded(original(device, ...values), 'private mesh draw');
        ++meshLayer.draws; ++layerDraws;
        if (colorProduct) ++layerColorBlends;
    } finally {
        let failure = null;
        if (p.projection && !sourceDepth.isNull()) {
            try { succeeded(com(device,39,'int',['pointer'])(device,sourceDepth),'restore source depth'); }
            catch (error) { failure=error; }
        }
        for (const [index, target] of targets) {
            try { succeeded(com(device, 37, 'int', ['uint','pointer'])(device, index, target), 'restore source target'); }
            catch (error) { failure = error; }
        }
        try { if (!block.isNull()) succeeded(com(block, 5, 'int', [])(block), 'restore source state block'); }
        catch (error) { failure = error; }
        for (const resource of [...targets.map(t => t[1]), sourceShader, sourceDepth, block]) {
            try { if (!resource.isNull()) com(resource, 2, 'uint', [])(resource); }
            catch (error) { failure = error; }
        }
        d.pixelShader = oldPixel; d.currentTarget = oldTarget; layerDrawing = false;
        if (failure) throw failure;
    }
    const restored = Memory.alloc(16), restoredViewport = Memory.alloc(24);
    if (vertexBefore) for (const [register,count,original] of vertexBefore) {
        const current=Memory.alloc(count*16);
        succeeded(com(device,95,'int',['uint','pointer','uint'])(device,register,current,count),'verify vertex constants');
        if (hex(bytes(current,count*16))!==original) throw new Error('source vertex constants did not restore');
    }
    if (p.projection) {
        const current=Memory.alloc(4);current.writePointer(ptr(0));
        succeeded(com(device,40,'int',['pointer'])(device,current),'verify source depth');
        const depth=current.readPointer();
        try { if (!depth.equals(sourceDepth)) throw new Error('source depth did not restore'); }
        finally { if(!depth.isNull()) com(depth,2,'uint',[])(depth); }
    }
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
        const metadata={...captured.metadata, kind: 'render-layer', presentation_index: renderCapture.presentations + 1,
            diagnostic_settling: config.layer.settle || config.layer.presentations.length > 1, native_coverage_verified: false,
            request_index: (current.counter - gate.initialCounter) >>> 0,
            replayed_draws: current.draws, skipped_draws_total: layerSkipped,
            color_product_draws_total: layerColorBlends,
            source_graphics_state_verified: current.state_verified, hresult: 0,
            ...(config.layer.projection ? {normalized_projection:true,projection_pivot:config.layer.projection.pivot,
                pixels_per_world_unit:config.layer.projection.pixels_per_world_unit,
                source_render_origin:current.origin,source_facing_left:current.source_facing_left,
                native_absolute_body_origin:current.absolute_body_origin,
                native_pre_view_translation:current.pre_view_translation,
                private_view_offset:privateViewOffset,
                canonical_right_facing:true,pivot_verified:false,units_verified:false} : {})};
        if (config.layer.settle) pendingLayer={metadata,data:captured.data};
        else {
            send(metadata,captured.data);++layerCaptures;
            layerCapturedSteps.add(((current.counter-gate.initialCounter)>>>0)+':'+(renderCapture.presentations+1));
        }
    } finally { releaseLayer(); }
}
