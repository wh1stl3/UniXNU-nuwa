// SPDX-License-Identifier: BSD-2-Clause
// Actual C driver with software UEFI/crypto callbacks, not physical hardware.
extern "C" {
#include <Uefi.h>
#include <Guid/EventGroup.h>
#include <Guid/FileInfo.h>
#include <Protocol/SimpleFileSystem.h>
#include <Library/BaseCryptLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/UefiLib.h>
EFI_STATUS TestAuditVolumes(void);
void TestReady(void);
EFI_BOOT_SERVICES *gBS;
EFI_SYSTEM_TABLE *gST;
EFI_GUID gEfiFileInfoGuid=EFI_FILE_INFO_ID;
EFI_GUID gEfiSimpleFileSystemProtocolGuid=EFI_SIMPLE_FILE_SYSTEM_PROTOCOL_GUID;
EFI_GUID gEfiEventReadyToBootGuid=EFI_EVENT_GROUP_READY_TO_BOOT;
}
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include "NativeAdrenoSha256.h"
static std::vector<unsigned char> bytes;
static unsigned scenario,allocations,frees,reads,closes,openedIndex,holds,events;
static size_t position;
static EFI_SIMPLE_FILE_SYSTEM_PROTOCOL fs;
static EFI_FILE_PROTOCOL root,file;
static void check(bool ok) {if(!ok){std::fprintf(stderr,"FAIL scenario=%u alloc=%u free=%u close=%u\n",scenario,allocations,frees,closes);std::exit(1);}}
extern "C" VOID *EFIAPI AllocatePool(UINTN size) {
  if(scenario==5 && size>4096) return nullptr;
  void *p=std::malloc(size);if(p) allocations++;return p;
}
extern "C" VOID EFIAPI FreePool(VOID *p) {if(p){frees++;std::free(p);}}
extern "C" INTN EFIAPI CompareMem(CONST VOID *a,CONST VOID *b,UINTN n) {return std::memcmp(a,b,n);}
extern "C" UINTN EFIAPI Print(CONST CHAR16 *,...) {return 0;}
extern "C" BOOLEAN EFIAPI Sha256HashAll(CONST VOID *input,UINTN n,UINT8 *out) {
  if(scenario==16) return FALSE;
  NativeAdrenoSha256::hash(static_cast<const uint8_t *>(input),n,out);return TRUE;
}
static EFI_STATUS EFIAPI locate(EFI_LOCATE_SEARCH_TYPE type,EFI_GUID *,VOID *,UINTN *count,EFI_HANDLE **handles) {
  check(type==ByProtocol);
  if(scenario==18){*count=0;*handles=nullptr;return EFI_SUCCESS;}
  *count=(scenario==14?65:2);
  *handles=static_cast<EFI_HANDLE *>(AllocatePool(*count*sizeof(EFI_HANDLE)));
  check(*handles);for(unsigned i=0;i<*count;i++)(*handles)[i]=reinterpret_cast<EFI_HANDLE>(size_t(i+1));
  return EFI_SUCCESS;
}
static EFI_STATUS EFIAPI handle(EFI_HANDLE which,EFI_GUID *,VOID **out) {
  if(scenario==15) return EFI_DEVICE_ERROR;
  openedIndex=static_cast<unsigned>(reinterpret_cast<size_t>(which));*out=&fs;return EFI_SUCCESS;
}
static EFI_STATUS EFIAPI openVolume(EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *,EFI_FILE_PROTOCOL **out) {*out=&root;return EFI_SUCCESS;}
static EFI_STATUS EFIAPI open(EFI_FILE_PROTOCOL *,EFI_FILE_PROTOCOL **out,CHAR16 *path,UINT64 mode,UINT64 attr) {
  check(mode==EFI_FILE_MODE_READ && attr==0 && path[0]=='\\');
  if(scenario==8 || (openedIndex==2 && scenario!=13))return EFI_NOT_FOUND;
  *out=&file;return EFI_SUCCESS;
}
static EFI_STATUS EFIAPI close(EFI_FILE_PROTOCOL *) {closes++;return EFI_SUCCESS;}
static EFI_STATUS EFIAPI info(EFI_FILE_PROTOCOL *,EFI_GUID *,UINTN *size,VOID *buffer) {
  if(!buffer){*size=sizeof(EFI_FILE_INFO)+64;return scenario==17?EFI_DEVICE_ERROR:EFI_BUFFER_TOO_SMALL;}
  auto *value=static_cast<EFI_FILE_INFO *>(buffer);std::memset(buffer,0,*size);value->Size=*size;
  value->FileSize=bytes.size()+(scenario==3?1:0);
  if(scenario==6)value->Attribute=EFI_FILE_DIRECTORY;
  if(scenario==9)*size=1;
  return EFI_SUCCESS;
}
static EFI_STATUS EFIAPI read(EFI_FILE_PROTOCOL *,UINTN *size,VOID *out) {
  reads++;if(scenario==7)return EFI_DEVICE_ERROR;
  if(scenario==2 && position>=1048576){*size=0;return EFI_SUCCESS;}
  if(scenario==4 && position==bytes.size()){*size=1;*static_cast<UINT8 *>(out)=0;return EFI_SUCCESS;}
  if(scenario==10){*size+=1;return EFI_SUCCESS;}
  size_t got=*size;if(got>bytes.size()-position)got=bytes.size()-position;
  if(scenario==1 && got>65537)got=65537;
  if(scenario==11 && got>1)got=1;
  std::memcpy(out,bytes.data()+position,got);
  if(scenario==12 && position==0 && got)*static_cast<UINT8 *>(out)^=1;
  position+=got;*size=got;return EFI_SUCCESS;
}
static EFI_STATUS EFIAPI closeEvent(EFI_EVENT) {events++;return EFI_SUCCESS;}
static EFI_STATUS EFIAPI stall(UINTN usec) {check(usec==30000000);holds++;return EFI_SUCCESS;}
int main(int argc,char **argv) {
  check(argc==2);FILE *input=std::fopen(argv[1],"rb");check(input);
  bytes.resize(58335232);check(std::fread(bytes.data(),1,bytes.size(),input)==bytes.size());std::fclose(input);
  EFI_BOOT_SERVICES bs={};EFI_SYSTEM_TABLE system={};gBS=&bs;gST=&system;
  bs.LocateHandleBuffer=locate;bs.HandleProtocol=handle;bs.CloseEvent=closeEvent;bs.Stall=stall;
  fs.OpenVolume=openVolume;root.Open=open;root.Close=close;file.Close=close;file.GetInfo=info;file.Read=read;
  for(scenario=0;scenario<19;scenario++) {
    position=0;allocations=frees=reads=closes=openedIndex=holds=events=0;
    EFI_STATUS status=TestAuditVolumes();
    check((status==EFI_SUCCESS)==(scenario<2));check(allocations==frees);
    if(scenario==14 || scenario==15 || scenario==18)check(closes==0);
    else if(scenario==8)check(closes==2);
    else if(scenario==13)check(closes==4);
    else check(closes==3);
    if(scenario==11)check(reads==4096);
  }
  scenario=8;allocations=frees=holds=events=0;TestReady();TestReady();
  check(holds==1 && events==1 && allocations==frees);
  std::puts("PASS actual FV driver: 19 file/volume/crypto cases plus ReadyToBoot once; pools and handles balanced");
  return 0;
}
