"""Build candidate-specific real-address aliases for an offline analysis archive.

Not a deployable kernel component: target headers, lifecycle and final link still
require qualification. No instructions, stubs or forced-success paths emitted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args()
    out=args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'out'):raise ValueError('Fresh out directory required')
    dispatchpath=ROOT/'reports/desktop-readiness/2026-10-29-storage-dispatch-r3/audit.json'
    dispatch=json.loads(dispatchpath.read_bytes())
    objdir=ROOT/'reports/desktop-readiness/2026-10-29-ramblock-compile-r2'
    probe=json.loads((objdir/'probe.json').read_bytes())
    if sha(objdir/'reference.o')!=probe['object_sha256']:raise ValueError('Driver object drift')
    for item in probe['headers_and_source']:
        if sha(Path(item['path']))!=item['sha256']:raise ValueError('Header/source drift: '+item['path'])
    kernel=ROOT/'out/trial-boot/xnu-entry-probe-54-strategy-r4/readback-kernel.macho'
    expected='2bceb55856bf1a6159855c1de7783261275a9949562d6adc549281df3245fad1'
    if sha(kernel)!=expected:raise ValueError('Candidate drift')
    bindings=dispatch['analysis_only_import_map']
    if len(bindings)!=11 or any('D1Ev' in n or 'D0Ev' in n for n in bindings):raise ValueError('Unsafe or changed base bindings')
    out.mkdir(parents=True)
    assembly=out/'original-bindings.S'
    assembly.write_text('// Fixed iOS16 candidate addresses; offline analysis only.\n'+''.join('.globl '+n+'\n.set '+n+', '+v+'\n' for n,v in sorted(bindings.items())))
    commands=[['/usr/bin/clang','-target','arm64-apple-ios16.0','-Werror','-c',str(assembly),'-o',str(out/'original-bindings.o')],
              ['/usr/bin/llvm-ar-14','rcs',str(out/'libNativeRamBlock.ios16-analysis.a'),str(objdir/'reference.o'),str(out/'original-bindings.o')]]
    for i,cmd in enumerate(commands):
        r=subprocess.run(cmd,capture_output=True,text=True)
        (out/('command-'+str(i)+'.log')).write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError('Analysis archive command failed')
    listing=subprocess.check_output(['/usr/bin/llvm-ar-14','t',str(out/'libNativeRamBlock.ios16-analysis.a')],text=True).splitlines()
    if listing!=['reference.o','original-bindings.o']:raise ValueError('Unexpected archive members')
    symbols=subprocess.check_output(['/usr/bin/llvm-nm-14','-g','--defined-only',str(out/'original-bindings.o')],text=True)
    resolved={}
    for line in symbols.splitlines():
        words=line.split()
        if len(words)==3 and words[1]=='A':resolved[words[2]]=int(words[0],16)
    if resolved!={k:int(v,16) for k,v in bindings.items()}:raise ValueError('Alias object mismatch')
    (out/'aliases-nm.txt').write_text(symbols)
    report=dict(scope='Offline fixed-candidate analysis archive; not enabled or linked into any boot image',
        deployable=False,hardware_executed=False,kernel_linked=False,commands=commands,members=listing,
        kernel_sha256=expected,driver_object_sha256=probe['object_sha256'],dispatch_report_sha256=sha(dispatchpath),
        archive_sha256=sha(out/'libNativeRamBlock.ios16-analysis.a'),alias_object_sha256=sha(out/'original-bindings.o'),
        bindings=bindings,weak_store_imports='Retained; final link and runtime mode require explicit review',
        blockers=['Header/SDK provenance and production compile configuration','Original and new metaclass registration order',
                  'Final kernel link and init path','Root transport and Data loader ownership','Native APFS mount and runtime evidence'],
        script_sha256=sha(Path(__file__)))
    (out/'analysis-archive.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'build-script.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(archive_sha256=report['archive_sha256'],bindings=len(bindings),deployable=False)))

if __name__=='__main__':main()
