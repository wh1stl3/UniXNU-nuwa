"""Read only the Android UFS LU0 GPT header, retaining geometry and digests."""
import argparse, hashlib, json, struct, subprocess, zlib
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Reference already exists')
    devices = subprocess.check_output(['adb', 'devices'], text=True).splitlines()
    targets = [line.split()[0] for line in devices if line.endswith('\tdevice')]
    targets = [s for s in targets if subprocess.check_output(['adb','-s',s,'shell','getprop ro.product.device'],text=True).strip()=='nuwa']
    if len(targets)!=1: raise ValueError('Expected one nuwa')
    def read(cmd):
        return subprocess.check_output(['adb','-s',targets[0],'exec-out',"su -c '"+cmd+"'"],timeout=15)
    path=read('readlink -f /sys/class/block/sda/device').decode().strip()
    host=read('cat /sys/class/scsi_host/host0/proc_name').decode().strip()
    if not path.endswith('/0:0:0:0') or '1d84000' not in path or 'ufs' not in host.lower(): raise ValueError('Not nuwa UFS LU0: '+path+' '+host)
    block=int(read('cat /sys/class/block/sda/queue/logical_block_size')); sectors=int(read('cat /sys/class/block/sda/size'))
    if block!=4096 or sectors%8: raise ValueError('Unsupported geometry')
    cmd='dd if=/dev/block/sda bs=4096 skip=1 count=1 2>/dev/null'
    page=read(cmd)
    if len(page)!=block or page!=read(cmd) or page[:8]!=b'EFI PART': raise ValueError('GPT block absent or unstable')
    size,crc=struct.unpack_from('<II',page,12);this,backup=struct.unpack_from('<QQ',page,24)
    if not 92<=size<=block or this!=1 or backup!=sectors//8-1: raise ValueError('Invalid GPT geometry')
    if zlib.crc32(page[:16]+bytes(4)+page[20:size])!=crc: raise ValueError('Header CRC mismatch')
    result=dict(scope='Android read-only reference, no UEFI/XNU access',sysfs=path,host=host,lun=0,lba=1,block_bytes=block,blocks=sectors//8,gpt_header_crc32=f'{crc:08x}',full_block_crc32=f'{zlib.crc32(page):08x}',full_block_sha256=hashlib.sha256(page).hexdigest(),identical_reads=2)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(result['blocks'],result['full_block_crc32'])

if __name__=='__main__': main()
