"""Requalify the existing OS/cryptex desktop inputs without assembling a root."""
import argparse,hashlib,importlib.util,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('desktop_root',ROOT/'scripts/audit-desktop-root.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
CACHE=Path('/mnt/d/Code/PortingiOSLegacy/common/cache/donor-ios16/components')
LOCK=Path('/mnt/d/Code/PortingiOSLegacy/config/donor-ios16.lock.json')

def digests(path):
    sha=hashlib.sha256();manifest=hashlib.sha384()
    with path.open('rb') as f:
        while block:=f.read(4*1024*1024):sha.update(block);manifest.update(block)
    return dict(sha256=sha.hexdigest(),sha384=manifest.hexdigest(),bytes=path.stat().st_size)

def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--work',type=Path,required=True);cli.add_argument('--output',type=Path,required=True);a=cli.parse_args()
    C=A.C;C.need(os.name!='nt','Use WSL');work=a.work.resolve();out=a.output.resolve()
    C.need(work.parent==Path('/var/tmp') and not work.exists(),'Fresh mount directory required')
    C.need(out.is_relative_to(ROOT/'reports') and not out.exists(),'Fresh report required')
    C.need(C.sha(C.TOOL.read_bytes())==C.TOOL_SHA,'APFS reader changed')
    raw=LOCK.read_bytes();lock=json.loads(raw);plan=A.donor_plan(LOCK)
    identity=next(i for i in lock['build_identities'] if i['device_class']=='d22ap' and i['restore_behavior']=='Erase')
    records=[];commands=[];work.mkdir()
    def run(argv):
        p=subprocess.run([str(x) for x in argv],capture_output=True,text=True,timeout=120)
        commands.append(dict(argv=[str(x) for x in argv],exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr));p.check_returncode()
    for index,name in enumerate(('OS','Cryptex1,SystemOS','Cryptex1,AppOS')):
        comp=identity['components'][name];filename=comp['path'];C.need(Path(filename).name==filename,'Unexpected component path')
        image=CACHE/filename;C.need(image.is_file() and image.stat().st_size==comp['size'],'Component size/type differs')
        before=digests(image);C.need(before['sha384']==comp['manifest_digest_hex'],'Component digest mismatch')
        mount=work/str(index);mount.mkdir();mounted=False
        print(json.dumps(dict(component=name,digest_matches_manifest=True)),flush=True)
        try:
            run([C.TOOL,'-o','ro',image,mount]);mounted=True;run(['mountpoint','-q',mount])
            root=mount/'root' if (mount/'root').is_dir() else mount
            info=A.inventory(root)
            version=None
            try:version=__import__('plistlib').loads(C.rooted(root,'/System/Library/CoreServices/SystemVersion.plist').read_bytes())
            except FileNotFoundError:pass
            binaries={}
            for key in ('launchd','dyld','SpringBoard','backboardd'):
                item=info['items'][key]
                if item['present']:
                    p=C.rooted(root,item['path']);data=p.read_bytes();binaries[key]=dict(sha256=C.sha(data),bytes=len(data),macho=C.macho(data))
            cache_headers=[]
            for item in info['dyld_cache_files']:
                with C.rooted(root,item['path']).open('rb') as f:head=f.read(104)
                C.need(head[:7]==b'dyld_v1','Unknown dyld cache header')
                cache_headers.append(dict(**item,magic=head[:16].hex(),uuid=head[88:104].hex(),scope='Header/size only; subcache UUID closure and signatures pending'))
        finally:
            if mounted:run(['fusermount','-u',mount])
        C.need(subprocess.run(['mountpoint','-q',str(mount)],capture_output=True).returncode!=0,'Component mount remains active')
        C.need(digests(image)==before,'Source image changed')
        records.append(dict(component=name,path=str(image),**before,manifest_digest_matches=True,inventory=info,system_version=version,binaries=binaries,cache_headers=cache_headers,mount_cleaned_up=True))
        print(json.dumps(dict(component=name,cache_files=len(cache_headers),main_jobs=len((info['main_launch_config'] or {}).get('jobs',[])))),flush=True)
    result=dict(script_sha256=C.sha(Path(__file__).read_bytes()),inventory_script_sha256=C.sha((ROOT/'scripts/audit-desktop-root.py').read_bytes()),tool_sha256=C.TOOL_SHA,donor=plan,images=records,commands=commands,device_accessed=False,userland_executed=False,root_image_assembled=False,release_guard_changed=False,limitations=['Input/file/header checks, not execution or GUI qualification','OS and cryptex inventories remain separate; namespace merge, writable data volume and cache closure pending','Mach-O page digests do not establish CMS trust or AMFI acceptance'])
    out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(json.dumps(result,indent=2).encode()+b'\n')
    print(json.dumps(dict(components=len(records),output=str(out))))

if __name__=='__main__':main()
