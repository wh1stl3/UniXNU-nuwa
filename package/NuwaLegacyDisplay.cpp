// SPDX-License-Identifier: BSD-2-Clause-Patent
// nuwa-only consumer of the unchanged original Legacy/IOSurface implementation.
//
// Shape follows UniXNU-enuma's board provider, out/enuma-gop-legacy-20261114-r2/
// package/EnumaLegacyDisplay.cpp (BSD-2-Clause-Patent): same probe/late-probe
// split, same failure-code order, same IOPlatformDevice nub over the firmware GOP
// range. Everything Apple-specific is nuwa's own input: no proxy-frame address,
// geometry or display class is copied from another board; geometry comes from
// PE_current_console() at run time.
//
// Two pieces of the base driver (UniXNU drivers/GopFramebuffer @ e47c1b8) are the
// reason this file exists:
//   * native_legacy_display_probe() / native_legacy_display_late_probe() are called
//     by patches/xnu/offline-component-load-probes.patch and
//     patches/xnu/offline-legacy-start.patch; the driver itself only supplies
//     native_legacy_display_allocate().
//   * kickOnce() calls native_legacy_prepare_scanout() before every validated
//     copy (NativeLegacyDisplay.cpp:592/626/669/687) and the base has no
//     definition for it. In this image the renderer owns the hand-off, so the
//     bridge below forwards to boot_progress_prepare_scanout().
//
// Not defined here on purpose: the IOSurface field readers
// (native_legacy_surface_descriptor/_width/_height/_stride/_allocation/_format/
// _planes), native_legacy_set_refresh_properties() and
// native_legacy_vsync_notify() are ABI-derived (original text entry points and
// IOSurface instance offsets) and belong to the display archive builder that
// generates OriginalLegacyFramebufferABI.h + original-bindings.S. The
// native_legacy_<counter> data symbols the diagnostic page reads stay owned by
// package/boot-progress-r13/nuwa_boot_progress_stubs.c (absolute 0) until that
// builder lands; defining them here too would be a duplicate symbol.
#include <IOKit/IOPlatformExpert.h>
#include <IOKit/IODeviceMemory.h>
#include <IOKit/IODeviceTreeSupport.h>
#include <IOKit/IOLib.h>
#include <IOKit/IOUserClient.h>
#include <libkern/c++/OSMetaClass.h>
#include <libkern/c++/OSData.h>
#include <pexpert/pexpert.h>
#include <console/video_console.h>
#include <mach/kmod.h>
#include <machine/machine_routines.h>
extern "C" {
extern kmod_info_t g_kernel_kmod_info;
kern_return_t OSKextLoadKextWithIdentifier(const char *);
void nuwa_legacy_static_init(void) __asm__("__GLOBAL__sub_I_NativeLegacyDisplay.cpp");
IOService *native_legacy_display_allocate(void); // Supplied by the component.
// Kernel side (out/nuwa-r34-20261119/BootProgress.c:983, r35 :1025):
//   int boot_progress_prepare_scanout(void)
// 1 = the diagnostic page yielded the panel (display_owned set, bound cleared,
// irreversible without the opt-in boot-diag-resume), 0 = a renderer pass was
// still running. Thread context only.
int boot_progress_prepare_scanout(void);
}
namespace {
IOService *displayObject, *displayNub;
// Same stage numbering as the enuma provider, so "refused stage=N reason=M"
// means the same thing on both boards: 1 early object created, 2 initialized,
// 3 late probe entered, 4 registered.
unsigned stage;
bool entered, lateEntered;
// PE_current_console() answers true on failure; the original code reads it that
// way (NativeLegacyDisplay.cpp:867). Same contract here.
bool console(PE_Video &v) {
  return !PE_current_console(&v) && v.v_baseAddr && v.v_width && v.v_height &&
      v.v_width <= 16384 && v.v_height <= 16384 && v.v_depth == 32 &&
      !v.v_rotate && v.v_display == 1 && v.v_rowBytes >= v.v_width * 4 &&
      v.v_rowBytes <= UINT64_MAX / v.v_height;
}
// offline-legacy-register=1 is both this probe's gate and the driver's
// registerService() gate (NativeLegacyDisplay.cpp:525-526); the same boot arg
// keeps the two halves from ever disagreeing.
bool enabled() {
  unsigned value = 0;
  return PE_parse_boot_argn("offline-legacy-register", &value, sizeof(value)) && value == 1;
}
void failure(unsigned code) {
  IOLog("NuwaLegacyDisplay: refused stage=%u reason=%u\n", stage, code);
}
}
extern "C" {
void native_legacy_display_probe(void) {
  // Both sites are the same bsd_autoconf boot thread; no new worker/lock domain.
  if (!enabled() || entered) return;
  entered = true;
  stage = 1;
  void *handle = OSMetaClass::preModLoad(g_kernel_kmod_info.name);
  if (!handle) { failure(1); return; }
  nuwa_legacy_static_init();
  if (OSMetaClass::postModLoad(handle)) { failure(2); return; }
  PE_Video v = {};
  if (!console(v)) { failure(3); return; }
  IOService *object = native_legacy_display_allocate();
  if (!object) { failure(4); return; }
  if (!object->metaCast("IOMobileFramebufferLegacy") || !object->init()) {
    object->release(); failure(5); return;
  }
  displayObject = object;
  stage = 2;
}
void native_legacy_display_late_probe(void) {
  if (!enabled() || lateEntered) return;
  lateEntered = true;
  // The early hook must have loaded IOMobileGraphicsFamily and initialized our
  // instance. Never initialize a subclass against an unloaded original base.
  if (!displayObject) { failure(6); return; }
  stage = 3;
  bool success = false, nubAttached = false, nubStarted = false, displayAttached = false;
  IOPlatformDevice *nub = nullptr;
  IODeviceMemory *memory = nullptr;
  OSArray *ranges = nullptr;
  IORegistryEntry *parentDT = nullptr;
  bool dtAttached = false;
  IOService *resource = IOService::getResourceService();
  PE_Video v = {};
  OSDictionary *matching = nullptr;
  IOService *surface = nullptr;
  if (OSKextLoadKextWithIdentifier("com.apple.iokit.IOSurface")) { failure(7); goto finish; }
  matching = IOService::nameMatching("IOCoreSurfaceRoot");
  surface = matching ? IOService::waitForMatchingService(matching, 5000000000ULL) : nullptr;
  if (!surface || !console(v)) { failure(8); goto finish; }
  nub = new IOPlatformDevice;
  memory = IODeviceMemory::withRange(v.v_baseAddr, v.v_rowBytes * v.v_height);
  ranges = OSArray::withCapacity(1);
  if (!nub || !memory || !ranges || !resource || !nub->init() || !ranges->setObject(memory)) {
    failure(9); goto finish;
  }
  nub->setName("NuwaGOPFramebuffer");
  nub->setDeviceMemory(ranges);
  if (!(nubAttached = nub->attach(resource)) || !(nubStarted = nub->start(resource))) {
    failure(10); goto finish;
  }
  parentDT = IORegistryEntry::fromPath("/arm-io", gIODTPlane);
  {
    const char type[] = "display-subsystem";
    OSData *property = OSData::withBytes(type, sizeof(type));
    bool set = property && nub->setProperty("device_type", property);
    OSSafeReleaseNULL(property);
    if (!parentDT || !set) { failure(11); goto finish; }
  }
  nub->setName("nuwa-gop-display", gIODTPlane);
  if (!(dtAttached = nub->attachToParent(parentDT, gIODTPlane)) ||
      !(displayAttached = displayObject->attach(nub))) { failure(12); goto finish; }
  {
    SInt32 score = 0;
    if (displayObject->probe(nub, &score) != displayObject || !displayObject->start(nub)) {
      failure(13); goto finish;
    }
  }
  // Original start and core startHardware already validated the mapped extent
  // (offline-legacy-gop=1 is that path's gate). registerService uses the core
  // guard and observer, not NGPPresent.
  displayNub = nub;
  displayObject->registerService();
  stage = 4;
  success = true;
finish:
  OSSafeReleaseNULL(surface);
  OSSafeReleaseNULL(matching);
  OSSafeReleaseNULL(ranges);
  OSSafeReleaseNULL(memory);
  OSSafeReleaseNULL(parentDT);
  if (!success) {
    // A failed start is responsible for its own start-time unwind. No stop() is
    // called on an object whose start never returned success.
    if (displayAttached) displayObject->detach(nub);
    OSSafeReleaseNULL(displayObject);
    if (dtAttached) {
      IORegistryEntry *parent = nub->getParentEntry(gIODTPlane);
      if (parent) nub->detachFromParent(parent, gIODTPlane);
    }
    if (nubStarted) nub->stop(resource);
    if (nubAttached) nub->detach(resource);
    OSSafeReleaseNULL(nub);
  }
  // Success intentionally retains both initial references for kernel lifetime.
}
bool native_legacy_gop_mapping_observed(IOService *object, IOMemoryMap *mapping, uint32_t width, uint32_t height) {
  PE_Video v = {};
  if (object != displayObject || !mapping || !console(v) || width != v.v_width ||
      height != v.v_height || !mapping->getVirtualAddress() ||
      mapping->getPhysicalAddress() != v.v_baseAddr ||
      mapping->getLength() != v.v_rowBytes * v.v_height) return false;
  return true; // The actual mapping is checked above; the mode is not hard-coded.
}
// The driver's only console-release point, called from kickOnce() with the
// family's pending swap already validated. A false return makes kickOnce drop
// the frame with kIOReturnNotReady; it must never be answered true on a guess.
// The renderer serializes itself and, on success, sets
// boot_progress_display_owned=1 with display.bound=0; from then on nothing
// repaints the page (the only way back is the opt-in boot-diag-resume=N).
bool native_legacy_prepare_scanout(void) {
  PE_Video v = {};
  if (!displayObject || !console(v)) return false;
  // boot_progress_prepare_scanout() CASes render_busy and paints one status
  // line; neither is legal from an interrupt context.
  if (ml_at_interrupt_context() || !ml_get_interrupts_enabled()) return false;
  return boot_progress_prepare_scanout() != 0;
}
// CPU-copy policy: refusing the GPU hand-off is not claiming a completed copy.
bool native_legacy_gpu_offer(void *, IOMemoryDescriptor *, uint64_t, uint32_t, uint32_t, uint32_t) { return false; }
void native_legacy_gpu_fallback_observed(int) {}
void native_legacy_registration_observed(IOService *) {}
void native_legacy_swap_stage(unsigned) {}
void native_legacy_client_enter(task_t, uint32_t) {}
void native_legacy_client_observed(IOReturn, IOUserClient *) {}
void native_legacy_pm_observed(unsigned, IOReturn, unsigned long) {}
void native_legacy_frame_observed(unsigned, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t) {}
void native_legacy_frame_colors_observed(const uint32_t *, const uint64_t *, uint64_t) {}
void native_legacy_swap_validation_observed(bool, unsigned, const void *, const void *) {}
void native_legacy_surface_rejected(uint64_t, uint64_t, uint32_t, uint32_t, uint64_t, uint64_t, uint64_t) {}
void native_legacy_transfer_observed(IOReturn, const void *, uint64_t) {}
void native_legacy_copy_timing_observed(uint64_t, uint64_t) {}
void native_legacy_retirement_observed(IOService *) {}
void native_legacy_vsync_observed(unsigned, unsigned) {}
__attribute__((noreturn)) void native_legacy_backend_guard(unsigned slot, void *, void *) {
  panic("NuwaLegacyDisplay: unqualified backend slot %u", slot);
}
}
