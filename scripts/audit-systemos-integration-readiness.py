"""Bounded SystemOS carry-forward review and native VFS ownership contracts."""
import argparse,hashlib,json,struct
from pathlib import Path
import exec_carrier_model as H
from exec_carrier_model import *
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
H.EXPECTED='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e';c=Carrier(t.R/'out/ufs-check-5-r1-qualified');rows=[]
for symbol,offset,get in [('_vfs_vnodecovered',0x38,'_vnode_getwithref'),('_vfs_devvp',0x980,'_vnode_get')]:
 for case,pointer,error in [('owned',VNODE,0),('missing',0,0),('reclaim',VNODE,2)]:
  m=Machine(c);m.put(MOUNT+offset,pointer);calls=[]
  def acquire():assert m.x(0)==VNODE;calls.append(get);m.ret(error)
  m.stub(get,acquire);m.x(0,MOUNT);m.run(symbol)
  assert m.x(0)==(VNODE if pointer and not error else 0) and len(calls)==bool(pointer)
  row=m.record(symbol+'_'+case);row['acquire_calls']=calls;rows.append(row)
write_report(a.output,c,rows,'Actual VFS covered/dev vnode accessors. vnode_get/getwithref are explicit lifetime boundaries; positive output owns acquired iocount, failed acquisition returns null. No actual mount or vnode reclaim scheduler.')
r=json.loads(a.output.read_bytes());refs={}
for rel in ['reports/payload-s1-r1/offline-package-r2.json','reports/desktop-readiness/2026-11-02-payload-preboot-contract-r1/native-boundaries.json',
 'reports/desktop-readiness/2026-11-02-payload-preboot-contract-r1/ignition-blob-reader.json','package/verified-root/NuwaSystemOsMount.cpp','package/verified-root/NuwaSystemOsTransaction.h',
 'package/verified-root/NuwaSystemOsMountPlan.h','package/verified-root/NuwaSystemOsSyscall.c','package/kernel-mainline/SystemOsMount-r1.S']:
 refs[rel]=hashlib.sha256((t.R/rel).read_bytes()).hexdigest()
payload=(t.R/'out/payload-s1-r1/kernel.macho').read_bytes();pq=json.loads((t.R/'reports/payload-s1-r1/offline-package-r2.json').read_bytes());assert hashlib.sha256(payload).hexdigest()==pq['kernel_sha256']
pm=c.b.macho(payload);site=BASE+0x769d2f8
def branch(raw,m):
 word=struct.unpack_from('<I',raw,c.b.backed(m,site,4))[0];assert word&0x7c000000==0x14000000
 imm=word&0x3ffffff;imm=imm-(1<<26) if imm&(1<<25) else imm
 return dict(instruction=hex(word),target=hex(site+imm*4))
old=branch(payload,pm);current=branch(c.raw,c.m);assert current['target']==hex(c.sy['_memorystatus_init_at_boot_snapshot']) and old!=current
dyldreport=t.R/'reports/desktop-readiness/2026-11-02-payload-dyld-startup-r2/audit.json';dr=json.loads(dyldreport.read_bytes())
assert dr['passed'] and dr['mount_cleanup_complete']
# Check the extracted input is still one of the originally audited byte streams.
dyldhash=hashlib.sha256((t.R/'out/payload-dyld-startup-r2/dyld').read_bytes()).hexdigest()
assert dyldhash in dyldreport.read_text()
r.update(script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),refs=refs,dyld_input_sha256=dyldhash,
 injection_site=hex(site),payload_s1=old,check5=current,check5_contains_systemos_mount=False,
 carry_forward=['relink only selected SystemOS/trust components against CHECK5 imports and allocation ranges; never use old payload whole kernel',
 'preserve CHECK5 observer cleanup and new exec-thread latch; regenerate independent package only when integration is justified',
 'keep PID1/scratch/single-attempt guard, original-root authorization, selected device identity, native mount and postcondition checks',
 'mount returning zero followed by upper authorization failure stays fatal; no speculative unmount after checkdirs',
 'failure-visible E codes do not detect nonreturn inside selector/mount/cleanup; lack of E is not completion',
 'preserve original trust module checks and native policy; static_loaded alone is insufficient'],
 nonce_caller_order=dict(callsite='0xfffffff0046eebbc',first='nonce-lock loop at 0xfffffff0046ed9ec',next='0xfffffff0046ed6bc',
 boundary='gate open precedes next function; no proof blob is populated/authenticated at gate-open'),
 manifest_decision='No change to standard property or bit3/4. Existing diagnostic hash is not Apple IM4M; indirect consumers and runtime blob/boot-spec validity remain separate gates.',
 candidate_changed=False,device_root_cause_confirmed=False)
a.output.write_text(json.dumps(r,indent=2)+'\n');print('PASS SystemOS integration contract and 6 native VFS accessor cases')
