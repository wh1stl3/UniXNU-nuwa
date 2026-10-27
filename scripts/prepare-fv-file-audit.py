"""Pin an opt-in FV diagnostic profile; reconstruct unchanged guards in memory."""
import copy
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
from native_prelink_inputs import ROOT
from virtual_patch import Tree

FW=Path('D:/Code/PortingiOS/nuwa/uefi-nuwa')
MU=Path('D:/Code/PortingiOSLegacy/common/sources/mu-nuwa-firmware/Mu_Basecore')
BASE=Path('D:/Code/UniXNU-integration')
PIN='a155c495c863e06d400b515315e3b8f7791dc308'


def blob(repo,pin,path):
    return subprocess.check_output(['git','--no-optional-locks','-c',f'safe.directory={repo}','-C',str(repo),'show',pin+':'+path]).replace(b'\r\n',b'\n')


def main():
    target=ROOT/'config/firmware-fv-file-audit-profile.json'
    patch=ROOT/'patches/firmware-candidates/0020-fv-file-audit-selection.patch'
    if target.exists() or patch.exists():
        raise ValueError('Fresh profile/selection patch required')
    old=json.loads((ROOT/'config/firmware-upstream-merged-profile.json').read_text())
    new=copy.deepcopy(old)
    new['scope']='Opt-in FV ReadyToBoot read-only file SHA diagnostic; preserve image verification, board, Heap and HOB guards'
    new['source_evidence']='docs/operations/2026-10-24-file-audit-access-denied.md'
    new['recipe']['sources']['firmware']['commit']=PIN
    # Preserve old build timestamp deliberately, preventing an unrelated SEC date change.
    new['recipe']['source_date_epoch']=1792776324
    new['recipe']['source_date_epoch_origin']='6176a822e66b846620b5bcd2739a0666814ee663'
    extra=[
      'Platforms/Xiaomi/nuwaPkg/Drivers/NuwaFileAuditDxe/NuwaFileAuditDxe.c',
      'Platforms/Xiaomi/nuwaPkg/Drivers/NuwaFileAuditDxe/NuwaFileAuditDxe.inf',
      'Silicon/Silicium/SiliciumPkg/SiliciumPkg.dsc.inc',
      'Silicon/Silicium/SiliciumPkg/SecureBoot-Keys.inc',
      'Mu_Basecore/SecurityPkg/Library/DxeImageVerificationLib/DxeImageVerificationLib.c',
      'Mu_Basecore/SecurityPkg/Library/DxeImageVerificationLib/DxeImageVerificationLib.h']
    trees={k:Tree(ROOT/'out/nonexistent-fv-profile-source') for k in ('firmware','unixnu')}
    for item in new['recipe']['inputs']:
        if item['root']=='unixnu':
            raw=(BASE/item['path']).read_bytes().replace(b'\r\n',b'\n')
        elif item['path'].startswith('Mu_Basecore/'):
            raw=blob(MU,'cfb93724a06ff86ff5ba971413368a7809ee42a5',item['path'].split('/',1)[1])
        else:
            raw=blob(FW,PIN,item['path'])
        if hashlib.sha256(raw).hexdigest()!=item['lf_sha256']:
            raise ValueError('Previously pinned input changed: '+item['path'])
        trees[item['root']].files[item['path']]=raw.decode()
    for path in extra:
        if any(i['root']=='firmware' and i['path']==path for i in new['recipe']['inputs']):
            continue
        raw=(blob(MU,'cfb93724a06ff86ff5ba971413368a7809ee42a5',path.split('/',1)[1])
             if path.startswith('Mu_Basecore/') else blob(FW,PIN,path))
        trees['firmware'].files[path]=raw.decode()
        new['recipe']['inputs'].append(dict(root='firmware',path=path,lf_sha256=hashlib.sha256(raw).hexdigest()))
    for item in old['candidate']['patches']:
        raw=(ROOT/item['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['sha256']:
            raise ValueError('Guard patch changed')
        trees[item['root']].apply(raw.decode().replace('\r\n','\n'))
    module='nuwaPkg/Drivers/NuwaFileAuditDxe/NuwaFileAuditDxe.inf'
    parts=[]
    for path in ('Platforms/Xiaomi/nuwaPkg/nuwa.dsc','Platforms/Xiaomi/nuwaPkg/nuwa.fdf'):
        before=trees['firmware'].read(path)
        anchor='  '+('INF ' if path.endswith('.fdf') else '')+'nuwaPkg/Drivers/NuwaBootAuditDxe/NuwaBootAuditDxe.inf\n'
        if before.count(anchor)!=1:
            raise ValueError('Ambiguous module anchor')
        after=before.replace(anchor,anchor+'  '+('INF ' if path.endswith('.fdf') else '')+module+'\n')
        parts.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+path,tofile='b/'+path))
    patch.write_text(''.join(parts),encoding='utf-8',newline='\n')
    trees['firmware'].apply(patch.read_text())
    new['candidate']['patches'].append(dict(root='firmware',path=patch.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(patch.read_bytes()).hexdigest()))
    new['candidate']['modules'].append(module)
    for item in new['candidate']['post_patch_inputs']:
        if item['root']=='firmware' and item['path'] in ('Platforms/Xiaomi/nuwaPkg/nuwa.dsc','Platforms/Xiaomi/nuwaPkg/nuwa.fdf'):
            item['lf_sha256']=hashlib.sha256(trees['firmware'].read(item['path']).encode()).hexdigest()
        elif hashlib.sha256(trees[item['root']].read(item['path']).encode()).hexdigest()!=item['lf_sha256']:
            raise ValueError('Original guard post-hash changed')
    new['candidate']['file_audit']=dict(guid='45b28639-79a9-456d-afc5-edcfe78cdae1',
        data_bytes=58335232,data_sha256='eb66542cc9b6c34f369c07229900408ab67288152f561be63fa6061efce9ffca',
        expected_sec_sha256='7192fd3f3f37061ebaf466d2e98ef0e661abf29fe5b38eaa60cba99f0d40fd90',
        image_verification_policy_changes=False,board_changes=False,kernel_execution_enabled=False)
    target.write_text(json.dumps(new,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(inputs=len(new['recipe']['inputs']),patches=len(new['candidate']['patches']),firmware_pin=PIN)))


if __name__=='__main__':main()
