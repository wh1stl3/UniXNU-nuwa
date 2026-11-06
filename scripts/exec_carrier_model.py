"""Strict read-only CHECK4 instruction harness. Runtime objects are model memory."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import unicorn as U
from unicorn.arm64_const import *
import flush_trace_inputs as t

EXPECTED = '551a0cf621b5fca221be267ae25aba142d5aaa904cccdd5310dfb53b88474ec3'
BASE = 0xfffffff000000000
MEM = 0x20000000
THREAD, PROC, IMG, NDP, ATTR = [MEM+x for x in (0x1000,0x4000,0x8000,0xa000,0xc000)]
VNODE, MOUNT, CTX, OPS, HEADER = [MEM+x for x in (0x10000,0x12000,0x15000,0x16000,0x18000)]
STACK, SENTINEL, VNOP = MEM+0x38000, MEM+0x3f000, MEM+0x3e000

class Carrier:
    def __init__(self, work):
        self.raw = (work/'kernel.macho').read_bytes()
        assert hashlib.sha256(self.raw).hexdigest() == EXPECTED
        self.proof = json.loads((work/'kernel-proof.json').read_bytes())
        self.b = t.builder(); self.m = self.b.macho(self.raw); self.sy = self.m['symbols']

class Machine:
    def __init__(self, carrier):
        self.c=carrier; self.u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM)
        self.u.mem_map(MEM,0x40000)
        self.pages=set(); self.callbacks={}; self.visits=Counter(); self.events=[]; self.draws=[]
        self.recent=[]; self.stopped=None
        self.u.hook_add(U.UC_HOOK_MEM_UNMAPPED,self.fault)
        self.u.hook_add(U.UC_HOOK_CODE,self.hook)
        self.u.reg_write(UC_ARM64_REG_SP,STACK)
        self.u.reg_write(UC_ARM64_REG_LR,SENTINEL)
        self.u.reg_write(UC_ARM64_REG_TPIDR_EL1,THREAD)
        self.u.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20)
        self.callbacks[SENTINEL]=lambda: self.stop('return')
        self.callbacks[carrier.proof['symbols']['draw']]=self.draw
    def fault(self,u,access,addr,size,value,data):
        page=addr&~4095
        seg=next((s for s in self.c.m['segments'] if s['va']<=page<s['va']+s['size']),None)
        assert seg is not None,('unexpected unmapped address',hex(addr),self.recent[-12:])
        n=max(0,min(4096,seg['filesize']-page+seg['va'])); off=seg['fileoff']+page-seg['va']
        u.mem_map(page,4096);u.mem_write(page,self.c.raw[off:off+n]+bytes(4096-n));self.pages.add(page)
        return True
    def ensure(self,addr):
        if not MEM<=addr<MEM+0x40000 and addr&~4095 not in self.pages:self.fault(self.u,0,addr,1,0,None)
    def put(self,addr,value,n=8):
        self.ensure(addr);self.u.mem_write(addr,(value&((1<<(n*8))-1)).to_bytes(n,'little'))
    def get(self,addr,n=8):
        self.ensure(addr);return int.from_bytes(self.u.mem_read(addr,n),'little')
    def x(self,n,value=None):
        reg=UC_ARM64_REG_X0+n if n<29 else (UC_ARM64_REG_X29 if n==29 else UC_ARM64_REG_LR)
        if value is None:return self.u.reg_read(reg)
        self.u.reg_write(reg,value&((1<<64)-1))
    def ret(self,value=0):
        self.x(0,value);self.u.reg_write(UC_ARM64_REG_PC,self.x(30))
    def stop(self,reason):self.stopped=reason;self.u.emu_stop()
    def draw(self):self.draws.append([self.x(0),self.x(1)]);self.ret(self.x(0))
    def stub(self,name,fn):self.callbacks[self.c.sy[name]]=fn
    def hook(self,u,pc,size,data):
        self.visits[pc]+=1;self.recent.append(hex(pc));self.recent[:]=self.recent[-32:]
        if pc in self.callbacks:self.callbacks[pc]()
    def run(self,start,count=100000):
        self.u.emu_start(self.c.sy[start] if isinstance(start,str) else start,0,count=count)
        assert self.stopped,('instruction budget exhausted',self.recent)
    def record(self,name):
        return dict(name=name,stop=self.stopped,result=self.x(0)&0xffffffff,draws=self.draws,
                    events=self.events,executed_instructions=sum(self.visits.values()),
                    unique_instructions=len(self.visits),visited_symbols=[k for k,v in self.c.sy.items() if v in self.visits])

def environment(c, flags=0, sleep='stop', getattr_error=0, size=4096, mode=0o755, supported=True):
    m=Machine(c); m.locked=False
    m.put(PROC+0x458,flags,4);m.put(IMG+0x28,ATTR);m.put(IMG+0x30,ATTR+0x400)
    m.put(IMG+0x40,HEADER);m.put(IMG+0x2a8,CTX);m.put(NDP+0x28,VNODE)
    m.put(VNODE+0x70,1,2);m.put(VNODE+0xd8,MOUNT);m.put(VNODE+0xd0,OPS)
    m.put(MOUNT+0x84,4096,4);m.put(CTX,THREAD);m.put(CTX+8,MEM+0x17000)
    desc=c.sy['_vnop_getattr_desc'];index=m.get(desc,4);assert index<256
    m.put(OPS+index*8,VNOP)
    state=c.proof['targets']['coarse_state'];m.put(state+104,THREAD)
    def lock():
        assert m.x(0)==PROC+0x50 and not m.locked;m.locked=True;m.events.append('mutex acquire');m.ret()
    def unlock():
        assert m.x(0)==PROC+0x50 and m.locked;m.locked=False;m.events.append('mutex release');m.ret()
    def msleep():
        assert m.x(0)==PROC+0x458 and m.x(1)==PROC+0x50 and m.locked
        assert m.get(PROC+0x458,4)&0xc0==0xc0
        m.events.append('msleep with transition waiter bit')
        if sleep=='stop':m.stop('scheduler boundary')
        elif sleep=='wake':m.put(PROC+0x458,m.get(PROC+0x458,4)&~0xc0,4);m.ret()
        else:raise AssertionError(sleep)
    def wakeup():
        assert m.x(0)==PROC+0x458 and m.locked
        assert m.get(PROC+0x458,4)&0xe0==0 and m.get(PROC+0x648)==0
        m.events.append('wakeup after clear');m.ret()
    def vnop():
        arg=m.x(0);assert m.get(arg)==desc and m.get(arg+8)==VNODE and m.get(arg+16)==ATTR and m.get(arg+24)==CTX
        m.events.append('VNOP_GETATTR descriptor dispatch')
        if getattr_error is None:m.stop('filesystem getattr boundary');return
        if not getattr_error:
            m.put(ATTR,m.get(ATTR+8) if supported else 0)
            m.put(ATTR+0x30,size);m.put(ATTR+0x4c,mode,2)
        m.ret(getattr_error)
    m.stub('_lck_mtx_assert',lambda:m.ret());m.stub('_lck_mtx_lock',lock);m.stub('_lck_mtx_unlock',unlock)
    m.stub('_msleep',msleep);m.stub('_wakeup',wakeup)
    m.stub('_get_bsdthreadtask_info',lambda:m.ret(PROC));m.stub('_kauth_cred_issuser',lambda:m.ret(1))
    m.callbacks[VNOP]=vnop
    return m

def write_report(path,carrier,rows,scope):
    path.parent.mkdir(parents=True,exist_ok=True)
    assert not path.exists(), 'Refuse to overwrite evidence'
    path.write_text(json.dumps(dict(passed=True,kernel_sha256=EXPECTED,cases=rows,scope=scope,
        device_executed=False,tool_versions={'unicorn':U.__version__},
        harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+'\n')
