"""Read-only inventory of the payload needed before an iOS desktop can boot.

Never executes image programs or changes the root/launch package.
Presence is not runtime, signature, ABI or hardware qualification.
"""
import argparse, hashlib, importlib.util, json, os, plistlib, stat, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('closure_inventory',ROOT/'scripts/audit-userland-closure.py')
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
ITEMS={
    'launchd':'/sbin/launchd','dyld':'/usr/lib/dyld',
    'SpringBoard':'/System/Library/CoreServices/SpringBoard.app/SpringBoard',
    'backboardd':'/usr/libexec/backboardd',
    'SpringBoard_job':'/System/Library/LaunchDaemons/com.apple.SpringBoard.plist',
    'backboardd_job':'/System/Library/LaunchDaemons/com.apple.backboardd.plist',
    'UIKitCore':'/System/Library/PrivateFrameworks/UIKitCore.framework/UIKitCore',
    'QuartzCore':'/System/Library/Frameworks/QuartzCore.framework/QuartzCore',
    'IOSurface':'/System/Library/Frameworks/IOSurface.framework/IOSurface',
    'IOMobileFramebuffer':'/System/Library/PrivateFrameworks/IOMobileFramebuffer.framework/IOMobileFramebuffer',
}
CACHE_DIRS=('/System/Library/Caches/com.apple.dyld','/System/Library/dyld')
MAIN_CONFIG='/System/Library/xpc/launchd.plist'

def config_jobs(obj,trail=()):
    C.need(len(trail)<=8,'Launch configuration nesting too deep')
    if not isinstance(obj,dict):return []
    if 'Program' in obj or 'ProgramArguments' in obj:
        return [(trail,obj)]
    found=[]
    for key,value in obj.items():
        if isinstance(value,dict):found.extend(config_jobs(value,trail+(str(key),)))
    return found

def inventory(root):
    items={}; jobs=[]; caches=[]; main_config=None
    for name,path in ITEMS.items():
        try:
            p=C.rooted(root,path);st=p.stat();C.need(stat.S_ISREG(st.st_mode),'Expected regular payload file')
            items[name]=dict(path=path,present=True,bytes=st.st_size)
        except FileNotFoundError:items[name]=dict(path=path,present=False)
    for folder in CACHE_DIRS:
        try:directory=C.rooted(root,folder)
        except FileNotFoundError:continue
        for p in sorted(directory.glob('dyld_shared_cache*')):
            actual=C.rooted(root,folder+'/'+p.name);st=actual.stat()
            if stat.S_ISREG(st.st_mode):caches.append(dict(path=folder+'/'+p.name,bytes=st.st_size))
    for folder in ('/System/Library/LaunchDaemons','/Library/LaunchDaemons'):
        try:directory=C.rooted(root,folder)
        except FileNotFoundError:continue
        for p in sorted(directory.glob('*.plist')):
            raw=C.rooted(root,folder+'/'+p.name).read_bytes();C.need(len(raw)<131072,'Plist too large')
            obj=plistlib.loads(raw);C.need(isinstance(obj,dict),'Job is not a dictionary')
            args=obj.get('ProgramArguments',[]);program=obj.get('Program') or (args[0] if args else None)
            C.need(program is None or isinstance(program,str),'Invalid job program')
            declared={k:obj[k] for k in ('RunAtLoad','KeepAlive','Disabled','MachServices','Sockets','UserName','GroupName','LaunchOnlyOnce') if k in obj}
            present=False
            if program and program.startswith('/'):
                try:present=C.rooted(root,program).is_file()
                except FileNotFoundError:pass
            jobs.append(dict(path=folder+'/'+p.name,sha256=C.sha(raw),label=obj.get('Label'),program=program,program_present=present,declared=declared))
    try:config_raw=C.rooted(root,MAIN_CONFIG).read_bytes()
    except FileNotFoundError:pass
    else:
        C.need(len(config_raw)<8*1024*1024,'Launch config too large');config=plistlib.loads(config_raw)
        C.need(isinstance(config,dict),'Main launch config is not a dictionary')
        main_config=dict(path=MAIN_CONFIG,sha256=C.sha(config_raw),keys=list(config),jobs=[])
        for trail,obj in config_jobs(config):
            args=obj.get('ProgramArguments',[]);program=obj.get('Program') or (args[0] if args else None)
            C.need(program is None or isinstance(program,str),'Invalid main config program')
            present=False
            if program and program.startswith('/'):
                try:present=C.rooted(root,program).is_file()
                except FileNotFoundError:pass
            main_config['jobs'].append(dict(keys=list(trail),label=obj.get('Label'),program=program,program_present=present,declared={k:obj[k] for k in ('RunAtLoad','KeepAlive','Disabled','MachServices','Sockets','UserName','GroupName') if k in obj}))
    missing=[name for name in ('SpringBoard','backboardd') if not items[name]['present']]
    return dict(items=items,dyld_cache_files=caches,launch_jobs=jobs,main_launch_config=main_config,
                desktop_executable_gaps=missing,
                framework_resolution='Shared-cache membership not parsed; absent standalone framework is not by itself a missing dependency',
                classification='desktop executable payload incomplete' if missing else 'desktop executables present; dependency/runtime qualification pending')

def donor_plan(path):
    raw=path.read_bytes();doc=json.loads(raw)
    C.need((doc['product_type'],doc['version'],doc['build'])==('iPhone10,3','16.7.16','20H392'),'Pinned IPSW identity changed')
    ids=[i for i in doc['build_identities'] if i['device_class']=='d22ap' and i['restore_behavior']=='Erase' and int(i['ap_chip_id'],16)==0x8015 and int(i['ap_board_id'],16)==6]
    C.need(len(ids)==1,'Ambiguous donor identity')
    components=ids[0]['components'];wanted=('OS','RestoreRamDisk','StaticTrustCache','Cryptex1,SystemOS','Cryptex1,AppOS','Cryptex1,SystemTrustCache','Cryptex1,AppTrustCache')
    return dict(lock_sha256=C.sha(raw),manifest_sha256=doc['manifest_sha256'],identity=dict(product=doc['product_type'],version=doc['version'],build=doc['build'],device_class='d22ap'),
                components={k:components[k] for k in wanted if k in components},
                status='Manifest metadata only; no new component downloaded, authenticated or installed')

def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--mount',type=Path,required=True);cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--lock',type=Path,required=True);a=cli.parse_args()
    C.need(os.name!='nt','Use WSL read-only mount');out=a.output.resolve();mount=a.mount.resolve()
    C.need(out.is_relative_to(ROOT/'reports') and not out.exists(),'Fresh reports output required')
    C.need(mount.parent==Path('/var/tmp') and not mount.exists(),'Fresh /var/tmp mount required')
    C.need(C.sha(C.IMAGE.read_bytes())==C.IMAGE_SHA and C.sha(C.TOOL.read_bytes())==C.TOOL_SHA,'Pinned image/tool changed')
    plan=donor_plan(a.lock);commands=[];mounted=False
    def run(argv):
        p=subprocess.run([str(x) for x in argv],capture_output=True,text=True,timeout=90)
        commands.append(dict(argv=[str(x) for x in argv],exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr));p.check_returncode()
    mount.mkdir()
    try:
        run([C.TOOL,'-o','ro',C.IMAGE,mount]);mounted=True;run(['mountpoint','-q',mount])
        root=mount/'root' if (mount/'root').is_dir() else mount;result=inventory(root)
    finally:
        if mounted:run(['fusermount','-u',mount])
    C.need(subprocess.run(['mountpoint','-q',str(mount)],capture_output=True).returncode!=0,'Mount still active')
    C.need(C.sha(C.IMAGE.read_bytes())==C.IMAGE_SHA,'Image changed')
    result.update(image_sha256=C.IMAGE_SHA,tool_sha256=C.TOOL_SHA,script_sha256=C.sha(Path(__file__).read_bytes()),closure_parser_sha256=C.sha((ROOT/'scripts/audit-userland-closure.py').read_bytes()),donor=plan,commands=commands,mount_cleaned_up=True,device_accessed=False,userland_executed=False,release_guard_changed=False)
    out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(json.dumps(result,indent=2).encode()+b'\n')
    print(json.dumps(dict(classification=result['classification'],missing=result['desktop_executable_gaps'],jobs=len(result['launch_jobs']),cache_files=len(result['dyld_cache_files']))))

if __name__=='__main__':main()
