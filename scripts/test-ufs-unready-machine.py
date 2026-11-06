"""Execute actual linked UFS guards with an explicitly unready host/layout fixture."""
import argparse, gc, hashlib, json, runpy, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'out/python-tools'))
import unicorn as U
from unicorn import arm64_const as A

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile',type=Path,required=True); ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(); output=args.output.resolve()
    if not output.is_relative_to(ROOT/'reports') or output.exists(): raise ValueError('Fresh report required')
    profile=json.loads(args.profile.read_bytes()); raw=(ROOT/profile['native_path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=profile['native_sha256']: raise ValueError('Kernel drift')
    helper=runpy.run_path(str(ROOT/'scripts/ci/build-ramblock-kernel.py')); names,backed=helper['symbols'](raw)
    segments=[]; at=32
    for _ in range(struct.unpack_from('<I',raw,16)[0]):
        cmd,length=struct.unpack_from('<II',raw,at)
        if cmd==0x19:
            va,size,off,n=struct.unpack_from('<4Q',raw,at+24)
            if size: segments.append((va,size,off,n))
        at+=length
    base=min(s[0] for s in segments)&~4095
    end=(max(s[0]+s[1] for s in segments)+4095)&~4095
    parser=names['_PE_parse_boot_argn']['value']; stop=0x10f000; records=[]
    for mode in (None,1,2):
        for function in ('mode','open','read','write','sync','gpt_check'):
            u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM)
            u.mem_map(base,end-base)
            for va,size,off,n in segments:
                if n:u.mem_write(va,raw[off:off+n])
            u.mem_map(0x100000,0x10000);u.reg_write(A.UC_ARM64_REG_SP,0x108000);u.reg_write(A.UC_ARM64_REG_X30,stop)
            arguments={'open':(1,0x101000,0x101008),'read':(0,1,0x102000),'write':(0,1,0x102000)}.get(function,())
            for i,value in enumerate(arguments):u.reg_write(getattr(A,'UC_ARM64_REG_X'+str(i)),value)
            calls=[]
            def hook(uc,pc,size,data):
                if pc!=parser:return
                address=uc.reg_read(A.UC_ARM64_REG_X0); text=bytes(uc.mem_read(address,32)).split(b'\0')[0]
                if text!=b'sheng-data-persist':raise AssertionError('Unexpected boot argument')
                if uc.reg_read(A.UC_ARM64_REG_X2)!=4:raise AssertionError('Boot argument width')
                if mode is not None:uc.mem_write(uc.reg_read(A.UC_ARM64_REG_X1),struct.pack('<I',mode))
                uc.reg_write(A.UC_ARM64_REG_X0,int(mode is not None));uc.reg_write(A.UC_ARM64_REG_PC,uc.reg_read(A.UC_ARM64_REG_X30));calls.append(text.decode())
            u.hook_add(U.UC_HOOK_CODE,hook)
            u.emu_start(names['_native_ufs_store_'+function]['value'],stop,count=2000)
            if u.reg_read(A.UC_ARM64_REG_PC)!=stop:raise AssertionError('Did not return')
            result=u.reg_read(A.UC_ARM64_REG_X0)&0xffffffff
            expected=(mode or 0) if function=='mode' else (1 if function=='gpt_check' else 0)
            if result!=expected:raise AssertionError((mode,function,result,expected))
            records.append(dict(boot_mode=mode,function=function,result=result,boot_argument_calls=len(calls),passed=True))
            del u;gc.collect()
    report=dict(passed=True,kernel_sha256=profile['native_sha256'],checks=records,
        fixture='Linked static data/BSS: no host or layout setup; valid non-null I/O arguments; only boot-argument parser stubbed',
        scope='Actual ARM64 guard execution in Unicorn, not C++ initialization or hardware execution',
        controller_memory_mapped=False,hardware_proven=False,device_accessed=False)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps(dict(passed=True,checks=len(records),hardware_proven=False)))

if __name__=='__main__':main()
