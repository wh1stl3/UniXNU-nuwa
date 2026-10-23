"""Compile the exact candidate HOB audit with guard pages and host sanitizers."""
import hashlib,json,subprocess
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class HobStageBounds(unittest.TestCase):
 def test_actual_checker_and_trusted_arena(self):
  profile=json.loads((ROOT/'config/firmware-hob-stage-audit-profile.json').read_text());item=profile['candidate']['patches'][-1];raw=(ROOT/item['path']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),item['sha256'])
  added='\n'.join(line[1:] for line in raw.decode().splitlines() if line.startswith('+') and not line.startswith('+++'))
  helper=added[added.index('// NUWA_HOB_AUDIT_PURE_BEGIN'):added.index('\nVOID\nBuildMemoryTypeInformationHob') if '\nVOID\nBuildMemoryTypeInformationHob' in added else added.index('\n  NuwaHobAuditCheckpoint ("create-before"')]
  # The added snippet ends after Init, before instrumentation of existing code.
  end=helper.index('  NuwaHobAuditCheckpoint ("hob-constructor", 0, TRUE);')
  helper=helper[:helper.index('\n}',end)+2]
  host=r'''
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <sys/mman.h>
#define STATIC static
#define CONST const
#define VOID void
#define EFIAPI
#define TRUE 1
#define FALSE 0
#define MAX_UINTN SIZE_MAX
#define EFI_D_ERROR 1
#define DEBUG(x) do {} while(0)
typedef uint8_t UINT8; typedef uint16_t UINT16; typedef uint32_t UINT32; typedef uint64_t UINT64; typedef size_t UINTN; typedef char CHAR8; typedef int BOOLEAN;
typedef struct {UINT16 HobType,HobLength;UINT32 Reserved;} EFI_HOB_GENERIC_HEADER;
typedef struct {EFI_HOB_GENERIC_HEADER Header;UINT32 Version,BootMode;UINT64 EfiMemoryTop,EfiMemoryBottom,EfiFreeMemoryTop,EfiFreeMemoryBottom,EfiEndOfHobList;} EFI_HOB_HANDOFF_INFO_TABLE;
#define EFI_HOB_TYPE_END_OF_HOB_LIST 0xffff
#define EFI_HOB_TYPE_HANDOFF 1
static void ZeroMem(void *p,size_t n){memset(p,0,n);}
static UINT64 ReadUnaligned64(const UINT64 *p){UINT64 x;memcpy(&x,p,8);return x;}
static void *current;static int dead;
static void *GetHobList(void){return current;}
static void CpuDeadLoop(void){dead++;}
'''+helper+r'''
static void put(UINT8*p,UINTN at,UINT16 type,UINT16 len){EFI_HOB_GENERIC_HEADER h={type,len,0};memcpy(p+at,&h,8);}
int main(void){
 UINT8 *space=mmap(NULL,12288,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);assert(space!=MAP_FAILED);assert(mprotect(space+4096,4096,PROT_READ|PROT_WRITE)==0);
 UINT8 *p=space+8192-336;UINT8 saved[336];NUWA_HOB_AUDIT_SCAN scan;
 put(p,0,1,56);put(p,56,7,80);for(UINTN at=136;at<328;at+=48)put(p,at,3,48);put(p,328,0xffff,8);memcpy(saved,p,336);
 assert(NuwaAuditHobBuffer(p,336,328,&scan)==0&&scan.Count==6&&scan.Offset==328);assert(memcmp(saved,p,336)==0);
 for(UINTN n=0;n<336;n++)assert(NuwaAuditHobBuffer(p,n,328,&scan)==1);
 assert(NuwaAuditHobBuffer(NULL,336,328,&scan)==1);assert(NuwaAuditHobBuffer(p+1,335,328,&scan)==1);assert(NuwaAuditHobBuffer(p,336,329,&scan)==1);assert(NuwaAuditHobBuffer(p,336,SIZE_MAX,&scan)==1);assert(NuwaAuditHobBuffer(p,336,328,NULL)==1);
 UINT16 bad[]={0,1,7,9,0xffff};for(UINTN i=0;i<5;i++){memcpy(p,saved,336);put(p,280,4,bad[i]);assert(NuwaAuditHobBuffer(p,336,328,&scan)==2&&scan.Offset==280&&scan.Count==5);}
 memcpy(p,saved,336);put(p,280,4,0xfff8);assert(NuwaAuditHobBuffer(p,336,328,&scan)==3);
 memcpy(p,saved,336);put(p,280,0xffff,8);assert(NuwaAuditHobBuffer(p,336,328,&scan)==4);
 memcpy(p,saved,336);put(p,328,0xffff,16);assert(NuwaAuditHobBuffer(p,336,328,&scan)==4);
 UINT8 *many=calloc(4098,8);for(UINTN i=0;i<4097;i++)put(many,i*8,3,8);put(many,4097*8,0xffff,8);assert(NuwaAuditHobBuffer(many,4098*8,4097*8,&scan)==5);free(many);
 memcpy(p,saved,336);EFI_HOB_HANDOFF_INFO_TABLE *ph=(void*)p;ph->EfiMemoryBottom=(UINTN)p;ph->EfiMemoryTop=(UINTN)(space+8192);ph->EfiFreeMemoryTop=ph->EfiMemoryTop;ph->EfiEndOfHobList=(UINTN)(p+328);ph->EfiFreeMemoryBottom=ph->EfiEndOfHobList+8;current=p;
 NuwaHobAuditInit(p,space+8192-p);assert(dead==0&&mNuwaLastCount==6);put(p,280,4,0);NuwaHobAuditCheckpoint("bad",0,FALSE);assert(dead==1&&mNuwaLastCount==6);put(p,280,3,48);
 ph->EfiEndOfHobList=(UINTN)(space+8192+16);NuwaHobAuditCheckpoint("untrusted-end",0,FALSE);assert(dead==2);ph->EfiEndOfHobList=(UINTN)(p+328);
 current=p+8;NuwaHobAuditCheckpoint("wrong-list",0,FALSE);assert(dead==3);current=p;
 ph->EfiFreeMemoryBottom++;NuwaHobAuditCheckpoint("bad-bottom",0,FALSE);assert(dead==4);ph->EfiFreeMemoryBottom--;
 NuwaHobAuditInit(p,SIZE_MAX);assert(dead==5);NuwaHobAuditCheckpoint("restored",0,FALSE);assert(dead==5);
 assert(munmap(space,12288)==0);puts("PASS guard pages; 336 truncations; observed +0x118 zero length; malformed/oversized/early-end/count cap; trusted PHIT and no failed-state update");return 0;
}
'''
  work=ROOT/'out/hob-stage-audit';work.mkdir(parents=True,exist_ok=True);exe='/mnt/d/Code/UniXNU-nuwa/out/hob-stage-audit/host-audit'
  cmd=['wsl','-d','Ubuntu-22.04','--','clang','-x','c','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-o',exe,'-']
  compile_result=subprocess.run(cmd,input=host,capture_output=True,text=True);self.assertEqual(compile_result.returncode,0,compile_result.stderr)
  result=subprocess.run(['wsl','-d','Ubuntu-22.04','--',exe],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
  report=dict(scope='Exact candidate diagnostic on host with ASan/UBSan and guard pages; not firmware or device execution',patch_sha256=item['sha256'],helper_sha256=hashlib.sha256(helper.encode()).hexdigest(),host_stdin_sha256=hashlib.sha256(host.encode()).hexdigest(),compile_command=cmd,compile_stderr=compile_result.stderr,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr)
  (ROOT/'reports/hob-stage-audit/host-tests.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':unittest.main()
