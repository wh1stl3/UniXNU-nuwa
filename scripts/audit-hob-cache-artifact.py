"""Inspect actual cache-handoff instructions and IVAC range implementation, never run firmware."""
import argparse,hashlib,importlib.util,json,re,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'out/python-tools'));import capstone

def main():
 cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('run',type=int);cli.add_argument('--profile',choices=('hob-cache-handoff','upstream-merged'),default='hob-cache-handoff');cli.add_argument('--artifact',type=Path);args=cli.parse_args();artifact=args.artifact.resolve() if args.artifact else ROOT/f'out/firmware-ci/{args.run}/nuwa-firmware-{args.run}';out=ROOT/f'reports/{args.profile}/{args.run}/cache-code-audit.json'
 if not artifact.resolve().is_relative_to((ROOT/'out').resolve()):raise ValueError('Artifact must stay under out/')
 if out.exists():raise ValueError('Fresh audit required')
 spec=importlib.util.spec_from_file_location('cache_reader',ROOT/'scripts/ci/inspect-firmware-candidate.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader);checked=reader.inspect(artifact,'NuwaBootMemoryDxe',True,True,True,args.profile)
 captured=[];original=reader.heap_descriptors
 def capture(data):captured.append(data);return original(data)
 reader.heap_descriptors=capture;reader.Firmware().volume((artifact/'build/FV/SILICIUM_UEFI.fd').read_bytes(),'Actual FD');assert len(captured)==1;data=captured[0];strip=struct.unpack_from('<H',data,6)[0];base=struct.unpack_from('<Q',data,16)[0];sections=[]
 for i in range(data[4]):
  at=40+40*i;vs,va,size,off=struct.unpack_from('<4I',data,at+8);sections.append((base+va,off-strip+40,size))
 def read(addr,n):
  for va,off,size in sections:
   if va<=addr and addr+n<=va+size:return data[off+addr-va:off+addr-va+n]
  raise ValueError('Unbacked actual TE address')
 mapping=artifact/'build/FV/Ffs/9AFFB503-E643-4141-8B90-17E8588B1D35Sec/9AFFB503-E643-4141-8B90-17E8588B1D35.map';symbols={m[2]:base+int(m[1],16) for m in re.finditer(r'^([0-9a-fA-F]{8,16})\s+0+\s+0\s+(\S+)\s*$',mapping.read_text(),re.M)}
 engine=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_LITTLE_ENDIAN);engine.detail=True
 names=['NuwaHobCacheHandoff','InvalidateDataCacheRange','CacheRangeOperation','ArmInvalidateDataCacheEntryByMVA','ArmDataSynchronizationBarrier','ArmInstructionSynchronizationBarrier'];records=[];decoded={}
 for name in names:
  if name not in symbols:raise ValueError('Required actual symbol absent: '+name)
  addr=symbols[name];end=min(a for a in symbols.values() if a>addr);body=read(addr,end-addr);ins=list(engine.disasm(body,addr));decoded[name]=ins;calls=[]
  for x in ins:
   if x.mnemonic in ('bl','b') and len(x.operands)==1 and x.operands[0].type==capstone.arm64.ARM64_OP_IMM:
    target=x.operands[0].imm;calls.append(dict(address=hex(x.address),op=x.mnemonic,target=hex(target),symbols=[n for n,a in symbols.items() if a==target]))
  records.append(dict(name=name,address=hex(addr),bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),calls=calls,instructions=[dict(address=hex(x.address),mnemonic=x.mnemonic,operands=x.op_str) for x in ins]))
 sequence=[];wanted=['ArmDataSynchronizationBarrier','InvalidateDataCacheRange','ArmInstructionSynchronizationBarrier']
 for c in records[0]['calls']:
  sequence.extend(n for n in c['symbols'] if n in wanted)
 if sequence!=[wanted[0],wanted[1],wanted[0],wanted[2]]:raise ValueError('Unexpected actual handoff barrier/invalidate sequence: '+str(sequence))
 forbidden={'AllocatePool','AllocatePages','FreePool','FreePages','WriteBackDataCacheRange','WriteBackInvalidateDataCacheRange'}
 if any(forbidden.intersection(c['symbols']) for c in records[0]['calls']):raise ValueError('Unexpected helper allocator/clean call')
 if not any('CpuDeadLoop' in c['symbols'] for c in records[0]['calls']):raise ValueError('Fail-closed guard absent')
 ivac=decoded['ArmInvalidateDataCacheEntryByMVA'];assert any(x.mnemonic=='dc' and x.op_str.startswith('ivac,') for x in ivac)
 assert all(not(x.mnemonic=='dc' and not x.op_str.startswith('ivac,')) for x in ivac)
 assert any(x.mnemonic=='dsb' and x.op_str=='sy' for x in decoded['ArmDataSynchronizationBarrier'])
 assert any(x.mnemonic=='isb' for x in decoded['ArmInstructionSynchronizationBarrier'])
 assert any(x.mnemonic=='blr' for x in decoded['CacheRangeOperation'])
 assert any('ArmDataSynchronizationBarrier' in c['symbols'] for c in records[2]['calls'])
 # Resolve the passed line-operation address in the actual range wrapper.
 regs={};proof=[]
 for x in decoded['InvalidateDataCacheRange']:
  o=x.operands
  if x.mnemonic in ('adrp','adr') and len(o)==2 and o[1].type==capstone.arm64.ARM64_OP_IMM:regs[x.reg_name(o[0].reg)]=o[1].imm
  elif x.mnemonic=='add' and len(o)==3 and o[2].type==capstone.arm64.ARM64_OP_IMM:
   dst,src=x.reg_name(o[0].reg),x.reg_name(o[1].reg)
   if src in regs:regs[dst]=regs[src]+o[2].imm
   elif dst in regs:del regs[dst]
  if regs.get('x2')==symbols['ArmInvalidateDataCacheEntryByMVA']:proof.append(hex(x.address))
 if not proof:raise ValueError('Actual range line-operation pointer not resolved to IVAC')
 result=dict(scope='Static actual SEC helper sequence and range primitive audit; not runtime cache effect or root-cause proof',fd_sha256=checked['fd']['sha256'],sec_sha256=hashlib.sha256(data).hexdigest(),map_sha256=hashlib.sha256(mapping.read_bytes()).hexdigest(),explicit_operation_sequence=sequence,ivac_pointer_proof_addresses=proof,functions=records,device_accessed=False)
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(result='Actual DSB/IVAC/DSB/ISB and fail-closed path verified',sequence=sequence,ivac_pointer_proof=proof)))
if __name__=='__main__':main()
