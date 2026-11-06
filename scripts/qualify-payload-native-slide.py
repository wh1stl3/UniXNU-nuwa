"""Run actual XNU slide instructions on immutable cache samples; no pager/syscall claim."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import flush_trace_inputs as trace
from payload_cache_slide import parse_v2,rebase_page
sys.path.insert(0,str(trace.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);p.add_argument('--samples',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
assert not a.output.exists();raw=(a.work/'kernel.macho').read_bytes();proof=json.loads((a.work/'kernel-proof.json').read_bytes());audit=json.loads(a.audit.read_bytes())
sha=lambda v:hashlib.sha256(v).hexdigest()
assert sha(raw)==proof['kernel_sha256'] and audit['passed']
for name,digest in audit['sources'].items():assert sha((trace.R/'scripts'/name).read_bytes())==digest
B=trace.builder();m=B.macho(raw);bias=0xfffffff000000000;entry=m['symbols']['_vm_shared_region_slide_page']-bias
assert entry==0x737f0a4 and m['symbols']['_rebase_chain']-bias==0x737f814
# Actual instruction ldr x20,[x0,#0x30] binds the non-PAC si_slide_info_entry offset.
assert raw[B.backed(m,entry+bias+0x28,4):][:4]==bytes.fromhex('141840f9')
checks=[]
def run(name,page,info,index,slide,expected,error=0):
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM)
 for address in (0x737f000,m['symbols']['_printf']-bias & ~4095):
  u.mem_map(address,4096);off=B.backed(m,address+bias,4096);u.mem_write(address,raw[off:off+4096])
 u.mem_map(0x1000000,0x20000);u.mem_map(0x2000000,(len(info)+4095)&~4095)
 si=0x1001000;content=0x1004000;ip=0x2000000;sp=0x101f000;stop=0x101e000
 u.mem_write(ip,bytes(info));u.mem_write(si,struct.pack('<I',slide));u.mem_write(si+0x30,struct.pack('<Q',ip))
 u.mem_write(content,bytes(page));u.mem_write(content-16,b'P'*16);u.mem_write(content+4096,b'Q'*16)
 logs=[]
 def hook(uc,pc,size,data):
  if pc==m['symbols']['_printf']-bias:
   logs.append(pc);uc.reg_write(UC_ARM64_REG_X0,0);uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
 u.hook_add(U.UC_HOOK_CODE,hook)
 for reg,value in ((UC_ARM64_REG_X0,si),(UC_ARM64_REG_X1,content),(UC_ARM64_REG_X2,0x180000000),(UC_ARM64_REG_X3,index),(UC_ARM64_REG_X4,0),(UC_ARM64_REG_SP,sp),(UC_ARM64_REG_LR,stop)):u.reg_write(reg,value)
 u.emu_start(entry,stop,count=100000)
 assert u.reg_read(UC_ARM64_REG_PC)==stop and u.reg_read(UC_ARM64_REG_W0)==error,(name,hex(u.reg_read(UC_ARM64_REG_PC)),u.reg_read(UC_ARM64_REG_W0))
 assert u.reg_read(UC_ARM64_REG_SP)==sp
 assert bytes(u.mem_read(content-16,16))==b'P'*16 and bytes(u.mem_read(content+4096,16))==b'Q'*16
 actual=bytes(u.mem_read(content,4096))
 if expected is not None:assert sha(actual)==expected,name
 checks.append(dict(name=name,error=error,slide=slide,page_index=index,result_sha256=sha(actual),guards_preserved=True,diagnostic_calls=len(logs)))

for sample in audit['samples']:
 page=(a.samples/sample['page']).read_bytes();info=(a.samples/sample['info']).read_bytes()
 assert sha(page)==sample['input_sha256'] and sha(info)==sample['info_sha256']
 for amount,key in ((0,'zero_sha256'),(sample['slide'],'maximum_sha256')):run(sample['page']+'-'+key,page,info,sample['page_index'],amount,sample[key])

sample=audit['samples'][0];page=(a.samples/sample['page']).read_bytes();info=(a.samples/sample['info']).read_bytes();index=sample['page_index'];slide=sample['slide']
starts,count=struct.unpack_from('<II',info,8);slot=starts+index*2
run('page-index-out-of-range',page,info,count,slide,sha(page),5)
bad=bytearray(info);struct.pack_into('<I',bad,0,99);run('unsupported-version',page,bad,index,slide,sha(page),5)
bad=bytearray(info);struct.pack_into('<H',bad,slot,0x8000);struct.pack_into('<I',bad,20,0);run('extras-out-of-range',page,bad,index,slide,sha(page),5)
bad=bytearray(info);struct.pack_into('<H',bad,slot,1024);run('chain-out-of-page',page,bad,index,slide,sha(page),5)
bad=bytearray(info);struct.pack_into('<H',bad,slot,0x4000);run('no-rebase',page,bad,index,slide,sha(page))
original_start=struct.unpack_from('<H',info,slot)[0];assert original_start<0x4000
extra=bytearray(info);struct.pack_into('<II',extra,16,len(extra),1);struct.pack_into('<H',extra,slot,0x8000);extra+=struct.pack('<H',original_start|0x8000)
run('one-extras-chain',page,extra,index,slide,sample['maximum_sha256'])
boundary=bytearray(info);struct.pack_into('<H',boundary,slot,1023);bp=bytearray(4096);struct.pack_into('<I',bp,4092,0x1234)
want,n,b=rebase_page(bp,index,parse_v2(boundary,count*4096),slide);assert (n,b)==(1,1)
run('straddling-low-word',bp,boundary,index,slide,sha(want))
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(dict(passed=True,kernel_sha256=proof['kernel_sha256'],audit_sha256=sha(a.audit.read_bytes()),script_sha256=sha(Path(__file__).read_bytes()),cases=checks,device_accessed=False,native_mapping_syscall=False,native_pager_fault=False,scope='Actual vm_shared_region_slide_page/rebase_chain code; real sampled pages at zero/max slide plus negatives. printf is intercepted. No UFS, AMFI, mapping syscall or EL0.'),indent=2)+'\n')
print('PASS',len(checks),'native slide cases')
