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

const nil={isNull(){return true;}},nativeShader={isNull(){return false;},toString(){return 'native';}};
let released=0;
const inspect=vm.createContext({Map,Set,ptr(){return nil;},
    Memory:{alloc(){return {value:0,writePointer(v){this.value=v;},readPointer(){return this.value;},writeU32(v){this.value=v;},readU32(){return this.value;}};}},
    bytes(){return new Uint8Array(8);},succeeded(hr){assert.equal(hr,0);},
    Process:{getModuleByName(){throw Error('disassembly requested');}},
    com(object,slot){return (...args)=>{
        if(slot===108){args[1].writePointer(nativeShader);return 0;}
        if(slot===4){if(args[1]===nil)args[2].writeU32(8);return 0;}
        if(slot===2){released++;return 0;}
        throw Error('unexpected COM slot');
    };}
});
vm.runInContext(fs.readFileSync(__dirname+'/xrd-sign-layer.js','utf8'),inspect);
const byteOnly=vm.runInContext("shaderProgram({},'pixel',false)",inspect);
assert.equal(byteOnly.shader,'native');assert.equal(byteOnly.code.length,8);
assert.equal(released,1);
assert.throws(()=>vm.runInContext("shaderProgram({},'pixel')",inspect),/disassembly requested/);
assert.equal(released,2);
console.log('Byte-only shader checks retain bounds and release references; inspection still requests assembly.');
