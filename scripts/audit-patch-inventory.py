"""Snapshot patch purpose separately from selection, activation and field necessity.

Read-only inputs; a fresh JSON output is mandatory. Never removes patches.
"""
import argparse,collections,hashlib,json,re
from pathlib import Path
import resource_cluster_sites as C
ROOT=Path(__file__).resolve().parents[1]
CATEGORIES={'startup-adaptation','observation','mixed','control-guard','unreviewed'}
FIRMWARE={1:('startup-adaptation','shim plus FD image size'),2:('startup-adaptation','loader and initrd publisher wiring'),3:('startup-adaptation','read-only initrd publisher and HOB validation'),4:('startup-adaptation','SEC x0 GUID HOB producer'),5:('mixed','stage traces and splash clearing removal'),6:('startup-adaptation','relative text offset'),7:('startup-adaptation','PIL ABL boot selection'),8:('observation','allocation-state scan under existing lock'),9:('unreviewed','review-controlled heap layout proposal'),10:('observation','HOB and constructor traces'),11:('observation','constructor entry and returned status'),12:('observation','MMU constructor branch traces'),13:('observation','bounded HOB traversal traces'),14:('control-guard','invalid HOB CpuDeadLoop'),15:('control-guard','five-second recording pause'),16:('mixed','embedded diagnostic FAT and volume publisher'),17:('observation','BootAudit module selection; driver behavior needs binding'),18:('mixed','HOB audit and integrity path'),19:('mixed','pre-MMU HOB cache callback and audit'),20:('observation','FileAudit module selection; driver behavior needs binding')}
PURE={'probe_entry','probe_tables','probe_mmu_on','probe_cpu_base','probe_arm_vm','probe_pmap','probe_kernel_bootstrap','probe_avm_bases','probe_avm_memcheck','probe_avm_physmap','probe_avm_slide','probe_dt_lookup','probe_soc_base','probe_cpu_topo','probe_cpu_bootstrap','probe_machine_startup','probe_panic','probe_panic_options','probe_panic_trap','probe_timer_regs','probe_wfe_timeout','probe_wfe_init','probe_misc_boot_args','probe_misc_regs'}
MIXED={'probe_mmu':'MAP_FB and SNAP_VIDEO support diagnostics across translation','probe_arm_init':'TPIDR_EL1 early zero-page shim and marker','probe_ttbr0':'diagnostic translation handoff','probe_ttbr1':'diagnostic translation handoff','probe_console_policy':'no-pram policy routing and explicit unsupported-region stop'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ref(p):return dict(path=str(p.resolve()),sha256=sha(p))
def dense_body(assembly,label):
 start=assembly.find('\n'+label+':\n');end=assembly.find('\n.global '+label+'_replay',start)
 return assembly[start:end] if start>=0 and end>start else ''
def simple_dense(body,label):
 lines=[x.strip() for x in body.splitlines() if x.strip()]
 return bool(lines) and lines[0]==label+':' and all(x in ('PROBE_SAVE','PROBE_RESTORE') or re.fullmatch(r'DENSE_ONCE [0-9]+, 0x[0-9a-f]+',x) for x in lines[1:]) and 'PROBE_RESTORE' in lines
def classify(p,b,assembly):
 reason=p['reason'];site=int(p['va'],16) if p.get('va') else None
 if reason==b['root_mount_diagnostic']['hook']:return 'control-guard','conditional release239 boundary'
 if reason.startswith('probe_backend_trace_'):return 'observation','Scoped first-request backend/completion observation; revision-specific retired-code generator and exact replay checks; native policy unchanged'
 if reason in MIXED:return 'mixed',MIXED[reason]
 if reason in PURE:return 'observation','reviewed entry-probe.S snapshot/render and native replay'
 if reason.startswith('pthread_prelink_range_'):return 'startup-adaptation','pthread prelink overlay; not diagnostic-only'
 if reason in ('image4_amnm_provider','image4_chmh_provider'):return 'startup-adaptation','provider routing; native result preserved'
 if reason.startswith('Suppress BCM2837'):return 'startup-adaptation','suppresses foreign BCM MMIO; not mere tracing'
 if reason.startswith('Capture early exception'):return 'control-guard','exception snapshot then diagnostic stop'
 if reason in ('Add one bounded RX diagnostic segment','Use verified zero load-command padding'):return 'mixed','container for both startup shims and observations'
 if site in {x['site'] for x in C.points()}:return 'observation','scoped cluster observer; parent entry/call/return dependencies retained'
 if reason.startswith('probe_dense_'):
  body=dense_body(assembly,reason)
  if simple_dense(body,reason):return 'observation','exact generated save/DENSE_ONCE/restore stencil'
  if any(x in body for x in ('RESTORE_NATIVE_VECTORS','DISPLAY_INIT','pthread_load_before_bsd','fscompression_load')):return 'mixed','generated handoff/provider/display work mixed with observation'
 return 'unreviewed','needs explicit source and dependency review; no deletion inferred'
def row(category,why,**kw):
 assert category in CATEGORIES
 return dict(category=category,rationale=why,removal_allowed=False,necessity_proven=False,dependency_review='retain producers, consumers, native replay and diagnostic scope closure; mixed effects require split first',cost='No hardware timing measured. Hooks may save registers, read/write state and framebuffer; source-only entries require runtime selection binding.',**kw)
def carrier_snapshot(path, build, output):
    parent_path = Path(build['parent_build'])
    parent = json.loads(parent_path.read_bytes())
    parent_kernel = ROOT/parent['candidate']['path']
    assert sha(parent_kernel) == build['parent_sha256']
    kernel = path.parent/'kernel.macho'
    assert sha(kernel) == build['kernel_sha256']
    entries = []
    for index, change in enumerate(build['changes']):
        category = ('observation' if (change['reason'].startswith('first-visit coarse milestone:') or change['reason'] in ('AMFI original AON calls returned', 'existing panic tile becomes red banner'))
                    else 'mixed' if change['reason'] == 'BSD root selector observer' else 'startup-adaptation')
        if change['reason']=='first-visit coarse milestone: root_auth': category='mixed'
        if change['reason'] in ('first-visit coarse milestone: init_hold','first-visit coarse milestone: exec_hold'): category='control-guard'
        if change['reason'].startswith(('retire legacy diagnostic body:', 'retire early drawing-only hook:', 'retire unused exec-state prefix;')): category='observation'
        if 'bounded PID1' in change['reason']: category='observation'
        if change['address']=='0xfffffff00769d230': category='control-guard'
        entries.append(row(category, change['reason'], id='overlay-'+str(index), layer='kernel',
                           status='retired-or-replaced-in-candidate' if change['reason'].startswith('retire ') else 'in-built-candidate', patch=change))
    for obj in build['objects']:
        source = Path(obj['path'])
        assert sha(source) == obj['sha256']
        entries.append(row('mixed', 'Real NativeUfs implementation, gated metadata publication and phase counters',
                           id='object:'+source.name, layer='kernel', status='linked-in-candidate', file=ref(source)))
    if build.get('kernel_reused_byte_identically'):
        entries.append(row('control-guard', 'Native launchdsuffix=release selects real launchd; success continues, failure retains native panic; no authentication bypass',id='native-release-selection',layer='configuration',status='in-built-candidate'))
    coarse = 'coarse_state' in build['targets']
    r2 = 'el0_resume' in build['targets']
    source = ROOT/('package/kernel-mainline/CoarseStages-ufs-check4-r1.S' if 'ufs-check-4' in path.as_posix() else 'package/kernel-mainline/CoarseStages-ufs-check2-r1.S' if any(tag in path.as_posix() for tag in ('ufs-check-2','ufs-check-3')) else 'package/kernel-mainline/CoarseStages-ufs-check-r1.S' if 'ufs_probe_bind' in build.get('targets',{}) else 'package/kernel-mainline/CoarseStages-neighbor-r1.S' if 'coarse_n_neighbor_before' in build.get('symbols',{}) else 'package/kernel-mainline/CoarseStages-search-r1.S' if 'sscope_fast' in build.get('symbols',{}) else 'package/kernel-mainline/CoarseStages-btree-r1.S' if 'qscope_fast' in build.get('symbols',{}) else 'package/kernel-mainline/CoarseStages-inode-r1.S' if 'nscope_fast' in build.get('symbols',{}) else 'package/kernel-mainline/CoarseStages-vget-r1.S' if 'bscope_fast' in build.get('symbols',{}) else 'package/kernel-mainline/CoarseStages-apfs-fast-r1.S' if 'apfs_fast_reject' in build.get('symbols',{}) else 'package/kernel-mainline/CoarseStages-apfs-path-r1.S' if 'exec_apfs_call1_target' in build['targets'] else 'package/kernel-mainline/CoarseStages-apfs-lock-r1.S' if 'exec_apfs_locked_old' in build['targets'] else 'package/kernel-mainline/CoarseStages-apfs-r1.S' if 'exec_apfs_entry_old' in build['targets'] else 'package/kernel-mainline/CoarseStages-scoped-vnop-r1.S' if 'vnop_lookup_desc' in build['targets'] else 'package/kernel-mainline/CoarseStages-vnop-r1.S' if 'exec_callback_resume' in build['targets'] else 'package/kernel-mainline/CoarseStages-lookup-r1.S' if 'exec_vnop_zero' in build['targets'] else 'package/kernel-mainline/CoarseStages-namei-r1.S' if 'exec_lookup_zero' in build['targets'] else 'package/kernel-mainline/CoarseStages-path-r1.S' if build['targets'].get('exec_read_old') == 0xfffffff0076a0384 else 'package/kernel-mainline/CoarseStages-activate-r1.S' if 'exec_namei_target' in build['targets'] else 'package/kernel-mainline/CoarseStages-exec-r1.S' if 'exec_entry_old' in build['targets'] else 'package/kernel-mainline/CoarseStages-init-r1.S' if 'init_alloc_target' in build['targets'] else 'package/kernel-mainline/CoarseStages-root-r1.S' if build.get('owner_root_binding_enabled') else 'package/kernel-mainline/CoarseStages-pmgr-r1.S' if 'pmgr_alloc' in build['targets'] else 'package/kernel-mainline/CoarseStages-r2.S' if r2 else 'package/kernel-mainline/CoarseStages.S' if coarse else 'package/kernel-mainline/MetadataEntry.S')
    if build.get('observer_source'):source=ROOT/build['observer_source']
    assert sha(source) == build['source_sha256']
    entries.append(row('mixed', 'Storage loading, class registration, one root-entry observer and native resume on success',
                       id='metadata-entry', layer='kernel', status='in-built-candidate', file=ref(source)))
    sources = [ROOT/('scripts/build-ufs-check4-r1.py' if 'ufs-check-4' in path.as_posix() else 'scripts/build-ufs-check2-r1.py' if any(tag in path.as_posix() for tag in ('ufs-check-2','ufs-check-3')) else 'scripts/build-ufs-check1-r1.py' if 'ufs_probe_bind' in build.get('targets',{}) else 'scripts/build-ufs-kmain21-r1.py' if 'coarse_n_neighbor_before' in build.get('symbols',{}) else 'scripts/build-ufs-kmain20-r1.py' if 'sscope_fast' in build.get('symbols',{}) else 'scripts/build-ufs-kmain19-r1.py' if 'qscope_fast' in build.get('symbols',{}) else 'scripts/build-ufs-kmain18-r1.py' if 'nscope_fast' in build.get('symbols',{}) else 'scripts/build-ufs-kmain17-r1.py' if 'bscope_fast' in build.get('symbols',{}) else 'scripts/build-ufs-kmain16-r1.py' if 'apfs_fast_reject' in build.get('symbols',{}) else 'scripts/build-ufs-kmain15-r1.py' if 'exec_apfs_call1_target' in build['targets'] else 'scripts/build-ufs-kmain14-r1.py' if 'exec_apfs_locked_old' in build['targets'] else 'scripts/build-ufs-kmain13-r1.py' if 'exec_apfs_entry_old' in build['targets'] else 'scripts/build-ufs-kmain12-r1.py' if 'vnop_lookup_desc' in build['targets'] else 'scripts/build-ufs-kmain11-r2.py' if 'kmain-11-r2' in path.as_posix() else 'scripts/build-ufs-kmain11-r1.py' if 'exec_callback_resume' in build['targets'] else 'scripts/build-ufs-kmain10-r1.py' if 'exec_vnop_zero' in build['targets'] else 'scripts/build-ufs-kmain9-r1.py' if 'exec_lookup_zero' in build['targets'] else 'scripts/build-ufs-kmain8-r1.py' if build['targets'].get('exec_read_old') == 0xfffffff0076a0384 else 'scripts/build-ufs-kmain7-r1.py' if 'exec_namei_target' in build['targets'] else 'scripts/build-ufs-kmain6-r1.py' if 'exec_entry_old' in build['targets'] else 'scripts/build-ufs-kmain5-r1.py' if 'init_alloc_target' in build['targets'] else 'scripts/build-ufs-kmain4-r1.py' if build.get('owner_root_binding_enabled') else 'scripts/build-ufs-kmain3-r1.py' if 'pmgr_alloc' in build['targets'] else 'scripts/build-ufs-kmain2-r3.py' if 'kmain-2-r3' in str(path) else 'scripts/build-ufs-kmain2-r2.py' if r2 else 'scripts/build-ufs-kmain2.py' if coarse else 'scripts/build-ufs-iokit-mainline.py'), ROOT/'scripts/ufs_carrier_object_link.py',
               ROOT/'config/ramblock-ios16-link-contract.json', ROOT/'docs/PATCH-INVENTORY.md', Path(__file__)]
    result = dict(schema=2, build=ref(path), kernel=ref(kernel), parent_build=ref(parent_path),
                  parent_kernel=ref(parent_kernel), entries=entries, mapped_sections=build['chunks'],
                  scope='Exact overlay delta and CI objects. Historical parent patches remain in the linked parent build.',
                  sources=[ref(p) for p in sources], counts=dict(collections.Counter(e['category'] for e in entries)),
                  device_accessed=False)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed=True, overlay_entries=len(entries))))

def main():
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('--build',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a=a.parse_args()
 assert not a.output.exists();b=json.loads(a.build.read_bytes())
 if b.get('schema')=='nuwa.native-ufs-carrier.v1':
  carrier_snapshot(a.build,b,a.output);return
 kernel=ROOT/b['candidate']['path'];assert sha(kernel)==b['candidate']['sha256']
 assembly_path=kernel.parent/'probe.S';assembly=assembly_path.read_text(encoding='utf-8')
 rows=[]
 for index,p in enumerate(b['patches']):
  category,why=classify(p,b,assembly)
  rows.append(row(category,why,id=f'kernel-patch-{index}',layer='kernel',status='in-built-candidate',patch=p,source='scripts/build-kernel-entry-probe.py + generated probe.S',validation='native replay, scope/ancestry, full candidate evidence',retirement='review dependencies and generate a new candidate'))
 for p in C.removed_points():rows.append(row('observation','PROBE54 retired scoped cluster point',id=f'removed-{p["site"]:x}',layer='kernel',status='removed-in-candidate',point=p,source='scripts/resource_cluster_sites.py',validation='test-cluster-hook-removal.py',retirement='already removed; no claim of field root cause'))
 for p in sorted((ROOT/'patches').rglob('*')):
  if not p.is_file() or p.suffix not in ('.patch','.S'):continue
  cat,why='unreviewed','candidate file presence is not proof of selection or runtime effect'
  if p.parent.name=='firmware-candidates':cat,why=FIRMWARE.get(int(p.name[:4]) if p.name[:4].isdigit() else -1,('unreviewed','new firmware candidate requires explicit purpose review'))
  rows.append(row(cat,why,id='source:'+p.relative_to(ROOT).as_posix(),layer='uefi' if p.parent.name=='firmware-candidates' else 'source-candidate',status='source-present-activation-unbound',file=ref(p),validation='bind exact build selection and emitted binary before retirement',retirement='no automatic removal'))
 firmware=ROOT.parent/'uefi-nuwa/Platforms/Xiaomi/nuwaPkg'
 files=[firmware/'nuwa.dsc',firmware/'nuwa.fdf',ROOT/'package/entry-probe/entry-probe.S',ROOT/'scripts/probe_bootstrap_sites.py',ROOT/'scripts/resource_cluster_sites.py',ROOT/'docs/PATCH-INVENTORY.md',Path(__file__)]
 prior=json.loads((ROOT/'reports/kernel-entry-probe/2026-10-29-probe53-io-r2/root-launch.json').read_bytes())
 current=json.loads((a.build.parent/'root-launch.json').read_bytes())
 for key in ('fd_path','shim_path'):assert current[key]==prior[key]
 image_refs=[ref(ROOT/prior[k]) for k in ('fd_path','shim_path')]
 package=json.loads((ROOT/'reports/xnu-first-entry/entry-probe-53.json').read_bytes())
 assert image_refs[0]['sha256']==package['fd_sha256'] and image_refs[1]['sha256']==package['shim_sha256']
 assert len(rows)==len({x['id'] for x in rows})
 assert all(not x['removal_allowed'] and not x['necessity_proven'] for x in rows)
 assert classify(dict(reason='unknown',va=None),b,assembly)[0]=='unreviewed'
 assert not simple_dense('label:\nPROBE_SAVE\nmsr tpidr_el1,x0\nPROBE_RESTORE','label')
 assert classify(dict(reason='probe_arm_init',va=None),b,assembly)[0]=='mixed'
 out=dict(schema=1,build=ref(a.build),kernel=ref(kernel),assembly=ref(assembly_path),sources=[ref(p) for p in files],firmware_inherited_from_probe53=image_refs,firmware_source_to_image_binding='not established by this inventory; DSC/FDF is current source only',scope='all current builder patch records, retired cluster sites and candidate source files; baseline prelink internal history not fully classified',counts=dict(collections.Counter(x['category'] for x in rows)),entries=rows,checks=['complete patch count and unique IDs','unknown stays unreviewed','mixed TPIDR shim protected','side-effect stencil rejected','no automatic deletion or necessity claim'],device_accessed=False)
 a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(entries=len(rows),counts=out['counts'],passed=True)))
if __name__=='__main__':main()
