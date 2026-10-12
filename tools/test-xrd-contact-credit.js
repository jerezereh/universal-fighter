// Exercise the actual RPC ingress without Frida or a running game.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const context=vm.createContext({rpc:{},Date,Map});
vm.runInContext(fs.readFileSync(__dirname+'/xrd-sign-boundary.js','utf8')+`
function fixture(counter=4) {
    config={dynamic_contact_results:true,input:{},candidate:{counter_field:8}};
    gate={root:{add(){return {readU32(){return counter;}};}},initialCounter:0,
        externalPairs:0,pending:false,credits:0,resumed:false,deadline:Date.now()+8000,
        renewable:false,ownsState:false,pendingContact:null,lastContactStep:null};
}
function creditState(){return [gate.pending,gate.credits,gate.pendingContact];}
`,context);
const run=s=>vm.runInContext(s,context);
function reject(call) {
    run('fixture()');
    assert.throws(()=>run(call));
    assert.equal(JSON.stringify(run('creditState()')),'[false,0,null]');
}
for(const call of [
    'rpc.exports.step([0,0],3,{step:5,ordinal:1,damage:8})',
    'rpc.exports.step([0,0],4,{step:45,ordinal:1,damage:8})',
    'rpc.exports.step([0,0],4,{step:5,ordinal:2,damage:8})',
    'rpc.exports.step([0,0],4,{step:5,ordinal:1,damage:true})',
    'rpc.exports.step([0,0],4,{step:5,ordinal:1,damage:420})',
    'rpc.exports.step([0,0],4,{step:5,ordinal:1,damage:8,extra:1})',
    'rpc.exports.step([1,0],4,{step:5,ordinal:1,damage:8})'
])reject(call);
run('fixture();rpc.exports.step([0,0],4,{step:5,ordinal:1,damage:8})');
assert.equal(JSON.stringify(run('creditState()')),'[true,1,{"step":5,"ordinal":1,"damage":8}]');
assert.throws(()=>run('rpc.exports.step([0,0],4,{step:5,ordinal:1,damage:8})'));
run('fixture(44);gate.externalPairs=1;gate.lastContactStep=5;rpc.exports.step([0,0],44,{step:45,ordinal:2,damage:13})');
assert.equal(run('gate.pendingContact.damage'),13);
run('fixture(3);rpc.exports.step([0,0],3)');
assert.equal(JSON.stringify(run('creditState()')),'[true,1,null]');
run('fixture(3)');
assert.throws(()=>run('rpc.exports.step([0,0],3,{step:5,ordinal:1,damage:8})'));
for(const invalid of ['false','0','""']) {
    run('fixture(3)');
    assert.throws(()=>run('rpc.exports.step([0,0],3,'+invalid+')'));
    assert.equal(JSON.stringify(run('creditState()')),'[false,0,null]');
}
run('fixture(9);rpc.exports.step([0,0],9,{step:10,ordinal:1,damage:8})');
assert.equal(run('gate.pendingContact.step'),10);
run('fixture(49);gate.externalPairs=1;gate.lastContactStep=10;rpc.exports.step([0,0],49,{step:50,ordinal:2,damage:13})');
assert.equal(run('gate.pendingContact.step'),50);
for(const setup of ['fixture(0)','fixture(65)','fixture(9);gate.externalPairs=4',
    'fixture(9);gate.externalPairs=1;gate.lastContactStep=5']) {
    run(setup);
    assert.throws(()=>run('rpc.exports.step([0,0],gate.root.add().readU32(),{step:gate.root.add().readU32()+1,ordinal:gate.externalPairs+1,damage:8})'));
    assert.equal(JSON.stringify(run('creditState()')),'[false,0,null]');
}
run('fixture();config.dynamic_contact_results=false');
assert.throws(()=>run('rpc.exports.step([0,0],4,{step:5,ordinal:1,damage:8})'));
console.log('Owned contact credit counter, ordinal, shape, neutral input and replay rejection passed.');

context.Interceptor={flush(){}};
context.detachCalls=0;
context.inventoryHooks=[{inventoryOnly:true,listener:{detach(){context.detachCalls++;}}},
    {inventoryOnly:false,listener:{detach(){throw Error('needed binding hook detached');}}}];
run('fixture();config.streaming=true;renderHooks=inventoryHooks;drawTrace={frames:1,active:false};retireDrawInventoryHooks()');
assert.equal(context.detachCalls,0);
run('drawTrace.frames=2;drawTrace.active=true;retireDrawInventoryHooks()');
assert.equal(context.detachCalls,0);
run('drawTrace.active=false;retireDrawInventoryHooks();retireDrawInventoryHooks()');
assert.equal(context.detachCalls,1);
console.log('Only finished streaming inventory hooks retire, exactly once.');

let clock=0;
const sent=[];
context.Date={now(){return clock;}};
context.send=message=>sent.push(message);
run('snapshot=function(){return {data:null,segments:[]};};fixture();config.streaming=true;');
const state='{root:null,before:4,thread:1,depth:0,return_address:"test",this_delta:4,entered_ms:0}';
run(`publish(${state},4,false)`);
clock=49;run(`publish(${state},4,false)`);
assert.equal(sent.length,1);
// Executed states always publish, even inside the held-copy interval.
run(`publish(${state},5,true)`);
assert.equal(sent.length,2);assert.equal(sent[1].executed,true);
clock=98;run(`publish(${state},5,false)`);assert.equal(sent.length,2);
clock=99;run(`publish(${state},5,false)`);assert.equal(sent.length,3);
run('config.streaming=false');run(`publish(${state},5,false)`);assert.equal(sent.length,4);
console.log('Held diagnostic sampling retains every executed state and leaves nonstreaming traces unchanged.');

let region={base:0x1000,size:0x10000,state:0x1000,protect:4},querySize=28,queries=0;
context.Process={pointerSize:4,getModuleByName(){return {getExportByName(){return {};}};}};
context.NativeFunction=function(){return ()=>{queries++;return querySize;};};
context.Memory={alloc(){return {readPointer(){return {toUInt32(){return region.base;}};},
    add(offset){return {readU32(){return ({12:region.size,16:region.state,20:region.protect})[offset];}};}};}};
const actor='{toUInt32(){return 0x1100;}}';
run(`assertReadableActor(${actor},0x2600)`);run(`assertReadableActor(${actor},0x2600)`);
assert.equal(queries,2); // Never cache a region across reads.
for(const bad of [{protect:0x104},{protect:1},{protect:16},{state:0x2000},
        {base:0x1200},{size:0x200},{base:0xffff0000,size:0x20000}]) {
    const saved=region;region={...region,...bad};
    assert.throws(()=>run(`assertReadableActor(${actor},0x2600)`));region=saved;
}
querySize=0;assert.throws(()=>run(`assertReadableActor(${actor},0x2600)`));querySize=28;
context.Process.pointerSize=8;assert.throws(()=>run(`assertReadableActor(${actor},0x2600)`));
console.log('Fresh native actor range checks reject guards, unreadable/uncommitted spans, wrap and query failure.');

run('fixture();config.streaming=true;config.transactions=true;gate.ownsState=true;gate.frameReady=4;verifyGateOwner=function(){};');
for(const value of ['false','[]','[{x:0,y:0},{x:1,y:0}]','[{x:true,y:0},{x:400000,y:0}]',
        '[{x:0,y:1},{x:400000,y:0}]','[{x:0,y:0,z:0},{x:400000,y:0}]','[{x:700000,y:0},{x:0,y:0}]']) {
    assert.throws(()=>run(`rpc.exports.step([0,0],4,null,${value})`));
    assert.equal(run('gate.pending'),false);
}
assert.throws(()=>run('rpc.exports.step([4,0],4,null,[{x:0,y:0},{x:400000,y:0}])'));
run('rpc.exports.step([0,0],4,null,[{x:-252000,y:0},{x:252000,y:0}])');
assert.equal(JSON.stringify(run('gate.pendingProjection')),'[{"x":-252000,"y":0},{"x":252000,"y":0}]');
assert.throws(()=>run('rpc.exports.step([0,0],4,null,[{x:352000,y:0},{x:-252000,y:0}])'));
const writes=[];let secondY=1,parentFlags=0;
const actors=[0,1].map(i=>({add(field){return {readS32(){return field===8 && i===1?secondY:0;},
    readU32(){return parentFlags;},readPointer(){return {isNull(){return true;}};},writeS32(value){writes.push([i,field,value]);}};}}));
context.actorRoot={add(offset){return {readPointer(){return actors[offset/4];}};}};
run('assertReadableActor=function(){return 4;};gate.root=actorRoot;');
const profile='{state:{fields:{slots:0,x:4,y:8},parents:[16],guarded_parents:[]}}';
assert.throws(()=>run(`applyPositionProjection(gate,${profile})`));assert.equal(writes.length,0);
secondY=0;run(`applyPositionProjection(gate,${profile})`);
assert.deepEqual(writes,[[0,4,-252000],[1,4,252000]]);
assert.equal(run('gate.pendingProjection'),null);
run(`applyPositionProjection(gate,${profile})`);assert.equal(writes.length,2);
run('gate.pendingProjection=[{x:352000,y:0},{x:-252000,y:0}]');
parentFlags=0x80000000;
assert.throws(()=>run('applyPositionProjection(gate,{state:{fields:{slots:0,x:4,y:8},parents:[16],guarded_parents:[{parent_field:16,flags_field:12,required_mask:2147483648}]}})'));
assert.equal(writes.length,2);parentFlags=0;
run('assertReadableActor=function(){return 2;}');
assert.throws(()=>run(`applyPositionProjection(gate,${profile})`));assert.equal(writes.length,2);
console.log('Owned position ingress validates before credits; native projection checks both actors before one-time writes.');
