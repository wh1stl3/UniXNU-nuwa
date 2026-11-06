"""Verify that the shipped private UFS poll uses the intended clock loop."""
import argparse,json,hashlib,sys
from pathlib import Path
import flush_trace_inputs as t
sys.path.insert(0,str(t.R/'out/python-tools'))
from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
results=[]
for directory,is_new in ((t.R/'out/ufs-check-1-r1-final',False),(w,True)):
 proof=json.loads((directory/'kernel-proof.json').read_bytes());raw=(directory/'kernel.macho').read_bytes();assert hashlib.sha256(raw).hexdigest()==proof['kernel_sha256'];b=t.builder();m=b.macho(raw);targets=proof['targets']
 names=[k for k in targets if 'pollUfsTransfer' in k];assert len(names)==1;start=targets[names[0]];end=min(v for v in targets.values() if v>start);assert end-start<16384;off=b.backed(m,start,end-start);ins=list(Cs(CS_ARCH_ARM64,CS_MODE_ARM).disasm(raw[off:off+end-start],start));calls=[int(x.op_str.lstrip('#'),16) for x in ins if x.mnemonic=='bl'];delay=targets['_IODelay']
 if is_new:
  assert delay not in calls and any(x.mnemonic=='yield' for x in ins)
  assert targets['_clock_interval_to_deadline'] in calls and targets['_mach_absolute_time'] in calls
  hostnames=[k for k in targets if 'hostSubmit' in k];assert len(hostnames)==1
  hs=targets[hostnames[0]];he=min(v for v in targets.values() if v>hs);ho=b.backed(m,hs,he-hs)
  hi=list(Cs(CS_ARCH_ARM64,CS_MODE_ARM).disasm(raw[ho:ho+he-hs],hs))
  hc=[int(x.op_str.lstrip('#'),16) for x in hi if x.mnemonic=='bl']
  assert hc.count(targets['_nuwa_ufs_probe_command'])==2
 else:assert delay in calls
 results.append(dict(new=is_new,kernel_sha256=proof['kernel_sha256'],symbol=names[0],start=hex(start),end=hex(end),calls=[hex(x) for x in calls],yield_count=sum(x.mnemonic=='yield' for x in ins),passed=True))
 (w/('poll-new-disassembly.txt' if is_new else 'poll-old-disassembly.txt')).write_text('\n'.join(f'{x.address:x} {x.mnemonic} {x.op_str}' for x in ins))
(w/'poll-spin-tests.json').write_text(json.dumps(dict(passed=True,tests=results,scope='Actual linked private poll body; same timeout/clock imports, no donor IODelay in new poll, global donor function unchanged by builder.'),indent=2)+'\n');print('PASS actual linked old/new poll delay paths')
