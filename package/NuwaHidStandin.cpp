// SPDX-License-Identifier: BSD-2-Clause-Patent
// Software enumeration only; no reports, timers, hardware or event hooks.
#include "OriginalHidDeviceABI.h"
#include <IOKit/IOBufferMemoryDescriptor.h>
#include <IOKit/IOLib.h>
#include <IOKit/IOWorkLoop.h>
#include <libkern/c++/OSIterator.h>
#include <libkern/c++/OSKext.h>
#include <libkern/c++/OSSymbol.h>
#include <mach/kmod.h>
#include <pexpert/pexpert.h>

extern "C" {
extern kmod_info_t g_kernel_kmod_info;
kern_return_t OSKextLoadKextWithIdentifier(const char *);
void nuwa_hid_static_init() __asm__("__GLOBAL__sub_I_NuwaHidStandin.cpp");
volatile uint32_t native_touch_seq, native_touch_count, native_touch_hid_reports;
volatile int native_touch_xs[12], native_touch_ys[12], native_touch_ids[12];
void native_touch_set_sink(void (*)(void *), void *) {}
void native_buttons_set_sink(void (*)(void *, uint32_t), void *) {}
bool native_hid_input_requested() { return false; }
void native_hid_input_observed(unsigned stage, int result) {
    IOLog("NuwaHidStandin: stage=%u result=%#x\n", stage, result);
}
}

// Keyboard first, for the original generic keyboard personality. Keyboard
// and finger fields adapted from UniXNU/ShengHidInput@71a40e76 (same license).
static const uint8_t descriptor[] = {
    0x05,0x01,0x09,0x06,0xa1,0x01,0x85,0x01,
    0x05,0x07,0x19,0xe0,0x29,0xe7,0x15,0x00,0x25,0x01,
    0x75,0x01,0x95,0x08,0x81,0x02,0x75,0x08,0x95,0x01,0x81,0x03,
    0x19,0x00,0x29,0x65,0x15,0x00,0x25,0x65,
    0x75,0x08,0x95,0x06,0x81,0x00,0xc0,
    // Touch Screen application, one logical Finger and the Contact Count.
    0x05,0x0d,0x09,0x04,0xa1,0x01,0x85,0x03,
    0x09,0x22,0xa1,0x02,0x09,0x42,0x15,0x00,0x25,0x01,
    0x75,0x01,0x95,0x01,0x81,0x02,0x09,0x47,0x81,0x02,
    0x75,0x06,0x95,0x01,0x81,0x03,
    0x09,0x51,0x75,0x08,0x95,0x01,0x15,0x00,0x26,0xff,0x00,0x81,0x02,
    0x05,0x01,0x09,0x30,0x15,0x00,0x26,0xff,0x7f,0x75,0x10,0x95,0x01,
    0x81,0x02,0x09,0x31,0x81,0x02,0x05,0x0d,0xc0,
    0x09,0x54,0x75,0x08,0x95,0x01,0x15,0x00,0x25,0x01,0x81,0x02,0xc0
};

class NuwaHidStandin : public IOHIDDevice {
    OSDeclareDefaultStructors(NuwaHidStandin)
    IOWorkLoop *loop = nullptr;
public:
    bool init(OSDictionary *properties = nullptr) override {
        if (!IOHIDDevice::init(properties)) return false;
        loop = IOWorkLoop::workLoop();
        return loop && setProperty("HIDDefaultBehavior", true);
    }
    void free() override {
        OSSafeReleaseNULL(loop);
        IOHIDDevice::free();
    }
    IOWorkLoop *getWorkLoop() const override { return loop; }
    IOReturn newReportDescriptor(IOMemoryDescriptor **out) const override {
        *out = IOBufferMemoryDescriptor::withBytes(descriptor, sizeof(descriptor), kIODirectionNone);
        return *out ? kIOReturnSuccess : kIOReturnNoMemory;
    }
};
OSDefineMetaClassAndStructors(NuwaHidStandin, IOHIDDevice)

namespace {
bool classReady(const char *name, unsigned size = 0) {
    const OSSymbol *symbol = OSSymbol::withCString(name);
    if (!symbol) return false;
    const OSMetaClass *meta = OSMetaClass::getMetaClassWithName(symbol);
    symbol->release();
    return meta && (!size || meta->getClassSize() == size);
}

IOService *registeredChild(IOService *parent, const char *name) {
    OSIterator *it = parent->getChildIterator(gIOServicePlane);
    if (!it) return nullptr;
    IOService *found = nullptr;
    while (OSObject *child = it->getNextObject()) {
        IOService *service = OSDynamicCast(IOService, child);
        if (service && service->metaCast(name) && !service->isInactive() &&
            (service->getState() & kIOServiceRegisteredState)) {
            service->retain();
            found = service;
            break;
        }
    }
    it->release();
    return found;
}

bool publishDigitizer(IOService *service) {
    return service->setProperty("Built-In", true) &&
        service->setProperty("DisplayIntegrated", true) &&
        service->setProperty("PrimaryUsagePage", 0x0dULL, 32) &&
        service->setProperty("PrimaryUsage", 4ULL, 32);
}
}

extern "C" void native_hid_live_checkpoint(IOService *device) {
    // On the existing post-IOBSD thread, wait for this device's own matching
    // chain. Never change the candidate provider or its pre-match usage.
    for (unsigned i = 0; i < 500; ++i) {
        IOService *interface = registeredChild(device, "IOHIDInterface");
        if (interface) {
            IOService *driver = registeredChild(interface, "IOHIDEventDriver");
            if (driver) {
                bool published = publishDigitizer(driver) && publishDigitizer(interface);
                driver->release();
                interface->release();
                native_hid_input_observed(5, published ? kIOReturnSuccess : kIOReturnError);
                return;
            }
            interface->release();
        }
        IOSleep(10);
    }
    native_hid_input_observed(5, kIOReturnTimeout);
}

extern "C" void nuwa_hid_standin_probe() {
    unsigned enabled = 0;
    if (!PE_parse_boot_argn("nuwa-hid-standin", &enabled, sizeof(enabled)) || enabled != 1)
        return;
    kern_return_t status = OSKextLoadKextWithIdentifier("com.apple.iokit.IOHIDFamily");
    if (!status)
        status = OSKext::loadKextWithIdentifier("com.apple.iokit.IOHIDEventDriver",
            true, false, kOSKextExcludeNone, kOSKextExcludeNone, nullptr);
    if (status || !classReady("IOHIDDevice", sizeof(IOHIDDevice)) ||
        !classReady("IOHIDInterface") || !classReady("IOHIDEventDriver")) {
        native_hid_input_observed(1, status ? status : kIOReturnNotReady);
        return;
    }
    OSDictionary *match = IOService::serviceMatching("IOHIDResource");
    IOService *resource = match ? IOService::waitForMatchingService(match, 5000000000ULL) : nullptr;
    OSSafeReleaseNULL(match);
    if (!resource) { native_hid_input_observed(2, kIOReturnTimeout); return; }

    void *handle = OSMetaClass::preModLoad(g_kernel_kmod_info.name);
    if (!handle) {
        resource->release();
        native_hid_input_observed(3, kIOReturnError);
        return;
    }
    nuwa_hid_static_init();
    status = OSMetaClass::postModLoad(handle);
    if (status) {
        resource->release();
        native_hid_input_observed(3, status);
        return;
    }
    IOService *device = new NuwaHidStandin;
    bool attached = device && device->init() && device->attach(resource);
    bool started = attached && device->start(resource);
    if (!started) {
        if (attached) device->detach(resource);
        OSSafeReleaseNULL(device);
    }
    resource->release();
    native_hid_input_observed(4, started ? kIOReturnSuccess : kIOReturnError);
    // Keep the attachment for the diagnostic boot. Matching is not proof
    // that SpringBoard consumes this service.
    if (started) native_hid_live_checkpoint(device);
}
