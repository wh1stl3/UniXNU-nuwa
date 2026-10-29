// Offline integration candidate. Not selected by the production build.
// Caller must run on a sleepable boot thread AFTER original IOStorageFamily
// initialization, outside any preModLoad/postModLoad transaction. No unload.
#include <IOKit/IOReturn.h>
#include <libkern/c++/OSMetaClass.h>
#include <libkern/c++/OSSymbol.h>
#include <mach/kmod.h>

extern "C" kmod_info_t g_kernel_kmod_info;
extern "C" void ramblock_static_init() __asm__("__GLOBAL__sub_I_NativeRamBlock.cpp");
// Address-only declarations; the actual objects are concrete MetaClass subclasses.
extern const unsigned char ramblock_parent[] __asm__("__ZN20IOBlockStorageDevice10gMetaClassE");
extern const unsigned char ramblock_meta[] __asm__("__ZN14NativeRamBlock10gMetaClassE");

// 0: not attempted; 1: in progress; 2: registered; 3: failed permanently.
// A failed constructor/postModLoad must never be retried: iOS duplicates panic.
static unsigned state;
static OSReturn result = kIOReturnNotReady;

extern "C" OSReturn native_ramblock_register_late()
{
    unsigned expected = 0;
    if (!__atomic_compare_exchange_n(&state, &expected, 1, false,
                                    __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE)) {
        return expected == 1 ? kIOReturnBusy : result;
    }
    const OSSymbol *parentName = OSSymbol::withCString("IOBlockStorageDevice");
    const OSSymbol *childName = OSSymbol::withCString("NativeRamBlock");
    if (!parentName || !childName) {
        if (parentName) parentName->release();
        if (childName) childName->release();
        result = kIOReturnNoMemory;
        __atomic_store_n(&state, 3, __ATOMIC_RELEASE);
        return result;
    }
    const OSMetaClass *parent = OSMetaClass::getMetaClassWithName(parentName);
    const OSMetaClass *existing = OSMetaClass::getMetaClassWithName(childName);
    if (existing || parent != reinterpret_cast<const OSMetaClass *>(ramblock_parent) || parent->getClassSize() != 0x90) {
        result = existing ? kIOReturnExclusiveAccess : kIOReturnNotReady;
    } else {
        // The kernel OSKext identity must already exist. Never invent a kext ID.
        void *handle = OSMetaClass::preModLoad(g_kernel_kmod_info.name);
        if (!handle) {
            result = kIOReturnNoResources;
        } else {
            ramblock_static_init();
            result = OSMetaClass::postModLoad(handle);
            if (result == kOSReturnSuccess) {
                const OSMetaClass *registered = OSMetaClass::getMetaClassWithName(childName);
                if (registered != reinterpret_cast<const OSMetaClass *>(ramblock_meta) || registered->getSuperClass() != parent ||
                    registered->getClassSize() != 0x160) result = kIOReturnError;
            }
        }
    }
    childName->release();
    parentName->release();
    __atomic_store_n(&state, result == kOSReturnSuccess ? 2 : 3, __ATOMIC_RELEASE);
    return result;
}
