"""Review pinned 2273bdec actual cache control and SEC/MMU source anchors, no hardware access."""
from pathlib import Path
import importlib.util,sys,hashlib,json,re,struct,subprocess
r=Path(__file__).resolve().parents[1];sys.path.insert(0,str(r/'out/python-tools'));import capstone
spec=importlib.util.spec_from_file_location('reader',r/'scripts/ci/inspect-firmware-candidate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
a=r/'out/firmware-ci/40000310916/nuwa-firmware-40000310916';capture=[];old=m.heap_descriptors
m.heap_descriptors=lambda b:(capture.append(b),old(b))[1];fd=(a/'build/FV/SILICIUM_UEFI.fd').read_bytes()
if hashlib.sha256(fd).hexdigest()!='74ad39a67305944849b09935b80e457ac46e3016fa74e3ea22a93a9636d34051':raise ValueError('Pinned FD changed')
m.Firmware().volume(fd,'Actual FD');assert len(capture)==1
b=capture[0];strip=struct.unpack_from('<H',b,6)[0];base=struct.unpack_from('<Q',b,16)[0];sections=[]
for i in range(b[4]):
 at=40+40*i;vs,va,size,off=struct.unpack_from('<4I',b,at+8);sections.append((base+va,off-strip+40,size))
def read(addr,n):
 for va,off,size in sections:
  if va<=addr and addr+n<=va+size:return b[off+addr-va:off+addr-va+n]
 raise ValueError('Unbacked TE')
mp=a/'build/FV/Ffs/9AFFB503-E643-4141-8B90-17E8588B1D35Sec/9AFFB503-E643-4141-8B90-17E8588B1D35.map';syms={x[2]:base+int(x[1],16) for x in re.finditer(r'^([0-9a-fA-F]{8,16})\s+0+\s+0\s+(\S+)\s*$',mp.read_text(),re.M)};engine=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_LITTLE_ENDIAN)
functions=[]
for name in ('ArmDisableDataCache','ArmEnableDataCache','ArmEnableMmu','ArmSetTTBR0'):
 start=syms[name];end=min(x for x in syms.values() if x>start);raw=read(start,end-start);ins=[dict(address=hex(x.address),mnemonic=x.mnemonic,operands=x.op_str) for x in engine.disasm(raw,start)];functions.append(dict(name=name,address=hex(start),sha256=hashlib.sha256(raw).hexdigest(),instructions=ins,cache_maintenance_instructions=[x for x in ins if x['mnemonic']=='dc']))
fw=Path('D:/Code/uefi-nuwa');mu=Path('D:/Code/PortingiOS/common/sources/mu-nuwa-firmware/Mu_Basecore');sources=[]
for root,pin,path in ((fw,'6176a822e66b846620b5bcd2739a0666814ee663','Silicon/Silicium/SiliciumPkg/Sec/Sec.c'),(mu,'cfb93724a06ff86ff5ba971413368a7809ee42a5','UefiCpuPkg/Library/ArmMmuLib/AArch64/ArmMmuLibCore.c'),(mu,'cfb93724a06ff86ff5ba971413368a7809ee42a5','MdePkg/Library/ArmLib/AArch64/AArch64Support.S')):
 raw=subprocess.check_output(['git','--no-optional-locks','-c',f'safe.directory={root}','-C',str(root),'show',pin+':'+path]);keys=('ArmDisableDataCache','InvalidateDataCacheRange','ArmEnableDataCache','ArmEnableMmu','ArmSetTTBR0','ArmSetMAIR','FillTranslationTable','CTRL_C_BIT');sources.append(dict(commit=pin,path=path,sha256=hashlib.sha256(raw).hexdigest(),anchors=[dict(line=i,text=s.strip()) for i,s in enumerate(raw.decode().splitlines(),1) if any(k in s for k in keys)]))
result=dict(scope='Actual target cache-control disassembly and pinned source audit; runtime SCTLR/EL/TTBR not measured',functions=functions,sources=sources,inference='Highest-priority working hypothesis: stale HOB cache state becomes visible after translation/cache transition; not established root cause',runtime_registers_measured=False)
(r/'reports/hob-stage-audit-trial/2026-10-24/cache-transition-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(functions=[dict(name=x['name'],cache_operations=len(x['cache_maintenance_instructions'])) for x in functions])))
