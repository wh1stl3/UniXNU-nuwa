"""PROBE58: exact nine-marker restoration over archived PROBE57.

Qualification distinguishes inherited unchanged-code tests from current tests.
"""
import hashlib,json,struct
from pathlib import Path
R=Path(__file__).resolve().parents[1]
P57=R/'reports/kernel-entry-probe/2026-10-30-probe57-lean-r1'
P55=R/'reports/kernel-entry-probe/2026-10-29-probe55-provenance-r3'
MARKERS={'probe_entry','probe_mmu','probe_mmu_on','probe_arm_init','probe_kernel_bootstrap','probe_dense_7944b18','probe_dense_76729e0','probe_dense_744377c','probe_dense_769d2a4'}
TESTS={'bootstrap','milestones','vectors','pthread-startup','fscompression-startup','root-stop','root-inputs','read-boundaries','strategy-continuity','io-native-entry','vm-continuity','x18-interruption','read-vector-path','image4-launch','console-policy','transition-normal','transition-occupied-probe','transition-bad-topology','transition-occupied-fb','negative-controls'}
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ref(p):return dict(path=p.resolve().relative_to(R).as_posix(),sha256=sha(p))
def selected(c):
 return (c['kind']=='restore-native' and c['reason'] in MARKERS) or (c['kind']=='skip-render' and c['function'] in MARKERS and c['invocation'].split()[0] in {'BAND','BAND_ONCE','DENSE_ONCE'})
def inherited():
 q=read(P57/'qualification.json')
 for name in ('build','proof'):
  item=q[name];assert sha(R/item['path'])==item['sha256']
 old=read(P57/'build.json');raw=(R/old['candidate']['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==old['candidate']['sha256']
 proof=read(P57/'lean-proof-v2.json')
 for item in proof['sources']:assert sha(R/item['archive'])==item['sha256']
 for item in proof['tests'].values():assert sha(R/item['path'])==item['sha256']
 assert proof['candidate_sha256']==old['candidate']['sha256']
 return old,raw
def verify_bytes(b,raw):
 old,prior=inherited();changes=[c for c in old['lean_observation']['changes'] if selected(c)]
 assert len(changes)==14 and sum(c['kind']=='skip-render' for c in changes)==9
 assert b['probe_revision']==58 and b['milestone_observation']['markers']==sorted(MARKERS)
 assert b['milestone_observation']['baseline']==ref(P57/'build.json')
 assert b['milestone_observation']['restored_changes']==changes
 expected=bytearray(prior)
 for c in changes:
  at=c['file_offset'];assert expected[at:at+4]==bytes.fromhex(c['after']);expected[at:at+4]=bytes.fromhex(c['before'])
 assert bytes(expected)==raw,'Unexpected byte change outside fourteen restored words'
 start=b['probe']['file_offset'];size=(R/'out/kernel-entry-probe-55-provenance-r3/probe.bin').stat().st_size
 assert b['current_probe_code_sha256']==hashlib.sha256(raw[start:start+size]).hexdigest()
 assert b['lean_observation']['changes']==[c for c in old['lean_observation']['changes'] if not selected(c)]
 base=read(P55/'build.json');retired={c['reason'] for c in b['lean_observation']['changes'] if c['kind']=='restore-native'}
 assert b['patches']==[p for p in base['patches'] if p['reason'] not in retired]
 assert b['dense_bootstrap']['edges']==[e for e in base['dense_bootstrap']['edges'] if 'probe_dense_'+format(int(e['site'],16)&0xffffffff,'x') not in retired]
 for key in ('read_flow','root_mount_diagnostic','pthread_startup','fscompression_startup','image4_compatibility','probe'):
  assert b[key]==old[key],key
 return True
def metadata(build):
 folder=build.resolve().parent
 return {n:ref(folder/(n+'.json')) for n in ('build','milestone-proof','root-launch','launch-context','console-policy','transition-normal','transition-occupied-probe','transition-bad-topology','transition-occupied-fb')}
def bound(item):
 p=(R/item['path']).resolve();assert p.is_relative_to(R/'reports') and sha(p)==item['sha256'];return read(p)
def validate(meta,kernel_sha):
 b=bound(meta['build']);proof=bound(meta['milestone-proof']);kernel=R/b['candidate']['path']
 assert kernel.resolve().is_relative_to(R/'out') and sha(kernel)==kernel_sha==proof['candidate_sha256']==b['candidate']['sha256']
 assert b['loadable'] is False and b['runtime_qualified'] is False
 verify_bytes(b,kernel.read_bytes());assert set(proof['tests'])==TESTS
 for name,item in proof['tests'].items():
  report=bound(item);assert report['candidate_sha256']==kernel_sha
  checks=report.get('checks',report.get('cases'));assert checks and all(c['passed'] is True for c in checks),name
  assert len(checks)==proof['counts'][name]
 assert proof['counts']['bootstrap']==4 and proof['counts']['milestones']==24 and proof['counts']['negative-controls']==4
 q=read(P55/'qualification.json')
 for name in TESTS-{'bootstrap','milestones','negative-controls'}:assert proof['counts'][name]==q['check_counts'][name]
 for item in proof['sources']:assert sha(R/item['path'])==item['sha256']==sha(R/item['archive'])
 assert bound(proof['inherited_proof'])==read(P57/'lean-proof-v2.json')
 rb=bound(proof['reproduce_build']);assert sha(R/rb['candidate']['path'])==kernel_sha
 verify_bytes(rb,(R/rb['candidate']['path']).read_bytes())
 assert bound(meta['launch-context'])['components']['kernel']['sha256']==kernel_sha
 from nuwa_exec_detail_launch_context import API
 root=bound(meta['root-launch']);API.validate_report(root);assert root['candidate_sha256']==kernel_sha
 return b
