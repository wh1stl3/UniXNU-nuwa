"""Bind convergence decisions to frozen carrier/ADT and prior device evidence.
No code-page/cache/slide replay, firmware generation, or device access.
"""
import argparse,hashlib,json,struct
from pathlib import Path
import flush_trace_inputs as trace
import nuwa_launch_context as context
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
R=trace.R;sha=lambda x:hashlib.sha256(x).hexdigest()
def load(name):return json.loads((R/name).read_bytes())
trial=load('reports/kmain-15-r1/trial/result.json')
assert trial['root_mount_return_observed'] and trial['init_entry_observed'] and not trial['functional_root_cause_confirmed']
q=load('reports/payload-s1-r1/offline-package-r2.json');proof=load('out/payload-s1-r1/kernel-proof.json')
raw=(R/'out/payload-s1-r1/kernel.macho').read_bytes();assert sha(raw)==q['kernel_sha256']==proof['kernel_sha256']
assert proof['ci_source_kernel_sha256']==q['ci_source_kernel_sha256']!=sha(raw)
B=trace.builder();m=B.macho(raw)
def block(blob,parsed,va,n):off=B.backed(parsed,va,n);return blob[off:off+n]
def branch(pc,b):
 w=int.from_bytes(b,'little');assert w&0x7c000000==0x14000000
 n=w&0x3ffffff;return pc+((n-(1<<26) if n&(1<<25) else n)*4)
site=0xfffffff00769d2f8;word=block(raw,m,site,4)
target=proof['targets']['_nuwa_systemos_mount_trampoline'];target=int(target,0) if isinstance(target,str) else target
assert branch(site,word)==target
old=(R/'out/kmain-16-r1-final/kernel.macho').read_bytes();om=B.macho(old);ow=block(old,om,site,4)
assert branch(site,ow)==om['symbols']['_memorystatus_init_at_boot_snapshot']
adt=(R/'out/payload-s1-r1/launch/kernel.macho.adt').read_bytes()
assert sha(adt)==q['files']['kernel.macho.adt']
ch=context.properties(context.find(context.parse(adt),'/chosen'));manifest=ch['nuwa-launch-manifest']
assert ch['boot-manifest-hash']==hashlib.sha384(manifest).digest()
assert json.loads(manifest)['trust']['apple_im4m'] is False
amfi=load('reports/desktop-readiness/2026-11-02-payload-convergence-r1/native-amfi-r3.json')
assert amfi['passed'] and amfi['kernel_sha256']==sha(raw) and not amfi['device_amfi_acceptance']
report=dict(passed=True,device_accessed=False,images_generated=False,
 baseline=dict(candidate=trial['candidate'],result_sha256=sha((R/'reports/kmain-15-r1/trial/result.json').read_bytes()),root_mount_return=True,init_entry=True,root_cause_closed=False),
 candidates=dict(next='KMAIN-16 r1',reason='Restore existing init/VNOP visibility without introducing SystemOS mount',payload_s1_automatic_priority=False),
 carrier=dict(kernel_sha256=sha(raw),ci_source_kernel_sha256=q['ci_source_kernel_sha256'],distinct=True,mount_site=hex(site),payload_s1_instruction=word.hex(),payload_s1_target=hex(target),kmain16_instruction=ow.hex(),kmain16_target=hex(branch(site,ow)),kmain16_kernel_sha256=sha(old)),
 mount_nonreturn=dict(resolved=False,existing_visible_lower_bound='init entry',existing_visible_upper_bound='scoped exec entry FB10 bit 0',error_only='E0/E1',result_memory_is_persistent_log=False),
 trust=dict(native_load_query_closed_offline=True,actual_registration_device_verified=False,device_acceptance=False,evidence='native-amfi-r3.json'),
 ignition=dict(adt_sha256=sha(adt),boot_manifest_hash_bytes=len(ch['boot-manifest-hash']),boot_manifest_hash_is_diagnostic_sha384=True,apple_manifest_verified=False,boot_objects_path_present='boot-objects-path' in ch,actual_preboot_mount_verified=False,bit3_changed=False),
 unchanged_qualified_checks=['code pages','cache layout','slide'],script_sha256=sha(Path(__file__).read_bytes()))
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
print('PASS carrier/ADT convergence bindings; device gates remain open')
