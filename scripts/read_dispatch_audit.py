"""Fixed-input read-dispatch provenance; no runtime v_op target is inferred."""
import argparse,importlib.util,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'out/python-tools'))
from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
s=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build-kernel-entry-probe.py');B=importlib.util.module_from_spec(s);s.loader.exec_module(B)
PLAN=ROOT/'out/earlysec-2026-10-24/emission.json'
PLAN_SHA='e10770f6a5f85a1430494114a136ba801f4ab062a9af1ba09408f60feb9fc5f2'
APFS='com.apple.filesystems.apfs';ENTRY=0xfffffff0051a5858;WRITE=0xfffffff0051a5df8;DISPATCH=0xfffffff00746c688
CS=Cs(CS_ARCH_ARM64,CS_MODE_ARM);CS.detail=True

def disasm(raw,m,start,n):return list(CS.disasm(raw[B.backed(m,start,n):B.backed(m,start,n)+n],start))
def record(i):return dict(pc=hex(i.address),bytes=i.bytes.hex(),instruction=i.mnemonic+' '+i.op_str)
def stub(raw,m,target):
 try:ins=disasm(raw,m,target,12)
 except (StopIteration,ValueError):return None
 if [i.mnemonic for i in ins]!=['adrp','ldr','br'] or ins[0].op_str.split(',')[0]!='x16' or ins[2].op_str!='x16':return None
 if ins[1].operands[1].mem.base!=ins[0].operands[0].reg:return None
 slot=(ins[0].operands[1].imm+ins[1].operands[1].mem.disp)&((1<<64)-1)
 return dict(slot=slot,target=struct.unpack_from('<Q',raw,B.backed(m,slot,8))[0],instructions=[record(i) for i in ins])

def audit():
 raw=B.INPUT.read_bytes();assert B.sha(raw)==B.EXPECTED;assert B.sha(PLAN.read_bytes())==PLAN_SHA;p=json.loads(PLAN.read_text());assert p['candidate_sha256']==B.EXPECTED;m=B.macho(raw);sy=m['symbols'];rev={v:k for k,v in sy.items()};extent=next(e for e in p['extents'] if e['module']==APFS and e['segment']=='__TEXT_EXEC');at=B.backed(m,extent['va'],extent['size']);digest=B.sha(raw[at:at+extent['size']]);assert digest==p['original_executable_sha256'][APFS]=='ebc47d686c6917c7fb154a0b2e2ed19e3d6a277d994d1395b02d3214142577cc'
 desc=sy['_vnop_read_desc'];descs={v:k for k,v in sy.items() if k.startswith('_vnop_') and k.endswith('_desc')};refs=[];candidates=[]
 for bind in p['bindings']:
  if bind.get('module')!=APFS or bind.get('new_target')!=desc:continue
  site=bind['new_site'];off=B.backed(m,site,16);assert struct.unpack_from('<Q',raw,off)[0]==desc
  around=struct.unpack_from('<6Q',raw,off-16);handler=around[3]
  shaped=around[0] in descs and around[4] in descs
  item=dict(site=hex(site),handler=hex(handler),neighbor_descriptors=[descs.get(around[0]),descs.get(around[4])],operation_pair_shape=shaped,handler_symbol=rev.get(handler),handler_in_original_apfs_text=extent['va']<=handler<extent['va']+extent['size'])
  refs.append(item)
  if shaped:candidates.append(item)
 assert len(refs)==6 and len(candidates)==5 and sum(x['handler_in_original_apfs_text'] for x in candidates)==4
 assert any(int(x['handler'],16)==ENTRY for x in candidates)
 calls=[]
 for i in disasm(raw,m,ENTRY,WRITE-ENTRY):
  if i.mnemonic!='bl':continue
  target=i.operands[0].imm&((1<<64)-1);resolved=stub(raw,m,target);dest=resolved['target'] if resolved else target
  calls.append(dict(pc=hex(i.address),word=i.bytes.hex(),direct_target=hex(target),resolved_target=hex(dest),symbol=rev.get(dest),stub=resolved))
 decmp=next(c for c in calls if c['symbol']=='_decmpfs_read_compressed');assert decmp['pc']=='0xfffffff0051a59b8' and decmp['direct_target']=='0xfffffff00525e910'
 index=struct.unpack_from('<i',raw,B.backed(m,desc))[0];assert index==0
 out=dict(level='Static fixed-input audit only',native_input_sha256=B.EXPECTED,emission_report_sha256=PLAN_SHA,original_donor_sha256=p['original_sha256'],apfs_executable_extent={**extent,'va':hex(extent['va'])},apfs_executable_sha256=digest,descriptor=hex(desc),descriptor_disk_offset_value=index,dispatch_instructions=[record(i) for i in disasm(raw,m,0xfffffff00746c678,24)],descriptor_references=refs,operation_candidates=candidates,regular_read_candidate=dict(entry=hex(ENTRY),prologue=raw[B.backed(m,ENTRY):B.backed(m,ENTRY)+4].hex(),bounded_scan_end=hex(WRITE),scope='Window ends at adjacent operation write handler, not an asserted complete function CFG',direct_calls_in_window=calls,decmpfs_call=decmp),runtime_target_known=False,limitations=['Disk descriptor offset0 is not proof of the runtime index assigned by vfs_op_init','Five static operation pairs are not a captured live vnode v_op table','Regular-read candidate classification follows matching operation descriptor plus direct decmpfs import, not a recovered symbol name','Other static handlers and runtime substitutions remain possible until x8 is observed','No device, memory/TCR/identity or permission changes'],source_sha256=B.sha(Path(__file__).read_bytes()),device_accessed=False)
 return raw,m,out

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists() and a.output.resolve().is_relative_to(ROOT/'reports');_,_,out=audit();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(dict(descriptor_references=6,operation_pairs=5,apfs_handlers=4,regular_read_candidate=hex(ENTRY),decmpfs_call='0xfffffff0051a59b8',runtime_target_known=False)))
if __name__=='__main__':main()
