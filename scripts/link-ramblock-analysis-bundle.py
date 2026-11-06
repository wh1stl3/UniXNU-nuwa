"""Run a real Mach-O link against the fixed kernel as bundle-loader evidence.

This is a non-loadable analysis bundle, NOT a final static kernel link. Exact
weak UFS imports remain allowed; all other unresolved symbols are errors.
Run with WSL Python after prepare-ramblock-start-path.py.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    out=p.parse_args().output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'out'):raise ValueError('Fresh out directory')
    auditpath=ROOT/'reports/desktop-readiness/2026-10-29-ramblock-start-r2/audit.json'
    audit=json.loads(auditpath.read_bytes())
    kernel=ROOT/'out/trial-boot/xnu-entry-probe-54-strategy-r4/readback-kernel.macho'
    archive=ROOT/'out/ramblock-ios16-late-20261029-r6/libNativeRamBlock.late-analysis.a'
    aliasdir=ROOT/'out/ramblock-ios16-analysis-20261029-r1'
    alias=aliasdir/'original-bindings.o'
    aliasreport=json.loads((aliasdir/'analysis-archive.json').read_bytes())
    if audit['missing_strong'] or sha(kernel)!=audit['kernel_sha256'] or sha(archive)!=audit['archive_sha256'] or sha(alias)!=aliasreport['alias_object_sha256']:
        raise ValueError('Input/closure drift')
    weak=[r['name'] for r in audit['import_resolution'] if r['source']=='unresolved' and r['weak']]
    if len(weak)!=6 or not all(n.startswith('_native_ufs_store_') for n in weak):raise ValueError('Weak interface drift')
    out.mkdir(parents=True)
    command=['/usr/bin/ld64.lld-14','-arch','arm64','-platform_version','ios','16.0','16.0',
             '-bundle','-bundle_loader',str(kernel),'-undefined','error','-no_adhoc_codesign',
             '-force_load',str(archive),str(alias),'-o',str(out/'RamBlock.analysis.bundle')]
    for name in weak:command+=['-U',name]
    run=subprocess.run(command,capture_output=True)
    (out/'link.stdout').write_bytes(run.stdout);(out/'link.stderr').write_bytes(run.stderr)
    report=dict(command=command,exit_code=run.returncode,deployable=False,final_kernel_link=False,
                hardware_executed=False,allowed_weak_imports=weak,audit_sha256=sha(auditpath),
                kernel_sha256=sha(kernel),archive_sha256=sha(archive),script_sha256=sha(Path(__file__)))
    if run.returncode==0:
        report['bundle_sha256']=sha(out/'RamBlock.analysis.bundle')
        for name,cmd in [('symbols',['/usr/bin/llvm-nm-14','-m']),('headers',['/usr/bin/llvm-objdump-14','--macho','--private-headers']),('bindings',['/usr/bin/llvm-objdump-14','--macho','--bind','--weak-bind','--lazy-bind'])]:
            r=subprocess.run(cmd+[str(out/'RamBlock.analysis.bundle')],capture_output=True,check=True)
            (out/(name+'.txt')).write_bytes(r.stdout)
    (out/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'link-script.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(report,indent=2))
    if run.returncode:raise SystemExit(run.returncode)

if __name__=='__main__':main()
