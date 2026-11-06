"""Read-only mapping/slide audit of the fixed SystemOS arm64 cache set."""
import argparse,hashlib,importlib.util,json,os,struct,subprocess
from pathlib import Path
from payload_cache_slide import parse_v2,rebase_page
from desktop_cache import CacheSet,need
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('core',ROOT/'scripts/audit-desktop-core-services.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--samples',type=Path,required=True);a=p.parse_args()
 work=a.work.resolve();output=a.output.resolve();samples=a.samples.resolve()
 need(os.name!='nt' and work.parent==Path('/var/tmp') and not work.exists(),'Fresh WSL work required')
 need(output.is_relative_to(ROOT/'reports') and not output.exists() and samples.is_relative_to(ROOT/'out') and not samples.exists(),'Fresh outputs required')
 parent=ROOT/'reports/desktop-readiness/2026-11-02-payload-code-integrity-r1/audit.json';prior=json.loads(parent.read_bytes())
 need(prior['passed'] and prior['all_selected_original_trust_covered'],'Integrity/coverage prerequisite')
 item=next(v for v in prior['inputs'] if v['component']=='Cryptex1,SystemOS');image=Path(item['path'])
 need(core.C.sha(core.C.TOOL.read_bytes())==core.C.TOOL_SHA,'Reader drift')
 before=core.A.digests(image);need(before==item['after'],'SystemOS drift')
 work.mkdir();samples.mkdir(parents=True);mount=work/'mount';mount.mkdir();mounted=False;cache=None;error=None;regions=[];sample_records=[];header=None
 def run(argv):subprocess.run(list(map(str,argv)),check=True,capture_output=True,timeout=120)
 try:
  run([core.C.TOOL,'-o','ro',image,mount]);mounted=True;run(['mountpoint','-q',mount])
  root=mount/'root' if (mount/'root').is_dir() else mount
  cache=CacheSet(root/'System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64')
  head=cache.readers[0].read(0,0x200);base,size,slide=struct.unpack_from('<3Q',head,0xe0)
  need(base==0x180000000 and 0<size<=0x100000000 and size+slide<=0x100000000 and slide<=0xffffffff and slide%4096==0,'Unexpected shared region')
  header=dict(base=hex(base),size=hex(size),kernel_reserved_size='0x100000000',max_slide=hex(slide))
  for reader,file in zip(cache.readers,cache.files):
   head=reader.read(0,0x200);table,count=struct.unpack_from('<II',head,0x138)
   need(count==len(file['mappings']) and count<=64,'Slide mapping count')
   rows=reader.read(table,count*56)
   for index,legacy in enumerate(file['mappings']):
    addr,length,offset,so,sn,flags,maxprot,initprot=struct.unpack_from('<6Q2I',rows,index*56)
    need((addr,length,offset,maxprot,initprot)==tuple(legacy[k] for k in ('address','size','offset','maxprot','initprot')),'Mapping tables disagree')
    need(base<=addr and addr+length<=base+size and addr+length+slide<=base+0x100000000,'Mapping outside shared region at maximum slide')
    need(all(x%4096==0 for x in (addr,length,offset)) and initprot & ~maxprot==0,'Mapping alignment/protection')
    record=dict(file=reader.path.name,index=index,address=hex(addr),bytes=length,flags=hex(flags),maxprot=maxprot,initprot=initprot,slide_bytes=sn)
    if sn:
     info=reader.read(so,sn);parsed=parse_v2(info,length);record.update(version=2,page_size=parsed['page'],pages=parsed['count'])
     info_name=f'region-{len(regions)}.slide';(samples/info_name).write_bytes(info)
     digests={0:hashlib.sha256(),slide:hashlib.sha256()};pointers=0;boundary=0;selected=0
     for page_index,start in enumerate(parsed['starts']):
      if start==0x4000:continue
      page=reader.read(offset+page_index*4096,4096)
      zero,n,b=rebase_page(page,page_index,parsed,0);maximum,n2,b2=rebase_page(page,page_index,parsed,slide)
      need((n,b)==(n2,b2),'Slide changes chain traversal');pointers+=n;boundary+=b
      for amount,data in ((0,zero),(slide,maximum)):digests[amount].update(struct.pack('<I',page_index)+data)
      if selected<2 or b and boundary==b:
       name=f'region-{len(regions)}-page-{page_index}.bin';(samples/name).write_bytes(page)
       sample_records.append(dict(page=name,info=info_name,page_index=page_index,slide=slide,input_sha256=core.C.sha(page),info_sha256=core.C.sha(info),zero_sha256=core.C.sha(zero),maximum_sha256=core.C.sha(maximum)));selected+=1
     record.update(rebased_pointers=pointers,straddling_pointers=boundary,zero_slide_sha256=digests[0].hexdigest(),maximum_slide_sha256=digests[slide].hexdigest())
    regions.append(record)
   print('Mapping/slide checked:',reader.path.name,flush=True)
 except BaseException as exc:error=dict(type=type(exc).__name__,message=str(exc))
 finally:
  if cache:cache.close()
  if mounted:
   try:run(['fusermount','-u',mount])
   except BaseException as exc:error=error or dict(type=type(exc).__name__,message=str(exc))
  cleanup=subprocess.run(['mountpoint','-q',str(mount)],capture_output=True).returncode!=0
  after=core.A.digests(image)
  if before!=after:error=error or dict(type='InputChanged',message=str(image))
  report=dict(passed=error is None and cleanup,error=error,mount_cleanup_complete=cleanup,input=dict(path=str(image),before=before,after=after),parent_sha256=core.C.sha(parent.read_bytes()),header=header,regions=regions,samples=sample_records,device_accessed=False,native_pager_executed=False,sources={n:core.C.sha((ROOT/'scripts'/n).read_bytes()) for n in ('audit-payload-cache-slide.py','payload_cache_slide.py','desktop_cache.py')},scope='Host reconstruction at zero/max slide; mapping bounds and all v2 chains, not native mapping, code signing, symbol binding or user execution')
  output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
 need(error is None and cleanup,'Audit failed: '+str(error))
 print('PASS',len(regions),'mappings;',sum(v.get('rebased_pointers',0) for v in regions),'rebase locations;',len(sample_records),'native-model samples')


if __name__=='__main__':main()
