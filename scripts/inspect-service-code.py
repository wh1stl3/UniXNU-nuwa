"""Disassemble an exact standalone Mach-O VA range, including LC_MAIN binaries."""
import argparse,struct
from pathlib import Path
import capstone
def segments(raw):
 assert struct.unpack_from('<I',raw)[0]==0xfeedfacf
 at=32;result=[]
 for _ in range(struct.unpack_from('<I',raw,16)[0]):
  cmd,size=struct.unpack_from('<II',raw,at)
  if cmd==0x19:
   va,vs,off,fs=struct.unpack_from('<QQQQ',raw,at+24);result.append(dict(va=va,size=vs,fileoff=off,filesize=fs))
  at+=size
 return result
def readva(raw,address,size):
 seg=next(s for s in segments(raw) if s['va']<=address and address+size<=s['va']+s['filesize']);off=seg['fileoff']+address-seg['va'];return raw[off:off+size]
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--start',type=lambda x:int(x,0),required=True);p.add_argument('--size',type=lambda x:int(x,0),required=True);a=p.parse_args()
 for ins in capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_ARM).disasm(readva(a.binary.read_bytes(),a.start,a.size),a.start):print(hex(ins.address),ins.mnemonic,ins.op_str)
