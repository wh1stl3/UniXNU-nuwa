"""Non-deployable host capability probe using real headers, without ABI shims."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shlex

ROOT=Path(__file__).resolve().parents[1]

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--public-reference',action='store_true',help='Public kext reference object only; never a driver archive')
    cli.add_argument('--platform-reference',action='store_true',help='Explicit iOS platform constants for annotation only, not SDK qualification')
    cli.add_argument('--ramblock-reference',action='store_true',help='Probe the real driver; output remains non-deployable')
    args=cli.parse_args();out=args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'reports'):
        raise ValueError('Fresh report directory required')
    out.mkdir(parents=True)
    source=ROOT.parent/'Toolchain-nuwa/IOStorageFamily-609cbbdf9fa8fd5eae973d9135c7d44b47e6502e/IOStorageFamily-609cbbdf9fa8fd5eae973d9135c7d44b47e6502e'
    include=out/'include/IOKit';include.mkdir(parents=True);(include/'storage').symlink_to(source,target_is_directory=True)
    if args.platform_reference:
        if not args.public_reference:raise ValueError('Platform reference requires non-deployable public reference mode')
        (out/'include/TargetConditionals.h').write_text('''// Analysis-only platform selection; not an SDK header.
#pragma once
#if !__is_target_arch(arm64) || !__is_target_os(ios)
#error This reference requires arm64 iOS
#endif
#define TARGET_OS_MAC 1
#define TARGET_OS_IPHONE 1
#define TARGET_OS_IOS 1
#define TARGET_OS_OSX 0
#define TARGET_OS_EMBEDDED 1
#define TARGET_OS_SIMULATOR 0
#define TARGET_IPHONE_SIMULATOR 0
#define TARGET_OS_TV 0
#define TARGET_OS_WATCH 0
#define TARGET_OS_DRIVERKIT 0
#define TARGET_CPU_ARM64 1
#define TARGET_CPU_64 1
''')
    legacy=Path('/mnt/d/Code/PortingiOSLegacy/common/sources/xnu-ios16-full')
    exported=Path('/var/tmp/portingios-1000/xnu-linux-kernel-20261020T165955800820Z/obj/EXPORT_HDRS')
    recordpath=ROOT/'out/kernel-ci/39793231214/nuwa-8796-source/reports/compile-records/iokit/DEVELOPMENT/IOPlatformExpert.cpo.json'
    record=json.loads(recordpath.read_text().strip().rstrip(','))
    defs=[]
    for i,arg in enumerate(record['arguments']):
        if arg=='-D':defs+=['-D',record['arguments'][i+1]]
        elif arg.startswith('-D'):defs.append(arg)
    omitted=[]
    if args.public_reference:
        kept=[]
        for i in range(0,len(defs),2):
            value=defs[i+1]
            if 'PRIVATE' in value.split('=')[0] or value.split('=')[0]=='IOKITSTATS':omitted.append(value)
            else:kept+=defs[i:i+2]
        defs=kept
    command=['/usr/bin/clang++','-target','arm64-apple-ios16.0','-std=gnu++17','-ffreestanding','-fno-exceptions','-fno-rtti','-fno-common','-mkernel','-O2','-g']+defs
    for path in [out/'include',legacy/'iokit',legacy/'EXTERNAL_HEADERS']+[exported/x for x in ('iokit','osfmk','bsd','libkern','pexpert','security','san')]:
        command+=['-I',str(path)]
    unit=source/'IOBlockStorageDevice.cpp'
    if args.ramblock_reference:
        unit=ROOT.parent/'Toolchain-nuwa/ramblock-d4d22d9819b0162eda49f6402235dddc2279410d/RamBlock-d4d22d9819b0162eda49f6402235dddc2279410d/NativeRamBlock.cpp'
    command+=['-MMD','-MF',str(out/'reference.d'),'-c',str(unit),'-o',str(out/'reference.o')]
    run=subprocess.run(command,capture_output=True,text=True)
    (out/'compile.log').write_text(run.stdout+run.stderr)
    report=dict(command=command,exit_code=run.returncode,deployable=False,
        public_reference=args.public_reference,omitted_private_definitions=omitted,
        analysis_platform_header=args.platform_reference,
        ramblock_reference=args.ramblock_reference,
        scope='Capability probe: old generated export headers are unqualified; not a target archive build',
        compile_record_sha256=hashlib.sha256(recordpath.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        compiler_version=subprocess.check_output(['/usr/bin/clang++','--version'],text=True))
    if run.returncode==0:
        dependencies=(out/'reference.d').read_text().replace('\\\n',' ')
        paths=shlex.split(dependencies.split(':',1)[1])
        report['headers_and_source']=[dict(path=p,sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest()) for p in dict.fromkeys(paths)]
        report['object_sha256']=hashlib.sha256((out/'reference.o').read_bytes()).hexdigest()
        archive=out/('libNativeRamBlock.reference.a' if args.ramblock_reference else 'libIOStorageReference.a')
        ar=['/usr/bin/llvm-ar-14','rcs',str(archive),str(out/'reference.o')]
        result=subprocess.run(ar,capture_output=True,text=True)
        report['archive_command']=ar;report['archive_exit_code']=result.returncode
        (out/'archive.log').write_text(result.stdout+result.stderr)
        if result.returncode==0:
            report['archive_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
    (out/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'probe-script.py').write_bytes(Path(__file__).read_bytes())
    print((run.stdout+run.stderr)[-6000:]);print('compiler_exit_code',run.returncode)

if __name__=='__main__':main()
