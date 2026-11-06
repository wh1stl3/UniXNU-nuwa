"""Seal current milestone tests and explicitly inherited unchanged-code evidence."""
import argparse,copy,json
from pathlib import Path
import unmap_trace_inputs as M
def save(p,v):
 with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2);f.write('\n')
def main():
 a=argparse.ArgumentParser();a.add_argument('--build',type=Path,required=True);a.add_argument('--reproduce',type=Path,required=True);a=a.parse_args()
 build=a.build.resolve();folder=build.parent;b=M.read(build);raw=(M.R/b['candidate']['path']).read_bytes();M.verify_bytes(b,raw);ks=M.sha(M.R/b['candidate']['path'])
 rb=M.read(a.reproduce);assert M.sha(M.R/rb['candidate']['path'])==ks;M.verify_bytes(rb,(M.R/rb['candidate']['path']).read_bytes())
 checks=[dict(name='exact-fifteen-hooks-and-retired-slots-over-61',passed=True)]
 for kind in ('unlisted-byte','missing-marker','policy-drift'):
  bad=bytearray(raw);report=copy.deepcopy(b)
  if kind=='unlisted-byte':bad[-1]^=1
  elif kind=='missing-marker':
   c=next(p for p in b['patches'] if p['reason'].startswith('probe_backend_trace_'));bad[c['file_offset']:c['file_offset']+4]=bytes.fromhex(c['before'])
  else:report['root_mount_diagnostic']['conditional_boundary_only']=False
  try:M.verify_bytes(report,bytes(bad))
  except (AssertionError,ValueError):checks.append(dict(name='reject:'+kind,passed=True))
  else:raise AssertionError('Bad candidate accepted:'+kind)
 save(folder/'negative-controls.json',dict(candidate_sha256=ks,checks=checks,device_accessed=False))
 tests={};counts={}
 for name in sorted(M.TESTS):
  path=folder/(name+'.json');v=M.read(path);assert v['candidate_sha256']==ks,name
  checks=v.get('checks',v.get('cases'));assert checks and all(c['passed'] is True for c in checks),name
  tests[name]=M.ref(path);counts[name]=len(checks)
 archive=folder/'bound-sources';archive.mkdir();sources=[]
 paths=list((M.R/'scripts').glob('*.py'))+[M.R/'out/run-probe65-unmap.py',M.R/'docs/PATCH-INVENTORY.md',M.R/b['backend_trace']['source_path'],M.R/b['backend_trace']['code_path']]
 for p in sorted(paths):
  dest=archive/p.relative_to(M.R);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes());sources.append(dict(**M.ref(p),archive=dest.relative_to(M.R).as_posix()))
 save(folder/'milestone-proof.json',dict(candidate_sha256=ks,tests=tests,counts=counts,sources=sources,reproduce_build=M.ref(a.reproduce.resolve()),inherited_proof=M.ref(M.P57/'lean-proof-v2.json'),inherited_scope='PROBE57 broad hook tests are historical. PROBE65 freshly reruns the listed shared bootstrap, root, strategy, target and init bridge tests on its exact bytes. Fifteen native hooks and bounded code in retired observer code plus 176 bytes of inert data reservation over PROBE61; scoped backend trace has separate current machine-code tests; no whole-boot timing or hardware transparency claim',device_accessed=False))
 M.validate(M.metadata(build),ks);print(json.dumps(dict(qualified=True,counts=counts,candidate_sha256=ks)))
if __name__=='__main__':main()
