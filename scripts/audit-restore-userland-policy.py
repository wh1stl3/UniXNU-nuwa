"""Read pinned restore launch configuration through a temporary read-only host mount."""
import argparse,hashlib,json,plistlib,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TOOL=Path('/mnt/d/Code/PortingiOSLegacy/common/tools/apfs-fuse-linux/bin/apfs-fuse')
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--mount',type=Path,required=True);a=p.parse_args()
    if os.name=='nt':raise ValueError('Use WSL')
    output=a.output.resolve();mount=a.mount.resolve()
    if not output.is_relative_to(ROOT/'reports') or output.exists() or mount.parent!=Path('/var/tmp') or mount.exists():raise ValueError('Fresh reports and native /var/tmp mountpoint required')
    image=ROOT/'out/root-mainline-v29/restore/restore-payload.bin'
    if sha(image.read_bytes())!='d180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a' or sha(TOOL.read_bytes())!='4196d312862f49574fa5b0c870542544507b59ed2d93010be12cdbe0e1394922':raise ValueError('Pinned host inputs differ')
    mount.mkdir();commands=[];records=[];mounted=False
    def run(argv):
        r=subprocess.run(argv,capture_output=True,text=True,timeout=60);commands.append(dict(argv=[str(x) for x in argv],exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));r.check_returncode()
    try:
        run([str(TOOL),'-o','ro',str(image),str(mount)]);run(['mountpoint','-q',str(mount)]);mounted=True
        root=mount/'root' if (mount/'root').is_dir() else mount
        for path in (root/'System/Library/LaunchDaemons').glob('*.plist'):
            if path.stat().st_size>128*1024:raise ValueError('Unexpected plist size')
            raw=path.read_bytes();obj=plistlib.loads(raw)
            if 'restor' in json.dumps(obj,default=str).lower():records.append(dict(path=path.relative_to(root).as_posix(),sha256=sha(raw),properties={k:obj[k] for k in ('Label','Program','ProgramArguments','RunAtLoad','KeepAlive','MachServices') if k in obj}))
    finally:
        if mounted:run(['fusermount','-u',str(mount)])
    expected=next(x for x in records if x['path'].endswith('/com.apple.restored_external.plist'))
    if expected['sha256']!='ac190dd86eb7c5dec961559d355eec55fcb55b6826113de5327f8974884c0bf9' or expected['properties'].get('RunAtLoad') is not True:raise ValueError('Restore launch policy changed')
    if subprocess.run(['mountpoint','-q',str(mount)]).returncode==0:raise ValueError('Mount cleanup failed')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(json.dumps(dict(scope=__doc__,image_sha256=sha(image.read_bytes()),tool_commit='66b86bd525e8cb90f9012543be89b1f092b75cf3',tool_sha256=sha(TOOL.read_bytes()),commands=commands,records=records,mount_cleaned_up=True,device_accessed=False,userland_executed=False),indent=2).encode()+b'\n')
    print(json.dumps(dict(restore_service_run_at_load=True,mount_cleaned_up=True)))
if __name__=='__main__':main()
