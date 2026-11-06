"""Verify retired sites are native instructions, not hidden diagnostic branches."""
import argparse,json,sys
from pathlib import Path
import resource_cluster_sites as P
import read_dispatch_audit as A
R=Path(__file__).resolve().parents[1]
def verify(raw,b,original,om):
 m=A.B.macho(raw);patches={int(p['va'],16) for p in b['patches'] if p.get('va')}
 edges={int(p['site'],16) for p in b['dense_bootstrap']['edges']}
 for p in P.removed_points():
  site=p['site'];at=A.B.backed(m,site);old=A.B.backed(om,site)
  assert raw[at:at+4]==original[old:old+4],hex(site)
  assert site not in patches and site not in edges
  assert 'probe_dense_'+format(site&0xffffffff,'x') not in b['probe']['symbols']
 active={p['offset'] for p in P.points()}
 assert set(P.TILE_OFFSETS)|set(P.G.OFFSETS)<=active
 for p in P.points():
  assert p['site'] in patches and p['site'] in edges
  assert 'probe_dense_'+format(p['site']&0xffffffff,'x') in b['probe']['symbols']
 assert {p['offset'] for p in P.points() if p['group']=='strategy'}=={0x46e538,0x46e54c,0x46e550,0x46e570,0x46e574,0x46e590}
 for s in P.SPECS:
  assert s['entry'] in active and s['ret'] in active
  if s['parent'] in {x['name'] for x in P.SPECS}:
   parent=next(x for x in P.SPECS if x['name']==s['parent'])
   call=parent['calls'][s['parent_bit']]
   assert call in active and call+4 in active
def main():
 c=argparse.ArgumentParser();c.add_argument('--build',type=Path,required=True);c.add_argument('--output',type=Path,required=True);a=c.parse_args()
 assert not a.output.exists();b=json.loads(a.build.read_bytes());raw=(R/b['candidate']['path']).read_bytes()
 original=A.B.INPUT.read_bytes();om=A.B.macho(original)
 assert A.B.sha(raw)==b['candidate']['sha256'] and A.B.sha(original)==A.B.EXPECTED
 verify(raw,b,original,om)
 bad=bytearray(raw);at=A.B.backed(A.B.macho(raw),P.removed_points()[0]['site']);bad[at:at+4]=bytes.fromhex('00000014')
 try:verify(bytes(bad),b,original,om)
 except AssertionError:pass
 else:raise AssertionError('Reintroduced branch accepted')
 out=dict(candidate_sha256=A.B.sha(raw),source_sha256=A.B.sha(Path(__file__).read_bytes()),removed=P.removed_points(),retained=P.points(),checks=[dict(name='native-bytes-and-no-stubs',passed=True),dict(name='ancestry-and-IO-closure',passed=True),dict(name='reintroduced-branch-negative',passed=True)],device_accessed=False)
 a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(removed=len(P.removed_points()),retained=len(P.points()),passed=True)))
if __name__=='__main__':main()
