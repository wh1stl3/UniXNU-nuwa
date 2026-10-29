"""Compile RamBlock from this macOS XNU build's real private compile record.

No old analysis objects, synthetic SDK headers, address aliases or kernel link.
The produced archive still requires actual target ABI and final-link review.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import runpy
import shlex
import subprocess
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
STORAGE='609cbbdf9fa8fd5eae973d9135c7d44b47e6502e'
TAR_SHA='42bfd0c4740148e25a7d1c86a94c55b7ce6de66010102bf82368228c5e76759b'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def tools():
    spec=importlib.util.spec_from_file_location('archive_tools',ROOT/'scripts/ci/audit-driver-archives.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    return helper

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--work',type=Path,required=True)
    cli.add_argument('--base',type=Path,required=True)
    cli.add_argument('--llvm-bin',type=Path,required=True)
    args=cli.parse_args();work=args.work.resolve();base=args.base.resolve()
    if platform.system()!='Darwin' or os.environ.get('GITHUB_ACTIONS')!='true':
        raise ValueError('Requires the actual macOS Actions XNU build')
    if not work.is_relative_to(Path(os.environ['RUNNER_TEMP']).resolve()):raise ValueError('Temporary build only')
    h=tools();late=runpy.run_path(str(ROOT/'scripts/build-ramblock-late-analysis.py'))
    target=work/'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837'
    records=list(target.rglob('IOPlatformExpert.cpo.json'))
    if len(records)!=1:raise ValueError('Exactly one current compile record required')
    record,original=h.load_record(records[0],work)
    source=base/'drivers/NativeRamBlock'
    pin=json.loads((ROOT/'config/kernel-merged-profile.json').read_bytes())['modules']['drivers/NativeRamBlock']
    if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=pin:
        raise ValueError('RamBlock revision differs')
    if subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip():
        raise ValueError('RamBlock source is dirty')
    llvm=args.llvm_bin.resolve()
    for name in ('llvm-objcopy','llvm-ar','llvm-nm','llvm-dwarfdump'):
        if not (llvm/name).is_file():raise ValueError('Missing tool: '+name)
    out=work/'build/ramblock-archive';reports=work/'reports/ramblock-archive'
    out.mkdir(exist_ok=False);reports.mkdir(exist_ok=False)
    report=dict(passed=False,deployable=False,kernel_linked=False,source_revision=pin,
                compile_record_sha256=sha(records[0]),original_object=h.inspect_object(original),
                commands=[],scope='Current private compiler/SDK archive only; ABI and final kernel link pending')
    def run(cmd,cwd=None):
        index=len(report['commands']);report['commands'].append(list(map(str,cmd)))
        r=subprocess.run(cmd,cwd=cwd,capture_output=True)
        (reports/f'command-{index}.stdout').write_bytes(r.stdout)
        (reports/f'command-{index}.stderr').write_bytes(r.stderr)
        if r.returncode:raise RuntimeError(f'Command {index} failed with {r.returncode}')
    try:
        tar=out/'storage.tar.gz'
        with urllib.request.urlopen('https://codeload.github.com/apple-oss-distributions/IOStorageFamily/tar.gz/'+STORAGE,timeout=60) as response:
            tar.write_bytes(response.read())
        if sha(tar)!=TAR_SHA:raise ValueError('Storage reference download hash mismatch')
        with tarfile.open(tar) as archive:archive.extractall(out,filter='data')
        include=out/'include/IOKit';include.mkdir(parents=True)
        storage=out/('IOStorageFamily-'+STORAGE)
        (include/'storage').symlink_to(storage,target_is_directory=True)
        report['storage_reference']=dict(revision=STORAGE,tar_sha256=TAR_SHA,donor_identical=False)
        units=[('NativeRamBlock',source/'NativeRamBlock.cpp'),
               ('NativeRamBlockLateInit',ROOT/'package/NativeRamBlockLateInit.cpp'),
               ('IOBlockStorageReference',storage/'IOBlockStorageDevice.cpp')]
        commands={};dependencies=[]
        for name,unit in units:
            command=h.driver_command(record,unit,out/(name+'.o'),work)
            command+=['-I',str(out/'include'),'-MMD','-MF',str(out/(name+'.d'))]
            commands[name]=command
            run(command,record['directory'])
            h.inspect_object(out/(name+'.o'))
            text=(out/(name+'.d')).read_text().replace('\\\n',' ')
            for value in shlex.split(text.split(':',1)[1]):
                p=(Path(record['directory'])/value).resolve()
                dependencies.append(dict(path=str(p),sha256=sha(p)))
        cmd=commands['NativeRamBlock'][:]
        cmd[cmd.index('-c')]='-S';cmd[cmd.index('-o')+1]=str(out/'driver.s')
        run(cmd,record['directory'])
        (out/'explicit.s').write_bytes((out/'driver.s').read_bytes()+('\n.globl '+late['INIT']+'\n').encode())
        run([record['arguments'][0],'-target','arm64-apple-ios16.0','-c',str(out/'explicit.s'),'-o',str(out/'explicit.o')])
        objcopy=str(llvm/'llvm-objcopy')
        run([objcopy,'--strip-debug',str(out/'NativeRamBlock.o'),str(out/'baseline.o')])
        run([objcopy,'--strip-debug']+['--remove-section='+n for n in sorted(late['REMOVED'])]+[str(out/'explicit.o'),str(out/'NativeRamBlock.late.o')])
        baseline=(out/'baseline.o').read_bytes()
        removed=set(late['inspect'](baseline)[0])&late['REMOVED']
        if '__DATA,__mod_init_func' not in removed:raise ValueError('Expected actual automatic initializer')
        sections,relocs=late['verify'](baseline,(out/'NativeRamBlock.late.o').read_bytes(),removed)
        report['removed_sections']=sorted(removed)
        wrapper=out/'NativeRamBlockLateInit.o'
        if set(late['inspect'](wrapper.read_bytes())[0])&late['REMOVED']:raise ValueError('Wrapper has automatic initializer')
        archive=out/'libNativeRamBlock.late.a'
        run([str(llvm/'llvm-ar'),'rcs',str(archive),str(out/'NativeRamBlock.late.o'),str(wrapper)])
        run([str(llvm/'llvm-nm'),'-m',str(archive)])
        for name,_ in units:run([str(llvm/'llvm-dwarfdump'),'--debug-info',str(out/(name+'.o'))])
        run([record['arguments'][0],'--version']);run([objcopy,'--version'])
        report.update(passed=True,archive_sha256=sha(archive),retained_sections=sections,
                      retained_relocations=relocs,dependencies=dependencies,
                      archive=str(archive.relative_to(work)),private_definitions_preserved=True)
    finally:
        report['script_sha256']=sha(Path(__file__))
        (reports/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
        for p in [Path(__file__),ROOT/'package/NativeRamBlockLateInit.cpp']:
            (reports/p.name).write_bytes(p.read_bytes())

if __name__=='__main__':main()
