// Getter/disassembler failures release each acquired reference independently.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function fixture(failure=null) {
    const calls=[],messages=[],zero={isNull:()=>true};
    const shader={name:'shader',isNull:()=>false,toString:()=> 'shader'};
    const assembly={name:'assembly',isNull:()=>false};
    const texture={name:'texture',isNull:()=>false,toString:()=> '0x3000'};
    const surface={name:'surface',isNull:()=>false,toString:()=> '0x4000'};
    const declaration={name:'declaration',isNull:()=>false};
    const text={readUtf8String:()=> 'vs_3_0\nmov o0,v0\n'};
    const allocation=()=>({pointer:zero,data:new Uint8Array(4096),n:0,
        writePointer(p){this.pointer=p;},readPointer(){return this.pointer;},writeU32(n){this.n=n;},readU32(){return this.n;},
        add(offset){return {readU32:()=>offset===24?256:16};}});
    const context=vm.createContext({Map,Memory:{alloc:allocation},ptr:()=>zero,Uint8Array,
        config:{layer:{inspect_transforms:true},suppress_draws:{parts:{body:{index_buffer:'i',vertex_buffer:'v'}}}},
        gate:{initialCounter:10},renderCapture:{presentations:2},
        Process:{getModuleByName:()=>({enumerateExports:()=>[{name:'D3DXDisassembleShader',address:1}]})},
        bytes:(p,n)=>p.data.slice(0,n),hex:data=>Buffer.from(data).toString('hex'),send:(m,data)=>messages.push(m),
        succeeded:(hr,name)=>{if(hr<0)throw Error(name+' failed');}});
    context.NativeFunction=function(){return (code,color,comments,output)=>{
        if(failure==='disassemble')return -1;output.writePointer(assembly);return 0;};};
    context.com=(object,slot)=>(...args)=>{
        if(slot===2){calls.push(object.name);if(failure==='release-'+object.name)throw Error('release failed');return 0;}
        if(object===shader && slot===4){args[2].writeU32(8);return failure==='program'?-1:0;}
        if(object===assembly && slot===4)return failure==='text-size'?200000:20;
        if(object===assembly && slot===3)return text;
        if(slot===93 || slot===108){if(failure==='shader')return -1;args[1].writePointer(shader);return 0;}
        if(slot===88){if(failure==='declaration')return -1;args[1].writePointer(declaration);return 0;}
        if(object===declaration && slot===4){args[2].writeU32(failure==='declaration-size'?100:3);return failure==='elements'?-1:0;}
        if(slot===95 || slot===110)return failure==='constants'?-1:0;
        if(slot===58){if(failure==='state')return -1;args[2].writeU32(0);return 0;}
        if(slot===68){if(failure==='sampler')return -1;args[3].writeU32(0);return 0;}
        if(slot===64){if(failure==='texture')return -1;args[2].writePointer(texture);return 0;}
        if(object===texture && slot===10)return failure==='type'?5:3;
        if(object===texture && slot===18){if(failure==='surface')return -1;args[2].writePointer(surface);return 0;}
        if(object===surface && slot===12){args[1].writeU32(21);return failure==='description'?-1:0;}
        throw Error('unexpected method');
    };
    context.device={};context.d={indexBuffer:'i',vertexBuffer:'v',pixelShader:'shader',currentTarget:'target',screenShaders:new Set(),lutShaders:new Set(),colorBoundarySteps:new Set(),counter:12,frames:0,events:[]};context.viewport=allocation();
    vm.runInContext(fs.readFileSync(__dirname+'/xrd-sign-layer.js','utf8'),context);
    vm.runInContext('meshLayer={};filter={vertices:new Set()};',context);
    return {calls,messages,run:()=>vm.runInContext('inspectLayerTransform(device,d,10,viewport)',context),
        inspect:()=>vm.runInContext('inspectMeshVertexShader(device,d,filter)',context),
        screen:()=>vm.runInContext('inspectScreenShader(device,d)',context),
        texture:()=>vm.runInContext('textureSurface(device,2)',context),context,
        boundary:()=>vm.runInContext('observeLayerColorBoundary(d)',context)};
}
const normal=fixture();normal.run();assert.deepEqual(normal.calls,['assembly','shader']);
assert.equal(normal.messages[0].read_only,true);normal.run();assert.equal(normal.messages.length,1);
const inventory=fixture();inventory.inspect();inventory.inspect();
assert.equal(inventory.messages.length,1);assert.equal(inventory.messages[0].kind,'mesh-vertex-shader');
assert.deepEqual(inventory.calls,['assembly','shader']);
for(const failure of ['shader','program','constants','disassemble','text-size','release-assembly']) {
    const f=fixture(failure);assert.throws(f.run,/failed|unbounded/);
    if(failure!=='shader') assert.ok(f.calls.includes('shader'));
    if(['text-size','release-assembly'].includes(failure))assert.ok(f.calls.includes('assembly'));
}
console.log('Read-only transform observation, one body sample and independent shader/disassembly cleanup passed.');
const screenVertex=fixture();vm.runInContext('inspectScreenVertex(device)',screenVertex.context);
assert.deepEqual(screenVertex.calls,['assembly','shader','shader']);
for(const failure of ['shader','program','constants','disassemble','release-assembly']) {
    const f=fixture(failure);assert.throws(()=>vm.runInContext('inspectScreenVertex(device)',f.context),/failed/);
    if(failure!=='shader')assert.ok(f.calls.includes('shader'));
}
function quadInput(f) {
    const numbers=[0,4,0,4,2,0,101,0,32];
    f.context.quadArgs=numbers.map(n=>({toUInt32:()=>n,data:new Uint8Array(256)}));
    return vm.runInContext('inspectScreenInput(device,quadArgs)',f.context);
}
const quad=fixture();assert.equal(quadInput(quad).vertices_hex.length,256);
assert.deepEqual(quad.calls,['declaration']);
for(const failure of ['declaration','declaration-size','elements']) {
    const f=fixture(failure);assert.throws(()=>quadInput(f),/failed|unbounded/);
    if(failure!=='declaration')assert.ok(f.calls.includes('declaration'));
}
const screen=fixture();screen.screen();screen.screen();
assert.equal(screen.messages.length,1);assert.equal(screen.messages[0].kind,'screen-shader');
assert.equal(screen.messages[0].constants_hex.length,224*16*2);
assert.equal(screen.messages[0].samplers.length,16);assert.equal(screen.messages[0].samplers[0].texture,null);
assert.deepEqual(screen.calls,['assembly','shader']);
const post=fixture();quadInput(post);
vm.runInContext('config.capture_screen_stages=true;d.screenStagesStarted=true;inspectScreenShader(device,d,"DrawIndexedPrimitiveUP",quadArgs)',post.context);
assert.ok(post.messages[0].vertex_program);
assert.equal(post.messages[0].vertex_input.stride,32);
assert.equal(post.messages[0].lut_source,null);
const beforePost=fixture();
vm.runInContext('config.capture_screen_stages=true;inspectScreenShader(device,d)',beforePost.context);
assert.equal(beforePost.messages[0].vertex_program,null);
const reused=fixture();reused.screen();
vm.runInContext('config.capture_screen_stages=true;d.screenStagesStarted=true;inspectScreenShader(device,d)',reused.context);
assert.equal(reused.messages.length,2);assert.ok(reused.messages[1].vertex_program);
vm.runInContext('d.screenStagesDone=true;d.currentTarget="unrelated-ui";inspectScreenShader(device,d)',reused.context);
assert.equal(reused.messages.length,2);
for(const failure of ['shader','program','constants','disassemble','text-size','release-assembly','state','sampler']) {
    const f=fixture(failure);assert.throws(f.screen,/failed|unbounded/);
    if(failure!=='shader')assert.ok(f.calls.includes('shader'));
}
const selection=vm.createContext({rpc:{exports:{}},Map});
vm.runInContext(fs.readFileSync(__dirname+'/xrd-sign-boundary.js','utf8'),selection);
for(const [method,values,expected] of [
    ['DrawPrimitive',[0,4,0,2],true],['DrawPrimitiveUP',[0,4,2,100],true],
    ['DrawIndexedPrimitiveUP',[0,4,0,4,2],true],['DrawPrimitiveUP',[0,4,3,2],false],
    ['DrawIndexedPrimitive',[0,4,0,4,2],false]]) {
    selection.method=method;selection.args=values.map(n=>({toUInt32:()=>n}));
    assert.equal(vm.runInContext('twoTriangleDraw(method,args)',selection),expected);
}
console.log('Screen program getters, constants/sRGB observations, COM failures and two-triangle selection passed.');
const linked=fixture();const description=linked.texture();
assert.equal(description.texture,'0x3000');assert.equal(description.surface,'0x4000');assert.equal(description.width,256);
assert.deepEqual(linked.calls,['surface','texture']);
for(const failure of ['texture','type','surface','description','release-surface']) {
    const f=fixture(failure);assert.throws(f.texture,/failed|texture/);
    if(failure!=='texture')assert.ok(f.calls.includes('texture'));
    if(['description','release-surface'].includes(failure))assert.ok(f.calls.includes('surface'));
}
console.log('Native LUT texture/surface association and independent reference cleanup passed.');
const point=fixture();
vm.runInContext(`config.state={engine_global_rva:0};config.candidate={counter_field:0};config.layer.hdr=true;
    gate={initialCounter:10,resumed:false,executing:false};renderCapture={counter:10,presentations:2};
    Process.mainModule={base:{add:()=>({readPointer:()=>({add:()=>({readU32:()=>10})})})}};
    meshLayer={counter:10,draws:13};d.lutShaders.add('shader');`,point.context);
point.boundary();point.boundary();
assert.equal(point.messages.length,1);assert.equal(point.messages[0].private_draws,13);
assert.equal(point.messages[0].native_grading_replayed,false);assert.equal(point.messages[0].request_index,0);
vm.runInContext('meshLayer=null',point.context);point.boundary();assert.equal(point.messages.length,1);
vm.runInContext('meshLayer={counter:11,draws:13};renderCapture.counter=11',point.context);
assert.throws(point.boundary,/source advanced/);
console.log('Private layer lifetime/color-phase identity, deduplication and changed counter rejection passed.');
