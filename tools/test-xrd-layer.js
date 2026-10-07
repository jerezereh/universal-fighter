// Authored device state verifies private replay cleanup; no game/shader assets required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function fixture(failure = null, alpha = false, colorProduct = false) {
    const calls = [], releases = [];
    const pointer = name => ({name, isNull: () => name === 'null', toString: () => name});
    const zero = pointer('null'), target = pointer('target'), shader = pointer('source-shader');
    const privateTarget = pointer('private-target'), privateShader = pointer('private-shader'), block = pointer('block');
    function allocation() {
        const values = new Map();
        return {pointer: zero, values, writePointer(p) {this.pointer=p;}, readPointer() {return this.pointer;},
            writeU32(n) {values.set(0,n);}, readU32() {return values.get(0);}, writeByteArray(a) {this.data=a;},
            add(offset) {return {readU32:()=>values.get(offset),writeFloat:n=>values.set(offset,n)};}};
    }
    let states = new Map([[14,1],[15,alpha?1:0],[19,9],[20,3],[23,2],[27,colorProduct?1:0],[52,1],[168,7],
        [171,1],[206,0],[207,5],[208,6],[209,1]]);
    let boundTarget = target, boundShader = shader, constants = 'original-constants', saved;
    const viewport = 'original-viewport';
    const root = {add:()=>({readU32:()=>9})};
    const context = vm.createContext({Memory:{alloc:allocation}, ptr:()=>zero, Date, Map,
        Process:{mainModule:{base:{add:()=>({readPointer:()=>root})}}},
        config:{state:{engine_global_rva:0},candidate:{counter_field:0},layer:{target:'target',capture_steps:[0,1,2,3],programs:{
            'source-shader':{original_hex:'01020304',variant_hex:'0102030405060708'}}}},
        gate:{resumed:false,executing:false,deadline:Date.now()+8000,initialCounter:9},renderCapture:{counter:9,presentations:2},
        bytes:(address)=>address.data,hex:array=>Buffer.from(array).toString('hex'),
        succeeded:(hr,name)=>{if(hr<0) throw Error(name+' failed');}});
    context.com = (object, slot) => (...args) => {
        calls.push([object.name||'device',slot]);
        if (slot===2) {releases.push(object.name);if(failure==='release-'+object.name) throw Error('release failure');return 0;}
        if (object===block && slot===5) {
            states=new Map(saved.states);boundShader=saved.shader;constants=saved.constants;return 0;
        }
        if (object===target && slot===12) {
            for (const [offset,n] of [[16,0],[24,2],[28,2]]) args[1].values.set(offset,n);return 0;
        }
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
            case 59: saved={states:new Map(states),shader:boundShader,constants};args[2].writePointer(block);break;
            case 28: args[7].writePointer(privateTarget);break;
            case 106: args[2].writePointer(privateShader);break;
            case 37: if(args[1]===0) boundTarget=args[2];break;
            case 57: states.set(args[1],args[2]);break;
            case 109: constants='private-constants';break;
            case 107: boundShader=args[1];break;
        }
        return 0;
    };
    context.device=pointer('device');context.d={currentTarget:'target',pixelShader:'source-shader'};
    context.original=()=>{assert.equal(boundTarget,privateTarget);assert.equal(boundShader,privateShader);
        assert.equal(states.get(14),0);assert.equal(states.get(52),0);if(failure==='draw') return -1;return 0;};
    vm.runInContext(fs.readFileSync(__dirname+'/xrd-sign-layer.js','utf8'),context);
    return {context,calls,releases,run:()=>vm.runInContext('replayMeshDraw(device,original,[4,0,0,3,0,1],d)',context),
        release:()=>vm.runInContext('releaseLayer()',context),
        check:()=>{assert.equal(boundTarget,target);assert.equal(boundShader,shader);assert.equal(constants,'original-constants');
            assert.equal(states.get(14),1);assert.equal(states.get(52),1);
            assert.equal(states.get(206),0);assert.equal(states.get(207),5);assert.equal(states.get(208),6);
            assert.equal(context.d.pixelShader,'source-shader');assert.equal(context.d.currentTarget,'target');
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
const duplicate=fixture();vm.runInContext('layerCapturedSteps.add(0)',duplicate.context);duplicate.run();
assert.equal(duplicate.calls.length,0);
console.log('Private replay state restoration, opaque guard, draw failures and independent resource release passed.');
