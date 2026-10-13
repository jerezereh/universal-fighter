// Bounded render-thread interop probe. No shared handle or producer capability.
const on12Ids = {
    device9: 'e7fda234-b589-4049-940d-8878977531c8',
    device12: '189819f1-1db6-4b57-be54-1821339b85f7',
    queue: '0ec870a6-5d7e-4c22-8cfc-5baae07616ed',
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
let on12Probed=false;
function probeOn12Resource(device, texture) {
    if(on12Probed)return null;
    on12Probed=true;
    const held=[];
    let on12=ptr(0), resource=ptr(0), returned=false, fence=ptr(0), queue=ptr(0), signaled=false;
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
        succeeded(com(d12,36,'int',['uint64','uint','pointer','pointer'])(d12,uint64(0),0,on12Guid(on12Ids.fence),cell),'CreateFence');
        fence=keep(cell,'D3D12 fence');
        cell=on12Cell();
        succeeded(com(on12,4,'int',['pointer','pointer','pointer','pointer'])(on12,texture,queue,on12Guid(on12Ids.resource),cell),'UnwrapUnderlyingResource');
        resource=keep(cell,'unwrapped fighter texture');
        succeeded(com(queue,14,'int',['pointer','uint64'])(queue,fence,uint64(1)),'Queue.Signal');
        signaled=true;
        const value=Memory.alloc(8), fences=on12Cell();value.writeU64(uint64(1));fences.writePointer(fence);
        succeeded(com(on12,5,'int',['pointer','uint','pointer','pointer'])(on12,texture,1,value,fences),'ReturnUnderlyingResource');
        returned=true;
        const until=Date.now()+1000;
        while(com(fence,8,'uint64',[])(fence).toNumber()<1&&Date.now()<until)Thread.sleep(0.001);
        if(com(fence,8,'uint64',[])(fence).toNumber()<1)throw new Error('On12 fence did not complete');
        return {unwrapped:true,returned:true,source:'private graded fighter texture'};
    } finally {
        if(!resource.isNull()&&!returned)
            try {
                const value=Memory.alloc(8), fences=on12Cell();value.writeU64(uint64(1));fences.writePointer(fence);
                com(on12,5,'int',['pointer','uint','pointer','pointer'])(on12,texture,
                    signaled?1:0,signaled?value:ptr(0),signaled?fences:ptr(0));
            }
            catch (_) { /* preserve the original failure for the bounded diagnostic */ }
        for(const object of held.reverse())com(object,2,'uint',[])(object);
    }
}
