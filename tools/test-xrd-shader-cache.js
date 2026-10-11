// Check the actual cache hit and teardown paths, including per-frame reference ownership.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const calls=[];
const resource=name=>({name,toString(){return name;}});
const device=resource('device'),source=resource('source'),shader=resource('shader'),target=resource('target');
const copy=resource('copy');
const context=vm.createContext({Map,Set,device,source,shader,target,copy,
    config:{streaming:true},com(object,slot){return ()=>calls.push([object.name,slot]);}});
vm.runInContext(fs.readFileSync(__dirname+'/xrd-sign-layer.js','utf8')+`
layerShaderCache.set('device:source',{source,shader,original_hex:'aa',variant_hex:'bb'});
meshLayer={shaders:new Map(),target};
`,context);
const run=s=>vm.runInContext(s,context);
assert.equal(run("layerShader(device,source,{original_hex:'aa',variant_hex:'bb'})"),shader);
assert.equal(run("layerShader(device,source,{original_hex:'aa',variant_hex:'bb'})"),shader);
assert.deepEqual(calls,[['shader',1]]);
run('releaseLayer()');
assert.deepEqual(calls.slice(1),[['shader',2],['target',2]]);
assert.equal(run('layerShaderCache.size'),1);
run('meshLayer={shaders:new Map(),target}');
assert.throws(()=>run("layerShader(device,source,{original_hex:'changed',variant_hex:'bb'})"));
assert.equal(run('meshLayer.shaders.size'),0);
assert.equal(run("layerShader(device,source,{original_hex:'aa',variant_hex:'bb'})"),shader);
run('releaseLayer();releaseLayerShaderCache();releaseLayerShaderCache()');
assert.equal(run('layerShaderCache.size'),0);
assert.deepEqual(calls.slice(-2),[['shader',2],['source',2]]);
run('coverageShaderCache={shader:copy};releaseLayerShaderCache();releaseLayerShaderCache()');
assert.deepEqual(calls.slice(-1),[['copy',2]]);
assert.equal(run('coverageShaderCache'),null);
console.log('Shader witness drift, one frame reference, retained cache and one-time owner release passed.');
