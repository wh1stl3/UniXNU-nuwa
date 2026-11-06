"""Conservative source CFG effect audit of generated legacy observer bodies."""
import argparse,re,json,hashlib,sys,importlib.util,collections
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import flush_trace_inputs as t
sp=importlib.util.spec_from_file_location('inventory',t.R/'scripts/audit-patch-inventory.py');A=importlib.util.module_from_spec(sp);sp.loader.exec_module(A)
DIAG={'probe_flags','probe_result_state','probe_read_state','probe_read_body_state','probe_decmp_state','probe_fetch_state','probe_deep_state','probe_read_trace_state','probe_exec_state','probe_hex_result_cache','probe_cluster_tile_seen'}
def audit(body,label):
 lines=[x.split('//')[0].strip() for x in body.splitlines()];lines=[x for x in lines if x]
 if not lines or lines[0]!=label+':' or lines.count('PROBE_SAVE')!=1 or lines.count('PROBE_RESTORE')!=1:return False,'not bounded save/restore body'
 if lines[-1]!='PROBE_RESTORE':return False,'nonterminal restore'
 # PROBE_SAVE preserves x9-x28/NZCV; reject unpreserved argument mutations.
 for line in lines:
  if re.match(r'(?:mov|movz|movk|add|adds|sub|subs|ldr|ldp|ldnp|adr|LOADABS|mrs|and|ands|orr|eor|lsl|lsr|ubfx|csel|cset|madd|mul|bic|sxtw|uxtw)\s+[xw][0-8]\b',line):return False,'unsaved argument write'
  if re.match(r'(?:mov|movz|movk|add|adds|sub|subs|ldr|ldp|ldnp|adr|LOADABS|mrs|and|ands|orr|eor|lsl|lsr|ubfx|csel|cset|madd|mul|bic|sxtw|uxtw)\s+[xw](?:29|30)\b',line):
   if line not in ('mov x29, x17','ldp x29, x30, [sp], #16'):return False,'unsaved frame write'
   if lines[2]!='stp x29, x30, [sp, #-16]!' or sum(x.startswith('stp x29, x30,') for x in lines)!=1 or sum(x.startswith('ldp x29, x30,') for x in lines)!=1 or lines[-2]!='ldp x29, x30, [sp], #16':return False,'frame save/restore mismatch'
 labels={x[:-1]:i for i,x in enumerate(lines) if x.endswith(':')}
 initial={f'x{i}':frozenset({'unknown'}) for i in range(31)};initial['sp']=frozenset({'stack'})
 states={0:initial};todo=[0];stores=0
 while todo:
  pc=todo.pop();env=dict(states[pc]);line=lines[pc];nexts=[pc+1];op=line.split()[0];regs=re.findall(r'\b(?:x[0-9]+|w[0-9]+|sp)\b',line);regs=[('x'+v[1:] if v.startswith('w') else v) for v in regs]
  if line.endswith(':') or op in ('PROBE_SAVE','PROBE_RESTORE','cmp','cmn','tst','nop'):pass
  elif op in ('DENSE_ONCE','HEXROW_VAL','BAND_ONCE','DISPLAY_CHECK'):
   if op=='DISPLAY_CHECK':return False,'display control macro requires review'
   for i in range(9,29):env[f'x{i}']=frozenset({'unknown'})
  elif op=='adr':
   name=line.split(',')[-1].strip();env[regs[0]]=frozenset({'diag' if name in DIAG or name.startswith('probe_resource_') else 'unknown'})
  elif op in ('str','strb','strh','stur','stp'):
   base=re.search(r'\[(x[0-9]+|sp)',line)
   if not base or not env.get(base[1],frozenset({'unknown'}))<=frozenset({'diag','stack'}):return False,'unproven store: '+line
   # Register-indexed offsets may point outside diagnostic storage.
   if re.search(r'\[[^]]*,\s*[xw]',line):return False,'indexed store'
   stores+=1
  elif op.startswith('ld'):
   count=2 if op in ('ldp','ldnp') else 1
   for reg in regs[:count]:env[reg]=frozenset({'unknown'})
  elif op=='mov' and len(regs)==2:env[regs[0]]=env.get(regs[1],frozenset({'unknown'}))
  elif op in ('add','sub') and len(regs)==2 and '#' in line:env[regs[0]]=env.get(regs[1],frozenset({'unknown'}))
  elif op in ('b','cbz','cbnz','tbz','tbnz') or op.startswith('b.'):
   target=line.split()[-1] if op=='b' or op.startswith('b.') else line.split(',')[-1].strip()
   if target not in labels:return False,'external branch: '+line
   if labels[target]<=pc:return False,'backward branch requires review'
   nexts=([labels[target]] if op=='b' else [pc+1,labels[target]])
  elif op in ('bl','blr','br','ret','msr','svc','hvc','smc','wfe','wfi'):return False,'call/control/system effect: '+line
  elif op in ('LOADABS','mrs','mov','movz','movk','add','adds','sub','subs','and','ands','orr','eor','lsl','lsr','ubfx','csel','cset','madd','mul','bic','sxtw','uxtw'):
   if regs:env[regs[0]]=frozenset({'unknown'})
  else:return False,'unsupported instruction: '+line
  for n in nexts:
   if n>=len(lines):continue
   if n not in states:states[n]=dict(env);todo.append(n)
   else:
    merged={k:states[n][k]|env[k] for k in env}
    if merged!=states[n]:states[n]=merged;todo.append(n)
 return True,'local forward-only CFG; writes restricted to diagnostic state/stack; saves/restores native registers; no native call'
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();bp=t.R/'reports/kernel-entry-probe/2026-10-30-probe61-init-bridge-r2/build.json';src=t.R/'out/kernel-entry-probe-61-init-bridge-r2/probe.S';b=json.loads(bp.read_bytes());assembly=src.read_text();rows=[]
 for x in b['patches']:
  if not x['reason'].startswith('probe_dense_'):continue
  body=A.dense_body(assembly,x['reason']);ok,why=audit(body,x['reason']);rows.append(dict(patch=x,source_effects_only_diagnostic=ok,reason=why,body_sha256=hashlib.sha256(body.encode()).hexdigest()))
 report=dict(parent_build_sha256=hashlib.sha256(bp.read_bytes()).hexdigest(),assembly_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),rows=rows,scope='Conservative source effect CFG; actual machine bytes/replay and consumer checks still required before applying removals. No name-based automatic deletion.')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(collections.Counter(x['source_effects_only_diagnostic'] for x in rows));print(collections.Counter(x['reason'] for x in rows if not x['source_effects_only_diagnostic']).most_common(12))
if __name__=='__main__':main()
