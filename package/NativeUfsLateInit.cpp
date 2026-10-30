// Register the real fixed provider after IOStorageFamily. No personality/start.
#include <IOKit/IOService.h>
#include <IOKit/IOReturn.h>
#include <libkern/c++/OSSymbol.h>
#include <mach/kmod.h>
#ifndef NUWA_UFS_CLASS_SIZE
#error Production DWARF class sizes are required
#endif
#ifndef NUWA_UFS_BLOCK_CLASS_SIZE
#error Production DWARF block class size is required
#endif
extern "C" kmod_info_t g_kernel_kmod_info;
extern "C" OSReturn native_ufs_register_late(void);
extern "C" void ufs_static_init() __asm__("__GLOBAL__sub_I_NativeUfs.cpp");
extern const unsigned char storage_parent[] __asm__("__ZN20IOBlockStorageDevice10gMetaClassE");
extern const unsigned char ufs_meta[] __asm__("__ZN9NativeUfs10gMetaClassE");
extern const unsigned char block_meta[] __asm__("__ZN14NativeUfsBlock10gMetaClassE");
static unsigned state;
static OSReturn result = kIOReturnNotReady;

extern "C" OSReturn native_ufs_register_late()
{
    unsigned expected = 0;
    if (!__atomic_compare_exchange_n(&state, &expected, 1, false,
                                    __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE)) {
        return expected == 1 ? kIOReturnBusy : result;
    }
    const OSSymbol *parentName = OSSymbol::withCString("IOBlockStorageDevice");
    const OSSymbol *ufsName = OSSymbol::withCString("NativeUfs");
    const OSSymbol *blockName = OSSymbol::withCString("NativeUfsBlock");
    if (!parentName || !ufsName || !blockName) {
        result = kIOReturnNoMemory;
    } else {
        const OSMetaClass *parent = OSMetaClass::getMetaClassWithName(parentName);
        if (parent != reinterpret_cast<const OSMetaClass *>(storage_parent) || parent->getClassSize() != 0x90) {
            result = kIOReturnNotReady;
        } else if (OSMetaClass::getMetaClassWithName(ufsName) || OSMetaClass::getMetaClassWithName(blockName)) {
            result = kIOReturnExclusiveAccess;
        } else {
            void *handle = OSMetaClass::preModLoad(g_kernel_kmod_info.name);
            if (!handle) {
                result = kIOReturnNoResources;
            } else {
                ufs_static_init();
                result = OSMetaClass::postModLoad(handle);
                if (result == kOSReturnSuccess) {
                    const OSMetaClass *ufs = OSMetaClass::getMetaClassWithName(ufsName);
                    const OSMetaClass *block = OSMetaClass::getMetaClassWithName(blockName);
                    if (ufs != reinterpret_cast<const OSMetaClass *>(ufs_meta) ||
                        block != reinterpret_cast<const OSMetaClass *>(block_meta) ||
                        ufs->getSuperClass() != &IOService::gMetaClass || block->getSuperClass() != parent ||
                        ufs->getClassSize() != NUWA_UFS_CLASS_SIZE || block->getClassSize() != NUWA_UFS_BLOCK_CLASS_SIZE) {
                        result = kIOReturnError;
                    }
                }
            }
        }
    }
    if (blockName) blockName->release();
    if (ufsName) ufsName->release();
    if (parentName) parentName->release();
    __atomic_store_n(&state, result == kOSReturnSuccess ? 2 : 3, __ATOMIC_RELEASE);
    return result;
}
