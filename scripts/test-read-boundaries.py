"""Execute native exec-header -> vn_rdwr -> vn_rdwr_64 -> VNOP_READ.

MAC and filesystem bodies are explicit API models; this is a Unicorn boundary
regression, never a hardware result. Native wrappers/branches and probes execute.
"""
import argparse,importlib.util,json,struct,sys,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
import read_boundary_sites as R
spec=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build-kernel-entry-probe.py')
B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)
STACK=0xf00000;FB=0xb8000000;ROW=5760
MODES=('success','mac-denied','read-error','mac-pending','dispatch-pending','swap','noauth','foreign-thread','foreign-frame','repeat','no-video')

def run(raw,b,mode,reference=False,capture=None,request=4096,ioflags=None,remaining=0,aresid=True,events=None):
    if reference:
        # Same fixed image layout, restore only this path's displaced native
        # instructions. Probe code/data remains mapped but never executes.
        raw=bytearray(raw)
        sites={R.FIRST,R.FIRST+4}|{pc+off for pc,_,_ in R.CALLS for off in (0,4)}
        for item in b['patches']:
            if item.get('va') is not None and int(item['va'],16) in sites:
                start=item['file_offset'];before=bytes.fromhex(item['before']);raw[start:start+len(before)]=before
        raw=bytes(raw)
    m=B.macho(raw);sy=m['symbols'];ps=b['probe']['symbols']
    base=min(s['va'] for s in m['segments'] if s['size']);end=max(s['va']+s['size'] for s in m['segments'])
    u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(base,B.align(end-base));u.mem_map(STACK,0x10000);u.mem_map(FB,0x1200000)
    for s in m['segments']:
        if s['filesize']:u.mem_write(s['va'],raw[s['fileoff']:s['fileoff']+s['filesize']])
    u.mem_write(int(ps['probe_scratch'],16),struct.pack('<QQ',0 if mode=='no-video' else FB,ROW))
    state=int(ps['probe_read_state'],16);flags=int(ps['probe_flags'],16)
    callback=STACK+0x1000;vp=STACK+0x4000;ops=STACK+0x5000
    u.mem_write(vp+0xd0,struct.pack('<Q',ops));opindex=struct.unpack('<i',u.mem_read(sy['_vnop_read_desc'],4))[0]
    u.mem_write(ops+8*opindex,struct.pack('<Q',callback))
    calls=[];resids=[];seen=[];bad=[];native_writes=[];native_accesses=set()
    def watch(u,pc,size,data):
        if pc==(R.FIRST+4 if reference else int(ps['probe_dense_769bf94_replay'],16)):u.emu_stop();return
        if pc in [c for c,_,_ in R.CALLS]+[c+4 for c,_,_ in R.CALLS]:seen.append(hex(pc))
        if pc==sy['_vn_rdwr'] and mode=='foreign-thread':u.reg_write(UC_ARM64_REG_TPIDR_EL1,0x2222)
        if pc==sy['_vn_rdwr_64'] and mode=='foreign-frame':u.mem_write(state+32,struct.pack('<Q',STACK+0x1234))
        fn=next((name for name in ('_uio_createwithbuffer','_uio_addiov','_mac_vnode_check_read','_vnode_isswap','_uio_resid','_vn_read_swapfile') if sy[name]==pc),None)
        if pc==callback:fn='filesystem-callback'
        if fn is None:return
        calls.append(fn)
        if events is not None:
            item=dict(function=fn,args=[u.reg_read(getattr(sys.modules[__name__],f'UC_ARM64_REG_X{i}')) for i in range(8)])
            if fn=='filesystem-callback':item['vnop_args']=bytes(u.mem_read(item['args'][0],40)).hex()
            events.append(item)
        if (fn=='_mac_vnode_check_read' and mode=='mac-pending') or (fn=='filesystem-callback' and mode=='dispatch-pending'):u.emu_stop();return
        if fn=='_uio_createwithbuffer':value=STACK+0x3000
        elif fn=='_mac_vnode_check_read':value=13 if mode=='mac-denied' else 0
        elif fn=='_vnode_isswap':value=int(mode=='swap')
        elif fn in ('filesystem-callback','_vn_read_swapfile'):value=5 if mode=='read-error' else 0
        elif fn=='_uio_resid':resids.append(pc);value=request if len(resids)==1 and mode not in ('mac-denied','swap') else remaining
        else:value=0
        u.reg_write(UC_ARM64_REG_X0,value);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
    u.hook_add(U.UC_HOOK_CODE,watch)
    u.hook_add(U.UC_HOOK_MEM_INVALID,lambda u,a,p,n,v,d:bad.append(hex(p)) or False)
    # Reject any probe write to the native text/data globals, vnode or op table.
    def writes(u,a,p,n,v,d):
        pc=u.reg_read(UC_ARM64_REG_PC)
        if int(ps['probe_entry'],16)<=pc<end and (base<=p<int(ps['probe_entry'],16) or vp<=p<ops+0x1000):native_writes.append(hex(p))
        if capture is not None and not int(ps['probe_entry'],16)<=pc<end:native_accesses.add((p,n))
    u.hook_add(U.UC_HOOK_MEM_WRITE,writes)
    outcomes=[]
    for attempt in range(2 if mode=='repeat' else 1):
        # Seed a stale later marker: every header call must clear it and reset returns.
        u.mem_write(flags+128+275,b'\x01');u.mem_write(state+96,struct.pack('<Q',0xdeadbeef))
        if mode!='no-video':u.mem_write(FB+784*ROW+(832+9*48)*4,struct.pack('<I',0xff00ff00))
        for i in range(31):u.reg_write(getattr(sys.modules[__name__],f'UC_ARM64_REG_X{i}'),0x101000+i*0x100)
        u.reg_write(UC_ARM64_REG_X0,0);u.reg_write(UC_ARM64_REG_X1,vp)
        u.reg_write(UC_ARM64_REG_X2,STACK+0x6000);u.reg_write(UC_ARM64_REG_X3,request)
        u.reg_write(UC_ARM64_REG_X4,0);u.reg_write(UC_ARM64_REG_X5,2)
        u.reg_write(UC_ARM64_REG_X6,(0x8000 if mode=='noauth' else 0) if ioflags is None else ioflags);u.reg_write(UC_ARM64_REG_X7,STACK+0x2800)
        u.reg_write(UC_ARM64_REG_X29,STACK+0x9000);u.reg_write(UC_ARM64_REG_SP,STACK+0x8000)
        u.reg_write(UC_ARM64_REG_TPIDR_EL1,0x1111);u.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20)
        u.mem_write(STACK+0x8000,struct.pack('<QQ',STACK+0x2000 if aresid else 0,STACK+0x2900))
        calls.clear();resids.clear();native_accesses.clear();u.emu_start(R.FIRST,0,count=2000000)
        if capture is not None:
            sp=u.reg_read(UC_ARM64_REG_SP);pc=u.reg_read(UC_ARM64_REG_PC)
            assert not bad,(mode,'invalid native/probe access',bad)
            capture.append(dict(registers=[hex(u.reg_read(getattr(sys.modules[__name__],f'UC_ARM64_REG_X{i}'))) for i in range(31)],simd=[hex(u.reg_read(getattr(sys.modules[__name__],f'UC_ARM64_REG_Q{i}'))) for i in range(32)],sp=hex(sp),nzcv=hex(u.reg_read(UC_ARM64_REG_NZCV)),fpcr=hex(u.reg_read(UC_ARM64_REG_FPCR)),fpsr=hex(u.reg_read(UC_ARM64_REG_FPSR)),tpidr_el1=hex(u.reg_read(UC_ARM64_REG_TPIDR_EL1)),pc=hex(R.FIRST+4 if pc==int(ps['probe_dense_769bf94_replay'],16) else pc),caller_stack_sha256=hashlib.sha256(u.mem_read(STACK+0x8000,0x8000)).hexdigest(),residual=bytes(u.mem_read(STACK+0x2000,8)).hex(),live_native_memory={hex(p)+':'+str(n):bytes(u.mem_read(p,n)).hex() for p,n in sorted(native_accesses) if p>=sp or p==STACK+0x2000},calls=list(calls)))
        if reference:
            outcomes.append(dict(attempt=attempt+1,pc=hex(u.reg_read(UC_ARM64_REG_PC))))
            continue
        st=struct.unpack('<14Q',u.mem_read(state,R.STATE_BYTES));lit=[]
        for i in range(266,276):
            x=832+(i-266)*48;y=784
            pixel=struct.unpack('<I',u.mem_read(FB+y*ROW+x*4,4))[0]
            if pixel:lit.append(i)
        expected={266,267,268,269,270,271,272,273}
        if mode=='mac-denied':expected={266,267,268,269}
        if mode=='mac-pending':expected={266,268}
        if mode=='dispatch-pending':expected={266,268,269,270,272}
        if mode=='swap':expected={266,267,268,269,274,275}
        if mode=='noauth':expected-={268,269}
        if mode in ('foreign-thread','no-video'):expected=set()
        if mode=='foreign-frame':expected={266,267}
        assert set(lit)==expected,(mode,lit,expected)
        pending=mode in ('mac-pending','dispatch-pending')
        assert st[0]==int(pending),(mode,'scope active',st)
        if not pending:
            assert u.reg_read(UC_ARM64_REG_X0)==(13 if mode=='mac-denied' else 5 if mode=='read-error' else 0),(mode,'native errno lost')
            assert u.reg_read(UC_ARM64_REG_SP)==STACK+0x8000,(mode,'native stack lost')
        if mode=='mac-denied':assert 'filesystem-callback' not in calls and st[9]==13
        if mode=='noauth':assert '_mac_vnode_check_read' not in calls
        if mode not in ('foreign-thread','foreign-frame'):
            assert st[12]==(0 if mode=='swap' else (1<<64)-1),(mode,'stale swap return retained',st)
        assert not bad and not native_writes,(bad,native_writes)
        outcomes.append(dict(attempt=attempt+1,lit=lit,state=[hex(x) for x in st],calls=list(calls),pc=hex(u.reg_read(UC_ARM64_REG_PC))))
    return dict(name=mode,passed=True,attempts=outcomes)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    b=json.loads(a.build.read_text());raw=(ROOT/b['candidate']['path']).read_bytes();assert B.sha(raw)==b['candidate']['sha256']
    original=B.INPUT.read_bytes();assert B.sha(original)==B.EXPECTED
    m=B.macho(original)
    # Prologue/frame geometry and actual current_thread instruction pin the scoping.
    for fn,expected in (('_current_thread','80d038d5c0035fd6'),('_vn_rdwr','4302f837'),('_vn_rdwr_64','ffc302d1'),('_VNOP_READ','ffc301d1')):
        off=B.backed(m,m['symbols'][fn]);assert original[off:off+len(bytes.fromhex(expected))].hex()==expected
    checks=[run(raw,b,mode) for mode in MODES]
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(dict(scope=__doc__,candidate_sha256=b['candidate']['sha256'],source_sha256=B.sha((ROOT/'scripts/read_boundary_sites.py').read_bytes()),checks=checks,device_accessed=False,real_filesystem_body_executed=False,real_mac_policy_executed=False),indent=2)+'\n',newline='\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()