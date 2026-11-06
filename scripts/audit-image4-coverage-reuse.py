"""Reconcile historical full-init coverage with CHECK5; do not replay unchanged early init."""
import argparse,hashlib,json,struct,sys
from pathlib import Path
import unicorn
try:import tomllib
except ModuleNotFoundError:
 import pip._vendor.tomli as tomllib
 sys.modules['tomllib']=tomllib
import exec_carrier_model as H
from exec_carrier_model import Carrier,t
sha=lambda b:hashlib.sha256(b).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
H.EXPECTED='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e';c=Carrier(t.R/'out/ufs-check-5-r1-qualified')
oldpath=t.R/'out/kernel-entry-probe-71-flush-r1/kernel-entry-probe.macho';old=oldpath.read_bytes();assert sha(old)=='59da983a17d29ad065122eef9b3e5844eb6240c7ec14c7561709bb3a8272f783';om=c.b.macho(old)
reportpath=t.R/'reports/kernel-entry-probe/2026-10-31-probe71-flush-r1/image4-launch.json';historical=json.loads(reportpath.read_bytes());assert historical['candidate_sha256']==sha(old)
ranges=[]
for name,address,size in [('Image4 code and imports',0xfffffff0046e4000,0x16000),('Image4 static runtime and descriptor data',0xfffffff005cac000,0x6000)]:
 before=old[c.b.backed(om,address,size):][:size];after=c.raw[c.b.backed(c.m,address,size):][:size]
 assert before==after,name
 ranges.append(dict(name=name,address=hex(address),bytes=size,sha256=sha(after)))
qualification=t.R/'reports/ufs-check-5-r1/offline-qualification-final.json';q=json.loads(qualification.read_bytes())
assert sha(qualification.read_bytes())=='27755b0de2082c258e5a14454b652d794de85f070f39a410d36c212a0db00fdb'
adt=t.R/'out/ufs-check-5-r1-qualified/qualified-readback/kernel.macho.adt';currentadt=sha(adt.read_bytes())
assert currentadt=='42d3074d39960b09636169d62d5c16bf0ed1115d3e88875192bdea9e6529fd56'
callers=[]
for pc in range(0xfffffff0046e4000,0xfffffff0046fa000,4):
 word=struct.unpack_from('<I',c.raw,c.b.backed(c.m,pc,4))[0]
 if word&0xfc000000!=0x94000000:continue
 imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm
 if pc+4*imm==0xfffffff0046ecc14:callers.append(hex(pc))
gate_slot=0xfffffff005cabab0;gate_target=struct.unpack_from('<Q',c.raw,c.b.backed(c.m,gate_slot,8))[0];assert gate_target==c.sy['_lck_mtx_gate_close']
refs=Path('/mnt/d/Code/PortingiOSLegacy/common/sources/UniXNU/drivers/NativeAes');source=(refs/'NativeAES.cpp').read_bytes();abi=(refs/'OriginalAESABI.h').read_bytes()
assert b'return selector == 0;' in source and b'if (key->selector ||' in source
result=dict(passed=True,kernel_sha256=H.EXPECTED,script_sha256=sha(Path(__file__).read_bytes()),historical_report=dict(path=str(reportpath.relative_to(t.R)),sha256=sha(reportpath.read_bytes())),unchanged_ranges=ranges,
 current_adt_sha256=currentadt,historical_adt_sha256=historical['adt_sha256'],qualification_sha256=sha(qualification.read_bytes()),
 nonce_init=dict(entry='0xfffffff0046ecc14',direct_bl_candidates=callers,gate_close_call='0xfffffff0046eccc8',gate_close_slot=hex(gate_slot),gate_close_target=hex(gate_target),scope='Static actual call before persisted-seed read; not a runtime gate-state sample'),
 reuse='Exact early Image4 code/data coverage retained; different measured ADT is bound to existing CHECK5 final launch qualification. This is not a new complete-init execution on CHECK5 or hardware acceptance.',
 historical_hardware='PROBE19 reached BSD after early Image4/MAC per docs/operations/2026-10-25-v27-image4-to-bsd.md; no new device observation.',
 aes_reference=dict(source_sha256=sha(source),abi_sha256=sha(abi),raw_key_selector=0,nonzero_selector='explicitly rejected by reference implementation',ios16_link_abi_qualified=False,copy_into_candidate=False),
 priority='Do not repeat early /chosen/init tests. Separate later IOService AES dependency and nonce gate from early MAC initialization; prioritize actual object mapping and post-init consumer inputs.')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print('PASS current Image4 ranges identical; early coverage reused; NativeAES is not a qualified drop-in')
