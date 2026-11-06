"""Seal the lean candidate after serial semantic tests and independent derivation."""
import argparse,copy,hashlib,json
from pathlib import Path
import lean_probe_inputs as L
R=L.R
NAMES=('scopes','bootstrap','transparency','vectors','pthread-startup','fscompression-startup','root-stop','root-inputs','read-boundaries','strategy-continuity','io-native-entry','vm-continuity','x18-interruption','read-vector-path','image4-launch','console-policy','transition-normal','transition-occupied-probe','transition-bad-topology','transition-occupied-fb')
def save(p,v):
 with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2);f.write('\n')
def main():
 a=argparse.ArgumentParser();a.add_argument('--build',type=Path,required=True);a.add_argument('--reproduce',type=Path,required=True);a=a.parse_args()
 build=a.build.resolve();folder=build.parent;b=L.read(build);raw=(R/b['candidate']['path']).read_bytes();ks=L.sha(R/b['candidate']['path']);assert ks==b['candidate']['sha256'];L.verify_bytes(b,raw)
 rb=L.read(a.reproduce);assert rb['candidate']['sha256']==ks and L.sha(R/rb['candidate']['path'])==ks
 assert rb['lean_observation']['changes']==b['lean_observation']['changes'] and rb['probe']['symbols']==b['probe']['symbols']
 assert sum(c['kind']=='restore-native' for c in b['lean_observation']['changes'])==235
 assert sum(c['kind']=='skip-render' for c in b['lean_observation']['changes'])==1416
 checks=[dict(name='complete-byte-difference-allowlist',passed=True)]
 for kind in ('unlisted-byte','restore-native','skip-render','changed-policy'):
  bad=bytearray(raw);report=copy.deepcopy(b)
  if kind=='unlisted-byte':bad[-1]^=1
  elif kind=='changed-policy':report['root_mount_diagnostic']['conditional_boundary_only']=False
  else:
   row=next(c for c in b['lean_observation']['changes'] if c['kind']==kind);at=row['file_offset'];bad[at:at+4]=bytes.fromhex(row['before'])
  try:L.verify_bytes(report,bytes(bad))
  except (AssertionError,ValueError):checks.append(dict(name='reject:'+kind,passed=True))
  else:raise AssertionError(kind+' accepted')
 negative=dict(candidate_sha256=ks,checks=checks,device_accessed=False)
 if (folder/'negative-controls.json').exists():assert L.read(folder/'negative-controls.json')==negative
 else:save(folder/'negative-controls.json',negative)
 tests={};counts={}
 for name in (*NAMES,'negative-controls'):
  path=folder/(name+'.json');v=L.read(path);assert v['candidate_sha256']==ks,name
  checks=v.get('checks',v.get('cases'));assert checks and all(c['passed'] is True for c in checks),name
  tests[name]=L.ref(path);counts[name]=len(checks)
 sources=[];archive=folder/'bound-sources-v2';archive.mkdir()
 paths={p for p in (R/'scripts').glob('*.py')}
 paths|={R/'out/run-probe57-lean.py',R/'docs/PATCH-INVENTORY.md',R/b['candidate']['path'].replace('kernel-entry-probe.macho','probe-annotated.S')}
 for p in sorted(paths):
  dest=archive/p.relative_to(R);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes());sources.append(dict(**L.ref(p),archive=dest.relative_to(R).as_posix()))
 save(folder/'lean-proof-v2.json',dict(candidate_sha256=ks,tests=tests,counts=counts,sources=sources,independent_reproduce_path=rb['candidate']['path'],independent_reproduce_sha256=ks,reproduce_build=L.ref(a.reproduce.resolve()),scope='Offline qualification only; byte-constrained retirement plus native/scoped/functional checks',device_accessed=False))
 L.validate(L.metadata(build),ks)
 print(json.dumps(dict(qualified=True,counts=counts,kernel_sha256=ks)))
if __name__=='__main__':main()
