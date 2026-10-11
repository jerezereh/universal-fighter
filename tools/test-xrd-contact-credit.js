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
