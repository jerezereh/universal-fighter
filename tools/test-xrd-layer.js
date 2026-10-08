// Authored device state verifies private replay cleanup; no game/shader assets required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function fixture(failure = null, alpha = false, colorProduct = false, projection = false) {
    const calls = [], releases = [];
    const pointer = name => ({name, isNull: () => name === 'null', toString: () => name,equals:p=>p.name===name});
    const zero = pointer('null'), target = pointer('target'), shader = pointer('source-shader');
    const privateTarget = pointer('private-target'), privateShader = pointer('private-shader'), block = pointer('block');
    const depth=pointer('depth'),privateDepth=pointer('private-depth');let boundDepth=depth;
    let vertexConstants=new Float32Array(256*4);vertexConstants[13*4+3]=1;
    function allocation(size=256) {
        const values = new Map();
        const out={pointer: zero, values,data:new Uint8Array(size),writePointer(p) {this.pointer=p;}, readPointer() {return this.pointer;},
            writeU32(n) {values.set(0,n);}, readU32() {return values.get(0);}, writeByteArray(a) {this.data.set(a);},
            add(offset) {return {get data(){return out.data.slice(offset);},readU32:()=>values.get(offset),
                writeU32:n=>values.set(offset,n),readFloat:()=>new DataView(out.data.buffer,out.data.byteOffset).getFloat32(offset,true),
                writeFloat:n=>{values.set(offset,n);new DataView(out.data.buffer,out.data.byteOffset).setFloat32(offset,n,true);}};}};
        return out;
    }
    let states = new Map([[14,1],[15,alpha?1:0],[19,9],[20,3],[23,2],[27,colorProduct?1:0],[52,1],[168,7],
        [171,1],[206,0],[207,5],[208,6],[209,1],[7,1],[22,2]]);
    let boundTarget = target, boundShader = shader, constants = 'original-constants', saved;
    const viewport = 'original-viewport';
    const root = {add:()=>({readU32:()=>9,readPointer:()=>({add:()=>({readS32:()=>0})})})};
    const context = vm.createContext({Memory:{alloc:allocation}, ptr:()=>zero, Date, Map,
        Process:{mainModule:{base:{add:()=>({readPointer:()=>root})}}},
        config:{state:{engine_global_rva:0,fields:{slots:0,facing:0}},candidate:{counter_field:0},
            suppress_draws:{parts:{body:{index_buffer:'i',vertex_buffer:'v'}}},layer:{target:'target',capture_steps:[0,1,2,3],presentations:[3],programs:{
            'source-shader':{original_hex:'01020304',variant_hex:'0102030405060708'}}}},
        gate:{resumed:false,executing:false,deadline:Date.now()+8000,initialCounter:9},renderCapture:{counter:9,presentations:2},
        bytes:(address,n)=>address.data.slice(0,n),hex:array=>Buffer.from(array).toString('hex'),
        succeeded:(hr,name)=>{if(hr<0) throw Error(name+' failed');}});
    context.com = (object, slot) => (...args) => {
        calls.push([object.name||'device',slot]);
        if (slot===2) {releases.push(object.name);if(failure==='release-'+object.name) throw Error('release failure');return 0;}
        if (object===block && slot===5) {
            states=new Map(saved.states);boundShader=saved.shader;constants=saved.constants;vertexConstants=saved.vertex;return 0;
        }
        if (object===target && slot===12) {
            for (const [offset,n] of [[16,0],[24,2],[28,2]]) args[1].values.set(offset,n);return 0;
        }
        if(object===depth && slot===12) {args[1].writeU32(75);return 0;}
        if (object===shader && slot===4) {
            args[2].writeU32(4);if(!args[1].isNull?.()) args[1].data=[1,2,3,4];return 0;
        }
        if (failure===slot) return -1;
        switch(slot) {
            case 58: args[2].writeU32(states.get(args[1]));break;
            case 110: args[2].data=Buffer.from(constants);break;
            case 38: if(args[1]!==0) return 0x88760866|0;args[2].writePointer(boundTarget);break;
            case 108: args[1].writePointer(boundShader);break;
            case 48: args[1].data=Buffer.from(viewport);break;
            case 59: saved={states:new Map(states),shader:boundShader,constants,vertex:vertexConstants.slice()};args[2].writePointer(block);break;
            case 28: args[7].writePointer(privateTarget);break;
            case 106: args[2].writePointer(privateShader);break;
            case 37: if(args[1]===0) boundTarget=args[2];break;
            case 57: states.set(args[1],args[2]);break;
            case 109: constants='private-constants';break;
            case 107: boundShader=args[1];break;
            case 29: args[7].writePointer(privateDepth);break;
            case 40: args[1].writePointer(boundDepth);break;
            case 39: boundDepth=args[1];break;
            case 95: args[2].data=new Uint8Array(vertexConstants.slice(args[1]*4,(args[1]+args[3])*4).buffer);break;
            case 94: vertexConstants.set(new Float32Array(args[2].data.buffer),args[1]*4);break;
        }
        return 0;
    };
    context.device=pointer('device');context.d={currentTarget:'target',pixelShader:'source-shader',vertexShader:'vertex-shader',indexBuffer:'i',vertexBuffer:'v'};
    if(projection) context.config.layer.projection={width:640,height:768,pivot:[320,700],pixels_per_world_unit:2,
        programs:{'vertex-shader':{projection:1,ortho:7,local_to_world:10,original_hex:'01020304'}}};
    context.original=()=>{assert.equal(boundTarget,privateTarget);assert.equal(boundShader,privateShader);
        assert.equal(states.get(14),projection&&!colorProduct?1:0);assert.equal(states.get(52),0);
        if(projection){assert.equal(boundDepth,privateDepth);assert.notDeepEqual(vertexConstants,saved.vertex);}
        if(failure==='draw') return -1;return 0;};
    vm.runInContext(fs.readFileSync(__dirname+'/xrd-sign-layer.js','utf8'),context);
    if(projection) {
        context.vertexProgram=()=>({shader:'vertex-shader',code:Uint8Array.from([1,2,3,4])});
        vm.runInContext('bodyAnchor={counter:9,presentation:3,origin:[0,0,0,1],source_facing_left:false}',context);
    }
    return {context,calls,releases,run:()=>vm.runInContext('replayMeshDraw(device,original,[4,0,0,3,0,1],d)',context),
        release:()=>vm.runInContext('releaseLayer()',context),
        check:()=>{assert.equal(boundTarget,target);assert.equal(boundShader,shader);assert.equal(constants,'original-constants');
            assert.equal(states.get(14),1);assert.equal(states.get(52),1);
            assert.equal(states.get(206),0);assert.equal(states.get(207),5);assert.equal(states.get(208),6);
            assert.equal(context.d.pixelShader,'source-shader');assert.equal(context.d.currentTarget,'target');
            assert.equal(boundDepth,depth);if(saved)assert.deepEqual(vertexConstants,saved.vertex);
            assert.equal(vm.runInContext('layerDrawing',context),false);}};
}
const normal=fixture();normal.run();normal.check();
assert.equal(vm.runInContext('meshLayer.draws',normal.context),1);
normal.release();assert.deepEqual(normal.releases,['target','source-shader','block','private-shader','private-target']);
for(const failure of [59,28,106,37,47,43,57,109,107,'draw']) {
    const f=fixture(failure);assert.throws(f.run,/failed/);f.check();f.release();
    assert.ok(f.releases.includes('target') && f.releases.includes('source-shader'));
    if(failure!==59) assert.ok(f.releases.includes('block'));
    assert.equal(vm.runInContext('meshLayer',f.context),null);
}
const releaseFailure=fixture('release-private-shader');releaseFailure.run();
assert.throws(releaseFailure.release,/release failure/);assert.ok(releaseFailure.releases.includes('private-target'));
const alpha=fixture(null,true);alpha.context.send=()=>{};alpha.run();alpha.check();
assert.equal(vm.runInContext('layerSkipped',alpha.context),1);
assert.equal(alpha.calls.some(([,slot])=>slot===28),false);
const product=fixture(null,false,true);product.run();product.check();product.release();
assert.equal(vm.runInContext('layerColorBlends',product.context),1);
const stale=fixture();stale.context.renderCapture.counter=8;stale.run();assert.equal(stale.calls.length,0);
const duplicate=fixture();vm.runInContext("layerCapturedSteps.add('0:3')",duplicate.context);duplicate.run();
assert.equal(duplicate.calls.length,0);
console.log('Private replay state restoration, opaque guard, draw failures and independent resource release passed.');
const normalized=fixture(null,false,false,true);normalized.run();normalized.check();normalized.release();
assert.ok(normalized.releases.includes('private-depth'));
for(const failure of [29,40,94,95,47,43,107,'draw']) {
    const f=fixture(failure,false,false,true);assert.throws(f.run,/failed/);f.check();f.release();
}
console.log('Private projection/depth ownership and failure restoration passed.');
const rowFixture=fixture();rowFixture.context.p={width:640,height:768,pivot:[320,700],pixels_per_world_unit:2};
const rows=vm.runInContext('projectionRows([123,-540,-106,1],false,p)',rowFixture.context);
function project(world,m) {return [0,1,2,3].map(j=>world.reduce((n,v,i)=>n+v*m[i*4+j],0));}
const clip=project([123,-540,-106,1],rows.matrix);
assert.ok(Math.abs((1-clip[1]/clip[3])*384-700)<1e-9);assert.equal(clip[0],0);
const reflected=vm.runInContext('projectionRows([123,-540,-106,1],true,p)',rowFixture.context);
assert.ok(project([133,-540,-106,1],reflected.matrix)[0]<0);

function readiness() {
    const f=fixture(),sent=[];f.context.send=(m,data)=>{if(m.kind!=='layer-readiness')sent.push(m);};
    f.context.Process.getModuleByName=()=>({enumerateExports:()=>[{name:'RtlCompareMemory',address:1}]});
    f.context.NativeFunction=function(address,result,args,options) {
        assert.equal(options.abi,'stdcall');
        return (a,b,n)=>{let i=0;while(i<n && a.data[i]===b.data[i])++i;return i;};
    };
    return {sent,run(p,pixel=1,origin=0,counter=9){
        const data=Uint8Array.from([77,pixel,2,3,255]).buffer;
        f.context.testLayer={metadata:{kind:'render-layer',counter,request_index:0,presentation_index:p,
            width:1,height:1,state_size:1,replayed_draws:13,source_render_origin:[origin,0,0,1],
            source_facing_left:false},data};
        f.context.testScene={metadata:{kind:'render',counter,request_index:0,presentation_index:p},data};
        vm.runInContext('pendingLayer=testLayer;finishSettledPair(testScene)',f.context);
    }};
}
const ready=readiness();ready.run(3);assert.equal(ready.sent.length,0);ready.run(4);
assert.equal(ready.sent.filter(m=>m.kind!=='layer-readiness').length,4);
assert.deepEqual(Array.from(ready.sent.find(m=>m.kind==='render-layer').settled_pair),[3,4]);
const drift=readiness();drift.run(3);drift.run(4,2);assert.equal(drift.sent.length,0);
drift.run(5,2,1);assert.equal(drift.sent.length,4);
const stalePair=readiness();stalePair.run(3);stalePair.run(4,1,0,10);assert.equal(stalePair.sent.length,0);
const exhausted=readiness();exhausted.run(23);assert.throws(()=>exhausted.run(24,2),/did not settle/);
console.log('Projection pivot/reflection and bounded consecutive native-pixel readiness passed.');
