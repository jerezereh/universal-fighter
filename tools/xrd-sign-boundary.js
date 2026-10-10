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
let contactObserver = null;
let contactSamples = 0;
let dispatchObserver=null;
let dispatchSamples=0;
let dispatchReplacement=null;
let activeContact=null;
let contactCallObservers=[];
let contactCallSamples=0;
let contactCallUnsupported=[];
let externalPair=null;
let koTransition=null;


function applyExternalPair(p,index,thread) {
    const g=gate;
    if(g.externalPairs!==0)throw new Error('external pair replay');
    const actors=[0,1].map(i=>g.root.add(p.state.fields.slots+4*i).readPointer());
    if(actors.some(a=>a.isNull()) || actors[1].add(p.state.fields.hit_count).readS32()<=0)
        throw new Error('external pair requires an active native proxy normal');
    const before=actors.map(a=>a.add(p.state.scalar_fields.health_candidate).readS32());
    const isolation=p.ko_isolation;
    const fatalBefore=isolation?g.root.add(isolation.field).readU32():null;
    if(isolation && (hex(bytes(Process.mainModule.base.add(isolation.rva),9))!==isolation.before || fatalBefore&isolation.mask))
        throw new Error('fatal global witness/baseline changed');
    if(p.external_damage && before[0]<=p.external_damage)throw new Error('external damage experiment requires a nonfatal result');
    // Let native damage execute the fatal branch rather than merely publishing zero health.
    if(p.external_ko) {
        if(before[0]<=0)throw new Error('KO probe requires a living defender');
        actors[0].add(p.state.scalar_fields.health_candidate).writeS32(1);
    }
    g.externalApplying=true;
    try {if(!p.external_pair_control)externalPair(actors[1],actors[0],0);} finally {g.externalApplying=false;}
    const fatalHealth=p.external_ko?actors[0].add(p.state.scalar_fields.health_candidate).readS32():null;
    let isolated=false;
    if(isolation) {
        const flags=g.root.add(isolation.field),raised=flags.readU32();
        if(fatalHealth!==0 || (raised&isolation.mask)===0 || ((raised&~isolation.mask)>>>0)!==fatalBefore)
            throw new Error('native fatal branch did not match isolated global write');
        actors[0].add(p.state.scalar_fields.health_candidate).writeS32(1);
        flags.writeU32(raised&~isolation.mask);
        isolated=true;
    }
    if(p.external_guard_commit || p.external_ko) {
        const c=p.contact.dispatch.caller_result;
        const kind=actors[0].add(c.kind_field).readS32();
        if(hex(bytes(Process.mainModule.base.add(c.rva),10))!==c.before || (p.external_ko?![1,2,4,5].includes(kind):kind!==2))
            throw new Error('guard caller result witness changed');
        const flags=actors[0].add(c.pending_field);
        flags.writeU32(flags.readU32()|c.pending_mask);
    }
    if(p.external_damage)actors[0].add(p.state.scalar_fields.health_candidate).writeS32(before[0]-p.external_damage);
    g.externalPairs++;
    g.externalEvent={kind:'external-pair-result',request_index:index,counter:g.root.add(4+p.candidate.counter_field).readU32(),
        thread,attacker:1,defender:0,before,
        after:actors.map(a=>a.add(p.state.scalar_fields.health_candidate).readS32()),
        native_pair_called:!p.external_pair_control,
        caller_result_committed:p.external_guard_commit===true || p.external_ko===true,requested_ko:p.external_ko===true,
        native_fatal_health:fatalHealth,source_ko_isolated:isolated,
        native_reaction_requested:p.ko_transition?p.ko_transition.name:null,
        requested_damage:p.external_damage || null,hitstop_owner:p.external_host_stop?'host':'source',source_collision_suppressed:true};
}

function observeNativeContact(p) {
    const target=Process.mainModule.base.add(p.contact.rva);
    if(hex(bytes(target,32))!==p.contact.before)throw new Error('native contact entry changed');
    if(p.external_pair_step)externalPair=new NativeFunction(target,'void',['pointer','pointer','int'],{abi:'thiscall',exceptions:'propagate'});
    if(p.ko_transition) {
        const k=p.ko_transition,entry=Process.mainModule.base.add(k.rva),state=Process.mainModule.base.add(k.state_rva);
        if(hex(bytes(entry,32))!==k.before || state.readUtf8String(k.name.length)!==k.name || state.add(k.name.length).readU8()!==0)throw new Error('native reaction entry/name changed');
        koTransition=new NativeFunction(entry,'void',['pointer','pointer'],{abi:'thiscall',exceptions:'propagate'});
    }
    contactSamples=0;
    dispatchSamples=0;
    contactCallSamples=0;
    contactCallUnsupported=[];
    for(const c of p.contact.callees || []) {
        const entry=Process.mainModule.base.add(c.rva);
        if(hex(bytes(entry,32))!==c.before)throw new Error('native contact callee changed');
        const scalars=actors=>actors.map(a=>['health_candidate','hitstop_candidate'].map(k=>a.add(p.state.scalar_fields[k]).readS32()));
        let observer;
        try {observer=Interceptor.attach(entry,{
            onEnter(args) {
                this.call=null;
                const owner=activeContact;
                if(!owner || !gate || !gate.executing || this.threadId!==owner.thread)return;
                const returned=this.returnAddress.sub(Process.mainModule.base).toUInt32();
                if(!c.return_rvas.includes(returned))return;
                this.call={actors:owner.actors,rva:c.rva,return_rva:returned,thread:this.threadId,counter:owner.counter,
                    object_slot:owner.actors.findIndex(a=>a.equals(this.context.ecx)),before:scalars(owner.actors),
                    argument_words:[args[0].toUInt32(),args[1].toUInt32()],
                    argument_actor_slots:[args[0],args[1]].map(value=>owner.actors.findIndex(a=>a.equals(value)))};
            },
            onLeave() {
                if(!this.call)return;
                const value=this.call;contactCallSamples++;
                if(contactCallSamples<=256)send({kind:'native-contact-callee',rva:value.rva,return_rva:value.return_rva,
                    thread:value.thread,counter:value.counter,object_slot:value.object_slot,before:value.before,
                    after:scalars(value.actors),argument_words:value.argument_words,argument_actor_slots:value.argument_actor_slots,
                    argument_semantics_verified:false,original_called:true});
                else if(contactCallSamples===257)send({kind:'error',phase:'contact-callees',message:'native contact callee bound exceeded'});
            }
        });} catch(error) {
            if(!String(error).includes('unable to intercept function'))throw error;
            contactCallUnsupported.push({rva:c.rva,reason:String(error)});
            continue;
        }
        contactCallObservers.push({observer,entry,before:c.before});
    }
    if(p.contact.dispatch) {
        const d=p.contact.dispatch,entry=Process.mainModule.base.add(d.rva);
        if(hex(bytes(entry,32))!==d.before)throw new Error('native dispatch entry changed');
        if(d.owner) {
            const original=new NativeFunction(entry,'int',['pointer','int'],{abi:'thiscall',exceptions:'propagate'});
            dispatchReplacement=new NativeCallback(function(object,stage) {
                if(!gate || !gate.executing || gate.resumed)return original(object,stage);
                const root=Process.mainModule.base.add(p.state.engine_global_rva).readPointer();
                const returned=this.returnAddress.sub(Process.mainModule.base).toUInt32();
                if(!root.equals(gate.root) || !object.equals(root.add(4)) || !this.context.ecx.equals(object) ||
                        this.threadId!==d.owner.thread || stage<0 || stage>2 || returned!==d.owner.return_rvas[stage]) {
                    send({kind:'error',phase:'contact-suppress',message:'native dispatch owner changed; original called'});
                    return original(object,stage);
                }
                dispatchSamples++;
                if(dispatchSamples<=256)send({kind:'native-dispatch-observation',argument:stage,this_delta:4,
                    thread:this.threadId,return_rva:returned,counter:root.add(4+p.candidate.counter_field).readU32(),
                    result:0,original_called:false,suppressed:true});
                else if(dispatchSamples===257)send({kind:'error',phase:'contact-suppress',message:'suppression observation bound exceeded'});
                if((p.external_guard || p.external_ko) && stage===1 && gate.currentIndex===p.external_pair_step)applyExternalPair(p,gate.currentIndex,this.threadId);
                return 0;
            },'int',['pointer','int'],'thiscall');
            Interceptor.replace(entry,dispatchReplacement);
            dispatchObserver={detach(){Interceptor.revert(entry);}};
        } else dispatchObserver=Interceptor.attach(entry,{
            onEnter(args) {
                this.dispatch=null;
                if(!gate || !gate.executing || gate.resumed)return;
                const root=Process.mainModule.base.add(p.state.engine_global_rva).readPointer();
                if(!root.equals(gate.root))return;
                this.dispatch={kind:'native-dispatch-observation',argument:args[0].toInt32(),
                    this_delta:this.context.ecx.sub(root).toInt32(),thread:this.threadId,
                    return_rva:this.returnAddress.sub(Process.mainModule.base).toUInt32(),
                    counter:root.add(4+p.candidate.counter_field).readU32()};
            },
            onLeave(result) {
                if(!this.dispatch)return;
                dispatchSamples++;
                if(dispatchSamples<=256)send({...this.dispatch,result:result.toInt32(),original_called:true});
                else if(dispatchSamples===257)send({kind:'error',phase:'dispatch-observe',message:'dispatch observation bound exceeded'});
            }
        });
    }
    contactObserver=Interceptor.attach(target,{
        onEnter(args) {
            this.contact=null;
            if(!gate || !gate.executing || gate.resumed)return;
            try {
                const root=Process.mainModule.base.add(p.state.engine_global_rva).readPointer();
                if(!root.equals(gate.root))throw new Error('contact scene changed');
                const actors=[0,1].map(i=>root.add(p.state.fields.slots+4*i).readPointer());
                const attacker=actors.findIndex(a=>a.equals(this.context.ecx));
                const defender=actors.findIndex(a=>a.equals(args[0]));
                if(attacker<0 || defender<0 || attacker===defender)return;
                const health=()=>actors.map(a=>a.add(p.state.scalar_fields.health_candidate).readS32());
                this.contact={attacker,defender,argument:args[1].toInt32(),thread:this.threadId,
                    return_rva:this.returnAddress.sub(Process.mainModule.base).toUInt32(),
                    counter:root.add(4+p.candidate.counter_field).readU32(),before:health(),actors,
                    externally_requested:gate.externalApplying===true};
                if(activeContact!==null)throw new Error('nested native pair contact is unsupported');
                activeContact=this.contact;
            } catch(error) {send({kind:'error',phase:'contact-observe',message:String(error)});}
        },
        onLeave() {
            if(!this.contact)return;
            activeContact=null;
            const c=this.contact;contactSamples++;
            if(contactSamples<=256)send({kind:'native-contact-observation',attacker:c.attacker,defender:c.defender,
                argument:c.argument,thread:c.thread,return_rva:c.return_rva,counter:c.counter,before:c.before,
                after:c.actors.map(a=>a.add(p.state.scalar_fields.health_candidate).readS32()),original_called:true,externally_requested:c.externally_requested});
            else if(contactSamples===257)send({kind:'error',phase:'contact-observe',message:'contact observation bound exceeded'});
        }
    });
}

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
                        const input=inspectScreenInput(args[0],args);
                        const dev=args[0],signature=types.map(t=>t==='p'?'pointer':t==='i'?'int':'uint');
                        const values=types.map((t,i)=>t==='p'?args[i+1]:t==='i'?args[i+1].toInt32():args[i+1].toUInt32());
                        this.postReplay={device:dev,input,draw:vertices=>com(dev,slot,'int',signature)(dev,
                            ...values.map((v,i)=>i===6 && vertices?vertices:v))};
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
                    try {postColorLayer(this.postReplay.device,drawTrace,this.postReplay.draw,this.postReplay.input);}
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
                    if(root.isNull())return; // Offline menus can render without a battle engine.
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
                        if (config.streaming) assertLayerWindow();
                        if (config.layer && config.layer.settle) {
                            if (pendingLayer!==null) {
                                this.capture=config.streaming ? {metadata:{counter:this.counter,presentation_index:renderCapture.presentations}} : captureBackBuffer(args[0],root,this.counter);
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
                if (this.valid && (!config.reset_observation || gate===null || gate.resumed)) send({kind: 'present',counter: this.counter,device: this.device,
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
        const span = config.reaction_memory_bytes || 0x2600;
        const range = Process.findRangeByAddress(actor);
        if (!range || !range.protection.includes('r') || actor.add(span).compare(range.base.add(range.size)) > 0)
            throw new Error('actor snapshot exceeds readable memory range');
        const data = bytes(actor, span);
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

function ownedCreditReady(g) {
    return g.credits===1 && (!config.layer || meshLayer===null && pendingLayer===null);
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
        renewable: p.renewable === true,
        frameReady: null,
        lastCounter: null, heldState: null,
        ownsState: p.transactions || p.renewable && p.state.ownership_age_field!==undefined,
        executing: false, inputs: [0, 0], initialCounter: null,externalPairs:0,externalApplying:false};
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
            if (g.ownsState) assertTransactionHeld(g, s.before, transactionState(g.root));
        } catch (error) {
            g.resumed = true;
            send({kind: 'error',phase: 'gate',message: String(error) + '; original execution resumed',
                ...(error.ownership_changes?{ownership_changes:error.ownership_changes}:{})});
            original(object); return;
        }
        const execute = ownedCreditReady(g);
        if (g.initialCounter === null) g.initialCounter = s.before;
        if (execute) {
            g.credits = 0; g.executing = true;
            try {
                g.currentIndex=((s.before-g.initialCounter)>>>0)+1;
                original(object);
                const index=(object.add(p.candidate.counter_field).readU32()-g.initialCounter)>>>0;
                if(p.ko_transition && g.externalPairs===1 && index===p.external_pair_step+1)
                    koTransition(g.root.add(p.state.fields.slots).readPointer(),Process.mainModule.base.add(p.ko_transition.state_rva));
                if(!p.external_guard && !p.external_ko && p.external_pair_step && index===p.external_pair_step) {
                    applyExternalPair(p,index,this.threadId);
                }
                if(g.externalEvent) {send({...g.externalEvent,counter:object.add(p.candidate.counter_field).readU32()});g.externalEvent=null;}
                // Diagnostic only: host withholding credits owns freeze; native reaction may queue stop later.
                if(p.external_host_stop && g.externalPairs)for(let i=0;i<2;i++)
                    g.root.add(p.state.fields.slots+4*i).readPointer().add(p.state.scalar_fields.hitstop_candidate).writeS32(0);
            } finally { g.executing = false; }
        }
        try {
            const after=object.add(p.candidate.counter_field).readU32();
            if (g.ownsState) {
                const state=transactionState(g.root);
                if (after!==((s.before+(execute?1:0))>>>0) ||
                    g.heldState && state.some((v,i)=>v[0]!==g.heldState[i][0]))
                    throw new Error('transaction counter or fighter object changed');
                g.lastCounter=after;g.heldState=state;
            }
            publish(s, after, execute);
        } catch (error) {
            g.resumed = true;
            send({kind: 'error',phase: 'gate-snapshot',message: String(error)});
        } finally { if (execute) g.pending = false; }
    }, 'void', ['pointer'], 'thiscall');
    gate.replacement = replacement;
    Interceptor.replace(target, replacement);
    // A disconnected controller cannot leave this development gate installed indefinitely.
    armGateRemoval();
    return {installed: true, thiscall_oracle: true, mutation: 'native update gate', renewable: gate.renewable,
        lifetime_seconds: gate.renewable ? null : 12, lease_seconds: 8, render};
}

function transactionState(root) {
    const f=config.state.fields;
    return [0,1].map(i=>{
        const actor=root.add(f.slots+4*i).readPointer();
        if(actor.isNull())throw new Error('transaction fighter absent');
        const state=[actor.toString(),...['x','y','facing'].map(k=>actor.add(f[k]).readS32())];
        const age=config.state.ownership_age_field;
        if(age!==undefined) {
            if(!Number.isInteger(age) || age<0 || age>0x25fc || age%4)throw new Error('invalid ownership age field');
            state.push(actor.add(age).readS32());
        }
        return state;
    });
}

function assertTransactionHeld(g, counter, state) {
    if(g.heldState!==null && (state.length!==g.heldState.length || state.some((v,i)=>v.length!==g.heldState[i].length)))
        throw new Error('transaction state shape changed');
    const changes=[];
    if(g.lastCounter!==null && counter!==g.lastCounter)
        changes.push({field:'counter',before:g.lastCounter,after:counter});
    if(g.heldState!==null) state.forEach((fighter,i)=>fighter.forEach((value,j)=>{
        if(value!==g.heldState[i][j])changes.push({fighter:i,field:['actor','x','y','facing','age'][j],before:g.heldState[i][j],after:value});
    }));
    if(changes.length) {
        const error=new Error('transaction source changed outside owned update');
        error.ownership_changes=changes;throw error;
    }
}

function armGateRemoval() {
    clearTimeout(gate.timer);
    gate.timer = setTimeout(() => {
        if (gate !== null) {
            if (gate.renewable) {
                gate.resumed = true; gate.credits = 0;
                if (config.layer && meshLayer !== null) {
                    // COM resources belong to the render thread. Ordinary updates resume now;
                    // resource/hook teardown completes at the next EndScene/Present callback.
                    stopRequested = true; layerStopping = true;
                    send({kind:'error',phase:'watchdog',message:'gate cleanup deferred to renderer'});
                } else stopReceipt = finishStop();
            }
            else {
                Interceptor.revert(gate.target); removeInputHooks(); removeDrawFilter(); Interceptor.flush(); gate = null;
            }
            send({kind: 'error',phase: 'watchdog',message: 'hard gate lifetime expired; hook removed'});
        }
    }, 12000);
}

function verifyGateOwner(checkState=true) {
    try {
        const root=Process.mainModule.base.add(config.state.engine_global_rva).readPointer();
        if(!root.equals(gate.root))throw new Error('transaction scene changed');
        if(checkState)assertTransactionHeld(gate,root.add(4+config.candidate.counter_field).readU32(),transactionState(root));
    } catch(error) {
        gate.resumed=true;gate.credits=0;gate.frameReady=null;
        send({kind:'error',phase:'gate',message:String(error)+'; original execution resumed',
            ...(error.ownership_changes?{ownership_changes:error.ownership_changes}:{})});
        throw error;
    }
}

function finishStop() {
    let contactRestored=true;
    for(const c of contactCallObservers)c.observer.detach();
    Interceptor.flush();
    contactRestored=contactCallObservers.every(c=>hex(bytes(c.entry,32))===c.before);
    // Retain detached callback owners until script unload, like the native replacement.
    activeContact=null;
    if(dispatchObserver) {
        dispatchObserver.detach();dispatchObserver=null;Interceptor.flush();
        // Keep the native callback alive until script unload, including any retiring call.
        contactRestored=contactRestored && hex(bytes(Process.mainModule.base.add(config.contact.dispatch.rva),32))===config.contact.dispatch.before;
    }
    if(contactObserver) {
        contactObserver.detach();contactObserver=null;Interceptor.flush();
        contactRestored=contactRestored && hex(bytes(Process.mainModule.base.add(config.contact.rva),32))===config.contact.before;
    }
    if (config?.streaming) { pendingLayer=null; previousCandidate=null; pixelScratch=null; }
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
        diagnostic_mesh_draws_skipped: skipped,contact_observer_code_restored:contactRestored,contact_samples:contactSamples,dispatch_samples:dispatchSamples,contact_callee_samples:contactCallSamples,contact_callee_unsupported:contactCallUnsupported};
}

rpc.exports = {
    start(p) {
        if (listener || gate) throw new Error('already observing');
        if (p.reaction_memory_bytes !== undefined && (!Number.isInteger(p.reaction_memory_bytes) || p.reaction_memory_bytes < 0x2600 || p.reaction_memory_bytes > 0x10000 || p.reaction_memory_bytes % 4))
            throw new Error('invalid actor snapshot span');
        if (p.renewable !== undefined && typeof p.renewable !== 'boolean') throw new Error('invalid renewable mode');
        if (p.transactions !== undefined && typeof p.transactions !== 'boolean') throw new Error('invalid transaction mode');
        if (p.streaming !== undefined && typeof p.streaming !== 'boolean') throw new Error('invalid streaming mode');
        if (p.streaming && !p.transactions) throw new Error('streaming requires owned transactions');
        if (p.streaming && (p.capture_passes || p.capture_screen_stages || p.inspect_mesh_shaders || p.inspect_screen_shaders))
            throw new Error('streaming excludes inventory capture');
        if (p.transactions && (!p.renewable || !p.gate || !p.capture || !p.trace_draws || !p.suppress_draws ||
            !p.layer?.settle || !p.layer.projection || !p.streaming && p.layer.capture_steps.join(',') !== '0,1,2,3'))
            throw new Error('transaction experiment requires four consecutive normalized settled frames');
        if (p.renewable && !p.transactions && (!p.gate || p.capture || p.trace_draws || p.layer || p.suppress_draws))
            throw new Error('renewable control requires a gate without private rendering');
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
        if(p.contact)observeNativeContact(p);
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
    step(inputs, expectedCounter) {
        if (gate === null || gate.resumed || gate.pending || gate.credits !== 0)
            throw new Error('gate unavailable or step already pending');
        if (!Array.isArray(inputs) || inputs.length !== 2 || inputs.some(x => !Number.isInteger(x) || x < 0 || x > 0x3ff))
            throw new Error('invalid core input masks');
        if (!config.input && inputs.some(x => x !== 0)) throw new Error('native input ingress is not installed');
        if (Date.now() > gate.deadline) throw new Error('gate lease expired');
        if (config.transactions && (!Number.isInteger(expectedCounter) || expectedCounter < 0 || expectedCounter > 0xffffffff ||
            gate.frameReady === null || expectedCounter !== gate.frameReady ||
            !config.streaming && ((expectedCounter-gate.initialCounter)>>>0) >= 3))
            throw new Error('transaction frame not ready, stale or exhausted');
        if (gate.ownsState) verifyGateOwner();
        if (!gate.renewable) gate.deadline = Date.now() + 8000;
        gate.frameReady = null;
        if (config.streaming) { pendingLayer=null; previousCandidate=null; }
        gate.inputs = inputs.slice();
        gate.pending = true; gate.credits = 1;
        return {accepted: true};
    },
    heartbeat() {
        if (gate === null || !gate.renewable || gate.resumed || Date.now() > gate.deadline)
            throw new Error('renewable gate unavailable or expired');
        // Check scene identity even when updates stop; in-flight owned state may change.
        if(gate.ownsState)verifyGateOwner(!gate.pending && !gate.executing);
        gate.deadline = Date.now() + 8000;
        armGateRemoval();
        return {renewed: true, lease_seconds: 8,...(config.streaming ? {stream:{counter:gate.lastCounter,
            ready:gate.frameReady,pending:gate.pending,presentation:renderCapture.presentations,
            layer_failed:layerFailed,previous_counter:previousCandidate?.layer.metadata.counter??null}} : {})};
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
