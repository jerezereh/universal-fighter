// Graphics removal must be scheduled by RPC and completed at a renderer boundary.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const calls=[];
const context=vm.createContext({rpc:{exports:{}},Map,Uint8Array,
    Interceptor:{revert:target=>calls.push('revert-'+target),flush:()=>{}},
    clearTimeout:()=>calls.push('clear-watchdog'),fixtureCalls:calls,
    fixtureTarget:{toUInt32:()=>123},fixtureBytes:()=>Uint8Array.from([0xab,0xcd])});
vm.runInContext(fs.readFileSync(__dirname+'/xrd-sign-boundary.js','utf8'),context);
vm.runInContext("config={layer:false};bytes=fixtureBytes;gate={target:'owner',timer:1};"+
    "drawFilter={target:'draw',skipped:4};"+
    "inputHooks=[{detach(){fixtureCalls.push('detach-input');}}];"+
    "renderHooks=[{target:fixtureTarget,before:'abcd',listener:{detach(){fixtureCalls.push('detach-graphics');}}}];",context);
const pending=context.rpc.exports.stop();assert.equal(pending.pending_renderer_stop,true);
assert.equal(pending.render_targets[0].address,123);assert.equal(pending.render_targets[0].before,'abcd');
assert.deepEqual(calls,[],'RPC removed live graphics hooks instead of scheduling');
vm.runInContext('stopReceipt=finishStop()',context);
assert.deepEqual(calls,['revert-draw','detach-input','detach-graphics','clear-watchdog','revert-owner']);
const receipt=context.rpc.exports.stop();assert.equal(receipt.detached,true);
assert.equal(receipt.render_code_restored,true);assert.equal(receipt.diagnostic_mesh_draws_skipped,4);
assert.equal(calls.length,5,'cached stop receipt repeated teardown');
console.log('RPC scheduling, renderer graphics/input removal before source resume and idempotent stop receipt passed.');
