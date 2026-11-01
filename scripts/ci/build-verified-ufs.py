"""Build authenticated NativeUfs with real iOS16 private compiler records.

Separate archive: no policy key, disk contents, boot activation or device action.
Final carrier linkage must supply the locally qualified signed policy objects.
"""
import argparse, hashlib, json, os, platform, runpy, shutil, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--llvm-bin',type=Path,required=True)
    a=p.parse_args();work=a.work.resolve();llvm=a.llvm_bin.resolve()
    if platform.system()!='Darwin' or os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('Actual macOS CI required')
    if not work.is_relative_to(Path(os.environ['RUNNER_TEMP']).resolve()):raise ValueError('Runner temporary build only')
    contract=json.loads((ROOT/'config/ufs-ios16-verified-root-ci.json').read_bytes())
    for group in ('sources','patches'):
        for name,want in contract[group].items():
            if sha(ROOT/name)!=want:raise ValueError('Input drift: '+name)
    h=runpy.run_path(str(ROOT/'scripts/ci/build-ramblock-archive.py'))['tools']()
    late=runpy.run_path(str(ROOT/'scripts/build-ramblock-late-analysis.py'))
    provider=runpy.run_path(str(ROOT/'scripts/ci/ufs-provider.py'))
    target=work/'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837'
    def record(name):
        paths=list(target.rglob(name));assert len(paths)==1,name
        return h.load_record(paths[0],work)[0]
    cpp=record('IOPlatformExpert.cpo.json');c=record('bsd_init.o.json')
    previous=work/'build/ramblock-archive';prior=json.loads((work/'reports/ramblock-archive/audit.json').read_bytes())
    source=previous/'ufs-source'
    if not prior['passed'] or sha(source/'NativeUfs.cpp')!=prior['ufs_provider']['compiled_source_sha256']:raise ValueError('Provider source binding')
    out=work/'build/verified-ufs';out.mkdir(exist_ok=False)
    reports=work/'reports/verified-ufs';reports.mkdir(exist_ok=False)
    copied=out/'source';shutil.copytree(source,copied)
    report=dict(passed=False,commands=[],device_accessed=False,deployable=False,root_policy_embedded=False,final_kernel_link=False)
    def run(args,cwd=None):
        index=len(report['commands']);report['commands'].append(list(map(str,args)))
        q=subprocess.run(list(map(str,args)),cwd=cwd,capture_output=True)
        (reports/f'{index}.stdout').write_bytes(q.stdout);(reports/f'{index}.stderr').write_bytes(q.stderr)
        if q.returncode:raise RuntimeError(q.stderr.decode(errors='replace')[-4000:])
        return q.stdout.decode(errors='replace')
    try:
        for patch in contract['patches']:
            run(['git','apply','--check',ROOT/patch],copied);run(['git','apply',ROOT/patch],copied)
        cmd=h.driver_command(cpp,copied/'NativeUfs.cpp',out/'NativeUfs.o',work)
        cmd+=['-I',str(previous/'include'),'-I',str(ROOT/'package/verified-root'),'-include',str(ROOT/'include/nuwa/UfsCompilePrelude.h'),'-DNATIVE_VERIFIED_BLOCK=1','-Wno-error=missing-noreturn']
        run(cmd,cpp['directory']);h.inspect_object(out/'NativeUfs.o')
        sizes={name:provider['class_size'](run([llvm/'llvm-dwarfdump','--debug-info','--name='+name,out/'NativeUfs.o']),name) for name in ('NativeUfs','NativeUfsBlock')}
        if not (0x88<=sizes['NativeUfs']<0x10000 and 0x90<=sizes['NativeUfsBlock']<0x10000):raise ValueError('Class layout')
        slots=runpy.run_path(str(ROOT/'scripts/ci/build-ramblock-kernel.py'))['vtable'](out/'NativeUfs.o','NativeUfsBlock')
        expected=json.loads((ROOT/'config/ramblock-ios16-link-contract.json').read_bytes())['reference_vtable']
        if len(slots)!=len(expected):raise ValueError('Block vtable extent')
        for actual,want in zip(slots,expected):
            if not actual.startswith(('__ZN14NativeUfsBlock','__ZNK14NativeUfsBlock')) and actual!=want:raise ValueError('Inherited slot drift')
        assembly=cmd[:];assembly[assembly.index('-c')]='-S';assembly[assembly.index('-o')+1]=str(out/'ufs.s');run(assembly,cpp['directory'])
        init='__GLOBAL__sub_I_NativeUfs.cpp';(out/'ufs-explicit.s').write_bytes((out/'ufs.s').read_bytes()+('\n.globl '+init+'\n').encode())
        run([cpp['arguments'][0],'-target','arm64-apple-ios16.0','-c',out/'ufs-explicit.s','-o',out/'ufs-explicit.o'])
        run([llvm/'llvm-objcopy','--strip-debug',out/'NativeUfs.o',out/'baseline.o'])
        run([llvm/'llvm-objcopy','--strip-debug']+['--remove-section='+s for s in sorted(late['REMOVED'])]+[out/'ufs-explicit.o',out/'NativeUfs.late.o'])
        original=(out/'baseline.o').read_bytes();removed=set(late['inspect'](original)[0])&late['REMOVED']
        transformed,cold=late['restore_cold_flags'](original,(out/'NativeUfs.late.o').read_bytes(),removed,init=init);(out/'NativeUfs.late.o').write_bytes(transformed)
        sections,relocs=late['verify'](original,transformed,removed,init=init)
        wrapper=h.driver_command(cpp,ROOT/'package/NativeUfsLateInit.cpp',out/'NativeUfsLateInit.o',work)
        wrapper+=['-DNUWA_UFS_CLASS_SIZE='+str(sizes['NativeUfs']),'-DNUWA_UFS_BLOCK_CLASS_SIZE='+str(sizes['NativeUfsBlock'])];run(wrapper,cpp['directory'])
        for name in ('verified_root','xnu_crypto'):
            command=h.driver_command(c,ROOT/'package/verified-root'/(name+'.c'),out/(name+'.o'),work)
            command+=['-I',str(ROOT/'package/verified-root')];run(command,c['directory']);h.inspect_object(out/(name+'.o'))
        objects=[out/n for n in ('NativeUfs.late.o','NativeUfsLateInit.o','verified_root.o','xnu_crypto.o')]
        for obj in objects:
            if set(late['inspect'](obj.read_bytes())[0])&late['REMOVED']:raise ValueError('Unexpected automatic initializer')
        run([llvm/'llvm-ar','rcs',out/'libNativeUfs.verified.a']+objects)
        report.update(passed=True,class_sizes=sizes,inherited_vtable_verified=True,verified_root_enabled=True,source_sha256=sha(copied/'NativeUfs.cpp'),retained_sections=sections,retained_relocations=relocs,restored_cold_symbols=cold,objects={p.name:sha(p) for p in objects},archive_sha256=sha(out/'libNativeUfs.verified.a'),contract_sha256=sha(ROOT/'config/ufs-ios16-verified-root-ci.json'))
    finally:
        (reports/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
