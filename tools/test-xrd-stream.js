// Actual native-script control flow with authored frames; no game/process required.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let packets=[];
const c=vm.createContext({rpc:{},Date:{now:()=>0},send:(metadata,data)=>packets.push({metadata,data})});
for(const file of ['boundary','layer'])vm.runInContext(fs.readFileSync(`tools/xrd-sign-${file}.js`,'utf8'),c);
const run=s=>vm.runInContext(s,c),api=c.rpc.exports;
assert.throws(()=>api.start({streaming:1}),/invalid streaming/);
assert.throws(()=>api.start({streaming:true}),/owned transactions/);
assert.throws(()=>api.start({streaming:true,transactions:true,capture_passes:true}),/inventory/);
run(`config={streaming:true,transactions:true,input:true,layer:{settle:true,capture_steps:[]}};
gate={renewable:true,resumed:false,pending:false,executing:false,credits:0,
initialCounter:0xffffff00,frameReady:null,deadline:8000,ownsState:false};
equalPixels=(a,b)=>a.data[0]===b.data[0];`);
for(let index=0;index<1000;index++) {
    packets=[];c.counter=(0xffffff00+index)>>>0;
    run(`gate.pending=false;gate.credits=0;
        function candidate(presentation,pixel=7) {return {metadata:{counter,presentation_index:presentation,
            request_index:(counter-gate.initialCounter)>>>0,replayed_draws:13,source_facing_left:false},data:[pixel]};}
        assertSelected=layerRequestSelected((counter-gate.initialCounter)>>>0);
        pendingLayer=candidate(3);finishSettledPair({metadata:{counter,presentation_index:3}});`);
    assert.equal(run('assertSelected'),true);
    assert.equal(run('gate.frameReady'),null);assert.equal(packets.filter(p=>p.data).length,0);
    run('pendingLayer=candidate(4);finishSettledPair({metadata:{counter,presentation_index:4}})');
    assert.equal(run('gate.frameReady'),c.counter);
    assert.equal(packets.filter(p=>p.data).length,1); // one state/private-image packet, no scene pixels
    assert.equal(run('previousCandidate'),null);
    assert.equal(run('pendingLayer'),null);
    assert.equal(run('layerCapturedSteps.size'),0);assert.equal(run('layerCaptures'),0);
    assert.equal(run('layerRequestSelected((counter-gate.initialCounter)>>>0)'),false);
    assert.throws(()=>api.step([0,0],(c.counter-1)>>>0),/stale/);
    api.step([1,0],c.counter);
    assert.equal(run('gate.credits'),1);assert.equal(run('gate.frameReady'),null);
    assert.throws(()=>api.step([0,0],c.counter),/pending/);
}
run('gate.pending=false;gate.credits=0;pendingLayer=candidate(24,9);previousCandidate={layer:candidate(23,7),scene:{metadata:{}}}');
assert.throws(()=>run('finishSettledPair({metadata:{counter,presentation_index:24}})'),/bounded presentations/);
run('gate.frameReady=counter;gate.resumed=true');assert.throws(()=>api.step([0,0],c.counter),/unavailable/);
run('gate.resumed=false;gate.deadline=-1');assert.throws(()=>api.step([0,0],c.counter),/expired/);
run('gate.frameReady=null;renderCapture.presentations=25');
assert.throws(()=>run('assertLayerWindow()'),/bounded presentation window/);
run('gate.pending=true;assertLayerWindow();gate.pending=false;gate.frameReady=counter;assertLayerWindow()');
run('config.streaming=false;gate.frameReady=null;assertLayerWindow()');
c.Interceptor={flush:()=>{}};
run('config.streaming=true;gate=null;pendingLayer={};previousCandidate={};pixelScratch={};finishStop()');
assert.equal(run('pendingLayer'),null);assert.equal(run('previousCandidate'),null);assert.equal(run('pixelScratch'),null);
console.log('SIGN rolling frame checks passed: 1000 credits, uint32 wrap, bounded retention, stale/pending/expiry rejection');
