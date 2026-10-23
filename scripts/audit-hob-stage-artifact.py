"""Audit actual SEC call sites for the bounded HOB diagnostic, not runtime PCs."""
import argparse,hashlib,importlib.util,json,re,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'out/python-tools'))
import capstone

def main():
 cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('run',type=int);cli.add_argument('--profile',choices=('hob-stage-audit','hob-cache-handoff'),default='hob-stage-audit');args=cli.parse_args()
 artifact=ROOT/f'out/firmware-ci/{args.run}/nuwa-firmware-{args.run}';output=ROOT/f'reports/{args.profile}/{args.run}/sec-call-audit.json'
 if output.exists():raise ValueError('Fresh audit required')
 spec=importlib.util.spec_from_file_location('stage_reader',ROOT/'scripts/ci/inspect-firmware-candidate.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
 inspected=reader.inspect(artifact,'NuwaBootMemoryDxe',True,True,True,args.profile)
 captured=[];original=reader.heap_descriptors
 def capture(data):captured.append(data);return original(data)
 reader.heap_descriptors=capture;reader.Firmware().volume((artifact/'build/FV/SILICIUM_UEFI.fd').read_bytes(),'Actual FD')
 if len(captured)!=1:raise ValueError('Unique actual SEC required')
 data=captured[0];stripped=struct.unpack_from('<H',data,6)[0];base=struct.unpack_from('<Q',data,16)[0];sections=[]
 for i in range(data[4]):
  at=40+40*i;vs,va,size,offset=struct.unpack_from('<4I',data,at+8);sections.append((base+va,offset-stripped+40,size))
 def read(address,size):
  for va,at,length in sections:
   if va<=address and address+size<=va+length:return data[at+address-va:at+address-va+size]
  raise ValueError('Symbol not backed by SEC TE')
 mapping=artifact/'build/FV/Ffs/9AFFB503-E643-4141-8B90-17E8588B1D35Sec/9AFFB503-E643-4141-8B90-17E8588B1D35.map'
 symbols={m[2]:base+int(m[1],16) for m in re.finditer(r'^([0-9a-fA-F]{8,16})\s+0+\s+0\s+(\S+)\s*$',mapping.read_text(),re.M)}
 engine=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_LITTLE_ENDIAN);engine.detail=True
 target=symbols.get('NuwaHobAuditCheckpoint')
 if target is None:raise ValueError('Actual checkpoint symbol missing')
 names=['NuwaHobAuditCheckpoint','CreateHob','GetFirstGuidHob'];records=[]
 for name in names:
  address=symbols[name];end=min(a for a in symbols.values() if a>address);body=read(address,end-address);calls=[];indirect=[]
  for i in engine.disasm(body,address):
   if i.mnemonic in ('bl','b') and len(i.operands)==1 and i.operands[0].type==capstone.arm64.ARM64_OP_IMM:
    destination=i.operands[0].imm;calls.append(dict(address=hex(i.address),op=i.mnemonic,target=hex(destination),symbols=[n for n,a in symbols.items() if a==destination]))
   if i.mnemonic in ('blr','br'):indirect.append(hex(i.address))
  records.append(dict(symbol=name,address=hex(address),bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),branches=calls,indirect_branch_addresses=indirect,checkpoint_branches=sum(int(c['target'],16)==target for c in calls)))
 if records[1]['checkpoint_branches']<2 or records[2]['checkpoint_branches']<1:raise ValueError('Creation/query checkpoint calls absent')
 forbidden={'AllocatePool','AllocatePages','FreePool','FreePages','WriteBackDataCacheRange','InvalidateDataCacheRange','WriteBackInvalidateDataCacheRange','ArmConfigureMmu'}
 if records[0]['indirect_branch_addresses'] or any(forbidden.intersection(c['symbols']) for c in records[0]['branches']):raise ValueError('Unexpected diagnostic indirect/allocator/cache branch')
 if not any('CpuDeadLoop' in c['symbols'] for c in records[0]['branches']):raise ValueError('Fail-closed branch not found')
 result=dict(scope='Static actual SEC direct-branch audit; not runtime PCs or complete transitive call graph',fd_sha256=inspected['fd']['sha256'],sec_sha256=hashlib.sha256(data).hexdigest(),map_sha256=hashlib.sha256(mapping.read_bytes()).hexdigest(),functions=records,device_accessed=False)
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(result='Actual CreateHob/query checkpoint calls and fail-closed path verified',functions=[dict(symbol=x['symbol'],bytes=x['bytes'],checkpoint_branches=x['checkpoint_branches']) for x in records])))
if __name__=='__main__':main()
