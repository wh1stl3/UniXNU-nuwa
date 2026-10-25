"""Inspect the pinned restore APFS through a read-only host mount, not nuwa."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TOOL=Path('/mnt/d/Code/PortingiOS/common/tools/apfs-fuse-linux/bin/apfs-fuse')
PIN='4196d312862f49574fa5b0c870542544507b59ed2d93010be12cdbe0e1394922'
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output',type=Path,default=ROOT/'reports/kernel-entry-probe/2026-10-25-v29/restore-filesystem-retry.json')
    cli.add_argument('--mount',type=Path,default=Path('/var/tmp/unixnu-nuwa-restore-v29'))
    args=cli.parse_args()
    if os.name=='nt':raise ValueError('Run under WSL')
    source=ROOT/'out/root-mainline-v29/restore/restore-payload.bin';raw=source.read_bytes()
    if sha(raw)!='d180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a' or raw[32:36]!=b'NXSB':raise ValueError('Pinned APFS changed')
    block_size=int.from_bytes(raw[36:40],'little');blocks=int.from_bytes(raw[40:48],'little')
    assert block_size==4096 and blocks*block_size==len(raw)
    if sha(TOOL.read_bytes())!=PIN:raise ValueError('Host reader changed')
    # FUSE rejects Windows drvfs mountpoints. Keep all saved artifacts in out/
    # and use a fresh native WSL directory solely as the ephemeral mountpoint.
    mount=args.mount.resolve();output=args.output.resolve()
    if not output.is_relative_to(ROOT/'reports') or mount.parent!=Path('/var/tmp'):raise ValueError('Report under reports and fresh native WSL mountpoint required')
    if mount.exists() or output.exists():raise ValueError('Fresh host outputs required')
    mount.mkdir();commands=[];result=dict(scope=__doc__,device_accessed=False,source_sha256=sha(raw),apfs_block_size=block_size,apfs_blocks=blocks,bytes=len(raw),tool_sha256=PIN,tool_commit='66b86bd525e8cb90f9012543be89b1f092b75cf3',tool_license='GPL-2.0',mounted_read_only=False,mount_cleaned_up=False,commands=commands)
    def run(argv):
        p=subprocess.run(argv,capture_output=True,text=True,timeout=60);commands.append(dict(argv=[str(x) for x in argv],exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr));p.check_returncode();return p
    mounted=False
    try:
        run([str(TOOL),'-o','ro',str(source),str(mount)])
        run(['mountpoint','-q',str(mount)]);mounted=True;result['mounted_read_only']=True
        root=mount/'root' if (mount/'root').is_dir() else mount
        result['top_level']=sorted(p.name for p in root.iterdir());result['files']={}
        for name in ('sbin/launchd','usr/lib/dyld','usr/local/bin/restored_external','System/Library/CoreServices/SystemVersion.plist'):
            p=root/name
            if p.is_symlink():
                link=os.readlink(p);result['files'][name]=dict(symlink=link)
            elif p.is_file():
                size=p.stat().st_size
                if size>32*1024**2:raise ValueError('Inspected file exceeds budget')
                content=p.read_bytes();result['files'][name]=dict(bytes=size,sha256=sha(content),magic=content[:16].hex())
            else:result['files'][name]=dict(present=False)
        result['status']='host-readonly-inspection-complete'
    finally:
        if mounted:
            run(['fusermount','-u',str(mount)])
            assert subprocess.run(['mountpoint','-q',str(mount)]).returncode!=0
            result['mount_cleaned_up']=True
        output.write_bytes(json.dumps(result,indent=2).encode()+b'\n')
    print(json.dumps(dict(status=result['status'],mount_cleaned_up=result['mount_cleaned_up'])))
if __name__=='__main__':main()
