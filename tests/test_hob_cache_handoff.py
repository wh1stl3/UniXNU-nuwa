"""Host-check the exact handoff extent, guards, barrier order and one-shot hook."""
import hashlib,json,subprocess
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
def added(item):
 raw=(ROOT/item['path']).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('Patch changed')
 return '\n'.join(x[1:] for x in raw.decode().splitlines() if x.startswith('+') and not x.startswith('+++'))
class HandoffTests(unittest.TestCase):
 def test_exact_handoff(self):
  p=json.loads((ROOT/'config/firmware-hob-cache-handoff-profile.json').read_text());stage=added(p['candidate']['patches'][-2]);new=added(p['candidate']['patches'][-1])
  start=stage.index('// NUWA_HOB_AUDIT_PURE_BEGIN');end=stage.index('  NuwaHobAuditCheckpoint ("hob-constructor", 0, TRUE);');guard=stage[start:stage.index('\n}',end)+2]
  start=new.index('// NUWA_HOB_CACHE_BEGIN');handoff=new[start:new.index('// NUWA_HOB_CACHE_END')]
  start=new.index('// Candidate-only one-shot hook.');end=new.index('  mNuwaBeforeMmuInstall = Callback;',start);api=new[start:new.index('\n}',end)+2]
  start=new.index('  // NUWA_HOB_CACHE_HOOK_BEGIN');hook=new[start:new.index('  // NUWA_HOB_CACHE_HOOK_END')]
  host=r'''
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
#include <assert.h>
#define STATIC static
#define CONST const
#define VOID void
#define EFIAPI
#define TRUE 1
#define FALSE 0
#define MAX_UINTN SIZE_MAX
#define AARCH64_EL1 4
#define AARCH64_EL2 8
#define EFI_D_ERROR 1
#define EFI_SUCCESS 0
#define EFI_UNSUPPORTED 3
#define EFI_COMPROMISED_DATA 33
#define EFI_ERROR(s) ((s)!=0)
#define DEBUG(x) do{}while(0)
typedef uint8_t UINT8;typedef uint16_t UINT16;typedef uint32_t UINT32;typedef uint64_t UINT64;typedef size_t UINTN;typedef char CHAR8;typedef int BOOLEAN;typedef UINT64 EFI_STATUS;
typedef struct {UINT16 HobType,HobLength;UINT32 Reserved;} EFI_HOB_GENERIC_HEADER;
typedef struct {EFI_HOB_GENERIC_HEADER Header;UINT32 Version,BootMode;UINT64 EfiMemoryTop,EfiMemoryBottom,EfiFreeMemoryTop,EfiFreeMemoryBottom,EfiEndOfHobList;} EFI_HOB_HANDOFF_INFO_TABLE;
#define EFI_HOB_TYPE_END_OF_HOB_LIST 0xffff
#define EFI_HOB_TYPE_HANDOFF 1
static void ZeroMem(void*p,size_t n){memset(p,0,n);}
static UINT64 ReadUnaligned64(const UINT64*p){UINT64 n;memcpy(&n,p,8);return n;}
static void*current;static jmp_buf fatal;
static void*GetHobList(void){return current;}
static void CpuDeadLoop(void){longjmp(fatal,1);}
static UINTN el=4,sctlr,line=64;static int events[16],event_count,sctlr_reads;static void*maintained;static UINTN maintained_bytes;
static UINTN ArmReadCurrentEL(void){return el;}
static UINTN ArmReadSctlr(void){sctlr_reads++;return sctlr;}
static UINTN ArmDataCacheLineLength(void){return line;}
static void ArmDataSynchronizationBarrier(void){events[event_count++]=1;}
static void*InvalidateDataCacheRange(void*p,UINTN n){events[event_count++]=2;maintained=p;maintained_bytes=n;assert(((UINTN)p%line)==0&&n%line==0);return p;}
static void ArmInstructionSynchronizationBarrier(void){events[event_count++]=3;}
'''+guard+'\n'+handoff+'\n'+api+r'''
static int installed,failed;
static EFI_STATUS install(void){EFI_STATUS Status=EFI_SUCCESS;
'''+hook+r'''
 installed++;return EFI_SUCCESS;
FreeTranslationTable:failed++;return Status;
}
static EFI_STATUS fail_callback(void){return EFI_COMPROMISED_DATA;}
static void reject(void){event_count=0;if(setjmp(fatal)==0){NuwaHobCacheHandoff();assert(!"Guard accepted invalid state");}assert(event_count==0);}
int main(void){
 UINTN span;assert(!NuwaHobCacheExtent(0,4096,8,64,&span));assert(!NuwaHobCacheExtent(4096,4096,4096,64,&span));assert(!NuwaHobCacheExtent(4096,8192,4097,24,&span));assert(!NuwaHobCacheExtent(4096,8192,4097,8,&span));assert(!NuwaHobCacheExtent(4096,16384,4097,8192,&span));assert(!NuwaHobCacheExtent(4097,8192,4100,64,&span));assert(!NuwaHobCacheExtent(4096,8192,8193,64,&span));assert(!NuwaHobCacheExtent(4096,4223,4222,64,&span));assert(!NuwaHobCacheExtent(64,SIZE_MAX,SIZE_MAX-1,64,&span));assert(!NuwaHobCacheExtent(4096,8192,4097,64,NULL));
 for(UINTN n=1;n<=8192;n++){assert(NuwaHobCacheExtent(4096,12288,4096+n,64,&span));assert(span>=n&&span-n<64&&span%64==0);}
 UINT8 *p;assert(posix_memalign((void**)&p,4096,16384)==0);memset(p,0x5a,16384);EFI_HOB_HANDOFF_INFO_TABLE*ph=(void*)p;memset(ph,0,sizeof(*ph));ph->Header.HobType=1;ph->Header.HobLength=56;ph->EfiMemoryBottom=(UINTN)p;ph->EfiMemoryTop=(UINTN)p+16384;ph->EfiFreeMemoryTop=ph->EfiMemoryTop;ph->EfiEndOfHobList=(UINTN)p+0xfe8;ph->EfiFreeMemoryBottom=(UINTN)p+0xff0;
 EFI_HOB_GENERIC_HEADER h={7,0xfb0,0};memcpy(p+56,&h,8);h.HobType=0xffff;h.HobLength=8;memcpy(p+0xfe8,&h,8);current=p;NuwaHobAuditInit(p,16384);UINT8*copy=malloc(16384);memcpy(copy,p,16384);
 NuwaSetMmuBeforeInstallCallback(NuwaHobCacheHandoff);assert(install()==0);assert(installed==1&&failed==0&&mNuwaBeforeMmuInstall==NULL);assert(event_count==4&&events[0]==1&&events[1]==2&&events[2]==1&&events[3]==3);assert(maintained==p&&maintained_bytes==4096);assert(memcmp(copy,p,16384)==0);
 event_count=0;assert(install()==0&&installed==2&&event_count==0);NuwaSetMmuBeforeInstallCallback(fail_callback);assert(install()==EFI_COMPROMISED_DATA&&failed==1&&installed==2&&mNuwaBeforeMmuInstall==NULL);
 for(UINTN i=1;i<=5;i++){if((i&5)==0)continue;sctlr=i;reject();}sctlr=0;sctlr_reads=0;el=12;reject();assert(sctlr_reads==0);el=0;reject();assert(sctlr_reads==0);el=4;
 UINTN base=mNuwaAuditBase;mNuwaAuditBase=0;reject();mNuwaAuditBase=base;line=24;reject();line=64;
 ((EFI_HOB_GENERIC_HEADER*)(p+56))->HobLength=0;reject();memcpy(p,copy,16384);sctlr=0x30;event_count=0;assert(NuwaHobCacheHandoff()==0&&event_count==4&&memcmp(copy,p,16384)==0);
 free(copy);free(p);puts("PASS 8192 alignments, observed FF0->1000 extent, invalid states cause zero maintenance, DSB/IVAC/DSB/ISB order, byte-unchanged HOB, one-shot/default/failure callback");return 0;
}
'''
  exe='/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/hob-cache-handoff/host-handoff';(ROOT/'out/hob-cache-handoff').mkdir(parents=True,exist_ok=True)
  cmd=['wsl','-d','Ubuntu-22.04','--','clang','-x','c','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-o',exe,'-']
  compile_result=subprocess.run(cmd,input=host,capture_output=True,text=True);self.assertEqual(compile_result.returncode,0,compile_result.stderr)
  result=subprocess.run(['wsl','-d','Ubuntu-22.04','--',exe],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
  report=dict(scope='Exact candidate range/guard/helper and one-shot hook host test, register/cache operations recorded by test adapters; not real cache execution',patch_sha256=p['candidate']['patches'][-1]['sha256'],helper_sha256=hashlib.sha256(handoff.encode()).hexdigest(),host_stdin_sha256=hashlib.sha256(host.encode()).hexdigest(),compile_command=cmd,compile_stderr=compile_result.stderr,stdout=result.stdout,stderr=result.stderr,exit_code=result.returncode)
  (ROOT/'reports/hob-cache-handoff/host-tests.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':unittest.main()
