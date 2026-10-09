// Exercise the actual heartbeat/step exports with a simulated clock; no native process.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let now=0,armed=0,cleared=0;
const c=vm.createContext({rpc:{},Date:{now:()=>now},setTimeout:()=>++armed,clearTimeout:()=>++cleared});
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
console.log('SIGN renewable lease authored checks passed');
