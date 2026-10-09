// Exercise the actual heartbeat/step exports with a simulated clock; no native process.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let now=0,armed=0,cleared=0,timer;
const c=vm.createContext({rpc:{},Date:{now:()=>now},setTimeout:fn=>{timer=fn;return ++armed;},clearTimeout:()=>++cleared});
vm.runInContext(fs.readFileSync('tools/xrd-sign-boundary.js','utf8'),c);
const run=s=>vm.runInContext(s,c),api=c.rpc.exports;
run('config={input:true}; gate={renewable:true,resumed:false,pending:false,credits:0,deadline:8000,timer:null}');
now=7000;assert.equal(api.heartbeat().renewed,true);
now=14000;assert.equal(api.heartbeat().renewed,true); // held beyond old hard lifetime
assert.equal(armed,2);assert.equal(cleared,2);
const deadline=run('gate.deadline');
api.step([1,0]);assert.equal(run('gate.deadline'),deadline); // steps cannot hide controller loss
assert.equal(run('gate.credits'),1);
assert.throws(()=>api.step([0,0]),/pending/);
run('gate.pending=false; gate.credits=0');
assert.throws(()=>api.step([1024,0]),/invalid/);
now=22001;assert.throws(()=>api.heartbeat(),/expired/);
assert.throws(()=>api.step([0,0]),/expired/);
run('gate.resumed=true');assert.throws(()=>api.heartbeat(),/unavailable/);
run('gate=null');assert.throws(()=>api.heartbeat(),/unavailable/);
run('gate={renewable:false,resumed:false,pending:false,credits:0,deadline:30000,timer:null}');
now=23000;assert.throws(()=>api.heartbeat(),/unavailable/);
api.step([0,0]);assert.equal(run('gate.deadline'),31000); // legacy bounded experiment unchanged
assert.throws(()=>api.start({renewable:true}),/already/);
run('gate=null');assert.throws(()=>api.start({renewable:1}),/invalid renewable/);
assert.throws(()=>api.start({renewable:true,gate:{},capture:true}),/without private rendering/);
assert.throws(()=>api.start({transactions:1}),/invalid transaction/);
assert.throws(()=>api.start({transactions:true,renewable:true,gate:{}}),/four consecutive/);
vm.runInContext(fs.readFileSync('tools/xrd-sign-layer.js','utf8'),c);
c.send=()=>{};
run(`config={input:true,transactions:true}; gate={renewable:true,resumed:false,pending:false,
    executing:false,credits:0,initialCounter:100,frameReady:null,deadline:40000};
    equalPixels=()=>true;
    previousCandidate={layer:{metadata:{counter:100,presentation_index:3,replayed_draws:13,source_facing_left:false},data:null},scene:{metadata:{}}};
    pendingLayer={metadata:{counter:100,presentation_index:4,replayed_draws:13,source_facing_left:false,request_index:0},data:null};`);
assert.throws(()=>api.step([0,0],100),/not ready/);
run('finishSettledPair({metadata:{counter:100,presentation_index:4},data:null})');
assert.equal(run('gate.frameReady'),100);
assert.throws(()=>api.step([0,0],99),/stale/);
assert.equal(run('gate.frameReady'),100); // rejection preserves the ready frame
api.step([0,0],100);assert.equal(run('gate.frameReady'),null);
run('gate.pending=false;gate.credits=0');
assert.throws(()=>api.step([0,0],100),/not ready/); // completed credit cannot replay
run('gate.frameReady=103');assert.throws(()=>api.step([0,0],103),/exhausted/);
run('config.layer={};gate.credits=1;meshLayer={};armGateRemoval()');timer();
assert.equal(run('gate.resumed'),true);assert.equal(run('gate.credits'),0);
assert.equal(run('stopRequested && layerStopping'),true); // renderer thread owns COM teardown
run('meshLayer=null;gate={renewable:true,timer:null};finishStop=()=>{gate=null;return {detached:true}};armGateRemoval()');
timer();assert.equal(run('gate'),null);assert.equal(run('stopReceipt.detached'),true);
console.log('SIGN renewable lease authored checks passed');
