// Getter/disassembler failures release each acquired reference independently.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function fixture(failure=null) {
    const calls=[],messages=[],zero={isNull:()=>true};
    const shader={name:'shader',isNull:()=>false,toString:()=> 'shader'};
    const assembly={name:'assembly',isNull:()=>false};
    const text={readUtf8String:()=> 'vs_3_0\nmov o0,v0\n'};
    const allocation=()=>({pointer:zero,data:new Uint8Array(4096),n:0,
        writePointer(p){this.pointer=p;},readPointer(){return this.pointer;},writeU32(n){this.n=n;},readU32(){return this.n;}});
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
        if(slot===95 || slot===110)return failure==='constants'?-1:0;
        if(slot===58){if(failure==='state')return -1;args[2].writeU32(0);return 0;}
        if(slot===69){if(failure==='sampler')return -1;args[3].writeU32(0);return 0;}
        throw Error('unexpected method');
    };
    context.device={};context.d={indexBuffer:'i',vertexBuffer:'v',pixelShader:'shader',currentTarget:'target',screenShaders:new Set()};context.viewport=allocation();
    vm.runInContext(fs.readFileSync(__dirname+'/xrd-sign-layer.js','utf8'),context);
    vm.runInContext('meshLayer={};filter={vertices:new Set()};',context);
    return {calls,messages,run:()=>vm.runInContext('inspectLayerTransform(device,d,10,viewport)',context),
        inspect:()=>vm.runInContext('inspectMeshVertexShader(device,d,filter)',context),
        screen:()=>vm.runInContext('inspectScreenShader(device,d)',context)};
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
const screen=fixture();screen.screen();screen.screen();
assert.equal(screen.messages.length,1);assert.equal(screen.messages[0].kind,'screen-shader');
assert.equal(screen.messages[0].constants_hex.length,224*16*2);
assert.equal(screen.messages[0].samplers.length,16);assert.equal(screen.messages[0].samplers[0].texture,null);
assert.deepEqual(screen.calls,['assembly','shader']);
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
