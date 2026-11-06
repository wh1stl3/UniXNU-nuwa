"""Bind the genuine CI SystemOS selector and local policy to a frozen carrier.

Offline double-origin linking only; no patch injection or boot-image creation.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
import ufs_carrier_object_link as linker

ROOT=Path(__file__).resolve().parents[1]
RUN=41376381953
COMMIT='73db6bf41b8f0707b94826c1f7db26de6ca7b2b7'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('artifact','ci-checkout','work','carrier','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();assert not a.work.exists() and not a.output.exists()
    receipt=json.loads(subprocess.check_output(['gh','run','view',str(RUN),'--repo','wh1stl3/UniXNU-nuwa',
                    '--json','status,conclusion,headSha,url,createdAt,updatedAt']))
    assert receipt['status']=='completed' and receipt['conclusion']=='success' and receipt['headSha']==COMMIT
    audit_path=a.artifact/'nuwa-8796-source/reports/verified-ufs/audit.json';audit=json.loads(audit_path.read_bytes())
    contract_raw=subprocess.check_output(['git','-C',str(a.ci_checkout),'show',COMMIT+':config/ufs-ios16-verified-root-ci.json'])
    assert audit['passed'] and hashlib.sha256(contract_raw).hexdigest()==audit['contract_sha256']
    contract=json.loads(contract_raw)
    for group in ('sources','patches'):
        for name,digest in contract[group].items():assert sha(ROOT/name)==digest,name
    directory=a.artifact/'nuwa-8796-source/build/verified-ufs'
    for name,digest in audit['objects'].items():assert sha(directory/name)==digest,name
    assert sha(directory/'libNativeUfs.verified.a')==audit['archive_sha256']
    policy=ROOT/'out/ufs-policy-storage-r1/CompactRootPolicy.o'
    policy_report=json.loads((policy.parent/'compact-link.json').read_bytes())
    assert sha(policy)==policy_report['compact_object_sha256']
    carrier=a.carrier/'kernel.macho';proof=json.loads((a.carrier/'kernel-proof.json').read_bytes())
    assert sha(carrier)==proof['kernel_sha256']
    objects=[directory/name for name in audit['objects']]+[policy]
    chunks=linker.link(carrier.read_bytes(),objects,a.work,ROOT/'out/kernel-mainline-nuwa-route-r1/ld64','_nuwa_ufs_select_systemos')
    linked=a.work/'linked-0.macho'
    symbols=linker.run('llvm-nm','--defined-only','-n',linker.linux(linked)).decode().splitlines()
    entries=[int(line.split()[0],16) for line in symbols if line.split()[-1:] == ['_nuwa_ufs_select_systemos']]
    assert len(entries)==1
    entry=entries[0]+linker.BIAS
    imports=json.loads((a.work/'imports.json').read_bytes())
    assert any(addr<=entry<addr+len(data) for (segment,section),(addr,data) in chunks.items() if section=='__text')
    result=dict(ci=receipt,ci_audit_sha256=sha(audit_path),contract_sha256=hashlib.sha256(contract_raw).hexdigest(),
                sources=contract['sources'],objects={obj.name:sha(obj) for obj in objects},
                carrier_sha256=sha(carrier),entry=hex(entry),resolved_imports=len(imports),
                imports=imports,origins=[hex(linker.BASE),hex(linker.BASE+linker.DELTA)],
                linked_products={name:sha(a.work/name) for name in ('linked-0.macho','linked-1.macho')},
                sections=[dict(segment=key[0],section=key[1],address=hex(addr),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for key,(addr,data) in chunks.items()],
                passed=True,analysis_only=True,boot_embedded=False,device_accessed=False,
                actual_mount=False,script_sha256=sha(Path(__file__)),linker_script_sha256=sha(ROOT/'scripts/ufs_carrier_object_link.py'))
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(objects=len(objects),imports=len(imports),entry=hex(entry),section_bytes=sum(len(data) for addr,data in chunks.values()))))


if __name__=='__main__':main()
