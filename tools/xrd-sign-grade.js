// Private native color program plus native texture-copy coverage pass. Source effects remain separate.
function textureTarget(device,width,height,format) {
    const output=Memory.alloc(4);output.writePointer(ptr(0));
    let texture=ptr(0),surface=ptr(0),complete=false;
    try {
        succeeded(com(device,23,'int',['uint','uint','uint','uint','uint','uint','pointer','pointer'])(
            device,width,height,1,1,format,0,output,ptr(0)),'CreateTexture target');texture=output.readPointer();
        output.writePointer(ptr(0));
        succeeded(com(texture,18,'int',['uint','pointer'])(texture,0,output),'private GetSurfaceLevel');surface=output.readPointer();
        complete=true;return {texture,surface};
    } finally {
        if(!complete)try {if(!surface.isNull())com(surface,2,'uint',[])(surface);}
        finally {if(!texture.isNull())com(texture,2,'uint',[])(texture);}
    }
}

function gradingBlendStates(mask) {
    // RGB = previous graded RGB * source coverage; alpha = source coverage.
    return [[7,0],[14,0],[15,0],[19,1],[20,5],[22,1],[23,4],[27,mask?1:0],[52,0],[168,15],
        [171,1],[174,0],[194,0],[206,1],[207,2],[208,1],[209,1]];
}

function gradingQuad(width,height,mask) {
    const data=Memory.alloc(4*48);
    [[-.5,-.5,0,0],[width-.5,-.5,1,0],[-.5,height-.5,0,1],[width-.5,height-.5,1,1]].forEach(([x,y,u,v],i)=>{
        const vertex=[x,y,.5,1,u,v,u,v,...(mask?[1,1,1,1]:[u,v,0,0])];
        vertex.forEach((n,j)=>data.add(i*48+j*4).writeFloat(n));
    });return data;
}

function gradeLayer(device,d) {
    const current=meshLayer,p=config.layer.grade,g=gate;
    if(!p || current===null || current.graded || d.pixelShader!==p.shader || d.currentTarget!==p.target ||
        g===null || g.resumed || g.executing || renderCapture.counter!==current.counter)return;
    const root=Process.mainModule.base.add(config.state.engine_global_rva).readPointer();
    if(root.add(4+config.candidate.counter_field).readU32()!==current.counter)throw new Error('source advanced before private grading');
    const program=shaderProgram(device,'pixel');
    if(program.shader!==p.shader || hex(program.code)!==p.original_hex)throw new Error('native grading program drift');
    const oldPixel=d.pixelShader,oldTarget=d.currentTarget,targets=[],references=[],samplers=[];
    const vp=Memory.alloc(24),vertex=Memory.alloc(4096),pixel=Memory.alloc(224*16);
    let block=ptr(0),depth=ptr(0),lut=ptr(0),sourceShader=ptr(0),sourceVertex=ptr(0),sourceFvf=0,failure=null;
    const states=gradingBlendStates(false).map(([id])=>[id,renderState(device,id)]);
    layerDrawing=true;
    try {
        for(let slot=0;slot<4;++slot) {
            const output=Memory.alloc(4);output.writePointer(ptr(0));
            const hr=com(device,38,'int',['uint','pointer'])(device,slot,output);
            if(hr===0){targets.push([slot,output.readPointer()]);references.push(output.readPointer());}
            else if(hr===(0x88760866|0))targets.push([slot,ptr(0)]);
            else if(slot===0 || hr!==(0x8876086c|0))succeeded(hr,'grading GetRenderTarget');
        }
        const output=Memory.alloc(4);output.writePointer(ptr(0));
        const hr=com(device,40,'int',['pointer'])(device,output);
        if(hr===0){depth=output.readPointer();references.push(depth);}
        else if(hr!==(0x88760866|0))succeeded(hr,'grading GetDepthStencilSurface');
        succeeded(com(device,48,'int',['pointer'])(device,vp),'grading GetViewport');
        succeeded(com(device,95,'int',['uint','pointer','uint'])(device,0,vertex,256),'grading vertex constants');
        succeeded(com(device,110,'int',['uint','pointer','uint'])(device,0,pixel,224),'grading pixel constants');
        output.writePointer(ptr(0));succeeded(com(device,108,'int',['pointer'])(device,output),'grading GetPixelShader');
        sourceShader=output.readPointer();references.push(sourceShader);
        output.writePointer(ptr(0));succeeded(com(device,93,'int',['pointer'])(device,output),'grading GetVertexShader');
        sourceVertex=output.readPointer();references.push(sourceVertex);
        succeeded(com(device,90,'int',['pointer'])(device,output),'grading GetFVF');sourceFvf=output.readU32();
        for(const slot of new Set([...Object.values(p.samplers),p.copy_sampler])) {
            output.writePointer(ptr(0));succeeded(com(device,64,'int',['uint','pointer'])(device,slot,output),'grading source texture');
            const texture=output.readPointer();references.push(texture);const values=[];
            for(const state of [1,2,5,6,7,11]){succeeded(com(device,68,'int',['uint','uint','pointer'])(device,slot,state,output),'grading source sampler');values.push([state,output.readU32()]);}
            samplers.push({slot,texture,values});
        }
        output.writePointer(ptr(0));succeeded(com(device,64,'int',['uint','pointer'])(device,p.samplers.ColorGradingLUT,output),'grading LUT texture');
        lut=output.readPointer();references.push(lut);
        if(lut.isNull())throw new Error('missing native grading LUT');
        output.writePointer(ptr(0));succeeded(com(device,59,'int',['uint','pointer'])(device,1,output),'grading state block');
        block=output.readPointer();references.push(block);
        const colored=textureTarget(device,config.layer.projection.width,config.layer.projection.height,21);
        current.extra.push(colored.texture,colored.surface);
        const black=textureTarget(device,1,1,21);current.extra.push(black.texture,black.surface);
        succeeded(com(device,39,'int',['pointer'])(device,ptr(0)),'grading disable depth');
        for(const [slot] of targets)if(slot!==0)succeeded(com(device,37,'int',['uint','pointer'])(device,slot,ptr(0)),'grading disable MRT');
        succeeded(com(device,37,'int',['uint','pointer'])(device,0,black.surface),'grading black target');
        succeeded(com(device,43,'int',['uint','pointer','uint','uint','float','uint'])(device,0,ptr(0),1,0xff000000,1,0),'grading black clear');
        succeeded(com(device,37,'int',['uint','pointer'])(device,0,colored.surface),'grading color target');
        const privateVp=Memory.alloc(24);privateVp.writeByteArray(bytes(vp,24));privateVp.writeU32(0);privateVp.add(4).writeU32(0);
        privateVp.add(8).writeU32(config.layer.projection.width);privateVp.add(12).writeU32(config.layer.projection.height);
        privateVp.add(16).writeFloat(0);privateVp.add(20).writeFloat(1);
        succeeded(com(device,47,'int',['pointer'])(device,privateVp),'grading viewport');
        succeeded(com(device,92,'int',['pointer'])(device,ptr(0)),'grading fixed vertex shader');
        succeeded(com(device,89,'int',['uint'])(device,0xa0204),'grading XYZRHW/TEX2 float4 FVF');
        for(const [id,value] of gradingBlendStates(false))succeeded(com(device,57,'int',['uint','uint'])(device,id,value),'grading render state');
        for(const [name,slot] of Object.entries(p.samplers)) {
            const texture=name==='SceneColorTexture'?current.texture:name==='ColorGradingLUT'?lut:black.texture;
            succeeded(com(device,65,'int',['uint','pointer'])(device,slot,texture),'grading sampler texture');
            for(const [state,value] of [[1,3],[2,3],[11,0]])succeeded(com(device,69,'int',['uint','uint','uint'])(device,slot,state,value),'grading sampler state');
        }
        succeeded(com(device,107,'int',['pointer'])(device,sourceShader),'native grading shader');
        const quad=gradingQuad(config.layer.projection.width,config.layer.projection.height,false);
        succeeded(com(device,83,'int',['uint','uint','pointer','uint'])(device,5,2,quad,48),'native private grading draw');
        const copy=Memory.alloc(p.copy_hex.length/2);copy.writeByteArray(p.copy_hex.match(/../g).map(x=>parseInt(x,16)));
        output.writePointer(ptr(0));succeeded(com(device,106,'int',['pointer','pointer'])(device,copy,output),'coverage copy shader');
        const copyShader=output.readPointer();current.extra.push(copyShader);
        succeeded(com(device,107,'int',['pointer'])(device,copyShader),'coverage shader');
        const replicate=Memory.alloc(16);[0,0,0,1].forEach((n,i)=>replicate.add(i*4).writeFloat(n));
        succeeded(com(device,109,'int',['uint','pointer','uint'])(device,p.copy_constant,replicate,1),'coverage alpha selector');
        succeeded(com(device,65,'int',['uint','pointer'])(device,p.copy_sampler,current.texture),'coverage texture');
        for(const [state,value] of [[1,3],[2,3],[5,1],[6,1],[7,0],[11,0]])
            succeeded(com(device,69,'int',['uint','uint','uint'])(device,p.copy_sampler,state,value),'coverage point sampler');
        for(const [id,value] of gradingBlendStates(true))succeeded(com(device,57,'int',['uint','uint'])(device,id,value),'coverage blend state');
        const mask=gradingQuad(config.layer.projection.width,config.layer.projection.height,true);
        succeeded(com(device,83,'int',['uint','uint','pointer','uint'])(device,5,2,mask,48),'native coverage draw');
        current.graded=colored.surface;
    } finally {
        try {succeeded(com(device,39,'int',['pointer'])(device,ptr(0)),'grading detach private depth');}catch(error){failure=error;}
        for(const [slot,target] of targets)try{succeeded(com(device,37,'int',['uint','pointer'])(device,slot,target),'grading restore target');}catch(error){failure=error;}
        try{succeeded(com(device,39,'int',['pointer'])(device,depth),'grading restore depth');}catch(error){failure=error;}
        try{if(!block.isNull())succeeded(com(block,5,'int',[])(block),'grading restore state');}catch(error){failure=error;}
        for(const resource of references)try{if(!resource.isNull())com(resource,2,'uint',[])(resource);}catch(error){failure=error;}
        d.pixelShader=oldPixel;d.currentTarget=oldTarget;layerDrawing=false;
        if(failure)throw failure;
    }
    const nowVp=Memory.alloc(24),nowVertex=Memory.alloc(4096),nowPixel=Memory.alloc(224*16);
    succeeded(com(device,48,'int',['pointer'])(device,nowVp),'grading verify viewport');
    succeeded(com(device,95,'int',['uint','pointer','uint'])(device,0,nowVertex,256),'grading verify vertex');
    succeeded(com(device,110,'int',['uint','pointer','uint'])(device,0,nowPixel,224),'grading verify pixel');
    if(hex(bytes(vp,24))!==hex(bytes(nowVp,24)) || hex(bytes(vertex,4096))!==hex(bytes(nowVertex,4096)) ||
        hex(bytes(pixel,224*16))!==hex(bytes(nowPixel,224*16)) || states.some(([id,value])=>renderState(device,id)!==value))
        throw new Error('native grading state did not restore');
    const output=Memory.alloc(4);
    succeeded(com(device,90,'int',['pointer'])(device,output),'grading verify FVF');
    if(output.readU32()!==sourceFvf)throw new Error('source FVF did not restore');
    for(const [slot,expected] of [[93,sourceVertex],[108,sourceShader],[40,depth]]) {
        output.writePointer(ptr(0));const hr=com(device,slot,'int',['pointer'])(device,output);
        if(slot===40 && expected.isNull() && hr===(0x88760866|0))continue;
        succeeded(hr,'grading verify shader/depth');const resource=output.readPointer();
        try{if(!resource.equals(expected))throw new Error('source shader/depth did not restore');}
        finally{if(!resource.isNull())com(resource,2,'uint',[])(resource);}
    }
    for(const {slot,texture,values} of samplers) {
        output.writePointer(ptr(0));succeeded(com(device,64,'int',['uint','pointer'])(device,slot,output),'grading verify texture');
        const resource=output.readPointer();try{if(!resource.equals(texture))throw new Error('source texture did not restore');}
        finally{if(!resource.isNull())com(resource,2,'uint',[])(resource);}
        for(const [state,value] of values){succeeded(com(device,68,'int',['uint','uint','pointer'])(device,slot,state,output),'grading verify sampler');
            if(output.readU32()!==value)throw new Error('source sampler state did not restore');}
    }
    if(root.add(4+config.candidate.counter_field).readU32()!==current.counter)throw new Error('source advanced during private grading');
}
