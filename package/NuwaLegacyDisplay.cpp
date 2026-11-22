// SPDX-License-Identifier: BSD-2-Clause-Patent
// nuwa-only consumer of the unchanged original Legacy/IOSurface implementation.
//
// Shape follows UniXNU-enuma's board provider, out/enuma-gop-legacy-20261114-r2/
// package/EnumaLegacyDisplay.cpp (BSD-2-Clause-Patent): same probe/late-probe
// split, same failure-code order, an IOService nub over the firmware GOP
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
// _planes) are ABI-derived and emitted by the host display archive builder.
// The host TU publishes the refresh fallback from startHardware; the vsync
// sender remains unresolved. The native_legacy_<counter> data symbols the
// diagnostic page reads stay owned by
// package/boot-progress-r13/nuwa_boot_progress_stubs.c (absolute 0) until that
// builder lands; defining them here too would be a duplicate symbol.
#include <IOKit/IOPlatformExpert.h>
#include <IOKit/IODeviceMemory.h>
#include <IOKit/IODeviceTreeSupport.h>
#include <IOKit/IOLib.h>
#include <IOKit/IOUserClient.h>
#include <libkern/c++/OSMetaClass.h>
#include <libkern/c++/OSData.h>
#include <libkern/c++/OSBoolean.h>
#include <pexpert/pexpert.h>
#include <console/video_console.h>
#include <mach/kmod.h>
#include <machine/machine_routines.h>
#include <kern/task.h>
extern "C" {
void proc_selfname(char *, int);
int pid_from_task(task_t);
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
#if defined(NUWA_DISPLAY_BRINGUP_DIAG)
void boot_progress_diag_set(uint8_t stage, uint8_t reason);
void boot_progress_prop_set(uint16_t properties);
#endif
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
#if defined(NUWA_DISPLAY_BRINGUP_DIAG)
  // At stage 1, missing displayObject at the late hook is a consequence
  // of an already recorded early failure. Keep the original reason.
  if (code != 6 || stage != 1) boot_progress_diag_set(stage, code);
#endif
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
#if defined(NUWA_DISPLAY_BRINGUP_DIAG)
  boot_progress_diag_set(stage, 0);
#endif
}
void native_legacy_display_late_probe(void) {
  if (!enabled() || lateEntered) return;
  lateEntered = true;
  // The early hook must have loaded IOMobileGraphicsFamily and initialized our
  // instance. Never initialize a subclass against an unloaded original base.
  if (!displayObject) { failure(6); return; }
  stage = 3;
#if defined(NUWA_DISPLAY_BRINGUP_DIAG)
  bool propertyReadbackFailed = false;
#endif
  bool success = false, nubAttached = false, nubStarted = false, displayAttached = false;
  IOService *nub = nullptr;
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
  nub = new IOService;
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
  {
    // Match the provider's ADT u32 byte representation consumed by IOMFB.
    uint32_t width = (uint32_t)v.v_width, height = (uint32_t)v.v_height;
    uint8_t widthLE[] = { (uint8_t)width, (uint8_t)(width >> 8),
                          (uint8_t)(width >> 16), (uint8_t)(width >> 24) };
    uint8_t heightLE[] = { (uint8_t)height, (uint8_t)(height >> 8),
                           (uint8_t)(height >> 16), (uint8_t)(height >> 24) };
    OSData *w = OSData::withBytes(widthLE, sizeof(widthLE));
    OSData *h = OSData::withBytes(heightLE, sizeof(heightLE));
    bool set = w && h && nub->setProperty("canvas-width", w) &&
        nub->setProperty("canvas-height", h);
    OSSafeReleaseNULL(w);
    OSSafeReleaseNULL(h);
    if (!set) { failure(14); goto finish; }
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
  if (!displayObject->setProperty("NormalModeEnable", kOSBooleanTrue) ||
      !displayObject->setProperty("ADCLLoadAll", kOSBooleanFalse)) {
    failure(15); goto finish;
  }
#if defined(NUWA_DISPLAY_BRINGUP_DIAG)
  {
    const auto *normal = displayObject->getProperty("NormalModeEnable");
    const auto *adcl = displayObject->getProperty("ADCLLoadAll");
    // OSBoolean consists of two canonical singleton instances.
    propertyReadbackFailed = (normal != kOSBooleanTrue && normal != kOSBooleanFalse) ||
                             (adcl != kOSBooleanTrue && adcl != kOSBooleanFalse);
    if (propertyReadbackFailed) boot_progress_diag_set(stage, 16);
  }
#endif
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
#if defined(NUWA_DISPLAY_BRINGUP_DIAG)
  {
    uint16_t properties = 0;
    OSObject *width = nub->getProperty("canvas-width");
    if (width) properties |= 1u << 0;
    if (nub->getProperty("canvas-height")) properties |= 1u << 1;
    if (nub->getProperty("device_type")) properties |= 1u << 2;
    if (displayObject->getProperty("IOMFBNumLayers")) properties |= 1u << 3;
    OSObject *refresh = displayObject->getProperty("IOMFBDisplayRefresh");
    if (refresh) properties |= 1u << 4;
    if (displayObject->getProperty("NormalModeEnable")) properties |= 1u << 5;
    if (displayObject->getProperty("ADCLLoadAll")) properties |= 1u << 6;
    if (displayObject->getProperty("IOFBRotation")) properties |= 1u << 7;
    if (refresh && !OSDynamicCast(OSDictionary, refresh)) properties |= 1u << 8;
    OSData *widthData = OSDynamicCast(OSData, width);
    if (widthData && widthData->getLength() != 4) properties |= 1u << 9;
    boot_progress_prop_set(properties);
  }
  boot_progress_diag_set(stage, propertyReadbackFailed ? 16 : 0);
#endif
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
#if !defined(NUWA_DISPLAY_HOST_CPU_ONLY)
bool native_legacy_gpu_offer(void *, IOMemoryDescriptor *, uint64_t, uint32_t, uint32_t, uint32_t) { return false; }
void native_legacy_gpu_fallback_observed(int) {}
#endif
void native_legacy_registration_observed(IOService *) {}
void native_legacy_swap_stage(unsigned) {}
// High word is the count, low word is the latest independent value. CAS
// permits overlapping callers without a lock or a fabricated enter/exit pair.
uint64_t nuwa_cli_enter;
uint64_t nuwa_cli_observed;
// Low bits: backboardd seen, unavailable seen. High word: lookups in flight.
uint64_t nuwa_cli_identity;
uint32_t nuwa_cli_pid;
void native_legacy_client_enter(task_t task, uint32_t type) {
  __atomic_fetch_add(&nuwa_cli_identity, 1ULL << 32, __ATOMIC_RELAXED);
  __atomic_store_n(&nuwa_cli_pid, (uint32_t)pid_from_task(task), __ATOMIC_RELAXED);
  char name[64] = {};
  uint64_t flag = 0;
  if (task == current_task()) {
    proc_selfname(name, sizeof(name));
    if (!name[0]) flag = 2;
    else if (!strcmp(name, "backboardd")) flag = 1;
  } else flag = 2;
  if (flag) __atomic_fetch_or(&nuwa_cli_identity, flag, __ATOMIC_RELAXED);
  __atomic_fetch_sub(&nuwa_cli_identity, 1ULL << 32, __ATOMIC_RELAXED);
  uint64_t old = __atomic_load_n(&nuwa_cli_enter, __ATOMIC_RELAXED);
  uint64_t next;
  do {
    next = ((uint64_t)((uint32_t)(old >> 32) + 1) << 32) | type;
  } while (!__atomic_compare_exchange_n(&nuwa_cli_enter, &old, next, false,
                                        __ATOMIC_RELAXED, __ATOMIC_RELAXED));
}
void native_legacy_client_observed(IOReturn result, IOUserClient *) {
  uint64_t old = __atomic_load_n(&nuwa_cli_observed, __ATOMIC_RELAXED);
  uint64_t next;
  do {
    next = ((uint64_t)((uint32_t)(old >> 32) + 1) << 32) | (uint32_t)result;
  } while (!__atomic_compare_exchange_n(&nuwa_cli_observed, &old, next, false,
                                        __ATOMIC_RELAXED, __ATOMIC_RELAXED));
}
void native_legacy_pm_observed(unsigned, IOReturn, unsigned long) {}
void native_legacy_frame_observed(unsigned, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t) {}
void native_legacy_frame_colors_observed(const uint32_t *, const uint64_t *, uint64_t) {}
void native_legacy_swap_validation_observed(bool, unsigned, const void *, const void *) {}
void native_legacy_surface_rejected(uint64_t, uint64_t, uint32_t, uint32_t, uint64_t, uint64_t, uint64_t) {}
void native_legacy_transfer_observed(IOReturn, const void *, uint64_t) {}
void native_legacy_copy_timing_observed(uint64_t, uint64_t) {}
void native_legacy_retirement_observed(IOService *) {}
#if !defined(NUWA_DISPLAY_HOST_NO_SOFTWARE_VSYNC)
void native_legacy_vsync_observed(unsigned, unsigned) {}
#endif
__attribute__((noreturn)) void native_legacy_backend_guard(unsigned slot, void *, void *) {
  panic("NuwaLegacyDisplay: unqualified backend slot %u", slot);
}
}
