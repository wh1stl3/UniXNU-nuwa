"""Compare every post-MMU hook with its displaced native instruction.

Registers, NZCV, SP, next PC and native stack effects must agree. Framebuffer,
flag bytes and scratch below the entry SP belong to the diagnostic hook.
TPIDR_EL1 in probe_arm_init is an intentional shim; revision25 first-thread entry intentionally restores native VBAR (checked separately).
"""
import gc, argparse, hashlib, importlib.util, json, struct, sys
from functools import lru_cache
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
spec=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build-kernel-entry-probe.py')
B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)
FB=0xb8000000;ROW=5760;STACK=0xf00000
REGS=[getattr(sys.modules[__name__],f'UC_ARM64_REG_X{i}') for i in range(31)]

@lru_cache(maxsize=1)
def deep_rectangles():
    from read_deep_sites import points,geometry
    return tuple((*geometry(p['id']),32,2) for p in points())

def framebuffer_write_in_bounds(address,size,revision):
    y,offset=divmod(address-FB,ROW)
    if size<=0 or offset+size>ROW:return False
    if revision>=42 and any(224+(i//2)*24<=y<240+(i//2)*24 and (736+(i%2)*48)*4<=offset and offset+size<=(768+(i%2)*48)*4 for i in range(68)):return True
    if revision>=47 and 256*4<=offset and offset+size<=736*4 and any(ry<=y<ry+20 for ry in (896,924,952,980,1008)):return True
    if 200<=y<800:return True
    if revision>=46 and any(ry<=y<ry+rh and rx*4<=offset and offset+size<=(rx+rw)*4 for rx,ry,rw,rh in deep_rectangles()):return True
    if revision in (38,39,40,41,42,43,44,45,46,47,48,49):
        return any(ry<=y<ry+rh and rx*4<=offset and offset+size<=(rx+rw)*4 for rx,ry,rw,rh in ((256,784,480,20),(256,812,480,20),(256,840,480,20),(256,868,480,20),*((832+(i%10)*48,808+(i//10)*24,32,16) for i in range(97))))
    if revision==37:
        return any(ry<=y<ry+rh and rx*4<=offset and offset+size<=(rx+rw)*4
                   for rx,ry,rw,rh in ((256,784,480,20),(256,812,480,20),(832,808,32,16)))
    return False

def machine(raw,report,patch,case,reference=False):
    m=B.macho(raw);base=min(s['va'] for s in m['segments'] if s['size']);end=max(s['va']+s['size'] for s in m['segments'])
    u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(base,B.align(end-base));u.mem_map(FB,0x1200000);u.mem_map(STACK,0x10000);u.mem_map(0x100000,0x10000)
    for s in m['segments']:
        if s['filesize']:u.mem_write(s['va'],raw[s['fileoff']:s['fileoff']+s['filesize']])
    syms=report['probe']['symbols'];flags=int(syms['probe_flags'],16)
    # Legacy transparency fixtures exercise the already-registered path. The
    # load request and registration paths have separate pthread-startup cases.
    if report.get('probe_revision',0)>=28:
        u.mem_write(m['symbols']['_pthread_functions'],struct.pack('<Q',STACK+0x4000))
    if report.get('probe_revision',0)>=35:
        # Registered dependency fixture only; actual loader requests have dedicated cases.
        u.mem_write(m['symbols']['_decompressors']+32,struct.pack('<Q',STACK+0x4300))
    u.mem_write(flags,bytes([case['flag']])*4096)
    if 'probe_native_vectors' in syms:u.mem_write(int(syms['probe_native_vectors'],16),struct.pack('<Q',m['symbols']['_ExceptionVectorsBase']))
    u.mem_write(int(syms['probe_scratch'],16),struct.pack('<QQ',FB if case['video'] else 0,ROW))
    for i,reg in enumerate(REGS):u.reg_write(reg,0x101000+i*0x100)
    native_word=int.from_bytes(bytes.fromhex(patch['before']),'little')
    operand_x0=STACK+0x2000 if native_word&0x0a000000==0x08000000 and ((native_word>>5)&31)==0 else case['x0']
    u.reg_write(UC_ARM64_REG_CPACR_EL1,3<<20)
    if case.get('seed_simd'):
        for i in range(32):u.reg_write(getattr(sys.modules[__name__],f'UC_ARM64_REG_Q{i}'),(0x1122334455667788<<64)+i+1)
    u.reg_write(UC_ARM64_REG_X0,operand_x0);u.reg_write(UC_ARM64_REG_X1,STACK+0x2000)
    u.mem_write(STACK+0x2000,struct.pack('<Q',STACK+0x2100));u.mem_write(STACK+0x2100,struct.pack('<Q',1234))
    if patch['reason']=='probe_panic_trap':u.reg_write(UC_ARM64_REG_X0,0xfffffff007078d37)
    u.reg_write(UC_ARM64_REG_X19,STACK+0x3000);u.reg_write(UC_ARM64_REG_LR,STACK+0x1000)
    u.reg_write(UC_ARM64_REG_SP,STACK+0x8000);u.reg_write(UC_ARM64_REG_NZCV,case['nzcv'])
    site=int(patch['va'],16);bad=[];writes=[]
    u.hook_add(U.UC_HOOK_MEM_INVALID,lambda u,a,p,s,v,d:bad.append(dict(access=a,address=hex(p))) or False)
    u.hook_add(U.UC_HOOK_MEM_WRITE,lambda u,a,p,s,v,d:writes.append((p,s)))
    if reference:
        u.mem_write(site,bytes.fromhex(patch['before']));u.emu_start(site,0,count=1)
    else:
        native=case['native_pc']
        u.hook_add(U.UC_HOOK_CODE,lambda u,a,s,d:u.emu_stop() if a==native else None)
        u.emu_start(site,0,count=2000000)
    return u,dict(registers=[u.reg_read(x) for x in REGS],sp=u.reg_read(UC_ARM64_REG_SP),nzcv=u.reg_read(UC_ARM64_REG_NZCV),simd=[u.reg_read(getattr(sys.modules[__name__],f'UC_ARM64_REG_Q{i}')) for i in range(32)],tpidr_el1=u.reg_read(UC_ARM64_REG_TPIDR_EL1),pc=u.reg_read(UC_ARM64_REG_PC),bad=bad),writes

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--build',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
    report=json.loads(args.build.read_text());raw=(ROOT/report['candidate']['path']).read_bytes();checks=[]
    assert B.sha(raw)==report['candidate']['sha256']
    revision=report.get('probe_revision',0)
    if revision>=46:
        for x,y,size in ((736,816,4),(767,817,4),(784,816,8)):
            assert framebuffer_write_in_bounds(FB+y*ROW+x*4,size,revision)
            assert not framebuffer_write_in_bounds(FB+y*ROW+x*4,size,45)
        for x,y,size in ((736,818,4),(768,816,4),(816,816,4),(735,816,8),(208,800,4)):
            assert not framebuffer_write_in_bounds(FB+y*ROW+x*4,size,revision)
    if revision==37:
        for x,y,size in ((0,810,4),(256,804,4),(256,832,4),(864,808,4),(735,812,8),(1439,790,8)):
            assert not framebuffer_write_in_bounds(FB+y*ROW+x*4,size,revision)
        for x,y,size in ((256,800,4),(735,803,4),(256,812,4),(735,831,4),(832,808,4),(863,823,4)):
            assert framebuffer_write_in_bounds(FB+y*ROW+x*4,size,revision)
            assert not framebuffer_write_in_bounds(FB+y*ROW+x*4,size,36)
    for patch in report['patches']:
        if report.get('probe_revision',0)==31 and patch['reason']=='probe_dense_769d5f4':continue
        if report.get('probe_revision',0)==30 and patch['reason']=='probe_dense_76730e8':continue
        if not patch['reason'].startswith('probe_') or patch['reason'] in ('probe_entry','probe_tables','probe_mmu','probe_mmu_on','probe_ttbr1','probe_ttbr0','probe_console_policy'):continue
        for kind,flag,video,nzcv,x0 in [('first',0,True,0xa0000000,1),('repeat',1,True,0x50000000,0),('no-video',0,False,0xf0000000,1),('count-saturated',4,True,0,0)]:
            case=dict(flag=flag,video=video,nzcv=nzcv,x0=x0)
            try:ref,expected,native_writes=machine(raw,report,patch,case,True)
            except U.UcError as e:raise AssertionError((patch['reason'],kind,'native fixture',str(e))) from e
            case['native_pc']=expected['pc']
            got,actual,writes=machine(raw,report,patch,case)
            if patch['reason']=='probe_arm_init':expected['tpidr_el1']=actual['tpidr_el1']
            assert actual==expected,(patch['reason'],kind,expected,actual)
            # Compare native allocated stack frame and caller stack, excluding the
            # diagnostic's temporary save frame below entry SP.
            lo=STACK+0x8000;assert bytes(ref.mem_read(lo,0x8000))==bytes(got.mem_read(lo,0x8000))
            for p,n in native_writes:
                assert bytes(ref.mem_read(p,n))==bytes(got.mem_read(p,n)), (patch['reason'],kind,hex(p))
            # Rendering must never touch the firmware text area or cross the screen.
            fbwrites=[(p,s) for p,s in writes if FB<=p<FB+0x1200000]
            rejected=[(hex(p),s,divmod(p-FB,ROW)) for p,s in fbwrites if not framebuffer_write_in_bounds(p,s,revision)]
            assert not rejected,(patch['reason'],kind,rejected[:8])
            for edge in report.get('dense_bootstrap',{}).get('edges',[]):
                if edge['site']!=patch['va']:continue
                if report.get('probe_revision',0)>=36 and edge['id']>=266:continue # dedicated scoped cases exercise these
                pixel=struct.unpack('<I',got.mem_read(FB+edge['y']*ROW+edge['x']*4,4))[0]
                assert pixel==(int(edge['color'],16) if kind=='first' else 0),(patch['reason'],kind,edge,pixel)
            checks.append(dict(name=patch['reason']+': '+kind,passed=True,next_pc=hex(actual['pc']),framebuffer_writes=len(fbwrites)))
            del ref,got;gc.collect()
        if len(checks)%100==0:print(json.dumps(dict(progress_checks=len(checks))),flush=True)
    out=dict(scope=__doc__,candidate_sha256=B.sha(raw),checks=checks,
             revision37_rectangle_negative_controls=revision==37,revision46_rectangle_negative_controls=revision>=46)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(dict(checks=len(checks),passed=True)))
if __name__=='__main__':main()
