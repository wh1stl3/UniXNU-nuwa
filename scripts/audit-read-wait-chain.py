"""Map fixed XNU source read boundaries and native calls without device access."""
import argparse,hashlib,importlib.util,json,re,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build-kernel-entry-probe.py');B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)
SOURCE=Path('D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full')
PINS={'bsd/kern/decmpfs.c':'9d5c0d486cd31222e007e6335aed0ce1e3bd6e609ab02005ac61d03dd421471c','security/mac_vfs.c':'51c6c39b497514f073cdd94aa2204f25679e6e92461b7a0f9120c886ea36c553'}
ORDER={
 'decmpfs_read_compressed':['decmpfs_lock_compressed_data(cp, 0)','cluster_copy_ubc_data(','decmpfs_fetch_compressed_header(','compression_type_valid(','lck_rw_lock_shared(&decompressorsLock)','adjust_fetch(','VNOP_VERIFY(','ubc_create_upl_kernel(','ubc_upl_map(','decmpfs_fetch_uncompressed_data(','wait_for_decompress(cp)','cluster_copy_upl_data('],
 'decmpfs_fetch_uncompressed_data':['lck_rw_lock_shared(&decompressorsLock)','decmp_get_func(','err = fetch(','lck_rw_unlock_shared(&decompressorsLock)'],
 'compression_type_valid':['lck_rw_lock_shared(&decompressorsLock)','decmp_get_func(','lck_rw_unlock_shared(&decompressorsLock)'],
 'decmpfs_lock_compressed_data':['current_thread()','if (cp->lockowner == thread)','lck_rw_lock_exclusive(','lck_rw_lock_shared('],
 'wait_for_decompress':['lck_mtx_lock(&decompress_channel_mtx)','decmpfs_fast_get_state(cp)','if (state != FILE_IS_CONVERTING)','lck_mtx_unlock(&decompress_channel_mtx)','msleep('],
 'mac_vnode_check_read':['vfs_context_ucred(ctx)','mac_cred_check_enforce(cred)','MAC_CHECK(vnode_check_read','return error;']}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists() or not a.output.resolve().is_relative_to(ROOT/'reports'):raise ValueError('Fresh output under reports required')
 head=subprocess.check_output(['git','-C',str(SOURCE),'rev-parse','HEAD'],text=True).strip();assert head=='1b191cb58250d0705d8a51287127505aa4bc0789'
 sources={}
 for name,pin in PINS.items():
  raw=(SOURCE/name).read_bytes();assert B.sha(raw)==pin;sources[name]=raw.decode('utf-8')
 b=json.loads(a.build.read_text());raw=B.INPUT.read_bytes();assert B.sha(raw)==B.EXPECTED;m=B.macho(raw);reverse={}
 for name,va in m['symbols'].items():reverse.setdefault(va,[]).append(name)
 records=[]
 for fn,tokens in ORDER.items():
  file='security/mac_vfs.c' if fn=='mac_vnode_check_read' else 'bsd/kern/decmpfs.c';source=sources[file];match=re.search(r'^'+fn+r'\(',source,re.M);assert match,fn;end=re.search(r'^\}',source[match.start():],re.M);assert end,fn;body=source[match.start():match.start()+end.end()];positions=[body.index(t) for t in tokens];assert positions==sorted(positions),(fn,positions)
  item=dict(function=fn,source_file=file,definition_line=source[:match.start()].count('\n')+1,ordered_source_anchors=[dict(text=t,line=source[:match.start()+at].count('\n')+1) for t,at in zip(tokens,positions)],native_symbol='_'+fn)
  start=m['symbols'].get('_'+fn)
  if start is None:item.update(native_symbol_available=False,limitation='No separate symbol in fixed image; may be inlined or omitted, not inferred')
  else:
   finish=min(v for v in m['symbols'].values() if v>start);assert finish-start<0x10000;calls=[]
   for pc in range(start,finish,4):
    w=struct.unpack_from('<I',raw,B.backed(m,pc))[0]
    if w&0xfc000000==0x94000000:
     imm=w&0x3ffffff
     if imm&(1<<25):imm-=1<<26
     target=pc+imm*4;calls.append(dict(pc=hex(pc),word=hex(w),kind='BL',target=hex(target),target_symbols=reverse.get(target,[])))
    elif w&0xfffffc1f==0xd63f0000:calls.append(dict(pc=hex(pc),word=hex(w),kind='BLR',register='x'+str((w>>5)&31),target='runtime value required'))
   item.update(native_symbol_available=True,start=hex(start),end=hex(finish),calls=calls)
  records.append(item)
 decmpfs_lines=sources['bsd/kern/decmpfs.c'].splitlines();wait_context=[dict(line=i+1,text=decmpfs_lines[i]) for i in range(1828,1848)]
 out=dict(scope=__doc__,level='static-only',source_commit=head,source_repository='https://github.com/apple-oss-distributions/xnu',source_license='APSL-2.0',source_sha256=PINS,native_input_sha256=B.EXPECTED,candidate_sha256=b['candidate']['sha256'],test_source_sha256=B.sha(Path(__file__).read_bytes()),functions=records,conditional_conversion_wait_context=wait_context,limitations=['Source order is lexical and conditional; not every listed branch executes','No runtime APFS v_op table or actual 272 callback target captured','Registered type4 pointer does not prove compressed-data lock, UBC/UPL, validation or fetch returned','No observed lock owner, wait_event, blocked thread or IRQ state'],device_accessed=False)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n',newline='\n');print(json.dumps(dict(functions=len(records),native_symbols=sum(x['native_symbol_available'] for x in records),static_checks_passed=True)))
if __name__=='__main__':main()