// SPDX-License-Identifier: BSD-2-Clause
#include <Uefi.h>
#include <Protocol/DevicePath.h>
#include <Protocol/LoadedImage.h>
#include <Protocol/Rng.h>
#include <Protocol/SimpleTextInEx.h>
#include "Session.h"
#include "Sb0InputBinding.h"

static EFI_GUID LoadedGuid = EFI_LOADED_IMAGE_PROTOCOL_GUID;
static EFI_GUID TextInGuid = EFI_SIMPLE_TEXT_INPUT_PROTOCOL_GUID;
static EFI_GUID TextInExGuid = EFI_SIMPLE_TEXT_INPUT_EX_PROTOCOL_GUID;
static EFI_GUID RngGuid = EFI_RNG_PROTOCOL_GUID;
static EFI_GUID PmicGpioGuid = {0x4bc5c6d7, 0x4ca4, 0x8835,
    {0xd1,0xbc,0xd2,0x9c,0xc2,0x02,0x5d,0x4a}};
static const EFI_GUID ButtonFfs = {0x5bd181db,0x0487,0x4f1a,
    {0xae,0x73,0x82,0x0e,0x16,0x56,0x11,0xb3}};
static const EFI_GUID PmicFfs = {0x5776232e,0x082d,0x4b75,
    {0x9a,0x0e,0xfe,0x1d,0x13,0xf7,0xa5,0xd9}};
static const EFI_GUID RngFfs = {0xb0d3689e,0x11f8,0x43c6,
    {0x8e,0xce,0x02,0x3a,0x29,0xce,0xc3,0x5b}};

static struct {
  VENDOR_DEVICE_PATH vendor;
  EFI_DEVICE_PATH_PROTOCOL end;
} ButtonPath = {
  {{1,4,{20,0}}, {0xd7f58a0e,0xbed2,0x4b5a,{0xbb,0x43,0x8a,0xb2,0x3d,0xd0,0xe2,0xb0}}},
  {0x7f,0xff,{4,0}}
};

typedef EFI_STATUS (EFIAPI *IRQ_READ)(UINT32 pmic, UINT32 gpio, UINT32 type, BOOLEAN *level);
typedef struct {
  UINT64 revision;
  UINTN prior[6];
  IRQ_READ irqStatus;
} PMIC_GPIO_R4;
STATIC_ASSERT(OFFSET_OF(PMIC_GPIO_R4, irqStatus) == 0x38, "r4 GPIO slot");

static BOOLEAN Equal(const VOID *left, const VOID *right, UINTN size) {
  const UINT8 *a = left, *b = right;
  while (size--) if (*a++ != *b++) return FALSE;
  return TRUE;
}

static EFI_LOADED_IMAGE_PROTOCOL *FvImage(EFI_BOOT_SERVICES *bs, EFI_HANDLE handle,
                                          const EFI_GUID *guid) {
  EFI_LOADED_IMAGE_PROTOCOL *image = NULL;
  if (bs->HandleProtocol(handle, &LoadedGuid, (VOID **)&image) != EFI_SUCCESS || !image ||
      !image->ImageBase || !image->FilePath) return NULL;
  // DXE dispatcher passes a relative firmware-volume file node, then End.
  const UINT8 *path = (const UINT8 *)image->FilePath;
  static const UINT8 head[] = {4,6,20,0}, end[] = {0x7f,0xff,4,0};
  if (!Equal(path, head, sizeof head) || !Equal(path + 4, guid, sizeof(*guid)) ||
      !Equal(path + 20, end, sizeof end)) return NULL;
  return image;
}

static EFI_LOADED_IMAGE_PROTOCOL *UniqueProtocol(EFI_BOOT_SERVICES *bs, EFI_GUID *protocol,
                                                 const EFI_GUID *guid, VOID **iface) {
  EFI_HANDLE *handles = NULL;
  UINTN count = 0;
  EFI_LOADED_IMAGE_PROTOCOL *image = NULL;
  if (bs->LocateHandleBuffer(ByProtocol, protocol, NULL, &count, &handles) != EFI_SUCCESS)
    return NULL;
  if (count == 1 && bs->HandleProtocol(handles[0], protocol, iface) == EFI_SUCCESS && *iface)
    image = FvImage(bs, handles[0], guid);
  bs->FreePool(handles);
  return image;
}

static BOOLEAN PhysicalButton(EFI_SYSTEM_TABLE *st) {
  EFI_DEVICE_PATH_PROTOCOL *path = &ButtonPath.vendor.Header;
  EFI_HANDLE simple = NULL, extended = NULL;
  EFI_BOOT_SERVICES *bs = st->BootServices;
  if (bs->LocateDevicePath(&TextInGuid, &path, &simple) != EFI_SUCCESS ||
      path != &ButtonPath.end || !simple || simple == st->ConsoleInHandle ||
      !FvImage(bs, simple, &ButtonFfs)) return FALSE;
  path = &ButtonPath.vendor.Header;
  return bs->LocateDevicePath(&TextInExGuid, &path, &extended) == EFI_SUCCESS &&
         path == &ButtonPath.end && simple == extended;
}

static EFI_STATUS Print(EFI_SYSTEM_TABLE *st, const CHAR16 *text) {
  return st->ConOut->OutputString(st->ConOut, (CHAR16 *)text);
}

static EFI_STATUS Deny(EFI_SYSTEM_TABLE *st, const CHAR16 *reason) {
  Print(st, L"SB0-INPUT NO-GRANT REFUSED ");
  Print(st, reason);
  Print(st, L"\r\n");
  return EFI_ACCESS_DENIED;
}

EFI_STATUS EFIAPI EfiMain(EFI_HANDLE self, EFI_SYSTEM_TABLE *st) {
  (VOID)self;
  EFI_BOOT_SERVICES *bs = st->BootServices;
  if (!st->ConOut) return EFI_UNSUPPORTED;
  if (!PhysicalButton(st)) return Deny(st, L"BUTTON-HANDLE");

  PMIC_GPIO_R4 *gpio = NULL;
  EFI_LOADED_IMAGE_PROTOCOL *pmic = UniqueProtocol(bs, &PmicGpioGuid, &PmicFfs, (VOID **)&gpio);
  if (!pmic || pmic->ImageSize < 0x2f3f0 ||
      (UINTN)gpio != (UINTN)pmic->ImageBase + 0x2f3b0 ||
      gpio->revision != 0x30000 || (UINTN)gpio->irqStatus != (UINTN)pmic->ImageBase + 0x1b50)
    return Deny(st, L"PMIC-ABI");

  EFI_RNG_PROTOCOL *rng = NULL;
  UINT8 nonce[32];
  EFI_LOADED_IMAGE_PROTOCOL *random = UniqueProtocol(bs, &RngGuid, &RngFfs, (VOID **)&rng);
  if (!random || random->ImageSize < 0x80e8 ||
      (UINTN)rng != (UINTN)random->ImageBase + 0x80d8 ||
      (UINTN)rng->GetRNG != (UINTN)random->ImageBase + 0x1538 ||
      rng->GetRNG(rng, NULL, sizeof nonce, nonce) != EFI_SUCCESS)
    return Deny(st, L"RNG");
  UINT8 nonzero = 0;
  for (UINTN i = 0; i < sizeof nonce; ++i) nonzero |= nonce[i];
  if (!nonzero) return Deny(st, L"RNG-ZERO");

  static const CHAR16 hex[] = L"0123456789abcdef";
  CHAR16 line[67];
  for (UINTN i = 0; i < sizeof nonce; ++i) {
    line[i*2] = hex[nonce[i] >> 4];
    line[i*2+1] = hex[nonce[i] & 15];
  }
  line[64] = '\r'; line[65] = '\n'; line[66] = 0;
  if (Print(st, L"SB0-INPUT NO-GRANT BEGIN\r\n"
                L"TARGET LU0 LBA=57393401 BYTES=4096\r\n"
                L"W-OUTER " SB0_W_OUTER L"\r\n"
                L"SEED-ID " SB0_SEED_ID L"\r\n"
                L"PAYLOAD " SB0_PAYLOAD L"\r\n"
                L"ATTEMPT ") != EFI_SUCCESS ||
      Print(st, line) != EFI_SUCCESS ||
      Print(st, L"Leave VOL+ released until READY.\r\n") != EFI_SUCCESS)
    return EFI_DEVICE_ERROR;
  struct InputSession session = {InitialRelease, 0};
  for (UINTN sample = 0; sample < 1500; ++sample) {
    BOOLEAN raw = 0xff;
    // Exact r4 ButtonsDxe VOL+ call: PMIC index 1, GPIO index 5, type 0
    // (realtime); one read. Active-low, independent of either text queue.
    if (gpio->irqStatus(1, 5, 0, &raw) != EFI_SUCCESS || raw > 1)
      return Deny(st, L"GPIO-READ");
    enum InputStage prior = session.stage;
    InputSample(&session, raw == 0);
    if (session.stage == Refused) return Deny(st, L"HELD-AT-START");
    if (session.stage == FreshPress && prior == InitialRelease &&
        Print(st, L"READY; press and release VOL+ now.\r\n") != EFI_SUCCESS)
      return EFI_DEVICE_ERROR;
    if (session.stage == Observed) {
      if (Print(st, L"SB0-INPUT NO-GRANT RELEASE-PRESS-RELEASE ATTEMPT ") != EFI_SUCCESS)
        return EFI_DEVICE_ERROR;
      return Print(st, line);
    }
    if (bs->Stall(20000) != EFI_SUCCESS) return Deny(st, L"TIMER");
  }
  return Deny(st, L"TIMEOUT");
}
