"""Close CHECK5 document bindings after qualification, without rebuilding."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];D=R/'reports/ufs-check-5-r1'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
assert not (D/'final-binding.json').exists()
c=read(D/'candidate.json');q=read(D/'offline-qualification-final.json');w=(R/c['image_path']).parent
assert c['image_sha256']==q['image_sha256']==sha(R/c['image_path'])
assert c['kernel_sha256']==q['kernel_sha256']==sha(w/'kernel.macho')
assert c['offline_qualified'] and not any(c[k] for k in ('consumed','device_executed','deployable'))
for path,digest in q['sources'].items():assert sha(R/path)==digest,path
for path,binding in q['tests'].items():assert sha(R/path)==binding['sha256'],path
assert sha(R/q['reused']['qualification'])==q['reused']['sha256']
# Only documentation was updated after inventory generation. Refresh that
# reference and bind the resulting snapshot; code/test bindings must still match.
invpath=R/c['patch_inventory'];inv=read(invpath)
for src in inv['sources']:
 path=Path(src['path'])
 if path==R/'docs/PATCH-INVENTORY.md':src['sha256']=sha(path)
 else:assert sha(path)==src['sha256'],str(path)
save(invpath,inv);q['patch_inventory']['sha256']=sha(invpath)
q['sources'][str(Path(__file__).relative_to(R))]=sha(Path(__file__))
save(D/'offline-qualification-final.json',q)
rejected=R/'out/ufs-check-5-r1-clean'
save(rejected/'REJECTED.json',dict(candidate_eligible=False,image_sha256=sha(rejected/'boot-ufs-check-5-r1.img'),
 kernel_sha256=sha(rejected/'kernel.macho'),failed_test='test-ufs-check5-r1.py: late old init return rearmed target',
 cause='CRLF mismatch left old target store in first integrated source; actual machine-code assertion rejected package',
 replacement=c['image_path'],replacement_sha256=c['image_sha256']))
paths=[D/'candidate.json',D/'offline-qualification-final.json',invpath,D/'superseded-offline-artifacts.json',
 w/'build.json',w/'kernel-proof.json',R/'docs/STATUS.md',R/'docs/PATCH-INVENTORY.md',R/'docs/operations/2026-11-03-ufs-check5-candidate.md']
frozen=['out/ufs-check-4-r1-clean/boot-ufs-check-4-r1.img','out/ufs-check-4-r1-clean/kernel.macho']
assert [sha(R/x) for x in frozen]==['0a37f98ea65c14f80cb446aff89cff0e51184f983e723e50705a7ec701514257','551a0cf621b5fca221be267ae25aba142d5aaa904cccdd5310dfb53b88474ec3']
save(D/'final-binding.json',dict(passed=True,candidate=c['candidate'],image_sha256=c['image_sha256'],kernel_sha256=c['kernel_sha256'],
 files={str(p.relative_to(R)):sha(p) for p in paths},frozen_check4={p:sha(R/p) for p in frozen},
 source_bindings_checked=len(q['sources']),test_reports_checked=len(q['tests']),device_accessed=False))
print('PASS CHECK5 finalized; frozen CHECK4 intact; no rebuild/device action')
