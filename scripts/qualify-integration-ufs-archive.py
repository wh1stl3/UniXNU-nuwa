"""Replay existing UFS host tests from a byte-bound source archive, not a Git checkout.

The original qualify-ufs-storage.py Git gate is unchanged. This runner requires
every archived source file to match the existing qualified source manifest.
No Git revision is inferred from a directory name; provenance is the old report.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PIN='af785c1777161a62931425c2faaa536ce0bebd5b'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def manifest(root):
    return {p.relative_to(root).as_posix():sha(p) for p in root.rglob('*')
            if p.is_file() and '.git' not in p.parts}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();src=a.source.resolve();out=a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'out'):raise ValueError('Fresh isolated output required')
    oldpath=ROOT/'reports/desktop-readiness/2026-10-30-ufs-storage-r2/audit.json'
    old=json.loads(oldpath.read_bytes())
    if not old['passed'] or old['source_revision']!=PIN:raise ValueError('Historical qualification identity')
    before=manifest(src)
    if before!=old['source_sha256']:raise ValueError('Archive differs from qualified complete source manifest')
    test=ROOT/'tests/ufs_store_cycle.cpp';patch=ROOT/'patches/driver-candidates/native-ufs-dma-write-ownership.patch'
    if sha(test)!=old['fixture_sha256'] or sha(patch)!=old['patch_sha256']:
        raise ValueError('DMA regression input changed')
    out.mkdir(parents=True);local=out/'source';shutil.copytree(src,local,ignore=shutil.ignore_patterns('.git'))
    report=dict(passed=False,commands=[],source_revision_from_prior_report=PIN,git_head_verified=False,
                complete_source_manifest=before,prior_report_sha256=sha(oldpath),device_accessed=False)
    def save():(out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    def run(args,name,expected=0):
        args=list(map(str,args))
        # Git apply needs no repository here. Avoid discovering the Windows-only
        # .git pointer from WSL; --directory still targets the same isolated copy.
        cwd=ROOT.parent if args[:2]==['git','apply'] else ROOT
        r=subprocess.run(args,cwd=cwd,capture_output=True,timeout=120)
        (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
        report['commands'].append(dict(argv=args,cwd=str(cwd),exit=r.returncode,expected=expected,log=name));save()
        if r.returncode!=expected:raise RuntimeError(name+': '+r.stderr.decode(errors='replace')[-2000:])
    bridge=local/'tests/RootCommandsBridge.cpp';text=bridge.read_text();needle='static void IOLockLock(void *) {}'
    if text.count(needle)!=1:raise ValueError('Existing lock fixture context')
    bridge.write_text(text.replace(needle,'static void IOLockLock(void *) { callback(6,0,0,nullptr); }'))
    fixture=local/'tests/RootWindowRead.cpp';text=fixture.read_text();needle='{0ULL,UINT64_MAX}'
    if text.count(needle)!=1:raise ValueError('Existing Linux LP64 fixture context')
    fixture.write_text(text.replace(needle,'{uint64_t(0),UINT64_MAX}'))
    flags=['/usr/bin/clang++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-function',
           '-fsanitize=address,undefined','-fno-pie','-no-pie','-g','-pthread']
    run(flags+['-I',local/'tests',test,'-o',out/'old-cycle'],'old-build')
    run([out/'old-cycle','negative-control'],'old-negative',42)
    # Apply only to the isolated copy; source and original worktree are read-only inputs.
    run(['git','apply','--unsafe-paths','--directory='+str(local),patch],'apply-dma')
    route=json.loads((ROOT/'config/ramblock-ios16-link-contract.json').read_bytes())['ufs_route_patch']
    routepath=ROOT/route['path']
    if sha(routepath)!=route['sha256']:raise ValueError('Route binding')
    run(['git','apply','--unsafe-paths','--directory='+str(local),routepath],'apply-route')
    route_test=ROOT/'tests/ufs_nuwa_route.cpp'
    run(flags+['-I',local,route_test,'-o',out/'nuwa-route'],'route-build');run([out/'nuwa-route'],'route')
    run(flags+['-I',local/'tests',test,'-o',out/'cycle'],'cycle-build');run([out/'cycle'],'cycle')
    for name in ('RootCommands','RootLayout','RootWindowRead','RootPublication','TransferPoll','SmmuTakeover'):
        extra=['-lcrypto','-Wno-deprecated-declarations'] if name=='RootLayout' else []
        run(flags+[local/'tests'/(name+'.cpp'),'-o',out/name]+extra,name+'-build');run([out/name],name)
    if manifest(src)!=before:raise ValueError('Archive changed during test')
    report.update(passed=True,patch_sha256=sha(patch),fixture_sha256=sha(test),route_patch_sha256=sha(routepath),
                  route_test_sha256=sha(route_test),suites=8,
                  compiler=subprocess.check_output(['/usr/bin/clang++','--version'],text=True).splitlines()[0],
                  scope='Real production headers with existing HC/DMA/locking/media fixtures. No device I/O, SMMU takeover or mount proof.')
    save();print('PASS source-manifest-bound UFS: old defect negative control and 8 host suites')
if __name__=='__main__':main()
