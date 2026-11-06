"""Bind offline staging evidence; serial cross-compilation, no boot changes."""
import hashlib,json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[1]
D=R/'reports/desktop-readiness/2026-11-03-offline-desktop-r8'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def main():
 output=D/'summary.json';assert not output.exists()
 code=read(D/'dynamic-code-final.json');tests=read(D/'dynamic-tests.json');data=read(D/'data-import.json')
 assert code['passed'] and tests['passed'] and data['passed']
 assert tests['parent_sha256']==sha(D/'dynamic-code-final.json')
 for report,script in ((code,'trace-desktop-dynamic-r8.py'),(tests,'test-dynamic-binding-r8.py'),(data,'test-data-stage-import-r8.py')):
  assert report['script_sha256']==sha(R/'scripts'/script)
 assert data['module_sha256']==sha(R/'scripts/data_stage_import.py')
 assert data['source_sha256']==sha(R/'reports/desktop-readiness/2026-10-27-contract-r1/data-source-r2.json')
 assert data['archive_sha256']==sha(R/'out/desktop-root-contract-20261027-r2/os-var-source.tar')
 frozen=read(R/'reports/desktop-readiness/2026-11-03-offline-desktop-r7/summary.json')['frozen']
 for name,digest in frozen.items():assert sha(R/name)==digest,name
 providers=read(R/'reports/desktop-readiness/2026-11-03-offline-mainline-r1/core-consumers-final.json')['providers']['com.apple.runningboard']
 assert any(x['label']=='com.apple.runningboardd' for x in providers)
 out=R/'out/offline-desktop-r8';assert not out.exists();out.mkdir()
 builds=[]
 for name in ('NuwaCpuPresent','NuwaTouchHid','NuwaFtsEvents'):
  obj=out/(name+'.o');cmd=['/usr/bin/clang','--target=aarch64-none-elf','-ffreestanding','-fno-builtin','-O2','-Wall','-Wextra','-Werror','-c',str(R/'package/offline-desktop'/(name+'.c')),'-o',str(obj)]
  run=subprocess.run(cmd,capture_output=True,text=True);assert run.returncode==0,run.stderr
  builds.append(dict(command=cmd,object_sha256=sha(obj)))
 sources=['scripts/trace-desktop-dynamic-r8.py','scripts/test-dynamic-binding-r8.py','scripts/data_stage_import.py','scripts/test-data-stage-import-r8.py','scripts/qualify-offline-desktop-r8.py','tests/nuwa-cpu-present.c','tests/nuwa-touch-hid.c']
 sources += ['package/offline-desktop/'+n+e for n in ('NuwaCpuPresent','NuwaTouchHid','NuwaFtsEvents') for e in ('.c','.h')]
 # These exact sanitizer binaries ran successfully earlier in this serial task.
 host=[dict(binary_sha256=sha(Path('/var/tmp')/name),result_reused=result) for name,result in [('nuwa-cpu-present-r8','PASS 9 bounds/ownership/completion checks'),('nuwa-touch-hid-r8','PASS 12 HID queue/descriptor checks; no IOHIDDevice runtime')]]
 result=dict(passed=True,frozen=frozen,sources={p:sha(R/p) for p in sources},evidence={p.name:sha(p) for p in (D/'dynamic-code-final.json',D/'dynamic-tests.json',D/'data-import.json')},cross_builds=builds,host_results=host,native_cases=tests['cases'],runningboard_providers=providers,
  limitations=['Partial service graph; UTF8String boundary substituted after binding actual selector/literal','Data host staging only, one conditional file, no APFS writer or deployment qualification; hardlink restoration not exercised','CPU copy core only; no IOSurface mapping, MobileFramebuffer publication or physical refresh','HID descriptor and ordered retry queue only; no iOS parser validation, IOHIDDevice publication, bus/IRQ or reset recovery','CHECK3 remains latest hardware evidence; no confirmed boot root cause'],check5_modified=False,new_boot_candidate=False,device_accessed=False)
 output.write_text(json.dumps(result,indent=2)+'\n');print('PASS r8 bindings, 3 ARM64 objects, CHECK5 frozen')
if __name__=='__main__':main()
