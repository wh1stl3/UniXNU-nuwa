"""Bind newly executed native paths and exact upstream reference files; no candidate mutation."""
import argparse,hashlib,json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def sha(raw):return hashlib.sha256(raw).hexdigest()
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
legacy=Path('/mnt/d/Code/PortingiOSLegacy/common/sources')
references=[]
for name,commit,files in [
 ('UniXNU','75bc13dd34dc4e403826793739e316a264ce00dd',['LICENSE','scripts/audit-image4-ignition.py','scripts/check-image4-service-checkpoints.py','scripts/prepare-owner-data-fixture.py','drivers/NativeUfs/RootPublication.h']),
 ('UniXNU-sheng','a599a1a8a92093b5077543e071b72130769eb325',['LICENSE','scripts/build-userdata-root-image.py'])]:
 root=legacy/name
 def git(*args):return subprocess.check_output(['git','-c','safe.directory='+str(root),'-C',str(root),*args])
 assert git('rev-parse','HEAD').decode().strip()==commit
 for f in files:
  raw=(root/f).read_bytes();committed=git('show',commit+':'+f)
  # A CRLF checkout may differ physically; bind both and explicitly qualify.
  assert raw.replace(b'\r\n',b'\n')==committed.replace(b'\r\n',b'\n')
  references.append(dict(repository=name,commit=commit,path=f,working_sha256=sha(raw),git_blob_sha256=sha(committed),content_matches_commit_after_eol_normalization=True,license='BSD-2-Clause-Patent'))
base=R/'reports/desktop-readiness/2026-11-03-offline-mainline-r2';reports=[];count=0
for name,script,n in [('mach-command-chain','test-native-mach-command-chain.py',13),('nonce-persistence','test-native-nonce-persistence.py',6),('ignition-publication','test-native-ignition-publication.py',5)]:
 path=base/(name+'.json');raw=path.read_bytes();record=json.loads(raw)
 assert record['script_sha256']==sha((R/'scripts'/script).read_bytes())
 # Harness reports use cases, each with an observed terminal boundary.
 assert record['passed'] and len(record['cases'])==n
 assert record['kernel_sha256']=='c38fe9d4428467f9f3767408159f4d8327984fcaad2fbde175eca6ece93d313e'
 reports.append(dict(path=str(path.relative_to(R)),sha256=sha(raw),cases=n));count+=n
frozen=[]
for path,expected in [('out/ufs-check-5-r1-qualified/boot-ufs-check-5-r1.img','876d4b783fca141053479e44ee72f6d80a237611cf6d671353f1389b16a0d540'),('reports/ufs-check-5-r1/offline-qualification-final.json','27755b0de2082c258e5a14454b652d794de85f070f39a410d36c212a0db00fdb')]:
 digest=sha((R/path).read_bytes());assert digest==expected;frozen.append(dict(path=path,sha256=digest))
builder=R.parent/'Toolchain-nuwa/data-seed-20261027/make-data-seed-linux.py';source=builder.read_text()
assert 'S_IFDIR | mode' in source and "want('file count', seen['num_files'], 0)" in source
result=dict(passed=True,new_native_cases=count,reports=reports,references=references,frozen=frozen,
 data_builder=dict(path=str(builder),sha256=sha(builder.read_bytes()),scope='directory-only catalog builder; verifier requires file count zero; no regular-file, ACL, protection-class or hardlink importer qualified'),
 adopted_methods=['bind sysctl OID and actual handler separately from provider startup','distinguish AES service wait, nonce gate and blob serialization','retain publication lifecycle and started-object ownership','bind seed metadata to exact importer capabilities'],
 not_adopted=['iPadOS17 addresses/ABI and sheng partition geometry','authentication bypass or synthetic successful blob','macOS scratch copy as production metadata importer'],
 remaining=['native provider registration/start and authenticated context construction','full load_machfile VM lifecycle and signature implementation','shared-cache framework dynamic IPC and relative dirfd consumers','Data metadata importer and isolated APFS write/readback qualification'],
 scope='Read-only reference comparison plus actual CHECK5 instruction execution with explicit fixtures. No full XNU/APFS/QEMU boot, device action, deployable Data or newly fixed hardware root cause.',script_sha256=sha(Path(__file__).read_bytes()))
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print('PASS',count,'new native cases;',len(references),'pinned reference files; CHECK5 unchanged')
