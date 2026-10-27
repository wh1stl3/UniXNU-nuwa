"""Reject stale body call bits, fields and tiles on the next header attempt."""
import argparse,importlib.util,json,struct,sys
from pathlib import Path
import read_body_sites as P
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('body_reset_model',ROOT/'scripts/test-read-dispatch-observer.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T)

def run(raw,m,b):
 u=T.machine(raw,m,b'',0,[],False);sy={k:int(v,16) for k,v in b['probe']['symbols'].items()}
 u.mem_write(sy['probe_scratch'],struct.pack('<QQ',T.FB,T.ROW))
 u.mem_write(sy['probe_read_body_state'],b'\xff'*8)
 for p in P.points():
  i=p['id'];u.mem_write(sy['probe_flags']+128+i,b'\x01')
  x=832+((i-276)%10)*48;y=808+((i-276)//10)*24
  for row in range(y,y+16):u.mem_write(T.FB+row*T.ROW+x*4,b'\xff'*128)
 u.hook_add(T.U.UC_HOOK_CODE,lambda u,pc,n,d:u.emu_stop() if pc==m['symbols']['_vn_rdwr'] else None)
 u.emu_start(P.PREVIOUS.PREVIOUS.FIRST,0,count=2000000)
 assert u.reg_read(T.UC_ARM64_REG_PC)==m['symbols']['_vn_rdwr']
 assert bytes(u.mem_read(sy['probe_read_body_state'],8))==bytes(8)
 assert T.field(u,0xa038)==0 and T.field(u,0xa039)==0xffffffffffffffff
 for p in P.points():
  i=p['id'];assert bytes(u.mem_read(sy['probe_flags']+128+i,1))==b'\0'
  x=832+((i-276)%10)*48;y=808+((i-276)//10)*24
  assert all(bytes(u.mem_read(T.FB+row*T.ROW+x*4,128))==bytes(128) for row in range(y,y+16))

def main():
 p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 assert not a.output.exists();b=json.loads(a.build.read_text());raw=(ROOT/b['candidate']['path']).read_bytes();assert b['probe_revision'] in (38,39,40,41,42,43,44,45,46,47,48,49) and T.B.sha(raw)==b['candidate']['sha256'];m=T.B.macho(raw)
 run(raw,m,b)
 # Omit the actual reset of pairing bits in memory; stale-state assertion must fail.
 start=int(b['probe']['symbols']['probe_dense_769bf90'],16);end=int(b['probe']['symbols']['probe_dense_769bf90_replay'],16)
 ins=T.A.disasm(raw,m,start,end-start);state=int(b['probe']['symbols']['probe_read_body_state'],16)
 stores=[ins[i+1] for i,x in enumerate(ins[:-1]) if x.mnemonic=='adr' and x.op_str.startswith('x9, ') and x.operands[1].imm&((1<<64)-1)==state and ins[i+1].mnemonic=='str']
 assert len(stores)==1
 changed=bytearray(raw);at=T.B.backed(m,stores[0].address);changed[at:at+4]=bytes.fromhex('1f2003d5')
 rejected=False
 try:run(bytes(changed),m,b)
 except AssertionError:rejected=True
 assert rejected
 out=dict(candidate_sha256=T.B.sha(raw),source_sha256=T.B.sha((ROOT/'scripts/read_body_sites.py').read_bytes()),tile_count=len(P.points()),stale_fields_tiles_bits_cleared=True,omitted_reset_negative_rejected=True,device_accessed=False)
 a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(out))
if __name__=='__main__':main()
