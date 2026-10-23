"""Read-only nuwa Android headers and system-volume discovery contracts."""
import base64
import datetime
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
PIN='808d42e197506319ee65eb078d3defd9602e2ac2'
URL=f'https://android.googlesource.com/platform/system/tools/mkbootimg/+/{PIN}/include/bootimg/bootimg.h'
OUT=ROOT/'reports/system-volume-audit/inputs.json'

def main():
    if OUT.exists():raise ValueError('Fresh evidence required')
    schema=dict(repository='platform/system/tools/mkbootimg',commit=PIN,url=URL,
                git_blob_sha1='784499eae06f45ec7e4917d86e54eb5dbc40599a',license='Apache-2.0')
    try:
        with urllib.request.urlopen(URL+'?format=TEXT',timeout=20) as response: header=base64.b64decode(response.read())
        if b'struct vendor_boot_img_hdr_v4' not in header:raise ValueError('Header source differs')
        schema['sha256']=hashlib.sha256(header).hexdigest()
    except Exception as error:
        schema['byte_fetch_error']=str(error)
        schema['validation']='Pinned primary source structure read through web; byte download unavailable'
    devices=subprocess.check_output(['adb','devices'],text=True);found=[]
    for line in devices.splitlines():
        p=line.split()
        if len(p)==2 and p[1]=='device':
            name=subprocess.check_output(['adb','-s',p[0],'shell','getprop','ro.product.device'],text=True).strip()
            if name=='nuwa':found.append(p[0])
    if len(found)!=1:raise ValueError('Unique nuwa required')
    serial=found[0];commands=[]
    def read(command):
        p=subprocess.run(['adb','-s',serial,'exec-out',command],capture_output=True,timeout=30)
        commands.append(dict(argv=['adb','-s','<selected-nuwa>','exec-out',command],exit_code=p.returncode,
                             bytes=len(p.stdout),sha256=hashlib.sha256(p.stdout).hexdigest(),stderr=p.stderr.decode(errors='replace')))
        p.check_returncode();return p.stdout
    identity=read("su -c 'cat /sys/firmware/devicetree/base/model; cat /sys/firmware/devicetree/base/compatible'")
    if b'nuwa' not in identity.lower() or b'kalama' not in identity.lower():raise ValueError('Wrong hardware identity')
    if read('getprop sys.boot_completed').strip()!=b'1':raise ValueError('Android not complete')
    parts={}
    for name in ('boot_a','init_boot_a','vendor_boot_a'):
        data=read(f"su -c 'dd if=/dev/block/by-name/{name} bs=4096 count=1 2>/dev/null'")
        if len(data)!=4096:raise ValueError('Truncated header')
        if name!='vendor_boot_a':
            if data[:8]!=b'ANDROID!' or struct.unpack_from('<I',data,40)[0]!=4:raise ValueError('Expected boot v4')
            parts[name]=dict(header_version=4,kernel_bytes=struct.unpack_from('<I',data,8)[0],
                            ramdisk_bytes=struct.unpack_from('<I',data,12)[0],header_sha256=hashlib.sha256(data).hexdigest())
        else:
            if data[:8]!=b'VNDRBOOT' or struct.unpack_from('<I',data,8)[0]!=4:raise ValueError('Expected vendor v4')
            version,page,kernel_addr,ramdisk_addr,ramdisk_size=struct.unpack_from('<5I',data,8)
            hs,dtb_size,dtb_addr=struct.unpack_from('<IIQ',data,2096)
            ts,num,entrysize,bs=struct.unpack_from('<4I',data,2112)
            if hs!=2128 or page!=4096 or entrysize!=108:raise ValueError('Unexpected vendor v4 layout')
            info=dict(header_version=version,page_bytes=page,header_bytes=hs,vendor_ramdisk_bytes=ramdisk_size,
                      dtb_bytes=dtb_size,table_bytes=ts,table_entries=num,table_entry_bytes=entrysize,
                      bootconfig_bytes=bs,header_sha256=hashlib.sha256(data).hexdigest())
            # These are observed header values, not runtime address or board assignments.
            info['declared_addresses_not_runtime']=dict(kernel=hex(kernel_addr),ramdisk=hex(ramdisk_addr),dtb=hex(dtb_addr))
            first=read("su -c 'dd if=/dev/block/by-name/vendor_boot_a bs=4096 skip=1 count=1 2>/dev/null'")
            info['first_vendor_ramdisk_prefix_hex']=first[:16].hex()
            align=lambda n:(n+page-1)//page*page
            table_offset=align(hs)+align(ramdisk_size)+align(dtb_size)
            if ts!=num*entrysize or not 0<ts<=65536:raise ValueError('Unexpected or over-budget vendor table size')
            table=read(f"su -c 'dd if=/dev/block/by-name/vendor_boot_a bs=1 skip={table_offset} count={ts} 2>/dev/null'")
            if len(table)!=ts:raise ValueError('Truncated vendor table')
            info['table_sha256']=hashlib.sha256(table).hexdigest();info['fragments']=[]
            for i in range(num):
                size,offset,kind,label,*boardid=struct.unpack_from('<III32s16I',table,i*entrysize)
                if offset+size>ramdisk_size:raise ValueError('Fragment outside section')
                info['fragments'].append(dict(bytes=size,offset=offset,type=kind,name=label.split(b'\0')[0].decode(errors='replace')))
            parts[name]=info
    dt=json.loads((ROOT/'reports/system-volume-audit/android-dt-after-r011.json').read_text())
    chosen=next(n['properties'] for n in dt['selected_nodes'] if n['node']=='/chosen')
    start=int(chosen['linux,initrd-start']['hex'],16);end=int(chosen['linux,initrd-end']['hex'],16)
    length=end-start
    profile=json.loads((ROOT/'config/firmware-factory-heap-profile.json').read_text())
    package=json.loads((ROOT/'reports/factory-heap/39835052901/package.json').read_text())
    result=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Read-only Android post-recovery and pinned source contract, not candidate x0/initrd capture',
        primary_header_schema=schema,commands=commands,partitions=parts,
        android_initrd=dict(start=hex(start),end_exclusive=hex(end),bytes=length,mod512=length%512,
                            publisher_whole_sector_precondition_passes=length%512==0,source_dt_sha256=dt['sha256']),
        current_trial_package=dict(ramdisk_bytes=package['ramdisk_bytes'],fat_included=package['fat_included'],xnu_included=package['xnu_included']),
        source_contracts=[dict(root='firmware',commit=profile['recipe']['sources']['firmware']['commit'],path='Platforms/Xiaomi/nuwaPkg/Drivers/NuwaBootMemoryDxe/NuwaBootMemoryDxe.c',meaning='Publishes whole chosen initrd, requires positive length divisible by512; does not strip cpio/vendor prefix'),
                          dict(root='unixnu',commit=profile['recipe']['sources']['unixnu']['commit'],path='package/UniXNUPkg/UniXNUPkg.dec',meaning='Configuration path is EFI/UniXNU/unixnu.toml'),
                          dict(root='unixnu',commit=profile['recipe']['sources']['unixnu']['commit'],path='package/UniXNUPkg/Library/UniXNULib/Config.c',meaning='Search loaded volume then SimpleFileSystem volumes; no config -> built-in actions and fallback loader scan')],
        conclusions=['Current diagnostic package has no supplied FAT or operating-system payload',
                     'Historical/current Android initrd is not automatically a sector-aligned standalone FAT volume',
                     'Vendor fragment selection/generic initrd/bootconfig assembly must be accounted for before a FAT transport is claimed'],
        todo=['Actual candidate FDT chosen initrd and SHENGMEM outcome','Exact installed ABL v4 fragment selection/assembly for fastboot boot','Real target ADT/prelinked kernel ABI completion'],
        image_generated=False,device_mode_changed=False,board_feed_changed=False)
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(android_initrd=result['android_initrd'],partitions=parts),indent=2))

if __name__=='__main__':main()
