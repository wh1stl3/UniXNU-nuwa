"""Derive a layout-preserving observer retirement from the sealed PROBE55.

No device access. An unqualified analysis artifact until independent tests pass.
"""
import argparse, hashlib, importlib.util, json, re, subprocess
from pathlib import Path

R=Path(__file__).resolve().parents[1]
BASE=R/'reports/kernel-entry-probe/2026-10-29-probe55-provenance-r3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def save(p,v):
 with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2);f.write('\n')
def linux(p):return '/mnt/d/'+p.resolve().as_posix().split(':/',1)[1]

def main():
 a=argparse.ArgumentParser();a.add_argument('--work',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a=a.parse_args()
 w=a.work.resolve();out=a.output.resolve();assert not w.exists() and not out.exists()
 q=read(BASE/'qualification.json');b=read(BASE/'build.json')
 for row in q['evidence']+[q['sources']]:assert sha(R/row['path'])==row['sha256'],row['path']
 for row in read(R/q['sources']['path'])['sources']:assert sha(R/row['archive'])==row['sha256'],row['archive']
 old=R/b['candidate']['path'];assert sha(old)==b['candidate']['sha256']
 w.mkdir(parents=True);out.parent.mkdir(parents=True,exist_ok=True)
 source=(old.parent/'probe.S').read_text(encoding='utf-8')
 # Only macro invocations, never instruction-pattern guesses. Each expanded
 # range is bounded by linked symbols; annotations must reproduce all bytes.
 render={'BAND','BAND_ONCE','BAND_ONCE20','BAND_SNAPSHOT','HEXROW_VAL','DENSE_ONCE','DISPLAY_INIT','DISPLAY_CHECK'}
 protected={'probe_exception','probe_fault','probe_panic','probe_panic_options','probe_panic_trap','probe_console_policy','probe_dense_769d230','probe_native_vector_reject'}
 protected|={'probe_dense_'+format(p['site']&0xffffffff,'x') for p in b['read_flow']['resource_cluster']['points']}
 macro=None;function=None;marks=[];lines=[]
 for line in source.splitlines():
  t=line.strip()
  if t.startswith('.macro '):macro=t.split()[1]
  if t=='.endm':macro=None
  if not macro and re.fullmatch(r'[A-Za-z_]\w*:',t):function=t[:-1]
  op=t.split()[0] if t else ''
  # Native-vector handoff keeps every functional instruction; only its HEX
  # invocations are retired. Renderer definitions are otherwise left alone.
  selected=op in render and ((macro is None and function not in protected) or (macro=='RESTORE_NATIVE_VECTORS' and op=='HEXROW_VAL'))
  # Console success decoration can go; unsupported-policy error stays visible.
  selected|=macro is None and function=='probe_console_policy' and op=='BAND_ONCE'
  if selected:
   n=len(marks);suffix=r'_\@' if macro else '';start=f'lean_range_{n}_start'+suffix;end=f'lean_range_{n}_end'+suffix
   lines+=['.global '+start,start+':',line,'.global '+end,end+':']
   marks.append(dict(id=n,macro=macro,function=function,invocation=t))
  else:lines.append(line)
 annotated='\n'.join(lines)+'\n';(w/'probe-annotated.S').write_text(annotated,encoding='utf-8',newline='\n')
 rsp=(old.parent/'linker.rsp').read_text().replace(linux(old.parent/'probe.o'),linux(w/'probe.o')).replace(linux(old.parent/'probe.elf'),linux(w/'probe.elf'))
 (w/'linker.rsp').write_text(rsp,encoding='utf-8',newline='\n')
 commands=[]
 for argv in (['clang','--target=aarch64-none-elf','-c',linux(w/'probe-annotated.S'),'-o',linux(w/'probe.o')],['ld.lld','@'+linux(w/'linker.rsp')],['llvm-objcopy','-O','binary','--only-section=.text',linux(w/'probe.elf'),linux(w/'probe-annotated.bin')]):
  p=subprocess.run(['wsl','-d','Ubuntu-22.04','--',*argv],capture_output=True,text=True);commands.append(dict(argv=argv,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr));p.check_returncode()
 save(w/'commands.json',commands)
 assert (w/'probe-annotated.bin').read_bytes()==(old.parent/'probe.bin').read_bytes(),'Annotations changed executable code'
 nm=subprocess.check_output(['wsl','-d','Ubuntu-22.04','--','llvm-nm','--defined-only',linux(w/'probe.elf')],text=True)
 sy={name:int(addr,16) for addr,kind,name in re.findall(r'^([0-9a-fA-F]+)\s+(\S)\s+(\S+)$',nm,re.M)}
 spec=importlib.util.spec_from_file_location('lean_builder',R/'scripts/build-kernel-entry-probe.py');B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)
 raw=old.read_bytes();m=B.macho(raw);result=bytearray(raw);changes=[]
 for name,start in sy.items():
  match=re.fullmatch(r'lean_range_(\d+)_start(_\d+)?',name)
  if not match:continue
  end=sy[name.replace('_start','_end')];assert end>start and (end-start)%4==0
  at=B.backed(m,start);before=raw[at:at+4];after=B.branch(start,end)
  result[at:at+4]=after;changes.append(dict(kind='skip-render',va=hex(start),end=hex(end),file_offset=at,before=before.hex(),after=after.hex(),**marks[int(match[1])]))
 inventory=read(BASE/'patch-inventory.json')
 keep_panic={'probe_panic','probe_panic_options','probe_panic_trap'}
 obsolete={r['patch']['reason'] for r in inventory['entries'] if r['layer']=='kernel' and r['category']=='observation' and (r['rationale']=='exact generated save/DENSE_ONCE/restore stencil' or r['rationale']=='reviewed entry-probe.S snapshot/render and native replay')}-keep_panic
 obsolete.add('probe_console_init')
 for patch in b['patches']:
  if patch['reason'] not in obsolete:continue
  assert patch['reason'] not in protected
  at=patch['file_offset'];before=bytes.fromhex(patch['after']);after=bytes.fromhex(patch['before']);assert raw[at:at+len(before)]==before and len(before)==len(after)==4
  result[at:at+4]=after;changes.append(dict(kind='restore-native',va=patch['va'],file_offset=at,before=before.hex(),after=after.hex(),reason=patch['reason']))
 assert len({c['file_offset'] for c in changes})==len(changes)
 target=w/'kernel-entry-probe.macho';target.write_bytes(result)
 derived=json.loads(json.dumps(b));derived.update(candidate=dict(path=target.relative_to(R).as_posix(),sha256=sha(target),bytes=len(result)),probe_revision=57,lean_observation=dict(schema=1,baseline_build=(BASE/'build.json').relative_to(R).as_posix(),baseline_sha256=b['candidate']['sha256'],changes=changes,source_sha256=sha(Path(__file__)),annotated_source_sha256=sha(w/'probe-annotated.S'),annotations_byte_identical=True,qualified=False))
 derived['patches']=[p for p in b['patches'] if p['reason'] not in obsolete]
 derived['dense_bootstrap']['edges']=[e for e in b['dense_bootstrap']['edges'] if 'probe_dense_'+format(int(e['site'],16)&0xffffffff,'x') not in obsolete]
 derived['scope']='Unqualified PROBE57 layout-preserving observer retirement; inherited states remain for scope dependencies; not a device result'
 save(out,derived)
 print(json.dumps(dict(candidate=derived['candidate'],restored_native_hooks=sum(c['kind']=='restore-native' for c in changes),render_ranges=sum(c['kind']=='skip-render' for c in changes),qualified=False)))
if __name__=='__main__':main()
