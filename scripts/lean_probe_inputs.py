"""Strict independent binding for layout-preserving PROBE57 retirement."""
import hashlib,json,struct
from pathlib import Path
R=Path(__file__).resolve().parents[1]
BASE=R/'reports/kernel-entry-probe/2026-10-29-probe55-provenance-r3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def ref(p):return dict(path=p.relative_to(R).as_posix(),sha256=sha(p))
def bound(item):
 p=(R/item['path']).resolve();assert p.is_relative_to(R/'reports') and sha(p)==item['sha256'];return read(p)
def metadata(build):
 folder=build.resolve().parent
 return {name:ref(folder/('lean-proof-v2.json' if name=='lean-proof' else name+'.json')) for name in ('build','lean-proof','root-launch','launch-context','console-policy','transition-normal','transition-occupied-probe','transition-bad-topology','transition-occupied-fb')}
def verify_bytes(b,raw):
 if b.get("probe_revision")==72:
  from sync_trace_inputs import verify_bytes as sync_verify
  return sync_verify(b,raw)
 if b.get("probe_revision")==71:
  from flush_trace_inputs import verify_bytes as flush_verify
  return flush_verify(b,raw)
 if b.get("probe_revision")==70:
  from tlb_trace_inputs import verify_bytes as tlb_verify
  return tlb_verify(b,raw)
 if b.get("probe_revision")==69:
  from pmap_trace_inputs import verify_bytes as pmap_verify
  return pmap_verify(b,raw)
 if b.get("probe_revision")==68:
  from delete_trace_inputs import verify_bytes as delete_verify
  return delete_verify(b,raw)
 if b.get("probe_revision")==67:
  from map_trace_inputs import verify_bytes as map_verify
  return map_verify(b,raw)
 if b.get("probe_revision")==66:
  from upl_trace_inputs import verify_bytes as upl_verify
  return upl_verify(b,raw)
 if b.get('probe_revision')==65:
  from unmap_trace_inputs import verify_bytes as unmap_verify
  return unmap_verify(b,raw)
 if b.get('probe_revision')==64:
  from completion_trace_inputs import verify_bytes as completion_verify
  return completion_verify(b,raw)
 if b.get('probe_revision')==63:
  from mdev_trace_inputs import verify_bytes as mdev_verify
  return mdev_verify(b,raw)
 if b.get('probe_revision')==62:
  from backend_trace_inputs import verify_bytes as backend_verify
  return backend_verify(b,raw)
 if b.get('probe_revision')==61:
  from init_bridge_inputs import verify_bytes as bridge_verify
  return bridge_verify(b,raw)
 if b.get('probe_revision')==60:
  from strategy_target_inputs import verify_bytes as target_verify
  return target_verify(b,raw)
 if b.get('probe_revision')==59:
  from root_progress_inputs import verify_bytes as root_verify
  return root_verify(b,raw)
 if b.get('milestone_observation'):
  from milestone_probe_inputs import verify_bytes as verify_milestones
  return verify_milestones(b,raw)
 prior=read(BASE/'build.json');old=(R/prior['candidate']['path']).read_bytes()
 assert hashlib.sha256(old).hexdigest()==prior['candidate']['sha256']==b['lean_observation']['baseline_sha256']
 assert b['probe_revision']==57 and b['probe']['symbols']==prior['probe']['symbols'] and len(raw)==len(old)
 expected=bytearray(old);seen=set();restored=set()
 for row in b['lean_observation']['changes']:
  at=row['file_offset'];assert at not in seen;seen.add(at)
  before=bytes.fromhex(row['before']);after=bytes.fromhex(row['after']);assert len(before)==len(after)==4 and old[at:at+4]==before
  if row['kind']=='restore-native':
   patch=next(p for p in prior['patches'] if p['reason']==row['reason'])
   assert patch['file_offset']==at and patch['before']==row['after'] and patch['after']==row['before'];restored.add(row['reason'])
  else:
   assert row['kind']=='skip-render';start=int(row['va'],16);end=int(row['end'],16);assert end>start and (end-start)%4==0
   assert at==prior['probe']['file_offset']+start-int(prior['probe']['va'],16)
   assert struct.unpack('<I',after)[0]==0x14000000|((end-start)//4)
  expected[at:at+4]=after
 assert bytes(expected)==raw,'Unlisted byte change or missing retirement'
 assert b['patches']==[p for p in prior['patches'] if p['reason'] not in restored]
 assert b['root_mount_diagnostic']==prior['root_mount_diagnostic'] and b['image4_compatibility']==prior['image4_compatibility']
 assert b['pthread_startup']==prior['pthread_startup'] and b['fscompression_startup']==prior['fscompression_startup']
 return True
def validate(meta,kernel_sha):
 b=bound(meta['build']);proof=bound(meta['lean-proof']);path=(R/b['candidate']['path']).resolve();assert path.is_relative_to(R/'out')
 assert sha(path)==kernel_sha==b['candidate']['sha256']==proof['candidate_sha256']
 assert b['loadable'] is False and b['runtime_qualified'] is False
 assert sha(R/'scripts/build-lean-observation.py')==b['lean_observation']['source_sha256']
 verify_bytes(b,path.read_bytes())
 q=read(BASE/'qualification.json')
 for item in q['evidence']+[q['sources']]:assert sha(R/item['path'])==item['sha256']
 for item in read(R/q['sources']['path'])['sources']:assert sha(R/item['archive'])==item['sha256']
 for item in proof['sources']:
  assert sha(R/item['path'])==item['sha256']==sha(R/item['archive'])
 required={'scopes','bootstrap','transparency','vectors','pthread-startup','fscompression-startup','root-stop','root-inputs','read-boundaries','strategy-continuity','io-native-entry','vm-continuity','x18-interruption','read-vector-path','image4-launch','console-policy','transition-normal','transition-occupied-probe','transition-bad-topology','transition-occupied-fb','negative-controls'}
 assert set(proof['tests'])==required
 expected_counts={name:q['check_counts'][name] for name in required-{'scopes','bootstrap','transparency','negative-controls'}}
 excluded={'probe_entry','probe_tables','probe_mmu','probe_mmu_on','probe_ttbr1','probe_ttbr0','probe_console_policy'}
 expected_counts.update(scopes=2750,bootstrap=4,transparency=4*sum(p['reason'].startswith('probe_') and p['reason'] not in excluded for p in b['patches']),**{'negative-controls':5})
 assert proof['counts']==expected_counts
 for name,item in proof['tests'].items():
  report=bound(item);assert report['candidate_sha256']==kernel_sha
  checks=report.get('checks',report.get('cases'));assert checks and all(c['passed'] is True for c in checks),name
  assert len(checks)==proof['counts'][name]
 assert proof['independent_reproduce_sha256']==kernel_sha and sha(R/proof['independent_reproduce_path'])==kernel_sha
 reproduce=bound(proof['reproduce_build'])
 assert reproduce['candidate']['sha256']==kernel_sha and reproduce['lean_observation']['changes']==b['lean_observation']['changes']
 from nuwa_exec_detail_launch_context import API
 API.validate_report(bound(meta['root-launch']))
 assert bound(meta['root-launch'])['candidate_sha256']==kernel_sha
 assert bound(meta['launch-context'])['components']['kernel']['sha256']==kernel_sha
 return b
