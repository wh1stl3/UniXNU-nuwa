"""Serial checks for the integrated offline SystemOS candidate. No device access."""
import argparse,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--start-index',type=int,default=0);a=p.parse_args();w=a.work.resolve();root=Path(__file__).resolve().parents[1]
commands=[]
for name in ('test-systemos-mount-model.py','test-systemos-trust-dispatch.py','test-kmain4-r1-mainline.py','test-kmain16-stages.py','test-kmain4-pmgr.py','test-kmain16-scoped.py','test-kmain16-vnop-model.py','test-kmain16-apfs-model.py'):
 commands.append([name,'--work',str(w)])
commands += [
 ['qualify-systemos-payload-loader.py','--work',str(w),'--output',str(w/'payload-loader-tests.json')],
 ['qualify-systemos-mount-plan.py','--work',str(w),'--payload',str(root/'out/systemos-host-r4/mount-args.bin'),'--output',str(w/'systemos-arguments-tests.json')],
 ['qualify-systemos-handoff-boundaries.py','--work',str(w),'--output',str(w/'systemos-handoff-tests.json')]]
for case in ('normal','occupied-probe','bad-topology','occupied-fb'):commands.append(['qualify-ufs-iokit-bootstrap.py','--work',str(w),'--case',case])
for index,command in enumerate(commands):
 if index<a.start_index:continue
 print('RUN',index,command[0],command[-1] if '--case' in command else '',flush=True)
 q=subprocess.run([sys.executable,str(root/'scripts'/command[0]),*command[1:]],capture_output=True)
 attempt=0
 while (w/f'qualification-{index:02d}-{attempt}.stdout').exists():attempt+=1
 (w/f'qualification-{index:02d}-{attempt}.stdout').write_bytes(q.stdout);(w/f'qualification-{index:02d}-{attempt}.stderr').write_bytes(q.stderr)
 if q.returncode:
  print(q.stdout.decode(errors='replace')[-3000:]);print(q.stderr.decode(errors='replace')[-4000:]);raise SystemExit(q.returncode)
 print(q.stdout.decode(errors='replace')[-350:],flush=True)
print('PASS requested serial candidate checks; final package qualification requires the complete report set')
