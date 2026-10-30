"""Serial host qualification of pinned real UFS production headers, no device I/O."""
import argparse, hashlib, json, shutil, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PIN='af785c1777161a62931425c2faaa536ce0bebd5b'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    src=args.source.resolve();out=args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'out'):raise ValueError('Fresh output required')
    if subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()!=PIN:raise ValueError('Source pin')
    if subprocess.check_output(['git','-C',str(src),'status','--porcelain'],text=True).strip():raise ValueError('Dirty source')
    before={p.relative_to(src).as_posix():sha(p) for p in src.rglob('*') if p.is_file() and '.git' not in p.parts}
    out.mkdir(parents=True);local=out/'source';shutil.copytree(src,local,ignore=shutil.ignore_patterns('.git'))
    bridge=local/'tests/RootCommandsBridge.cpp';text=bridge.read_text();old='static void IOLockLock(void *) {}';assert text.count(old)==1
    bridge.write_text(text.replace(old,'static void IOLockLock(void *) { callback(6,0,0,nullptr); }'))
    fixture=local/'tests/RootWindowRead.cpp';text=fixture.read_text();assert text.count('{0ULL,UINT64_MAX}')==1
    fixture.write_text(text.replace('{0ULL,UINT64_MAX}','{uint64_t(0),UINT64_MAX}'))
    commands=[]
    def run(cmd,name,expected=0):
        p=subprocess.run(list(map(str,cmd)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
        (out/(name+'.log')).write_bytes(p.stdout);commands.append(dict(command=list(map(str,cmd)),exit=p.returncode,expected=expected,log=name+'.log'))
        if p.returncode!=expected:raise RuntimeError(name+': '+p.stdout.decode(errors='replace')[-2000:])
    flags=['/usr/bin/clang++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-function','-fsanitize=address,undefined','-fno-pie','-no-pie','-g','-pthread']
    test=ROOT/'tests/ufs_store_cycle.cpp'
    run(flags+['-I',local/'tests',test,'-o',out/'old-cycle'],'old-build')
    run([out/'old-cycle','negative-control'],'old-negative',42)
    patch=ROOT/'patches/driver-candidates/native-ufs-dma-write-ownership.patch'
    run(['git','apply','--unsafe-paths','--directory='+str(local),patch],'apply')
    run(flags+['-I',local/'tests',test,'-o',out/'cycle'],'cycle-build');run([out/'cycle'],'cycle')
    for name in ('RootCommands','RootLayout','RootWindowRead','RootPublication','TransferPoll','SmmuTakeover'):
        extra=['-lcrypto','-Wno-deprecated-declarations'] if name=='RootLayout' else []
        run(flags+[local/'tests'/(name+'.cpp'),'-o',out/name]+extra,name+'-build');run([out/name],name)
    assert before=={p.relative_to(src).as_posix():sha(p) for p in src.rglob('*') if p.is_file() and '.git' not in p.parts}
    report=dict(passed=True,source_revision=PIN,source_sha256=before,patch_sha256=sha(patch),fixture_sha256=sha(test),commands=commands,
      compiler=subprocess.check_output(['/usr/bin/clang++','--version'],text=True).splitlines()[0],
      bridge_change='Test-only lock callback models a previous request poisoning DMA while writer waits',
      host_fixture_change='Explicit uint64_t zero in initializer list for Linux LP64; production unchanged',
      scope='ASan/UBSan execution of real command/layout/window/publication code with simulated HC/DMA/media; no hardware or mount proof',device_accessed=False)
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,old_reproduced=True,suites=7)))
if __name__=='__main__':main()
