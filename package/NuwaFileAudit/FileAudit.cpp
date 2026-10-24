// SPDX-License-Identifier: BSD-2-Clause
// Read-only EFI application. Never interprets or executes READTEST.BIN.
extern "C" {
#include <Uefi.h>
#include <Guid/FileInfo.h>
#include <Protocol/LoadedImage.h>
#include <Protocol/SimpleFileSystem.h>
}
#include "NativeAdrenoSha256.h"
#include "ExpectedFile.h"

static EFI_GUID LoadedGuid = EFI_LOADED_IMAGE_PROTOCOL_GUID;
static EFI_GUID FsGuid = EFI_SIMPLE_FILE_SYSTEM_PROTOCOL_GUID;
static EFI_GUID InfoGuid = EFI_FILE_INFO_ID;
static EFI_SYSTEM_TABLE *System;

static void text(const CHAR16 *value) {
    if (System->ConOut) System->ConOut->OutputString(System->ConOut, const_cast<CHAR16 *>(value));
}
static void text(const wchar_t *value) {
    static_assert(sizeof(wchar_t)==sizeof(CHAR16), "UEFI wide strings require 16-bit wchar_t");
    text(reinterpret_cast<const CHAR16 *>(value));
}
static void hex(UINT64 value) {
    CHAR16 output[19] = {L'0', L'x'};
    for (unsigned i=0;i<16;i++) output[2+i]=L"0123456789abcdef"[(value>>(60-4*i))&15];
    output[18]=0; text(output);
}
static void digestText(const UINT8 *digest) {
    CHAR16 output[65];
    for (unsigned i=0;i<32;i++) {
        output[2*i]=L"0123456789abcdef"[digest[i]>>4];
        output[2*i+1]=L"0123456789abcdef"[digest[i]&15];
    }
    output[64]=0; text(output);
}

extern "C" EFI_STATUS EFIAPI EfiMain(EFI_HANDLE image, EFI_SYSTEM_TABLE *system) {
    System=system;
    EFI_BOOT_SERVICES *bs=system->BootServices;
    EFI_LOADED_IMAGE_PROTOCOL *loaded=nullptr;
    EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *fs=nullptr;
    EFI_FILE_PROTOCOL *root=nullptr, *file=nullptr;
    EFI_FILE_INFO *info=nullptr;
    UINT8 *buffer=nullptr;
    UINTN infoBytes=0, total=0, calls=0;
    UINT8 digest[32]={0}, extra=0;
    EFI_STATUS status;
    text(L"\r\n[NUWA-FILE-SHA] enter v1; read only, no kernel execution\r\n");
    text(L"[NUWA-FILE-SHA] expected bytes="); hex(NUWA_FILE_BYTES); text(L"\r\n");
    text(L"[NUWA-FILE-SHA] expected sha256="); digestText(NuwaExpectedSha); text(L"\r\n");
    status=bs->HandleProtocol(image,&LoadedGuid,reinterpret_cast<void **>(&loaded));
    if (EFI_ERROR(status)) goto done;
    status=bs->HandleProtocol(loaded->DeviceHandle,&FsGuid,reinterpret_cast<void **>(&fs));
    if (EFI_ERROR(status)) goto done;
    status=fs->OpenVolume(fs,&root);
    if (EFI_ERROR(status)) goto done;
    status=root->Open(root,&file,const_cast<CHAR16 *>(reinterpret_cast<const CHAR16 *>(L"\\EFI\\UniXNU\\Payloads\\READTEST.BIN")),EFI_FILE_MODE_READ,0);
    if (EFI_ERROR(status)) goto done;
    status=file->GetInfo(file,&InfoGuid,&infoBytes,nullptr);
    if (status!=EFI_BUFFER_TOO_SMALL || infoBytes<SIZE_OF_EFI_FILE_INFO || infoBytes>4096) {
        status=EFI_COMPROMISED_DATA; goto done;
    }
    status=bs->AllocatePool(EfiLoaderData,infoBytes,reinterpret_cast<void **>(&info));
    if (EFI_ERROR(status)) goto done;
    {
        UINTN available=infoBytes;
        status=file->GetInfo(file,&InfoGuid,&available,info);
        if (EFI_ERROR(status)) goto done;
        if (available>infoBytes || available<SIZE_OF_EFI_FILE_INFO || info->Size>available ||
            info->Size<SIZE_OF_EFI_FILE_INFO || (info->Attribute & EFI_FILE_DIRECTORY) ||
            info->FileSize!=NUWA_FILE_BYTES || NUWA_FILE_BYTES>64u*1024u*1024u) {
            status=EFI_COMPROMISED_DATA; goto done;
        }
    }
    status=bs->AllocatePool(EfiLoaderData,NUWA_FILE_BYTES,reinterpret_cast<void **>(&buffer));
    if (EFI_ERROR(status)) goto done;
    text(L"[NUWA-FILE-SHA] buffer allocated; reading same-volume file\r\n");
    while(total<NUWA_FILE_BYTES) {
        UINTN wanted=NUWA_FILE_BYTES-total;
        if(wanted>1024u*1024u) wanted=1024u*1024u;
        UINTN got=wanted;
        if(++calls>4096) {status=EFI_ABORTED;goto done;}
        status=file->Read(file,&got,buffer+total);
        if(EFI_ERROR(status)) goto done;
        if(got==0 || got>wanted) {status=EFI_COMPROMISED_DATA;goto done;}
        total+=got;
        if((total % (8u*1024u*1024u))==0 || total==NUWA_FILE_BYTES) {
            text(L"[NUWA-FILE-SHA] read bytes=");hex(total);text(L"\r\n");
        }
    }
    {
        UINTN got=1;
        status=file->Read(file,&got,&extra);
        if(EFI_ERROR(status)) goto done;
        if(got!=0) {status=EFI_COMPROMISED_DATA;goto done;}
    }
    NativeAdrenoSha256::hash(buffer,total,digest);
    text(L"[NUWA-FILE-SHA] actual sha256=");digestText(digest);text(L"\r\n");
    for(unsigned i=0;i<32;i++) if(digest[i]!=NuwaExpectedSha[i]) {status=EFI_CRC_ERROR;goto done;}
    text(L"[NUWA-FILE-SHA] PASS exact length, EOF and SHA256\r\n");
    status=EFI_SUCCESS;
done:
    if(EFI_ERROR(status)) {text(L"[NUWA-FILE-SHA] FAIL status=");hex(status);text(L"\r\n");}
    text(L"[NUWA-FILE-SHA] final bytes=");hex(total);text(L" read calls=");hex(calls);text(L"\r\n");
    if(buffer) bs->FreePool(buffer);
    if(info) bs->FreePool(info);
    if(file) file->Close(file);
    if(root) root->Close(root);
    text(L"[NUWA-FILE-SHA] hold 30s then return to firmware\r\n");
    bs->Stall(30000000);
    return status;
}
