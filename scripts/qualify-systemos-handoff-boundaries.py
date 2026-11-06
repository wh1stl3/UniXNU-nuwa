"""Model native scratch allocation and checkdirs root-reference boundaries.

External callees are explicit fixtures, including proc_iterate. Individual
checkdirs callbacks run against synthetic proc fields; real concurrency, VM,
reference subsystem and actual mount are NOT exercised.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'out/python-tools'))
import flush_trace_inputs as trace
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm64_const import *

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();assert not a.output.exists()
raw=(a.work/'kernel.macho').read_bytes();proof=json.loads((a.work/'kernel-proof.json').read_bytes())
assert hashlib.sha256(raw).hexdigest()==proof['kernel_sha256']
B=trace.builder();m=B.macho(raw);bias=0xfffffff000000000
sym={k:v-bias for k,v in m['symbols'].items()}
stack=0x1000000;old=0x200000;new=0x201000;mount=0x300000;context=0x400000;sentinel=0x900000
cases=[]

def machine():
    u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);pages=set()
    def mapping(address,size):
        for page in range(address&~4095,(address+size+4095)&~4095,4096):
            if page not in pages:u.mem_map(page,4096);pages.add(page)
    def code(address,size):
        off=B.backed(m,address+bias,size);mapping(address,size);u.mem_write(address,raw[off:off+size])
    mapping(stack,0x2000);mapping(sentinel,4)
    u.reg_write(UC_ARM64_REG_SP,stack+0x1000);u.reg_write(UC_ARM64_REG_LR,sentinel)
    return u,mapping,code

for page_size,error in ((4096,0),(16384,0),(16384,3)):
    u,mapping,code=machine();start=0x769d2d0;end=0x769d2f8
    code(start,end-start)
    targets=['_current_map','_vm_map_page_size','_mach_vm_allocate_kernel']
    for name in targets:code(sym[name],4)
    calls=[];allocated=0x80000
    def scratch_hook(uc,address,size,data):
        if address not in [sym[n] for n in targets]:return
        name=next(n for n in targets if sym[n]==address);calls.append(name)
        if name=='_current_map':result=0x500000
        elif name=='_vm_map_page_size':
            assert uc.reg_read(UC_ARM64_REG_X0)==0x500000;result=page_size
        else:
            assert [uc.reg_read(r) for r in (UC_ARM64_REG_X0,UC_ARM64_REG_X2,UC_ARM64_REG_X3,UC_ARM64_REG_X4)]==[0x500000,page_size,1,0]
            slot=uc.reg_read(UC_ARM64_REG_X1)
            assert slot==stack+0x1000+0x28 and bytes(uc.mem_read(slot,8))==bytes(8)
            if not error:uc.mem_write(slot,struct.pack('<Q',allocated))
            result=error
        uc.reg_write(UC_ARM64_REG_X0,result);uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
    u.hook_add(UC_HOOK_CODE,scratch_hook);u.emu_start(start,end,count=30)
    value=struct.unpack('<Q',u.mem_read(stack+0x1028,8))[0]
    assert value==(0 if error else allocated)
    assert u.reg_read(UC_ARM64_REG_X0)==error and calls==targets
    cases.append(dict(boundary='native_init_scratch',page_size=page_size,allocation_error=error,address=value,
                      native_ignores_allocator_status=True))

for root_match,usecount,error in ((True,2,0),(False,2,0),(True,1,0),(True,2,14)):
    u,mapping,code=machine();code(sym['_checkdirs'],0xd0)
    mapping(old,0x2000);mapping(sym['_rootvnode'],8)
    u.mem_write(old+0x60,struct.pack('<I',usecount));u.mem_write(old+0x78,struct.pack('<Q',mount))
    initial=old if root_match else 0x202000;u.mem_write(sym['_rootvnode'],struct.pack('<Q',initial))
    targets=['_VFS_ROOT','_proc_iterate','_vnode_ref','_lck_rw_lock_exclusive',
             '_lck_rw_unlock_exclusive','_vnode_rele','_vnode_put']
    for name in targets:code(sym[name],4)
    calls=[]
    def root_hook(uc,address,size,data):
        if address not in [sym[n] for n in targets]:return
        name=next(n for n in targets if sym[n]==address);calls.append(name)
        x0=uc.reg_read(UC_ARM64_REG_X0);x1=uc.reg_read(UC_ARM64_REG_X1)
        result=0
        if name=='_VFS_ROOT':
            assert x0==mount and uc.reg_read(UC_ARM64_REG_X2)==context
            if not error:uc.mem_write(x1,struct.pack('<Q',new))
            result=error
        elif name=='_proc_iterate':
            assert x0==5 and x1==sym['_checkdirs_callback']
            assert struct.unpack('<QQ',uc.mem_read(uc.reg_read(UC_ARM64_REG_X2),16))==(old,new)
        elif name in ('_vnode_ref','_vnode_put'):assert x0==new
        elif name=='_vnode_rele':assert x0==old
        else:
            assert x0==sym['_rootvnode_rw_lock']
            observed=struct.unpack('<Q',uc.mem_read(sym['_rootvnode'],8))[0]
            assert observed==(initial if name=='_lck_rw_lock_exclusive' else new)
        uc.reg_write(UC_ARM64_REG_X0,result);uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
    u.reg_write(UC_ARM64_REG_X0,old);u.reg_write(UC_ARM64_REG_X1,context)
    u.hook_add(UC_HOOK_CODE,root_hook);u.emu_start(sym['_checkdirs'],sentinel,count=100)
    expected=[] if usecount==1 else ['_VFS_ROOT'] if error else targets if root_match else ['_VFS_ROOT','_proc_iterate','_vnode_put']
    assert calls==expected and u.reg_read(UC_ARM64_REG_X0)==error
    after=struct.unpack('<Q',u.mem_read(sym['_rootvnode'],8))[0]
    assert after==(new if root_match and usecount!=1 and not error else initial)
    cases.append(dict(boundary='checkdirs',root_match=root_match,usecount=usecount,vfs_root_error=error,
                      calls=calls,root_updated=after!=initial))

for is_root,rootfs,flags,expected in ((True,True,1,0x10001),(True,True,0x21,0x21),
                                    (True,True,0x10021,0x21),(False,True,0x21,0x21),
                                    (True,False,0x21,0x21)):
    u,mapping,code=machine();code(0x7451b58,0x18);code(0x7451c9c,0x24)
    mapping(old,4096);mapping(mount,4096)
    u.mem_write(old+0x54,bytes([int(is_root)]));u.mem_write(old+0xd8,struct.pack('<Q',mount))
    u.mem_write(mount+0x71,bytes([0x40 if rootfs else 0]))
    u.reg_write(UC_ARM64_REG_X22,old);u.reg_write(UC_ARM64_REG_X27,flags)
    u.emu_start(0x7451b58,0x7451b70,count=20)
    assert u.reg_read(UC_ARM64_REG_X5)==expected
    cases.append(dict(boundary='mac_mount_root_union_flags',vroot=is_root,mnt_rootfs=rootfs,
                      input_flags=hex(flags),forwarded_flags=hex(expected)))

for mask,ref_failure,race_mask in ((0,0,None),(1,0,None),(2,0,None),(3,0,None),
                                 (3,1,None),(3,2,None),(3,0,0),(3,0,1)):
    u,mapping,code=machine();code(sym['_checkdirs_callback'],0x10c)
    proc,args,other=0x600000,0x601000,0x202000
    mapping(proc,8192);u.mem_write(args,struct.pack('<QQ',old,new))
    initial=[old if mask&(1<<i) else other for i in range(2)]
    u.mem_write(proc+0x118,struct.pack('<QQ',*initial))
    targets=['_proc_fdlock','_proc_fdunlock','_vnode_ref','_vnode_rele',
             '_proc_dirs_lock_exclusive','_proc_dirs_unlock_exclusive']
    for name in targets:code(sym[name],4)
    state=dict(fd=False,dirs=False,ref_attempts=0,new_refs=0,old_releases=0)
    calls=[]
    def callback_hook(uc,address,size,data):
        if address not in [sym[n] for n in targets]:return
        name=next(n for n in targets if sym[n]==address)
        x0=uc.reg_read(UC_ARM64_REG_X0);calls.append(dict(name=name,target=hex(x0)));result=0
        if name in ('_vnode_ref','_vnode_rele'):
            assert not state['fd'] and not state['dirs']
            if name=='_vnode_ref':
                assert x0==new;state['ref_attempts']+=1
                result=16 if state['ref_attempts']==ref_failure else 0
                if not result:state['new_refs']+=1
            elif x0==new:state['new_refs']-=1;assert state['new_refs']>=0
            else:assert x0==old;state['old_releases']+=1
        else:
            assert x0==proc
            if name=='_proc_fdlock':assert not state['fd'];state['fd']=True
            elif name=='_proc_fdunlock':assert state['fd'];state['fd']=False
            elif name=='_proc_dirs_lock_exclusive':
                assert not state['fd'] and not state['dirs']
                if race_mask is not None:
                    # Fixture for a competing update while locks were dropped.
                    changed=[old if race_mask&(1<<i) else other for i in range(2)]
                    uc.mem_write(proc+0x118,struct.pack('<QQ',*changed))
                state['dirs']=True
            else:assert state['dirs'] and not state['fd'];state['dirs']=False
        uc.reg_write(UC_ARM64_REG_X0,result);uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
    u.reg_write(UC_ARM64_REG_X0,proc);u.reg_write(UC_ARM64_REG_X1,args)
    u.hook_add(UC_HOOK_CODE,callback_hook);u.emu_start(sym['_checkdirs_callback'],sentinel,count=140)
    after=list(struct.unpack('<QQ',u.mem_read(proc+0x118,16)))
    expected=initial if ref_failure else [new if (mask if race_mask is None else race_mask)&(1<<i) else other for i in range(2)]
    assert after==expected and not state['fd'] and not state['dirs'] and u.reg_read(UC_ARM64_REG_X0)==0
    assert state['new_refs']==after.count(new) and state['old_releases']==after.count(new)
    cases.append(dict(boundary='checkdirs_callback',initial_match_mask=mask,failed_ref_call=ref_failure,
                      competing_match_mask=race_mask,transferred_refs=state['new_refs'],calls=calls))

report=dict(kernel_sha256=hashlib.sha256(raw).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            cases=cases,passed=True,actual_mount=False,proc_iterator_executed=False,individual_proc_callback_executed=True,
            external_callees='fixtures; no real VM allocation, reference subsystem or concurrency',
            next='Own/validate scratch at caller; preserve native checkdirs instead of manually changing root globals')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
print('PASS',len(cases),'native handoff boundary cases')
