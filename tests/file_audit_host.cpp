// SPDX-License-Identifier: BSD-2-Clause
// Actual EFI app with software protocol fixtures; no physical UEFI claim.
extern "C" {
#include <Uefi.h>
#include <Guid/FileInfo.h>
#include <Protocol/LoadedImage.h>
#include <Protocol/SimpleFileSystem.h>
EFI_STATUS EFIAPI EfiMain(EFI_HANDLE, EFI_SYSTEM_TABLE *);
}
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include "NativeAdrenoSha256.h"

static std::vector<unsigned char> bytes;
static unsigned scenario, allocations, frees, reads, closes, holds;
static size_t position;
static EFI_LOADED_IMAGE_PROTOCOL loaded;
static EFI_SIMPLE_FILE_SYSTEM_PROTOCOL fs;
static EFI_FILE_PROTOCOL root, file;
static void check(bool ok) {if(!ok){std::fprintf(stderr,"FAIL scenario=%u\n",scenario);std::exit(1);}}
static EFI_STATUS EFIAPI output(EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *,CHAR16 *) {return EFI_SUCCESS;}
static EFI_STATUS EFIAPI handle(EFI_HANDLE target,EFI_GUID *guid,void **out) {
    if(guid->Data1==0x5b1b31a1) {*out=&loaded;return EFI_SUCCESS;}
    check(target==loaded.DeviceHandle); *out=&fs; return EFI_SUCCESS;
}
static EFI_STATUS EFIAPI pool(EFI_MEMORY_TYPE,UINTN size,void **out) {
    if(scenario==5 && size>4096) return EFI_OUT_OF_RESOURCES;
    *out=std::malloc(size); if(!*out) return EFI_OUT_OF_RESOURCES;
    allocations++;return EFI_SUCCESS;
}
static EFI_STATUS EFIAPI freePool(void *value) {frees++;std::free(value);return EFI_SUCCESS;}
static EFI_STATUS EFIAPI openVolume(EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *,EFI_FILE_PROTOCOL **out) {*out=&root;return EFI_SUCCESS;}
static EFI_STATUS EFIAPI open(EFI_FILE_PROTOCOL *,EFI_FILE_PROTOCOL **out,CHAR16 *path,UINT64 mode,UINT64 attr) {
    check(mode==EFI_FILE_MODE_READ && attr==0);
    check(path[0]=='\\' && path[1]=='E');
    if(scenario==8) return EFI_NOT_FOUND;
    *out=&file;return EFI_SUCCESS;
}
static EFI_STATUS EFIAPI close(EFI_FILE_PROTOCOL *) {closes++;return EFI_SUCCESS;}
static EFI_STATUS EFIAPI info(EFI_FILE_PROTOCOL *,EFI_GUID *,UINTN *size,void *buffer) {
    if(!buffer) {*size=sizeof(EFI_FILE_INFO)+64;return EFI_BUFFER_TOO_SMALL;}
    auto value=static_cast<EFI_FILE_INFO *>(buffer);
    std::memset(buffer,0,*size);value->Size=*size;
    value->FileSize=bytes.size()+(scenario==3?1:0);
    if(scenario==6) value->Attribute=EFI_FILE_DIRECTORY;
    if(scenario==9) *size=1;
    return EFI_SUCCESS;
}
static EFI_STATUS EFIAPI read(EFI_FILE_PROTOCOL *,UINTN *size,void *out) {
    reads++;
    if(scenario==7) return EFI_DEVICE_ERROR;
    if(scenario==2 && position>=1048576) {*size=0;return EFI_SUCCESS;}
    if(scenario==4 && position==bytes.size()) {*size=1;*static_cast<UINT8 *>(out)=0;return EFI_SUCCESS;}
    if(scenario==10) {*size=*size+1;return EFI_SUCCESS;}
    size_t got=*size;
    if(got>bytes.size()-position) got=bytes.size()-position;
    if(scenario==1 && got>65537) got=65537;
    if(scenario==11 && got>1) got=1;
    std::memcpy(out,bytes.data()+position,got);
    if(scenario==12 && position==0 && got) *static_cast<UINT8 *>(out)^=1;
    position+=got;*size=got;return EFI_SUCCESS;
}
static EFI_STATUS EFIAPI stall(UINTN value) {check(value==30000000);holds++;return EFI_SUCCESS;}
static void knownVector(const unsigned char *data,size_t count,const char *expected) {
    unsigned char digest[32];NativeAdrenoSha256::hash(data,count,digest);
    char hex[65];for(unsigned i=0;i<32;i++) std::sprintf(hex+2*i,"%02x",digest[i]);
    check(std::strcmp(hex,expected)==0);
}
int main(int argc,char **argv) {
    check(argc==2);
    knownVector(nullptr,0,"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    knownVector(reinterpret_cast<const unsigned char *>("abc"),3,"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    std::vector<unsigned char> million(1000000,'a');
    knownVector(million.data(),million.size(),"cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
    FILE *input=std::fopen(argv[1],"rb");check(input);
    bytes.resize(58335232);check(std::fread(bytes.data(),1,bytes.size(),input)==bytes.size());
    check(std::fgetc(input)==EOF);std::fclose(input);
    EFI_BOOT_SERVICES bs={};EFI_SYSTEM_TABLE system={};EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL con={};
    system.BootServices=&bs;system.ConOut=&con;con.OutputString=output;
    bs.HandleProtocol=handle;bs.AllocatePool=pool;bs.FreePool=freePool;bs.Stall=stall;
    fs.OpenVolume=openVolume;root.Open=open;root.Close=close;
    file.GetInfo=info;file.Read=read;file.Close=close;
    loaded.DeviceHandle=reinterpret_cast<EFI_HANDLE>(2);
    for(scenario=0;scenario<13;scenario++) {
        position=0;allocations=frees=reads=closes=holds=0;
        EFI_STATUS status=EfiMain(reinterpret_cast<EFI_HANDLE>(1),&system);
        check((status==EFI_SUCCESS)==(scenario<2));
        check(allocations==frees && holds==1 && closes==(scenario==8?1u:2u));
        if(scenario==11) check(reads==4096);
    }
    std::puts("PASS actual EFI app: 13 file/protocol cases, all allocations closed; 3 SHA256 vectors");
    return 0;
}
