"""Export fixed APFS compression attributes and independently validate payloads.

Uses host zlib, not the kernel's allocator, vnode or compression implementation.
"""
import argparse,hashlib,json,os,struct,subprocess,zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
IMAGE=ROOT/'out/root-mainline-v29/restore/restore-payload.bin'
IMAGE_SHA='d180c38dcc754bc079cc92a40f58a4b5fad2c2b7ce72cf5e64a117453fd7c90a'
SOURCE=Path('/mnt/d/Code/PortingiOSLegacy/common/sources/apfs-fuse')
BLOCK=65536
def sha(b):return hashlib.sha256(b).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)

def expand_block(data,expected):
    need(bool(data),'Empty compressed block')
    if data[0]&15==15:
        decoded=data[1:];codec=dict(mode='literal',stream_bytes=len(data),unused_suffix_bytes=0)
    else:
        need(data[0]==0x78,'Unknown zlib block marker')
        dec=zlib.decompressobj()
        decoded=dec.decompress(data,expected+1)
        need(dec.eof and not dec.unconsumed_tail,'Truncated or oversized zlib stream')
        # apfs-fuse Util.cpp stops at Z_STREAM_END, even with remaining input.
        # Record the suffix rather than claiming it is part of the zlib stream.
        codec=dict(mode='zlib',stream_bytes=len(data)-len(dec.unused_data),unused_suffix_bytes=len(dec.unused_data),unused_suffix_sha256=sha(dec.unused_data))
    need(len(decoded)==expected,'Expanded block length mismatch')
    return decoded,codec

def decode(header,resource):
    need(len(header)>=16,'Short compression header')
    magic,kind,size=struct.unpack_from('<IIQ',header)
    need(magic==0x636d7066 and 0<size<=32*1024*1024,'Compression identity or size')
    if kind==3:
        raw,codec=expand_block(header[16:],size)
        return raw,dict(kind=kind,expanded_bytes=size,blocks=[dict(index=0,expanded_bytes=size,sha256=sha(raw),**codec)])
    need(kind==4 and len(header)==16,'Unsupported compression kind or extended header')
    need(len(resource)>=16,'Short resource header')
    data,management,data_size,management_size=struct.unpack_from('>4I',resource)
    need(data>=16 and data_size>=8 and data+data_size<=len(resource),'Resource data range')
    need(management>=data+data_size and management+management_size<=len(resource),'Resource management range')
    length=struct.unpack_from('>I',resource,data)[0]
    need(length==data_size-4,'Resource data length prefix')
    base=data+4;count=struct.unpack_from('<I',resource,base)[0]
    need(count==(size+BLOCK-1)//BLOCK and 4+count*8<=length,'Resource block table count')
    records=[];parts=[];previous_end=4+count*8
    for i in range(count):
        offset,n=struct.unpack_from('<II',resource,base+4+i*8)
        need(offset>=previous_end and 0<n<=BLOCK+1 and offset+n<=length,'Compressed block overlap or extent')
        payload=resource[base+offset:base+offset+n];expected=min(BLOCK,size-i*BLOCK)
        raw,codec=expand_block(payload,expected)
        records.append(dict(index=i,relative_offset=offset,resource_offset=base+offset,compressed_bytes=n,expanded_bytes=len(raw),compressed_sha256=sha(payload),expanded_sha256=sha(raw),**codec))
        previous_end=offset+n;parts.append(raw)
    raw=b''.join(parts);need(len(raw)==size,'Expanded total size')
    return raw,dict(kind=kind,expanded_bytes=size,resource_header=dict(data_offset=data,management_offset=management,data_bytes=data_size,management_bytes=management_size),blocks=records)

def read_window(parts,offset,length):
    size=sum(map(len,parts));need(0<=offset<=size and length>=0,'Window bounds')
    end=min(size,offset+length)
    if end==offset:return b'',[]
    first,last=offset//BLOCK,(end-1)//BLOCK
    return b''.join(parts[first:last+1])[offset-first*BLOCK:end-first*BLOCK],list(range(first,last+1))

def main():
    cli=argparse.ArgumentParser();cli.add_argument('--work',type=Path,required=True);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args()
    work=args.work.resolve();output=args.output.resolve()
    need(os.name!='nt' and work.is_relative_to(ROOT/'out') and not work.exists(),'Fresh WSL work required')
    need(output.is_relative_to(ROOT/'reports') and not output.exists(),'Fresh report required')
    need(sha(IMAGE.read_bytes())==IMAGE_SHA,'Pinned root differs')
    closure_path=ROOT/'reports/userland-closure/2026-10-27-r1/audit.json';closure=json.loads(closure_path.read_bytes())
    need(closure['image_sha256']==IMAGE_SHA,'Closure input differs')
    files=[(name,r) for name,r in closure['files'].items() if r['status']=='parsed']
    binary=ROOT/'out/apfs-resource-export-build-r1/nuwa-resource-export'
    work.mkdir();paths=''.join(r['resolved']+'\n' for name,r in files)
    (work/'paths.txt').write_text(paths)
    command=[str(binary),str(IMAGE),str(work/'attributes')]
    process=subprocess.run(command,input=paths,capture_output=True,text=True,timeout=120)
    (work/'export-stdout.txt').write_text(process.stdout);(work/'export-stderr.txt').write_text(process.stderr)
    process.check_returncode();lines=process.stdout.splitlines();need(len(lines)==len(files),'Export record count')
    records=[]
    for index,((name,old),line) in enumerate(zip(files,lines),1):
        fields=line.split('\t');need(len(fields)==5 and int(fields[0])==index and fields[4]==old['resolved'],'Export path binding')
        prefix=work/'attributes'/str(index)
        if fields[2]=='0':
            records.append(dict(path=name,compressed=False,inode=int(fields[1])));continue
        header=Path(str(prefix)+'.decmpfs').read_bytes()
        resource=Path(str(prefix)+'.rsrc').read_bytes() if fields[3]=='1' else b''
        raw,details=decode(header,resource)
        need(len(raw)==old['bytes'] and sha(raw)==old['sha256'],f'Independent decode differs: {name}')
        windows=[];parts=[raw[k:k+BLOCK] for k in range(0,len(raw),BLOCK)]
        for offset,n in ((0,4096),(0,16384),(max(0,BLOCK-8),32),(max(0,len(raw)-16),32),(len(raw),1)):
            if offset>len(raw):continue
            actual,used=read_window(parts,offset,n);need(actual==raw[offset:offset+n],'Window reconstruction')
            windows.append(dict(offset=offset,requested_bytes=n,returned_bytes=len(actual),block_indices=used,sha256=sha(actual)))
        records.append(dict(path=name,inode=int(fields[1]),compressed=True,header_sha256=sha(header),resource_sha256=sha(resource),resource_bytes=len(resource),expanded_sha256=sha(raw),host_read_sha256=old['sha256'],matches_prior_host_read=True,windows=windows,**details))
    need(sha(IMAGE.read_bytes())==IMAGE_SHA,'Image changed')
    manifest={p.relative_to(SOURCE).as_posix():sha(p.read_bytes()) for p in sorted(SOURCE.rglob('*')) if p.is_file() and (p.suffix in ('.c','.cpp','.h','.inc') or p.name=='CMakeLists.txt')}
    report=dict(image_sha256=IMAGE_SHA,closure_evidence_sha256=sha(closure_path.read_bytes()),export_binary_sha256=sha(binary.read_bytes()),export_adapter_sha256=sha((ROOT/'scripts/apfs-resource-export/main.cpp').read_bytes()),cmake_sha256=sha((ROOT/'scripts/apfs-resource-export/CMakeLists.txt').read_bytes()),source_manifest=manifest,source_license='apfs-fuse GPL-2.0-or-later; linked source retained read-only',script_sha256=sha(Path(__file__).read_bytes()),zlib_runtime=zlib.ZLIB_RUNTIME_VERSION,command=command,export_exit_code=process.returncode,stdout_sha256=sha(process.stdout.encode()),records=records,device_accessed=False,root_image_modified=False,kernel_modified=False,limitations=['Host APFS attribute extraction plus host zlib, not native XNU execution','Windows are pure data reconstruction, not kernel vnode/uio/vector execution','No allocator, lock, IRQ, error path or user release bypass'])
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(json.dumps(report,indent=2).encode()+b'\n')
    print(json.dumps(dict(files=len(records),compressed=sum(r['compressed'] for r in records),blocks=sum(len(r.get('blocks',[])) for r in records),all_decoded_payloads_match=True)))

if __name__=='__main__':main()
