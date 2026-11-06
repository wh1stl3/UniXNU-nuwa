"""Bind the offline desktop inventory and emit a non-deployable source plan."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);a=p.parse_args();work=a.work.resolve()
    require(work.is_relative_to(ROOT/'reports') and not work.exists(),'Fresh reports directory required')
    paths={
        'restore_inventory':ROOT/'reports/desktop-readiness/2026-10-27-r2/audit.json',
        'inventory_tests':ROOT/'reports/desktop-readiness/2026-10-27-r2/tests.json',
        'system_inventory':ROOT/'reports/desktop-readiness/2026-10-27-system-r1/audit.json',
        'probe41':ROOT/'reports/xnu-first-entry/entry-probe-41.json',
    }
    docs={k:json.loads(v.read_bytes()) for k,v in paths.items()};restore=docs['restore_inventory'];tests=docs['inventory_tests'];system=docs['system_inventory'];package=docs['probe41']
    require(restore['script_sha256']==system['inventory_script_sha256']==tests['script_sha256']==sha(ROOT/'scripts/audit-desktop-root.py'),'Inventory source mismatch')
    require(system['script_sha256']==sha(ROOT/'scripts/audit-desktop-system.py') and tests['test_sha256']==sha(ROOT/'scripts/test-desktop-root.py'),'System/test source mismatch')
    require(restore['closure_parser_sha256']==sha(ROOT/'scripts/audit-userland-closure.py'),'Parser changed')
    require(len(tests['checks'])==6 and all(c['passed'] is True for c in tests['checks']),'Inventory tests incomplete')
    require(restore['desktop_executable_gaps']==['SpringBoard','backboardd'] and restore['mount_cleaned_up'],'Restore inventory differs')
    require(all(v['device_accessed'] is False for v in (restore,tests,system)) and system['root_image_assembled'] is False,'Evidence scope differs')
    require(all(i['manifest_digest_matches'] and i['mount_cleaned_up'] for i in system['images']),'Component digest/mount checks incomplete')
    images={i['component']:i for i in system['images']};osimage=images['OS'];systemos=images['Cryptex1,SystemOS'];appos=images['Cryptex1,AppOS']
    require(osimage['system_version']['ProductBuildVersion']==systemos['system_version']['ProductBuildVersion']=='20H392','Input build mismatch')
    require(all(osimage['inventory']['items'][k]['present'] for k in ('launchd','dyld','SpringBoard','backboardd')),'Desktop executables missing')
    jobs=osimage['inventory']['main_launch_config']['jobs'];labels=('com.apple.SpringBoard','com.apple.backboardd','com.apple.runningboardd')
    selected=[j for j in jobs if j['label'] in labels];require(len(selected)==3 and all(j['program_present'] for j in selected),'Desktop job source missing')
    require(len(systemos['cache_headers'])==44,'Cache inventory changed')
    image=ROOT/package['image_path'];require(sha(image)==package['image_sha256']=='8d242a2dd953146af5c3c8ae59c6805cba6599aa7283188180667bfca5c2ec2a','PROBE41 changed')
    plan=dict(identity=system['donor']['identity'],source_layers=[{k:i[k] for k in ('component','path','sha256','sha384','bytes')} for i in (osimage,systemos,appos)],
        desktop_jobs=selected,total_main_launch_jobs=len(jobs),cache_files=systemos['cache_headers'],
        pending=['OS/cryptex namespace and symlink resolution','Complete shared-cache image/subcache UUID and dependency closure','Writable data layout, ownership and service content review','Native read/decode completion, exec and first EL0 evidence','iOS16 IOSurface/MobileFramebuffer ABI, refresh and actual scanout','nuwa HID/keys/touch and actual input events'],
        current_package=dict(path=package['image_path'],sha256=package['image_sha256'],purpose='Restore-root kernel diagnostic; not desktop payload'),
        executable=False,deployable=False,release_guard_changed=False,device_accessed=False)
    references=[
        dict(url='https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html',role='Generic launch-on-demand semantics; not an iOS16 config-layout specification'),
        dict(repository='dipa-studio/ios-sweet',commit='45263bee51df4a0f55cdf9c649af886399488ddb',path='tools/mkiosroot.sh',sha256='b1b28a8ca69e572452872e0622f441c0cee170ddf94e51f6a8709adcb53e8655',bytes=5594,license='MIT at repository root',role='Reference namespace/cache arrangement only; script not executed or copied; SM7150 board and policy modifications not adopted'),
        dict(repository='UniXNU/GopFramebuffer',commit='33e941a878dcf01b98dbd9160d798bd56e7551ea',license='BSD-2-Clause-Patent',role='Upstream display interface review; CPU/GPU scanout and MobileFramebuffer timer notification; nuwa/iOS16 ABI unqualified'),
        dict(url='https://unixnu.com/drivers/repositories',role='Driver selection references; SoC/device and OS ABI qualification remain separate'),
    ]
    work.mkdir();(work/'desktop-input-plan.json').write_bytes(json.dumps(plan,indent=2).encode()+b'\n')
    result=dict(script_sha256=sha(Path(__file__)),evidence=[dict(name=k,path=v.relative_to(ROOT).as_posix(),sha256=sha(v)) for k,v in paths.items()],plan_sha256=sha(work/'desktop-input-plan.json'),references=references,scope='Offline input qualification only; not assembled image, dependency closure, userland execution or desktop acceptance',device_accessed=False,release_guard_changed=False)
    (work/'qualification.json').write_bytes(json.dumps(result,indent=2).encode()+b'\n');print(json.dumps(dict(components=3,main_jobs=len(jobs),cache_files=44,tests=6,probe41_unchanged=True,deployable=False)))
if __name__=='__main__':main()
