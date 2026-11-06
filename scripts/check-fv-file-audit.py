"""Check complete FV diagnostic recipe and unchanged authentication/guard inputs."""
import argparse
import hashlib
import json
from pathlib import Path
from native_prelink_inputs import ROOT
import importlib.util
from virtual_patch import Tree


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output',required=True,type=Path)
    args=cli.parse_args()
    target=args.output.resolve()
    if not target.is_relative_to(ROOT/'reports') or target.exists():
        raise ValueError('Fresh report required')
    spec=importlib.util.spec_from_file_location('fv_prepare',ROOT/'scripts/prepare-fv-file-audit.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    p=json.loads((ROOT/'config/firmware-fv-file-audit-profile.json').read_text())
    old=json.loads((ROOT/'config/firmware-upstream-merged-profile.json').read_text())
    trees={key:Tree(ROOT/'out/nonexistent-fv-source') for key in ('firmware','unixnu')}
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    for item in p['recipe']['inputs']:
        if item['root']=='unixnu':
            raw=(helper.BASE/item['path']).read_bytes().replace(b'\r\n',b'\n')
        elif item['path'].startswith('Mu_Basecore/'):
            raw=helper.blob(helper.MU,'cfb93724a06ff86ff5ba971413368a7809ee42a5',item['path'].split('/',1)[1])
        else:
            raw=helper.blob(helper.FW,helper.PIN,item['path'])
        if sha(raw)!=item['lf_sha256']:
            raise ValueError('Pinned input changed: '+item['path'])
        trees[item['root']].files[item['path']]=raw.decode()
    for item in p['candidate']['patches']:
        raw=(ROOT/item['path']).read_bytes()
        if sha(raw)!=item['sha256']:
            raise ValueError('Patch changed')
        trees[item['root']].apply(raw.decode().replace('\r\n','\n'))
    for item in p['candidate']['post_patch_inputs']:
        if sha(trees[item['root']].read(item['path']).encode())!=item['lf_sha256']:
            raise ValueError('Post-patch hash changed: '+item['path'])
    if p['candidate']['patches'][:-1]!=old['candidate']['patches']:
        raise ValueError('Original guard patch chain changed')
    old_posts={(i['root'],i['path']):i['lf_sha256'] for i in old['candidate']['post_patch_inputs']}
    for item in p['candidate']['post_patch_inputs']:
        if item['path'] not in ('Platforms/Xiaomi/nuwaPkg/nuwa.dsc','Platforms/Xiaomi/nuwaPkg/nuwa.fdf'):
            if old_posts[(item['root'],item['path'])]!=item['lf_sha256']:
                raise ValueError('Original guard post-image changed')
    settings=json.loads((ROOT/'out/upstream-firmware-40014018074/nuwa-firmware-40014018074/build-settings.json').read_text())
    if str(p['recipe']['source_date_epoch'])!=settings['source_date_epoch']:
        raise ValueError('Timestamp differs from actually built SEC')
    result=dict(scope='Full fixed source and patch reconstruction only, not firmware execution',
        inputs=len(p['recipe']['inputs']),patches=len(p['candidate']['patches']),
        post_hashes=len(p['candidate']['post_patch_inputs']),firmware_source=helper.PIN,
        original_guard_patches_retained=True,original_guard_post_images_retained=True,
        source_date_epoch_matches_old_artifact=True,authentication_source_inputs_pinned=True,
        expected_sec_sha256=p['candidate']['file_audit']['expected_sec_sha256'],device_accessed=False)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
