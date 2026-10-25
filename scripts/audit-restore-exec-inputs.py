"""Inspect pinned APFS exec paths and Mach-O loader declarations without device access."""
import argparse,hashlib,json,os,stat,struct,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TOOL=Path('/mnt/d/Code/PortingiOS/common/tools/apfs-fuse-linux/bin/apfs-fuse')
IMAGE_SHA='d180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--mount',type=Path,required=True);a=p.parse_args()
    if os.name=='nt':raise ValueError('Use WSL')
    output=a.output.resolve();mount=a.mount.resolve();image=ROOT/'out/root-mainline-v29/restore/restore-payload.bin'
    if output.exists() or not output.is_relative_to(ROOT/'reports') or mount.exists() or mount.parent!=Path('/var/tmp'):raise ValueError('Fresh reports and native /var/tmp mountpoint required')
    if sha(image.read_bytes())!=IMAGE_SHA or sha(TOOL.read_bytes())!='4196d312862f49574fa5b0c870542544507b59ed2d93010be12cdbe0e1394922':raise ValueError('Pinned input differs')
    commands=[];records={};mounted=False
    def run(argv):
        r=subprocess.run(argv,capture_output=True,text=True,timeout=60);commands.append(dict(argv=[str(v) for v in argv],exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));r.check_returncode()
    mount.mkdir()
    try:
        run([str(TOOL),'-o','ro',str(image),str(mount)]);mounted=True;run(['mountpoint','-q',str(mount)])
        root=mount/'root' if (mount/'root').is_dir() else mount
        for name in ('sbin/launchd','usr/lib/dyld','usr/appleinternal/sbin/launchd.development','usr/appleinternal/sbin/launchd.debug'):
            path=root/name
            try:st=path.lstat()
            except FileNotFoundError:records[name]=dict(exists=False);continue
            record=dict(exists=True,mode=oct(st.st_mode),uid=st.st_uid,gid=st.st_gid,symlink=stat.S_ISLNK(st.st_mode),bytes=st.st_size)
            if stat.S_ISLNK(st.st_mode):record['link_target']=os.readlink(path)
            elif stat.S_ISREG(st.st_mode):
                if st.st_size>8*1024*1024:raise ValueError('Unexpected executable size')
                raw=path.read_bytes();record['sha256']=sha(raw)
                try:
                    record['xattr_names']=os.listxattr(path)
                    record['compression_xattrs']={}
                    for key in record['xattr_names']:
                        if key.endswith('com.apple.decmpfs'):
                            value=os.getxattr(path,key)
                            item=dict(bytes=len(value),sha256=sha(value),header_hex=value[:16].hex())
                            if len(value)>=16:
                                magic,kind,expanded=struct.unpack_from('<IIQ',value)
                                item.update(magic=hex(magic),compression_type=kind,expanded_bytes=expanded)
                            record['compression_xattrs'][key]=item
                except OSError as e:
                    record['xattr_error']=dict(errno=e.errno,message=str(e))
                if raw[:4]==b'\xcf\xfa\xed\xfe':
                    magic,cpu,subtype,kind,count,size,flags,reserved=struct.unpack_from('<8I',raw)
                    record['macho']=dict(cpu=hex(cpu),subtype=hex(subtype),filetype=kind,commands=[]);cursor=32
                    if count>1024 or 32+size>len(raw):raise ValueError('Mach-O command bounds')
                    for _ in range(count):
                        cmd,length=struct.unpack_from('<II',raw,cursor)
                        if length<8 or cursor+length>32+size:raise ValueError('Mach-O command length')
                        if cmd==0xe:
                            offset=struct.unpack_from('<I',raw,cursor+8)[0]
                            if not 12<=offset<length:raise ValueError('Dylinker path offset')
                            loader=raw[cursor+offset:cursor+length].split(b'\0')[0].decode('utf-8')
                            record['macho']['commands'].append(dict(command='LC_LOAD_DYLINKER',path=loader,exists_in_same_host_root=(root/loader.lstrip('/')).exists()))
                        cursor+=length
            records[name]=record
    finally:
        if mounted:run(['fusermount','-u',str(mount)])
    if subprocess.run(['mountpoint','-q',str(mount)]).returncode==0:raise ValueError('Mount cleanup failed')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(json.dumps(dict(scope=__doc__,image_sha256=IMAGE_SHA,tool_commit='66b86bd525e8cb90f9012543be89b1f092b75cf3',commands=commands,files=records,mount_cleaned_up=True,device_accessed=False,not_proven=['Kernel runtime namei resolution','Native mount namespace and selected filesystem','Userland execution']),indent=2).encode()+b'\n')
    print(json.dumps(records))
if __name__=='__main__':main()
