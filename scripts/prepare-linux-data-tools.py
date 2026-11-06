"""Build fixed APFS tools from a source archive, without creating a repository."""
import argparse, hashlib, json, os, subprocess
from pathlib import Path
from linux_data_inputs import extract_source, need
ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT.parent/'Toolchain-nuwa/data-seed-20261027'
LEGACY = Path('/mnt/d/Code/PortingiOSLegacy/common/sources/UniXNU/drivers/NativeRamBlock')


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--work',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a = p.parse_args()
    work=a.work.resolve(); output=a.output.resolve(); source=DEPS/'apfsprogs-1bd1c1c'
    need(os.name!='nt' and work.is_relative_to(ROOT/'out') and not work.exists() and output.is_relative_to(ROOT/'reports') and not output.exists(),'Fresh host paths required')
    manifest_path=ROOT/'reports/desktop-readiness/2026-10-27-data-linux-r1/dependencies.json'; manifest_raw=manifest_path.read_bytes(); manifest=json.loads(manifest_raw)
    for record in manifest:
        path=DEPS/Path(record['path'].replace('\\','/')).name
        need(sha(path)==record['sha256'],'Dependency download changed')
    need(sha(LEGACY/'SparseDisk.h')=='8b1202eda8ae920c6b505d7b97c44691e4cd2b3c7756b20bbd86ade40b8738fd','Local sparse snapshot changed')
    extract_source(DEPS/'apfsprogs-1bd1c1c.tar.gz',source); work.mkdir(); commands=[]
    def run(argv):
        child=subprocess.run([str(v) for v in argv],capture_output=True,text=True,timeout=180)
        commands.append(dict(argv=[str(v) for v in argv],exit_code=child.returncode,stdout=child.stdout,stderr=child.stderr))
        (work/'commands.json').write_bytes(json.dumps(commands,indent=2).encode()+b'\n'); child.check_returncode()
    run(['make','-C',source/'mkapfs','-j1'])
    run(['make','-C',source/'apfsck','-j1'])
    # Actual read-only snapshot header, not a copied implementation or a kernel build.
    run(['/usr/bin/clang++','-std=c++17','-O2','-Wall','-Wextra',LEGACY/'Test/sparse.cpp','-o',work/'sparse-host'])
    run([work/'sparse-host'])
    binaries={name:dict(path=str(path),sha256=sha(path)) for name,path in (('mkapfs',source/'mkapfs/mkapfs'),('apfsck',source/'apfsck/apfsck'),('sparse_host',work/'sparse-host'))}
    need(not (source/'.git').exists(),'No dependency Git repository permitted')
    result=dict(dependencies=dict(path=str(manifest_path.relative_to(ROOT)),sha256=hashlib.sha256(manifest_raw).hexdigest()),
                apfsprogs_commit='1bd1c1c2140d13d1b6d2e03379316572bee70aa3',source_directory=str(source),binaries=binaries,commands=commands,
                host_differential_operations=4000,source_headers=dict(path=str(LEGACY/'SparseDisk.h'),sha256=sha(LEGACY/'SparseDisk.h')),
                source_tests=dict(path=str(LEGACY/'Test/sparse.cpp'),sha256=sha(LEGACY/'Test/sparse.cpp')),
                local_git_metadata_read=False,git_repository_created=False,device_accessed=False,kernel_built=False,
                sources=[dict(path='scripts/'+name,sha256=sha(ROOT/'scripts'/name)) for name in ('linux_data_inputs.py','prepare-linux-data-tools.py')])
    output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(json.dumps(result,indent=2).encode()+b'\n')
    print(json.dumps(dict(tools=list(binaries),host_operations=4000,git_repository_created=False)))


if __name__=='__main__': main()
