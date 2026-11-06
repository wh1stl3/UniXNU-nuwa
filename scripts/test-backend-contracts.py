"""Execute pinned native instruction slices with explicit object/external-call fixtures."""
import hashlib, importlib.util, json, struct, sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(R/'out/python-tools'),str(R/'scripts')]
import unicorn as U
from unicorn import arm64_const as A

def main():
    output=Path(sys.argv[1]); assert not output.exists()
    spec=importlib.util.spec_from_file_location('contract_builder',R/'scripts/build-kernel-entry-probe.py')
    B=importlib.util.module_from_spec(spec);sys.modules[spec.name]=B;spec.loader.exec_module(B)
    build=json.loads((R/'reports/kernel-entry-probe/2026-10-30-probe59-root-progress-r1/build.json').read_bytes())
    raw=(R/build['candidate']['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==build['candidate']['sha256']
    m=B.macho(raw); checks=[]
    def setup(start,end):
        u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM)
        base=start&~4095;size=((end-base+4095)//4096)*4096
        u.mem_map(base,size);off=B.backed(m,start);u.mem_write(start,raw[off:off+end-start])
        u.mem_map(0x100000,0x10000);u.reg_write(A.UC_ARM64_REG_SP,0x108000)
        return u
    def reg(u,n,value):u.reg_write(getattr(A,'UC_ARM64_REG_X'+str(n)),value)
    def q(u,a,v):u.mem_write(a,struct.pack('<Q',v))
    def readq(u,a):return struct.unpack('<Q',u.mem_read(a,8))[0]
    def done(name):checks.append(dict(name=name,passed=True))
    # Execute both actual mount-private device-vnode selection branches.
    for fallback in (False,True):
        u=setup(0xfffffff00519467c,0xfffffff005194698)
        private,container,chain,vnode,args=0x101000,0x102000,0x103000,0x104000,0x105000
        reg(u,19,private);reg(u,21,args)
        q(u,private+0x2e0,0 if fallback else container)
        q(u,private+0xd0,container-0xc8)
        q(u,container,chain);q(u,chain,vnode)
        u.emu_start(0xfffffff00519467c,0xfffffff005194698,count=20)
        assert u.reg_read(A.UC_ARM64_REG_X0)==vnode and u.reg_read(A.UC_ARM64_REG_X1)==args
        done('device-vnode-'+('fallback' if fallback else 'primary'))
    # Native setfilter saves prior callback before publishing the new pair.
    for callback in (0,0xfffffff005198638):
        for save_old in (False,True):
            u=setup(0xfffffff00742b1dc,0xfffffff00742b228)
            bp,ctx,old=0x101000,0x102000,0x103000
            q(u,bp+0x80,0x104000);q(u,bp+0xd0,0x105000)
            u.mem_write(bp+0x50,struct.pack('<I',1));u.mem_write(bp+0x4c,struct.pack('<I',0x800123))
            for n,v in enumerate((bp,callback,ctx,old if save_old else 0,old+8 if save_old else 0)):reg(u,n,v)
            reg(u,30,0x10f000);u.emu_start(0xfffffff00742b1dc,0x10f000,count=30)
            assert readq(u,bp+0x80)==callback and readq(u,bp+0xd0)==ctx
            flags=struct.unpack('<I',u.mem_read(bp+0x4c,4))[0]
            assert flags==(0x800123 | (1<<22) if callback else 0x800123)
            if save_old:assert readq(u,old)==0x104000 and readq(u,old+8)==0x105000
            done(f'setfilter:{bool(callback)}:{save_old}')
    # Device major extraction and 56-byte bdevsw stride, actual final target.
    for major in (0,7,255):
        u=setup(0xfffffff007476f60,0xfffffff007476f7c)
        table=0xfffffff007a0d4c8;u.mem_map(table&~4095,0x5000)
        target=0xfffffff00741fcc8;bp=0x101000
        q(u,table+major*0x38+0x10,target);reg(u,20,(major<<24)|0x123456);reg(u,19,bp)
        u.emu_start(0xfffffff007476f60,0xfffffff007476f7c,count=20)
        assert u.reg_read(A.UC_ARM64_REG_X8)==target and u.reg_read(A.UC_ARM64_REG_X0)==bp
        done(f'device-major:{major}')
    # buf_strategy publishes only b_vnop_vp, dispatches via the DEVICE v_op,
    # and clears that transient field on return without replacing file b_vp.
    for result in (0,5):
        u=setup(0xfffffff00742b864,0xfffffff00742b898)
        bp,vp,filevp,args,ops=0x101000,0x102000,0x103000,0x104000,0x105000
        descriptor=0xfffffff0079feca8;u.mem_map(descriptor&~4095,4096)
        index=struct.unpack('<i',raw[B.backed(m,descriptor):B.backed(m,descriptor)+4])[0]
        assert 0<=index<256;u.mem_write(descriptor,struct.pack('<i',index))
        q(u,bp+0x88,filevp);q(u,vp+0xd0,ops);q(u,ops+8*index,0x10e000)
        reg(u,19,bp);reg(u,20,filevp);reg(u,21,args);reg(u,22,vp);reg(u,23,0x4000)
        seen=[]
        def device_dispatch(uc,pc,size,data):
            if pc==0xfffffff00742b884:
                assert uc.reg_read(A.UC_ARM64_REG_X8)==0x10e000
                assert uc.reg_read(A.UC_ARM64_REG_X0)==args
                assert readq(uc,bp+0x120)==vp and readq(uc,bp+0x88)==filevp
                seen.append(pc);reg(uc,0,result);uc.reg_write(A.UC_ARM64_REG_PC,pc+4)
        u.hook_add(U.UC_HOOK_CODE,device_dispatch)
        u.emu_start(0xfffffff00742b864,0xfffffff00742b898,count=40)
        assert seen and readq(u,bp+0x120)==0 and readq(u,bp+0x88)==filevp
        assert u.reg_read(A.UC_ARM64_REG_X25)==result
        done(f'buf-strategy-device-return:{result}')
    # Actual APFS completion tail copies old callback/argument before freeing ctx.
    # The free and atomic helpers are explicit fixtures; poison ctx after free.
    for old_callback in (0,0x10e000):
        u=setup(0xfffffff00519877c,0xfffffff0051987d0)
        bp,ctx,arg=0x101000,0x102000,0x103000
        reg(u,19,bp);reg(u,20,ctx);q(u,ctx,old_callback);q(u,ctx+8,arg)
        events=[];freed=[False]
        def on_read(uc,access,address,size,value,data):
            assert not(freed[0] and address<ctx+0x38 and address+size>ctx),'read freed context'
        def on_code(uc,pc,size,data):
            if pc==0xfffffff00519878c:
                assert uc.reg_read(A.UC_ARM64_REG_X1)==ctx
                events.append('free');uc.mem_write(ctx,b'\xdd'*0x38);freed[0]=True
                uc.reg_write(A.UC_ARM64_REG_PC,pc+4)
            elif pc==0xfffffff00519879c:
                events.append('account');uc.reg_write(A.UC_ARM64_REG_PC,pc+4)
            elif pc==0xfffffff0051987ac:
                assert uc.reg_read(A.UC_ARM64_REG_X22)==old_callback
                assert uc.reg_read(A.UC_ARM64_REG_X0)==bp and uc.reg_read(A.UC_ARM64_REG_X1)==arg
                events.append('old-callback');uc.reg_write(A.UC_ARM64_REG_PC,pc+4)
        u.hook_add(U.UC_HOOK_MEM_READ,on_read);u.hook_add(U.UC_HOOK_CODE,on_code)
        u.emu_start(0xfffffff00519877c,0xfffffff0051987b0,count=30)
        assert events==['free','account']+(['old-callback'] if old_callback else [])
        done(f'filter-release:{bool(old_callback)}')
    # Native biodone dispatch: filter runs before B_DONE; B_CALL runs after it.
    # Stop immediately after callback: async release can invalidate bp later.
    for callout in (False,True):
        u=setup(0xfffffff00742ba90,0xfffffff00742bb30)
        bp,callback,arg=0x101000,0x10e000,0x103000
        reg(u,19,bp);q(u,bp+0x80,callback);q(u,bp+0xd0,arg)
        flags=(1<<23) if callout else (1<<22)
        u.mem_write(bp+0x4c,struct.pack('<I',flags));events=[]
        def dispatch(uc,pc,size,data):
            if pc in (0xfffffff00742babc,0xfffffff00742bb2c):
                assert uc.reg_read(A.UC_ARM64_REG_X8)==callback
                assert uc.reg_read(A.UC_ARM64_REG_X0)==bp and uc.reg_read(A.UC_ARM64_REG_X1)==arg
                assert readq(uc,bp+0x80)==0 and readq(uc,bp+0xd0)==0
                actual=struct.unpack('<I',uc.mem_read(bp+0x4c,4))[0]
                assert actual==((1<<17) if callout else 0)
                events.append(pc);uc.emu_stop()
        u.hook_add(U.UC_HOOK_CODE,dispatch)
        u.emu_start(0xfffffff00742ba90,0xfffffff00742bb30,count=40)
        assert events==[0xfffffff00742bb2c if callout else 0xfffffff00742babc]
        done(f'biodone-dispatch:{callout}')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(dict(kernel_sha256=build['candidate']['sha256'],checks=checks,device_accessed=False,limitations=['Native instruction slices only; explicit synthetic objects and external calls','No APFS execution, live vnode validity, request pairing or hardware proof','No conclusion about live callback ownership after invoking old callback']),indent=2)+'\n',encoding='utf-8')
    print(f'{len(checks)} native contract checks passed: {output}')

if __name__=='__main__':main()
