"""Run native node getter/iterator/record tail-dispatch. Tree/IO services are fixtures."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import flush_trace_inputs as t
sys.path.insert(0,str(t.R/'out/python-tools'))
import unicorn as U
from unicorn.arm64_const import *
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
proof=json.loads((w/'kernel-proof.json').read_bytes());raw=(w/'kernel.macho').read_bytes();assert hashlib.sha256(raw).hexdigest()==proof['kernel_sha256']
B=t.builder();m=B.macho(raw);base=0xfffffff000000000;tests=[]
for mode,expected in [('tree-entry',[0xc1000000]),('tree-loader',[0xc1000000]),('tree-error',[0xc1000000,0xc2000005,0xc6000000]),('query-entry',[0xc1000000,0xc2000000,0xc3000000]),('query-error',[0xc1000000,0xc2000000,0xc3000000,0xc4000005]),('parse-entry',[0xc1000000,0xc2000000,0xc3000000,0xc4000000,0xc5000000])]:
 u=U.Uc(U.UC_ARCH_ARM64,U.UC_MODE_ARM);u.mem_map(0x20000000,0x20000);mapped=set();seen=[];draws=[];stopped=[];stack=0x20018000
 def put(addr,value,size=8):u.mem_write(addr,value.to_bytes(size,'little'))
 def map_page(addr):
  page=addr&~4095
  if page in mapped:return
  segment=next(s for s in m['segments'] if s['va']<=page and page+4096<=s['va']+s['size'])
  n=max(0,min(4096,segment['filesize']-(page-segment['va'])));off=segment['fileoff']+page-segment['va']
  u.mem_map(page,4096);u.mem_write(page,raw[off:off+n]+bytes(4096-n));mapped.add(page)
 def fault(uc,access,addr,size,value,data):
  try:map_page(addr)
  except Exception as e:print(mode,hex(addr),hex(uc.reg_read(UC_ARM64_REG_PC)),repr(e));raise
  return True
 u.hook_add(U.UC_HOOK_MEM_UNMAPPED,fault)
 state=proof['targets']['coarse_state'];map_page(state)
 fs,tree,buf,leaf,hdr,key,val,thread= [0x20001000+i*0x1000 for i in range(8)]
 put(state+104,thread);put(state+136,stack+0x230);put(tree+0xe8,0x110,4);put(leaf+0xc0,hdr);put(hdr+0x24,1,4);put(key,(3<<60)|42)
 for reg,value in [(UC_ARM64_REG_X0,fs),(UC_ARM64_REG_X1,42),(UC_ARM64_REG_X2,0),(UC_ARM64_REG_X3,0x20009000),(UC_ARM64_REG_SP,stack),(UC_ARM64_REG_TPIDR_EL1,thread),(UC_ARM64_REG_CPACR_EL1,3<<20)]:u.reg_write(reg,value)
 def ret(value=0):u.reg_write(UC_ARM64_REG_X0,value);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_LR))
 def hook(uc,pc,size,data):
  low=pc-base
  if pc==proof['symbols']['draw']:
   draws.append(uc.reg_read(UC_ARM64_REG_X1));ret();return
  if low in (0x51f7fa4,0x523561c,0x51f8610):
   depth=stack+0x230-uc.reg_read(UC_ARM64_REG_SP);seen.append([hex(pc),hex(depth)])
   assert depth==(0x5b0 if low==0x51f8610 else 0x590)
  if low==0x51f7fa4:
   if mode=='tree-loader':return
   if mode=='tree-entry':stopped.append('tree');uc.emu_stop();return
   put(uc.reg_read(UC_ARM64_REG_X4),tree);ret(5 if mode=='tree-error' else 0)
  elif low==0x5224700 and mode=='tree-loader':
   seen.append(['native-tree-loader-argument',hex(uc.reg_read(UC_ARM64_REG_X0))]);assert uc.reg_read(UC_ARM64_REG_X0)==fs
   stopped.append('tree-loader-entry');uc.emu_stop()
  elif low==0x51f4f84:ret(buf)
  elif low==0x523561c:
   assert uc.reg_read(UC_ARM64_REG_X4)==0
  elif low==0x5234a90:
   assert stack+0x230-uc.reg_read(UC_ARM64_REG_SP)==0x5f0
   assert uc.reg_read(UC_ARM64_REG_X4)==3 and uc.reg_read(UC_ARM64_REG_X5)==0
   seen.append([hex(pc),'0x5f0'])
   if mode=='query-entry':stopped.append('query-worker-not-completing');uc.emu_stop();return
   put(uc.reg_read(UC_ARM64_REG_X7),leaf)
   index_output=struct.unpack('<Q',uc.mem_read(uc.reg_read(UC_ARM64_REG_SP),8))[0]
   put(index_output,0,4);ret(5 if mode=='query-error' else 0)
  elif low in (0x522bd94,0x522af48):
   put(uc.reg_read(UC_ARM64_REG_X2),key if low==0x522bd94 else val);put(uc.reg_read(UC_ARM64_REG_X3),8 if low==0x522bd94 else 0x60,4);ret()
  elif low==0x51f8610:
   assert uc.reg_read(UC_ARM64_REG_X0)==fs and uc.reg_read(UC_ARM64_REG_X1)==key
   assert struct.unpack('<Q',uc.mem_read(uc.reg_read(UC_ARM64_REG_FP)+8,8))[0]==base+0x51f762c
   stopped.append('parse');uc.emu_stop()
  elif low==0x51f7270 and mode=='query-error':stopped.append('query-error');uc.emu_stop()
  elif low==0x5196810 and mode=='tree-error':stopped.append('node-return');uc.emu_stop()
 u.hook_add(U.UC_HOOK_CODE,hook);u.emu_start(base+0x5196808,0,count=20000)
 assert stopped and draws==expected,(mode,stopped,[hex(v) for v in draws],hex(u.reg_read(UC_ARM64_REG_PC)))
 tests.append(dict(mode=mode,events=[hex(v) for v in draws],actual_native_scope_depths=seen,stopped=stopped[0],passed=True))
(w/'node-native-chain-model.json').write_text(json.dumps(dict(passed=True,kernel_sha256=proof['kernel_sha256'],tests=tests,scope='Native getter, iterator and tail-call dispatch. Tree acquisition except native selector-to-loader case, lower B-tree worker, allocation, record extraction and draw are modeled. No physical UFS or lock scheduling proof.'),indent=2)+'\n',encoding='utf-8')
print('PASS 6 native node/iterator/tail-dispatch chains')
