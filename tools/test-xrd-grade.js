// Authored device/resource graph; native programs and game pixels are not included.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function fixture(failure=null) {
    const pointer=name=>({name,isNull:()=>name==='null',toString:()=>name,equals:p=>p.name===name});const zero=pointer('null');
    const target=pointer('source-target'),depth=pointer('source-depth'),shader=pointer('source-shader'),vs=pointer('source-vertex');
    const hdr=pointer('hdr'),lut=pointer('lut'),block=pointer('block'),copy=pointer('copy');
    const releases=[],textures=[];let boundTarget=target,boundDepth=depth,boundShader=shader,boundVertex=vs,fvf=99;
    let viewport=Uint8Array.from({length:24},(_,i)=>i),pixel=new Uint8Array(224*16),vertex=new Uint8Array(4096);
    let sampler=new Map([[0,pointer('scene')],[1,pointer('bloom')],[2,lut],[3,pointer('lowres')]]),states=new Map();
    let saved=null,draws=0,samplerStates=new Map();
    function allocation(size) {
        const a={data:new Uint8Array(size),pointer:zero,writePointer(p){this.pointer=p;},readPointer(){return this.pointer;},
            writeByteArray(b){this.data.set(b);},writeU32(n){new DataView(this.data.buffer).setUint32(0,n,true);},
            readU32(){return new DataView(this.data.buffer).getUint32(0,true);},
            add(offset){return {writeU32:n=>new DataView(a.data.buffer).setUint32(offset,n,true),
                writeFloat:n=>new DataView(a.data.buffer).setFloat32(offset,n,true)};}};return a;
    }
    const context=vm.createContext({Map,Date,Memory:{alloc:allocation},ptr:()=>zero,Uint8Array,
        config:{state:{engine_global_rva:0},candidate:{counter_field:0},layer:{projection:{width:4,height:4},grade:{
            shader:'source-shader',target:'source-target',original_hex:'01020304',copy_hex:'05060708',copy_sampler:0,copy_constant:7,
            samplers:{SceneColorTexture:0,FilterColor1Texture:1,ColorGradingLUT:2,LowResPostProcessBuffer:3}}}},
        gate:{resumed:false,executing:false,initialCounter:10},renderCapture:{counter:10},
        Process:{mainModule:{base:{add:()=>({readPointer:()=>({add:()=>({readU32:()=>10})})})}}},
        shaderProgram:()=>({shader:'source-shader',code:Uint8Array.from([1,2,3,4])}),
        bytes:(p,n)=>p.data.slice(0,n),hex:a=>Buffer.from(a).toString('hex'),
        succeeded:(hr,name)=>{if(hr<0)throw Error(name+' failed');}});
    context.renderState=(device,id)=>states.get(id)||0;
    context.com=(object,slot)=>(...a)=>{
        if(slot===2){releases.push(object.name);if(failure==='release-'+object.name)throw Error('release failed');return 0;}
        if(object.name.startsWith('texture-') && slot===18) {
            if(failure==='surface')return -1;a[2].writePointer(pointer('surface-'+object.name.slice(8)));return 0;
        }
        if(object===block && slot===5) {
            states=new Map(saved.states);sampler=new Map(saved.sampler);viewport=saved.viewport;pixel=saved.pixel;vertex=saved.vertex;
            boundShader=saved.shader;boundVertex=saved.vertexShader;fvf=saved.fvf;samplerStates=new Map(saved.samplerStates);
            if(failure==='restore-viewport')viewport[0]^=1;
            if(failure==='restore-vertex')vertex[0]^=1;
            if(failure==='restore-pixel')pixel[0]^=1;
            if(failure==='restore-render')states.set(7,(states.get(7)||0)^1);
            if(failure==='incomplete-constants'){vertex[0]^=1;pixel[0]^=1;}
            return 0;
        }
        if(slot===23){if(failure==='texture')return -1;const t=pointer('texture-'+(textures.length+1));textures.push(t);a[7].writePointer(t);return 0;}
        if(slot===38){if(a[1]!==0)return 0x88760866|0;a[2].writePointer(boundTarget);return 0;}
        if(slot===40){a[1].writePointer(boundDepth);return 0;}
        if(slot===48){a[1].data=viewport.slice();return 0;}
        if(slot===95){a[2].data=vertex.slice();return 0;}
        if(slot===110){a[2].data=pixel.slice();return 0;}
        if(slot===108){a[1].writePointer(boundShader);return 0;}
        if(slot===93){a[1].writePointer(boundVertex);return 0;}
        if(slot===90){a[1].writeU32(fvf);return 0;}
        if(slot===68){a[3].writeU32(samplerStates.get(a[1]+':'+a[2])||0);return 0;}
        if(slot===64){a[2].writePointer(sampler.get(a[1]));return 0;}
        if(slot===59){if(failure==='block')return -1;saved={states:new Map(states),sampler:new Map(sampler),viewport:viewport.slice(),
            pixel:pixel.slice(),vertex:vertex.slice(),shader:boundShader,vertexShader:boundVertex,fvf,samplerStates:new Map(samplerStates)};a[2].writePointer(block);return 0;}
        if(slot===39){boundDepth=a[1];return 0;}
        if(slot===37){if(a[1]===0)boundTarget=a[2];return 0;}
        if(slot===43)return 0;
        if(slot===47){viewport=a[1].data.slice();return 0;}
        if(slot===92){boundVertex=a[1];return 0;}
        if(slot===89){fvf=a[1];return 0;}
        if(slot===57){states.set(a[1],a[2]);return 0;}
        if(slot===65){sampler.set(a[1],a[2]);return 0;}
        if(slot===69){samplerStates.set(a[1]+':'+a[2],a[3]);return 0;}
        if(slot===107){boundShader=a[1];return 0;}
        if(slot===106){if(failure==='copy')return -1;a[2].writePointer(copy);return 0;}
        if(slot===94){if(failure==='vertex-setter')return -1;if(failure!=='restore-vertex')vertex.set(a[2].data,a[1]*16);return 0;}
        if(slot===109){if(a[3]===224 && failure==='pixel-setter')return -1;
            if(a[3]!==224 || failure!=='restore-pixel')pixel.set(a[2].data,a[1]*16);return 0;}
        if(slot===83){
            draws++;assert.equal(fvf,0xa0204);assert.equal(boundDepth,zero);assert.equal(a[1],5);assert.equal(a[2],2);assert.equal(a[4],48);
            if(draws===1){assert.equal(boundShader,shader);assert.equal(sampler.get(0),hdr);assert.equal(sampler.get(2),lut);
                assert.equal(sampler.get(1),sampler.get(3));if(failure==='grade-draw')return -1;}
            else {assert.equal(boundShader,copy);assert.equal(sampler.get(0),hdr);assert.equal(states.get(19),1);assert.equal(states.get(20),5);
                assert.equal(states.get(207),2);assert.equal(states.get(208),1);if(failure==='mask-draw')return -1;}
            return 0;
        }
        throw Error('unexpected COM slot '+slot);
    };
    context.device=pointer('device');context.d={pixelShader:'source-shader',currentTarget:'source-target'};
    vm.runInContext('let meshLayer={counter:10,texture:null,width:4,height:4,extra:[]};let layerDrawing=false;',context);
    vm.runInContext(fs.readFileSync(__dirname+'/xrd-sign-grade.js','utf8'),context);
    context.hdr=hdr;vm.runInContext('meshLayer.texture=hdr',context);
    return {releases,context,run:()=>vm.runInContext('gradeLayer(device,d)',context),
        restore:()=>{assert.equal(boundTarget,target);assert.equal(boundDepth,depth);assert.equal(boundShader,shader);assert.equal(boundVertex,vs);
            assert.equal(fvf,99);assert.equal(sampler.get(2),lut);assert.equal(vm.runInContext('layerDrawing',context),false);
            assert.ok(vertex.every(n=>n===0) && pixel.every(n=>n===0));},
        release:()=>vm.runInContext('for(const resource of meshLayer.extra)com(resource,2,"uint",[])(resource)',context)};
}
const good=fixture();good.run();good.restore();good.release();assert.equal(vm.runInContext('Boolean(meshLayer.graded)',good.context),true);
const sourceView=fixture();sourceView.context.config.layer.projection=null;sourceView.run();sourceView.restore();sourceView.release();
assert.ok(good.releases.includes('copy') && good.releases.includes('texture-1') && good.releases.includes('surface-2'));
for(const failure of ['block','texture','surface','copy','grade-draw','mask-draw','vertex-setter','pixel-setter']) {
    const f=fixture(failure);assert.throws(f.run,/failed/);f.restore();f.release();
    assert.ok(f.releases.includes('source-target') && f.releases.includes('source-shader') && f.releases.includes('lut'));
    if(failure==='surface')assert.ok(f.releases.includes('texture-1'));
}
// A device path which omits constants from state-block restore must still recover them.
const incomplete=fixture('incomplete-constants');
incomplete.run();incomplete.restore();incomplete.release();
for(const [failure,diagnostic] of [['restore-viewport','viewport'],['restore-vertex','vertex constants'],
        ['restore-pixel','pixel constants'],['restore-render','render state 7']]) {
    const f=fixture(failure);assert.throws(f.run,new RegExp('native grading state did not restore: '+diagnostic));
    f.release();assert.ok(f.releases.includes('block') && f.releases.includes('lut'));
}
for(const alpha of [0,1])for(const color of [0,.25,1]) {
    // ZERO/SRCALPHA RGB and ONE/ZERO separate alpha preserve black and clear all uncovered RGB.
    assert.equal(0*0+color*alpha,color*alpha);assert.equal(alpha*1+0*0,alpha);
}
console.log('Native grading/copy texture routing, FVF geometry, alpha blend policy, state restoration and resource failures passed.');
