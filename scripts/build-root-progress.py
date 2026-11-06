"""Restore nine existing stage marks, never old HEX, in a fresh PROBE59 artifact."""
import argparse,copy,json,hashlib
from pathlib import Path
import root_progress_inputs as M
def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 w=a.work.resolve();out=a.output.resolve();assert not w.exists() and not out.exists()
 old,raw=M.inherited();base=M.read(M.P55/'build.json');b=copy.deepcopy(old);result=bytearray(raw)
 changes=[c for c in old['lean_observation']['changes'] if M.selected(c)]
 for c in changes:result[c['file_offset']:c['file_offset']+4]=bytes.fromhex(c['before'])
 w.mkdir(parents=True);out.parent.mkdir(parents=True,exist_ok=True);target=w/'kernel-entry-probe.macho';target.write_bytes(result)
 b['probe_revision']=59;b['candidate']=dict(path=target.relative_to(M.R).as_posix(),sha256=M.sha(target),bytes=len(result))
 b['lean_observation']['changes']=[c for c in old['lean_observation']['changes'] if not M.selected(c)]
 retired={c['reason'] for c in b['lean_observation']['changes'] if c['kind']=='restore-native'}
 b['patches']=[p for p in base['patches'] if p['reason'] not in retired]
 b['dense_bootstrap']['edges']=[e for e in base['dense_bootstrap']['edges'] if 'probe_dense_'+format(int(e['site'],16)&0xffffffff,'x') not in retired]
 b['milestone_observation']=dict(markers=sorted(M.MARKERS),restored_changes=changes,baseline=M.ref(M.P57/'build.json'),source=M.ref(Path(__file__)),scope='Nine coarse milestones restored; no old HEX/calibration; native policy unchanged')
 b['scope']='PROBE59 derived from archived PROBE57, fourteen word changes; unqualified until separate proof'
 # The archival assembly is a layout reference, NOT the effective renderer selection.
 source=M.R/base['candidate']['path'].replace('kernel-entry-probe.macho','probe.S');(w/'probe.S').write_bytes(source.read_bytes())
 start=b['probe']['file_offset'];size=b['probe'].get('bytes',397312)
 b['current_probe_code_sha256']=hashlib.sha256(result[start:start+size]).hexdigest()
 M.verify_bytes(b,bytes(result))
 with out.open('x',encoding='utf-8') as f:json.dump(b,f,indent=2);f.write('\n')
 print(json.dumps(dict(candidate=b['candidate'],restored_words=len(changes),offline_qualified=False)))
if __name__=='__main__':main()
