"""Build local iOS16 UFS installation image and genuine signed block policies.
No device path accepted. Owner key lives outside the repository. Host evidence only.
"""
import argparse,ctypes,hashlib,importlib.util,json,os,re,shutil,struct,subprocess,uuid
from pathlib import Path
R=Path(__file__).resolve().parents[1]
V=Path('/mnt/d/Code/PortingiOSLegacy/common/sources/UniXNU/kits/VerifiedRoot')
UUIDS={'OS':'DADD93F8-DBBF-4B17-A1DF-0F11E64172F7','SystemOS':'96096B28-B6DC-4BC7-9D3A-2632A0FE53F1'}
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def run(args):return subprocess.check_output(list(map(str,args)),stderr=subprocess.STDOUT).decode()
class Window:
 def __init__(self,path,offset,size):self.f=path.open('rb',buffering=8<<20);self.f.seek(offset);self.remaining=size
 def read(self,n):
  n=min(n,self.remaining);data=self.f.read(n);self.remaining-=len(data);return data
class View(ctypes.Structure):
 _fields_=[('hashes',ctypes.c_void_p),('image_bytes',ctypes.c_uint64),('block_count',ctypes.c_uint64),('generation',ctypes.c_uint64),('uuid',ctypes.c_uint8*16),('sha',ctypes.c_uint8*32)]
def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();w=a.work.resolve()
 assert os.name!='nt' and w.is_relative_to(R/'out') and not w.exists()
 base=json.loads((R/'reports/desktop-readiness/2026-10-30-fullroot-offline-r1/audit.json').read_bytes());src=R/base['image']['path'];assert src.is_file() and src.stat().st_size==base['image']['bytes']
 w.mkdir(parents=True);print('Checking full original root input',flush=True);assert sha(src)==base['image']['sha256']
 spec=importlib.util.spec_from_file_location('upstream_manifest',V/'tools/manifest.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 keys=Path.home()/'.local/share/nuwa-ios16-root-owner-20261101';keys.mkdir(mode=0o700,parents=True,exist_ok=True);os.chmod(keys,0o700);private=keys/'owner.pem';public=keys/'owner-public.pem'
 if not private.exists():
  fd=os.open(private,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
  run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:3072','-out',private])
 os.chmod(private,0o600);run(['openssl','pkey','-in',private,'-pubout','-out',public])
 library=w/'verified-root.so';run(['/usr/bin/clang','-std=c11','-Wall','-Wextra','-Werror','-fPIC','-shared','-I',V/'include',V/'src/verified_root.c',V/'tests/openssl_provider.c','-lcrypto','-o',library])
 native=ctypes.CDLL(str(library));native.vr_host_open.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_uint64,ctypes.POINTER(View)];native.vr_host_block.argtypes=[ctypes.POINTER(View),ctypes.c_uint64,ctypes.c_void_p,ctypes.c_size_t]
 records=[]
 for window in base['windows']:
  name=window['name'];out=w/name;stream=Window(src,window['offset'],window['raw_bytes']);print('Signing '+name,flush=True)
  signed=mod.make(stream,window['raw_bytes'],private,public,UUIDS[name],1,out);stream.f.close();assert signed['image_sha256']==window['raw_sha256']
  envelope=(out/'manifest.bin').read_bytes();anchor=(out/'trusted-key.bin').read_bytes();encoded=ctypes.create_string_buffer(envelope);key=ctypes.create_string_buffer(anchor);view=View()
  assert native.vr_host_open(encoded,len(envelope),key,1,ctypes.byref(view))==0
  assert bytes(view.uuid)==uuid.UUID(UUIDS[name]).bytes and view.image_bytes==window['raw_bytes']
  stream=Window(src,window['offset'],window['raw_bytes']);digest=hashlib.sha256();print('C verification of every '+name+' block',flush=True)
  for i in range(view.block_count):
   data=stream.read(4096);assert native.vr_host_block(ctypes.byref(view),i,data,len(data))==0,(name,i);digest.update(data)
  assert stream.read(1)==b'' and digest.digest()==bytes(view.sha);stream.f.close()
  # Corrupted signature, table, wrong key, rollback floor, and data must fail.
  negatives={}
  for label,at in [('header',24),('signature',160),('hash_table',544)]:
   bad=bytearray(envelope);bad[at]^=1;buf=ctypes.create_string_buffer(bytes(bad));vv=View();negatives[label]=native.vr_host_open(buf,len(bad),key,1,ctypes.byref(vv));assert negatives[label]!=0
  badkey=bytearray(anchor);badkey[32]^=1;bk=ctypes.create_string_buffer(bytes(badkey));negatives['wrong_anchor']=native.vr_host_open(encoded,len(envelope),bk,1,ctypes.byref(View()));assert negatives['wrong_anchor']!=0
  negatives['rollback']=native.vr_host_open(encoded,len(envelope),key,2,ctypes.byref(View()));assert negatives['rollback']!=0
  with src.open('rb') as f:f.seek(window['offset']);data=bytearray(f.read(4096))
  data[100]^=1;negatives['corrupt_block']=native.vr_host_block(ctypes.byref(view),0,bytes(data),len(data));assert negatives['corrupt_block']!=0
  negatives['out_of_range']=native.vr_host_block(ctypes.byref(view),view.block_count,bytes(data),len(data));assert negatives['out_of_range']!=0
  records.append(dict(**window,volume_uuid=UUIDS[name],policy_sha256=sha(out/'manifest.bin'),policy_bytes=len(envelope),blocks_verified=view.block_count,negative_controls=negatives,owner_signature=True))
 # Policies are embedded as an installation trailer; runtime loads the separate
 # archive from the same bytes, NOT a key read from the untrusted media trailer.
 image=w/'ufs-root-ios16.img';print('Writing new local installation image',flush=True)
 with src.open('rb') as f,image.open('xb') as dst:shutil.copyfileobj(f,dst,8<<20)
 with image.open('r+b') as f:
  f.seek(0,2)
  for rec in records:
   pos=(f.tell()+4095)&~4095;f.seek(pos);rec['policy_offset_in_install_image']=pos;f.write((w/rec['name']/'manifest.bin').read_bytes())
  total=(f.tell()+4095)&~4095;f.truncate(total);f.seek(0);header=bytearray(f.read(4096));struct.pack_into('<Q',header,16,total);header[4064:]=hashlib.sha256(header[:4064]).digest();f.seek(0);f.write(header)
 (w/'root-manifest.bin').write_bytes(header)
 # Linkable ARM64 policy table, key anchor in a separate read-only section.
 asm=['.section __TEXT,__const','.p2align 3']
 for i,rec in enumerate(records):asm += [f'policy_{i}:',f'.incbin "{w/rec["name"]/"manifest.bin"}"']
 asm += ['.globl _verified_root_key','_verified_root_key:',f'.incbin "{w/"OS/trusted-key.bin"}"','.p2align 3','.globl _verified_root_policy_count','_verified_root_policy_count: .quad 2','.section __DATA_CONST,__const','.p2align 3','.globl _verified_root_policies','_verified_root_policies:']
 for i,rec in enumerate(records):asm += [f'.quad policy_{i}',f'.quad {rec["policy_bytes"]}']
 (w/'VerifiedRootPolicy.S').write_text('\n'.join(asm)+'\n')
 run(['clang','-target','arm64-apple-ios16.0','-c',w/'VerifiedRootPolicy.S','-o',w/'VerifiedRootPolicy.o'])
 run(['clang','-target','arm64-apple-ios16.0','-ffreestanding','-I',V/'include','-c',V/'src/verified_root.c','-o',w/'verified_root.o'])
 run(['llvm-ar','rcs',w/'libNuwaRootPolicy.a',w/'VerifiedRootPolicy.o',w/'verified_root.o'])
 layout=json.loads((R/'reports/ufs-r9-r1/trial/android-gpt-layout.json').read_bytes());partition=next(x for x in layout['rows'] if x['name']=='userdata');start=partition['first']*4096;capacity=(partition['last']-partition['first']+1)*4096;assert total+4*1024**2<capacity
 plan=dict(logical_block_bytes=4096,target_partition='userdata',target_lun=0,first_lba=partition['first'],last_lba=partition['last'],partition_bytes=capacity,proposed_write_start_byte=start,proposed_write_end_exclusive=start+total,image_bytes=total,root_guard_bytes=4*1024**2,data_layout_selected=False,log_writes_enabled=False,device_write_authorized=False,user_preference='Backup then migration/rebuild allowed in principle; exact writes require separate confirmation',danger='Writing this range overwrites Android userdata metadata; whole userdata backup/restore required, not only overwritten prefix')
 (w/'installation-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
 print('Reading back final installation image',flush=True)
 with image.open('rb') as f:
  assert f.read(4096)==header
  for rec in records:
   stream=Window(image,rec['offset'],rec['raw_bytes']);h=hashlib.sha256()
   while data:=stream.read(8<<20):h.update(data)
   stream.f.close();assert h.hexdigest()==rec['raw_sha256'];f.seek(rec['policy_offset_in_install_image']);assert f.read(rec['policy_bytes'])==(w/rec['name']/'manifest.bin').read_bytes()
 report=dict(passed=True,image={'path':str(image.relative_to(R)),'bytes':total,'sha256':sha(image)},windows=records,source_image_sha256=base['image']['sha256'],policy_archive_sha256=sha(w/'libNuwaRootPolicy.a'),public_anchor_sha256=sha(w/'OS/trusted-key.bin'),sources={str(p):sha(p) for p in [V/'tools/manifest.py',V/'src/verified_root.c',V/'tests/openssl_provider.c',V/'adapters/xnu_crypto.c',Path(__file__)]},host_signature_and_all_blocks_verified=True,apple_code_signing_replaced=False,private_key_exported=False,device_accessed=False,bootable=False,device_write_authorized=False,runtime_crypto_adapter_linked=False,verified_native_ufs_rebuilt=False,root_mount=False,remaining=['iOS16 NativeUfs rebuild with NATIVE_VERIFIED_BLOCK=1 and exact crypto/resolver ABI','final boot carrier mapping for enlarged policy archive','cold boot and recovery carrier acceptance before installation','explicit userdata backup/migration/write authorization','physical root mount and SystemOS/EL0'])
 (w/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['image']),flush=True)
if __name__=='__main__':main()
