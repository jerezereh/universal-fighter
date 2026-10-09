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

function gradingQuad(width,height,mask,uScale=1,vScale=1) {
    const data=Memory.alloc(4*48);
    [[-.5,-.5,0,0],[width-.5,-.5,1,0],[-.5,height-.5,0,1],[width-.5,height-.5,1,1]].forEach(([x,y,u,v],i)=>{
        const vertex=[x,y,.5,1,u*uScale,v*vScale,u,v,...(mask?[1,1,1,1]:[u,v,0,0])];
        vertex.forEach((n,j)=>data.add(i*48+j*4).writeFloat(n));
    });return data;
}

function gradeLayer(device,d,replaySource=null) {
    const current=meshLayer,p=config.layer.grade,g=gate;
    if(!p || current===null || current.graded || d.pixelShader!==p.shader || d.currentTarget!==p.target ||
        g===null || g.resumed || g.executing || renderCapture.counter!==current.counter)return;
    const root=Process.mainModule.base.add(config.state.engine_global_rva).readPointer();
    if(root.add(4+config.candidate.counter_field).readU32()!==current.counter)throw new Error('source advanced before private grading');
    const program=shaderProgram(device,'pixel');
    if(program.shader!==p.shader || hex(program.code)!==p.original_hex)throw new Error('native grading program drift');
    if(config.layer.source_color) {
        if(replaySource===null || hex(shaderProgram(device,'vertex').code)!==p.vertex_original_hex)
            throw new Error('unverified original color draw/vertex program');
    }
    if(config.layer.source_view) {
        const captured=captureBackBuffer(device,root,current.counter,true);
        if(![21,22].includes(captured.metadata.format))throw new Error('original color-stage capture requires native A8/X8 pixels');
        send({...captured.metadata,pass_index:((current.counter-g.initialCounter)>>>0)+1,
            trace_event:d.events.length,presentation_index:renderCapture.presentations+1,
            request_index:(current.counter-g.initialCounter)>>>0,capture_boundary:'after-original-color-draw',
            original_color_stage:true,original_color_shader:p.shader,hresult:0},captured.data);
    }
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
        const colored=textureTarget(device,current.width,current.height,21);
        current.extra.push(colored.texture,colored.surface);
        const black=config.layer.source_color?null:textureTarget(device,1,1,21);
        if(black)current.extra.push(black.texture,black.surface);
        succeeded(com(device,39,'int',['pointer'])(device,ptr(0)),'grading disable depth');
        for(const [slot] of targets)if(slot!==0)succeeded(com(device,37,'int',['uint','pointer'])(device,slot,ptr(0)),'grading disable MRT');
        if(black) {
            succeeded(com(device,37,'int',['uint','pointer'])(device,0,black.surface),'grading black target');
            succeeded(com(device,43,'int',['uint','pointer','uint','uint','float','uint'])(device,0,ptr(0),1,0xff000000,1,0),'grading black clear');
        }
        succeeded(com(device,37,'int',['uint','pointer'])(device,0,colored.surface),'grading color target');
        const privateVp=Memory.alloc(24);privateVp.writeByteArray(bytes(vp,24));privateVp.writeU32(0);privateVp.add(4).writeU32(0);
        privateVp.add(8).writeU32(current.width);privateVp.add(12).writeU32(current.height);
        privateVp.add(16).writeFloat(0);privateVp.add(20).writeFloat(1);
        succeeded(com(device,47,'int',['pointer'])(device,config.layer.source_color?vp:privateVp),'grading viewport');
        for(const [id,value] of gradingBlendStates(false))succeeded(com(device,57,'int',['uint','uint'])(device,id,value),'grading render state');
        if(!config.layer.source_color)for(const [name,slot] of Object.entries(p.samplers)) {
            const texture=name==='SceneColorTexture'?current.texture:name==='ColorGradingLUT'?lut:black.texture;
            succeeded(com(device,65,'int',['uint','pointer'])(device,slot,texture),'grading sampler texture');
            for(const [state,value] of [[1,3],[2,3],[11,0]])succeeded(com(device,69,'int',['uint','uint','uint'])(device,slot,state,value),'grading sampler state');
        }
        succeeded(com(device,107,'int',['pointer'])(device,sourceShader),'native grading shader');
        if(config.layer.source_color)succeeded(replaySource(),'original full-source private color draw');
        succeeded(com(device,47,'int',['pointer'])(device,privateVp),'coverage viewport');
        succeeded(com(device,92,'int',['pointer'])(device,ptr(0)),'grading fixed vertex shader');
        succeeded(com(device,89,'int',['uint'])(device,0xa0204),'grading XYZRHW/TEX2 float4 FVF');
        const quad=gradingQuad(current.width,current.height,false);
        if(!config.layer.source_color)succeeded(com(device,83,'int',['uint','uint','pointer','uint'])(device,5,2,quad,48),'native private grading draw');
        if(config.layer.post_color) {
            current.post={index:0,outputs:new Map([[p.target,colored]]),complete:false};
        } else {
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
        const mask=gradingQuad(current.width,current.height,true);
        succeeded(com(device,83,'int',['uint','uint','pointer','uint'])(device,5,2,mask,48),'native coverage draw');
        }
        current.graded=colored.surface;
    } finally {
        try {succeeded(com(device,39,'int',['pointer'])(device,ptr(0)),'grading detach private depth');}catch(error){failure=error;}
        for(const [slot,target] of targets)try{succeeded(com(device,37,'int',['uint','pointer'])(device,slot,target),'grading restore target');}catch(error){failure=error;}
        try{succeeded(com(device,39,'int',['pointer'])(device,depth),'grading restore depth');}catch(error){failure=error;}
        try{if(!block.isNull())succeeded(com(block,5,'int',[])(block),'grading restore state');}catch(error){failure=error;}
        // The observed native state-block path leaves both constant banks changed.
        if(!block.isNull()) {
            try{succeeded(com(device,94,'int',['uint','pointer','uint'])(device,0,vertex,256),'grading restore vertex constants');}catch(error){failure=error;}
            try{succeeded(com(device,109,'int',['uint','pointer','uint'])(device,0,pixel,224),'grading restore pixel constants');}catch(error){failure=error;}
        }
        for(const resource of references)try{if(!resource.isNull())com(resource,2,'uint',[])(resource);}catch(error){failure=error;}
        d.pixelShader=oldPixel;d.currentTarget=oldTarget;layerDrawing=false;
        if(failure)throw failure;
    }
    const nowVp=Memory.alloc(24),nowVertex=Memory.alloc(4096),nowPixel=Memory.alloc(224*16);
    succeeded(com(device,48,'int',['pointer'])(device,nowVp),'grading verify viewport');
    succeeded(com(device,95,'int',['uint','pointer','uint'])(device,0,nowVertex,256),'grading verify vertex');
    succeeded(com(device,110,'int',['uint','pointer','uint'])(device,0,nowPixel,224),'grading verify pixel');
    const changed=[];
    for(const [name,before,after,size] of [['viewport',vp,nowVp,24],['vertex constants',vertex,nowVertex,4096],
            ['pixel constants',pixel,nowPixel,224*16]])
        if(hex(bytes(before,size))!==hex(bytes(after,size)))changed.push(name);
    for(const [id,value] of states)if(renderState(device,id)!==value)changed.push('render state '+id);
    if(changed.length)throw new Error('native grading state did not restore: '+changed.join(', '));
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

// Source-view diagnostic only: replay each current CPU quad with private input lineage.
function normalizedPostQuad(width,height,input,declaration) {
    if(input.declaration_hex!==declaration || ![32,48].includes(input.stride))throw new Error('normalized post-color declaration drift');
    const raw=input.vertices_hex.match(/../g).map(x=>parseInt(x,16)),view=new DataView(Uint8Array.from(raw).buffer);
    const quad=Memory.alloc(raw.length);quad.writeByteArray(raw);
    [[-1-1/width,1+1/height,0,0],[1-1/width,1+1/height,1,0],
        [-1-1/width,-1+1/height,0,1],[1-1/width,-1+1/height,1,1]].forEach(([x,y,u,v],i)=>{
        if(view.getFloat32(i*input.stride+8,true)!==0 || view.getFloat32(i*input.stride+12,true)!==1)
            throw new Error('normalized post-color clip depth drift');
        const oldU=view.getFloat32(i*input.stride+16,true),oldV=view.getFloat32(i*input.stride+20,true);
        if(!Number.isFinite(oldU+oldV) || (i%2===0?oldU!==0:oldU<=0) || (i<2?oldV!==0:oldV<=0))
            throw new Error('normalized post-color quad corner order drift');
        [x,y,0,1,u,v].forEach((value,j)=>quad.add(i*input.stride+j*4).writeFloat(value));
    });return quad;
}

function postColorLayer(device,d,draw,input=null) {
    const current=meshLayer,post=current.post,stage=config.layer.post_color[post.index];
    const root=Process.mainModule.base.add(config.state.engine_global_rva).readPointer();
    if(gate.resumed || gate.executing || root.add(4+config.candidate.counter_field).readU32()!==current.counter)
        throw new Error('post-color source is not held');
    if(hex(shaderProgram(device,'pixel').code)!==stage.original_hex || hex(shaderProgram(device,'vertex').code)!==stage.vertex_hex)
        throw new Error('post-color native program drift');
    const sources=screenTextureSources(device,shaderProgram(device,'pixel').assembly);
    if(JSON.stringify(sources)!==JSON.stringify(stage.sources))throw new Error('post-color native texture lineage drift');
    const vp=Memory.alloc(24),vs=Memory.alloc(4096),ps=Memory.alloc(224*16),out=Memory.alloc(4);
    const targets=[],refs=[],textures=[],samplerStates=[];let depth=ptr(0),block=ptr(0),failure=null;
    const final=post.index===config.layer.post_color.length-1;
    const width=stage.private_width??stage.width,height=stage.private_height??stage.height;
    const renderStates=gradingBlendStates(true).map(([id])=>[id,renderState(device,id)]),shaderStates=[];
    // Snapshot every sampler we can modify, including the terminal coverage pass.
    const slots=new Set(sources.map(s=>s.slot));if(final)slots.add(config.layer.grade.copy_sampler);
    layerDrawing=true;
    try {
        for(let slot=0;slot<4;++slot) {
            out.writePointer(ptr(0));const hr=com(device,38,'int',['uint','pointer'])(device,slot,out);
            if(hr===0){const r=out.readPointer();targets.push([slot,r]);refs.push(r);}
            else if(hr===(0x88760866|0))targets.push([slot,ptr(0)]);
            else if(slot===0 || hr!==(0x8876086c|0))succeeded(hr,'post GetRenderTarget');
        }
        out.writePointer(ptr(0));const hr=com(device,40,'int',['pointer'])(device,out);
        if(hr===0){depth=out.readPointer();refs.push(depth);}
        else if(hr!==(0x88760866|0))succeeded(hr,'post GetDepthStencilSurface');
        succeeded(com(device,48,'int',['pointer'])(device,vp),'post GetViewport');
        succeeded(com(device,95,'int',['uint','pointer','uint'])(device,0,vs,256),'post vertex constants');
        succeeded(com(device,110,'int',['uint','pointer','uint'])(device,0,ps,224),'post pixel constants');
        for(const slot of [93,108]) {
            out.writePointer(ptr(0));succeeded(com(device,slot,'int',['pointer'])(device,out),'post source shader');
            const r=out.readPointer();refs.push(r);shaderStates.push([slot,r]);
        }
        succeeded(com(device,90,'int',['pointer'])(device,out),'post source FVF');const sourceFvf=out.readU32();
        shaderStates.push([90,sourceFvf]);
        for(const slot of slots) {
            out.writePointer(ptr(0));succeeded(com(device,64,'int',['uint','pointer'])(device,slot,out),'post source texture');
            const texture=out.readPointer();refs.push(texture);textures.push([slot,texture]);
            for(const state of [1,2,5,6,7,11]) {
                succeeded(com(device,68,'int',['uint','uint','pointer'])(device,slot,state,out),'post source sampler');
                samplerStates.push([slot,state,out.readU32()]);
            }
        }
        out.writePointer(ptr(0));succeeded(com(device,59,'int',['uint','pointer'])(device,1,out),'post state block');
        block=out.readPointer();refs.push(block);
        const target=textureTarget(device,width,height,stage.format);
        current.extra.push(target.texture,target.surface);
        succeeded(com(device,39,'int',['pointer'])(device,ptr(0)),'post disable depth');
        for(const [slot] of targets)if(slot!==0)succeeded(com(device,37,'int',['uint','pointer'])(device,slot,ptr(0)),'post disable MRT');
        succeeded(com(device,37,'int',['uint','pointer'])(device,0,target.surface),'post private target');
        const replayVp=Memory.alloc(24);replayVp.writeByteArray(bytes(vp,24));
        if(config.layer.projection) {
            replayVp.writeU32(0);replayVp.add(4).writeU32(0);replayVp.add(8).writeU32(width);replayVp.add(12).writeU32(height);
            const uniforms=stage.vertex_uniforms;
            if(uniforms.Transform!==undefined)for(let i=0;i<16;++i)
                if(vs.add(uniforms.Transform*16+i*4).readFloat()!==(i%5===0?1:0))throw new Error('normalized copy transform is not identity');
            const write=(slot,register,values)=>{
                const data=Memory.alloc(16);values.forEach((v,i)=>data.add(i*4).writeFloat(v));
                succeeded(com(device,slot,'int',['uint','pointer','uint'])(device,register,data,1),'normalized post texel size');
            };
            if(uniforms.RenderTargetSizeRCP!==undefined)write(94,uniforms.RenderTargetSizeRCP,[1/width,1/height,1-1/width,1-1/height]);
            for(const [slot,register,bank] of [[94,uniforms.SMAAParamA,vs],[109,stage.pixel_smaa,ps]])
                if(register!==undefined && register!==null)write(slot,register,[1/current.width,1/current.height,
                    bank.add(register*16+8).readFloat(),bank.add(register*16+12).readFloat()]);
        }
        succeeded(com(device,47,'int',['pointer'])(device,replayVp),'post replay viewport');
        succeeded(com(device,43,'int',['uint','pointer','uint','uint','float','uint'])(device,0,ptr(0),1,0,1,0),'post clear');
        for(const source of sources) {
            if(stage.lookup_slots?.includes(source.slot))continue; // Observed static native SMAA lookup, never a scene input.
            const input=post.outputs.get(source.surface);
            if(!input)throw new Error('missing private post-color input');
            succeeded(com(device,65,'int',['uint','pointer'])(device,source.slot,input.texture),'post private texture');
        }
        succeeded(draw(config.layer.projection?normalizedPostQuad(width,height,input,stage.declaration_hex):null),'private native post-color draw');
        if(final) {
            const p=config.layer.grade,code=Memory.alloc(p.copy_hex.length/2);
            code.writeByteArray(p.copy_hex.match(/../g).map(x=>parseInt(x,16)));
            out.writePointer(ptr(0));succeeded(com(device,106,'int',['pointer','pointer'])(device,code,out),'post coverage shader');
            const shader=out.readPointer();current.extra.push(shader);
            succeeded(com(device,107,'int',['pointer'])(device,shader),'post coverage pixel shader');
            succeeded(com(device,92,'int',['pointer'])(device,ptr(0)),'post coverage fixed vertex');
            succeeded(com(device,89,'int',['uint'])(device,0xa0204),'post coverage FVF');
            const privateVp=Memory.alloc(24);privateVp.writeByteArray(bytes(vp,24));
            privateVp.writeU32(0);privateVp.add(4).writeU32(0);privateVp.add(8).writeU32(width);privateVp.add(12).writeU32(height);
            succeeded(com(device,47,'int',['pointer'])(device,privateVp),'post coverage viewport');
            const selector=Memory.alloc(16);[0,0,0,1].forEach((v,i)=>selector.add(i*4).writeFloat(v));
            succeeded(com(device,109,'int',['uint','pointer','uint'])(device,p.copy_constant,selector,1),'post coverage alpha');
            succeeded(com(device,65,'int',['uint','pointer'])(device,p.copy_sampler,current.texture),'post coverage texture');
            for(const [state,value] of [[1,3],[2,3],[5,1],[6,1],[7,0],[11,0]])
                succeeded(com(device,69,'int',['uint','uint','uint'])(device,p.copy_sampler,state,value),'post coverage sampler');
            for(const [state,value] of gradingBlendStates(true))succeeded(com(device,57,'int',['uint','uint'])(device,state,value),'post coverage blend');
            // Original-camera crop: final backbuffer covers only part of the HDR allocation.
            succeeded(com(device,83,'int',['uint','uint','pointer','uint'])(device,5,2,
                gradingQuad(width,height,true,width/current.width,height/current.height),48),'post coverage draw');
        }
        post.outputs.set(stage.target,target);post.index++;
        if(final){post.complete=true;current.graded=target.surface;}
    } finally {
        for(const [slot,target] of targets)try{succeeded(com(device,37,'int',['uint','pointer'])(device,slot,target),'post restore target');}catch(e){failure=e;}
        try{succeeded(com(device,39,'int',['pointer'])(device,depth),'post restore depth');}catch(e){failure=e;}
        if(!block.isNull()) {
            try{succeeded(com(block,5,'int',[])(block),'post restore state');}catch(e){failure=e;}
            try{succeeded(com(device,94,'int',['uint','pointer','uint'])(device,0,vs,256),'post restore vertex constants');}catch(e){failure=e;}
            try{succeeded(com(device,109,'int',['uint','pointer','uint'])(device,0,ps,224),'post restore pixel constants');}catch(e){failure=e;}
        }
        for(const r of refs)try{if(!r.isNull())com(r,2,'uint',[])(r);}catch(e){failure=e;}
        layerDrawing=false;if(failure)throw failure;
    }
    const verifyVp=Memory.alloc(24),verifyVs=Memory.alloc(4096),verifyPs=Memory.alloc(224*16);
    succeeded(com(device,48,'int',['pointer'])(device,verifyVp),'post verify viewport');
    succeeded(com(device,95,'int',['uint','pointer','uint'])(device,0,verifyVs,256),'post verify vertex constants');
    succeeded(com(device,110,'int',['uint','pointer','uint'])(device,0,verifyPs,224),'post verify pixel constants');
    if(hex(bytes(vp,24))!==hex(bytes(verifyVp,24)) || hex(bytes(vs,4096))!==hex(bytes(verifyVs,4096)) ||
            hex(bytes(ps,224*16))!==hex(bytes(verifyPs,224*16)))throw new Error('post-color state did not restore');
    for(const [slot,expected] of textures) {
        out.writePointer(ptr(0));succeeded(com(device,64,'int',['uint','pointer'])(device,slot,out),'post verify texture');
        const r=out.readPointer();try{if(!r.equals(expected))throw new Error('post-color texture did not restore');}
        finally{if(!r.isNull())com(r,2,'uint',[])(r);}
    }
    for(const [id,value] of renderStates)if(renderState(device,id)!==value)throw new Error('post-color render state did not restore');
    for(const [slot,state,value] of samplerStates) {
        succeeded(com(device,68,'int',['uint','uint','pointer'])(device,slot,state,out),'post verify sampler');
        if(out.readU32()!==value)throw new Error('post-color sampler did not restore');
    }
    for(const [slot,expected] of shaderStates) {
        out.writePointer(ptr(0));succeeded(com(device,slot,'int',['pointer'])(device,out),'post verify shader/FVF');
        if(slot===90){if(out.readU32()!==expected)throw new Error('post-color FVF did not restore');continue;}
        const r=out.readPointer();try{if(!r.equals(expected))throw new Error('post-color shader did not restore');}
        finally{if(!r.isNull())com(r,2,'uint',[])(r);}
    }
    for(const [slot,expected] of targets) {
        out.writePointer(ptr(0));const hr=com(device,38,'int',['uint','pointer'])(device,slot,out);
        if(expected.isNull() && hr===(0x88760866|0))continue;
        succeeded(hr,'post verify target');const r=out.readPointer();
        try{if(!r.equals(expected))throw new Error('post-color target did not restore');}finally{if(!r.isNull())com(r,2,'uint',[])(r);}
    }
    out.writePointer(ptr(0));const hr=com(device,40,'int',['pointer'])(device,out);
    if(!(depth.isNull() && hr===(0x88760866|0))) {
        succeeded(hr,'post verify depth');const r=out.readPointer();
        try{if(!r.equals(depth))throw new Error('post-color depth did not restore');}finally{if(!r.isNull())com(r,2,'uint',[])(r);}
    }
    if(root.add(4+config.candidate.counter_field).readU32()!==current.counter)throw new Error('source advanced during post-color replay');
}
