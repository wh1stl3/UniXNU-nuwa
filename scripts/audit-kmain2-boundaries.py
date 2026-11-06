"""Bind coarse-stage semantics to the actual carrier instructions and XNU source."""
import hashlib,json,sys
from pathlib import Path
import flush_trace_inputs as t
sys.path.insert(0,str(t.R/'out/python-tools'))
import capstone
B=t.builder();p=t.R/'out/kmain-2-r2/kernel.macho';raw=p.read_bytes();m=B.macho(raw)
old=(t.R/'out/kmain-1-r1/kernel.macho').read_bytes();om=B.macho(old)
def word(a):return old[B.backed(om,a):][:4]
def call(a,target):
 w=int.from_bytes(word(a),'little');assert w>>26==0x25
 imm=w&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm
 assert a+imm*4==om['symbols'][target]
call(0xfffffff007673094,'_IOFindBSDRoot')
call(0xfffffff0076730e4,'_vfs_mountroot')
call(0xfffffff007673568,'_load_init_program')
call(0xfffffff0078e37a8,'__ZN9IOService14waitForServiceEP12OSDictionaryP13mach_timespec')
assert om['symbols']['_load_init_program_at_path']==0xfffffff00769d4e0
assert word(0xfffffff00769d624).hex()=='c0035fd6'
assert word(0xfffffff0073c3830).hex()=='a0010034' # AST-zero branch to 3864.
assert word(0xfffffff0073c38dc).hex()=='021041b9' # Actual saved CPSR +0x110.
assert word(0xfffffff0073c38e0).hex()=='018440f9' # Actual saved PC +0x108.
assert word(0xfffffff0073c3994).hex()=='e0039fd6' # Event precedes this ERET.
c=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_ARM)
regions={}
for name,a,n in [('root-caller',0xfffffff007673080,112),('init-caller',0xfffffff007673554,52),('exec-return',0xfffffff00769d5f8,48),('exception-return',0xfffffff0073c3800,408)]:
 regions[name]=[dict(address=hex(i.address),bytes=i.bytes.hex(),op=i.mnemonic,args=i.op_str) for i in c.disasm(old[B.backed(om,a):][:n],a)]
base=Path('D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full')
files=['bsd/kern/bsd_init.c','bsd/kern/kern_exec.c','bsd/kern/kern_sig.c','iokit/bsddev/IOKitBSDInit.cpp','osfmk/arm64/locore.s']
report=dict(passed=True,kernel_sha256=hashlib.sha256(raw).hexdigest(),reference_kernel_sha256=hashlib.sha256(old).hexdigest(),
 sources={str(base/f):hashlib.sha256((base/f).read_bytes()).hexdigest() for f in files},regions=regions,
 semantics=['stage 1 inferred from reaching native root entry in bsd_init; no all-platform-health claim',
 'root output dev_t comes from the original caller x20 passed as x2',
 'load_init_program_at_path RET gives errno including pre-exec failures',
 'bsdinit_task continuation after load_init_program indicates success and arms current TPIDR_EL1',
 'no_asts boundary matches armed thread and saved CPSR mode 0; disarmed before draw',
 'EL0 marker is before ERET and does not establish execution of a user instruction'])
out=t.R/'reports/kmain-2-r2/boundaries.json';assert not out.exists();out.write_text(json.dumps(report,indent=2)+'\n');print('PASS exact root/init/EL0 call and state boundaries')
