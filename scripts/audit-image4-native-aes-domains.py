"""Read exact CHECK5 nonce domains through native indexed accessor, not a supplied table."""
import argparse,hashlib,json,sys
from pathlib import Path
import unicorn
try:import tomllib
except ModuleNotFoundError:
 import pip._vendor.tomli as tomllib
 sys.modules['tomllib']=tomllib
import exec_carrier_model as H
from exec_carrier_model import *
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
H.EXPECTED='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e';c=Carrier(t.R/'out/ufs-check-5-r1-qualified');rows=[]
for index in range(11):
 m=Machine(c);m.x(0,index);m.run(0xfffffff0046ee47c);assert m.stopped=='return';ptr=m.x(0)
 assert ptr==m.get(0xfffffff005caef20+index*8)
 rows.append(dict(index=index,address=hex(ptr),words=[hex(m.get(ptr+i*8)) for i in range(8)],selector=m.get(ptr+0x38,4)))
r=dict(passed=True,kernel_sha256=H.EXPECTED,domains=rows,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='11 actual native accessor executions and immutable domain fields. Does not establish active domain count or real nonce producer execution; NativeAES supports selector zero only.')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))