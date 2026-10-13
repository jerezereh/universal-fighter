// Bounded render-thread interop probe. No producer capability.
const on12Ids = {
    device9: 'e7fda234-b589-4049-940d-8878977531c8',
    device12: '189819f1-1db6-4b57-be54-1821339b85f7',
    queue: '0ec870a6-5d7e-4c22-8cfc-5baae07616ed',
    allocator: '6102dee4-af59-4b09-b999-b44d73f09b24',
    list: '5b160d0f-ac1b-4185-8ba8-b3ae42a5a455',
    resource: '696442be-a72e-4059-bc79-5b5c98040fad',
    fence: '0a753dcf-c4d8-4b91-adf6-be5a60d95a76'
};
function on12Guid(id) {
    const h=id.replace(/-/g,''), p=Memory.alloc(16);
    p.writeU32(parseInt(h.slice(0,8),16));
    p.add(4).writeU16(parseInt(h.slice(8,12),16));
    p.add(6).writeU16(parseInt(h.slice(12,16),16));
    for(let i=0;i<8;i++)p.add(8+i).writeU8(parseInt(h.slice(16+i*2,18+i*2),16));
    return p;
}
function on12Cell() { const p=Memory.alloc(4);p.writePointer(ptr(0));return p; }
const on12Probed=new Set();
const on12Outputs=[];
function closeOn12Output(output) {
    const close=new NativeFunction(Module.getGlobalExportByName('CloseHandle'),'int',['pointer'],'stdcall');
    for(const object of output.held.reverse())com(object,2,'uint',[])(object);
    for(const handle of output.handles)close(handle);
}
function probeOn12Resource(device, texture, width, height, retain, requestIndex) {
    if(on12Probed.has(requestIndex) || on12Probed.size>=config.layer.on12_frames)return null;
    on12Probed.add(requestIndex);
    const held=[],handles=[];
    let on12=ptr(0), resource=ptr(0), returned=false, fence=ptr(0), queue=ptr(0), signaled=false, keepOutput=false;
    const keep=(cell,name)=>{const p=cell.readPointer();if(p.isNull())throw new Error(name+' returned null');held.push(p);return p;};
    try {
        let cell=on12Cell();
        succeeded(com(device,0,'int',['pointer','pointer'])(device,on12Guid(on12Ids.device9),cell),'On12 QueryInterface');
        on12=keep(cell,'On12 device');
        cell=on12Cell();
        succeeded(com(on12,3,'int',['pointer','pointer'])(on12,on12Guid(on12Ids.device12),cell),'On12 GetD3D12Device');
        const d12=keep(cell,'D3D12 device'), desc=Memory.alloc(16);
        desc.writeByteArray(new Array(16).fill(0));
        cell=on12Cell();
        succeeded(com(d12,8,'int',['pointer','pointer','pointer'])(d12,desc,on12Guid(on12Ids.queue),cell),'CreateCommandQueue');
        queue=keep(cell,'D3D12 queue');
        cell=on12Cell();
        succeeded(com(d12,36,'int',['uint64','uint','pointer','pointer'])(d12,uint64(0),1,on12Guid(on12Ids.fence),cell),'CreateFence');
        fence=keep(cell,'D3D12 fence');
        cell=on12Cell();
        succeeded(com(d12,9,'int',['uint','pointer','pointer'])(d12,0,on12Guid(on12Ids.allocator),cell),'CreateCommandAllocator');
        const allocator=keep(cell,'D3D12 allocator');
        cell=on12Cell();
        succeeded(com(d12,12,'int',['uint','uint','pointer','pointer','pointer','pointer'])(
            d12,0,0,allocator,ptr(0),on12Guid(on12Ids.list),cell),'CreateCommandList');
        const list=keep(cell,'D3D12 list');
        const heap=Memory.alloc(20);heap.writeByteArray(new Array(20).fill(0));heap.writeU32(1);
        const resourceDesc=Memory.alloc(56);resourceDesc.writeByteArray(new Array(56).fill(0));
        resourceDesc.writeU32(3);resourceDesc.add(16).writeU64(uint64(width));resourceDesc.add(24).writeU32(height);
        resourceDesc.add(28).writeU16(1);resourceDesc.add(30).writeU16(1);resourceDesc.add(32).writeU32(87);
        resourceDesc.add(36).writeU32(1);resourceDesc.add(48).writeU32(0x21);
        cell=on12Cell();
        succeeded(com(d12,27,'int',['pointer','uint','pointer','uint','pointer','pointer','pointer'])(
            d12,heap,1,resourceDesc,0,ptr(0),on12Guid(on12Ids.resource),cell),'CreateCommittedResource');
        const output=keep(cell,'shared output texture');
        cell=on12Cell();
        const name='sign-probe-'+Process.id+'-'+Date.now()+'-'+requestIndex;
        succeeded(com(d12,31,'int',['pointer','pointer','uint','pointer','pointer'])(
            d12,output,ptr(0),0x10000000,Memory.allocUtf16String(name+'-memory'),cell),'CreateSharedHandle');
        if(cell.readPointer().isNull())throw new Error('shared handle returned null');
        handles.push(cell.readPointer());
        if(retain) {
            cell=on12Cell();
            succeeded(com(d12,31,'int',['pointer','pointer','uint','pointer','pointer'])(
                d12,fence,ptr(0),0x10000000,Memory.allocUtf16String(name+'-fence'),cell),'CreateSharedHandle(fence)');
            if(cell.readPointer().isNull())throw new Error('shared fence handle returned null');
            handles.push(cell.readPointer());
        }
        cell=on12Cell();
        succeeded(com(on12,4,'int',['pointer','pointer','pointer','pointer'])(on12,texture,queue,on12Guid(on12Ids.resource),cell),'UnwrapUnderlyingResource');
        resource=keep(cell,'unwrapped fighter texture');
        com(list,17,'void',['pointer','pointer'])(list,output,resource);
        succeeded(com(list,9,'int',[])(list),'CommandList.Close');
        const lists=on12Cell();lists.writePointer(list);
        com(queue,10,'void',['uint','pointer'])(queue,1,lists);
        succeeded(com(queue,14,'int',['pointer','uint64'])(queue,fence,uint64(1)),'Queue.Signal');
        signaled=true;
        const value=Memory.alloc(8), fences=on12Cell();value.writeU64(uint64(1));fences.writePointer(fence);
        succeeded(com(on12,5,'int',['pointer','uint','pointer','pointer'])(on12,texture,1,value,fences),'ReturnUnderlyingResource');
        returned=true;
        const until=Date.now()+1000;
        while(com(fence,8,'uint64',[])(fence).toNumber()<1&&Date.now()<until)Thread.sleep(0.001);
        if(com(fence,8,'uint64',[])(fence).toNumber()<1)throw new Error('On12 fence did not complete');
        if(retain) {on12Outputs.push({held,handles});keepOutput=true;}
        return {unwrapped:true,returned:true,copied:true,shared_handle_created:true,
            source:'private graded fighter texture',
            ...(retain?{memory:name+'-memory',fence:name+'-fence',value:1,width,height}: {})};
    } finally {
        if(!resource.isNull()&&!returned)
            try {
                const value=Memory.alloc(8), fences=on12Cell();value.writeU64(uint64(1));fences.writePointer(fence);
                com(on12,5,'int',['pointer','uint','pointer','pointer'])(on12,texture,
                    signaled?1:0,signaled?value:ptr(0),signaled?fences:ptr(0));
            }
            catch (_) { /* preserve the original failure for the bounded diagnostic */ }
        if(!keepOutput)closeOn12Output({held,handles});
    }
}
