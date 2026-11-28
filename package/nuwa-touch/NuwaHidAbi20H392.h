// SPDX-License-Identifier: BSD-2-Clause-Patent
// Static donor evidence only; NOT a runtime-qualified or linkable ABI.
// iPhone10,3 iOS 16.7.16 20H392, decompressed kernelcache SHA-256:
// 2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221
// Re-extract and check instruction anchors, tables and getters:
//   sed -n '/^# BEGIN NUWA_HID_ABI_EXTRACT$/,/^# END NUWA_HID_ABI_EXTRACT$/p' \
//     docs/nuwa-touch-hid-abi-20261128.md | python3 -B
// Run at the device repository root under WSL with UniXNU at the path in the
// document. See that document for symbolic provenance, exact anchors and limits.
//
// "Verified" below means self-checked against this donor on the host; private
// kext method names are reconstructed, not exported donor symbols. Addresses
// are unslid donor VAs, not final prelink/runtime addresses. An independent
// verifier and deep_reviewer have not qualified this ABI.
#pragma once
#include <stdint.h>

// Verified: instance vptr addresses, excluding the two-word vtable header.
// Derived from C2 vptr stores and named metaclass initializers in the donor.
#define NUWA_HID20_DEVICE_VPTR  UINT64_C(0xfffffff006cbe2d0)
#define NUWA_HID20_SERVICE_VPTR UINT64_C(0xfffffff006cbfb20)
#define NUWA_HID20_DRIVER_VPTR  UINT64_C(0xfffffff006cc0770)
#define NUWA_HID20_EVENT_VPTR   UINT64_C(0xfffffff006cc1018)

// Verified donor targets; these are observations, not declarations to bind.
#define NUWA_HID20_DEVICE_HANDLE_REPORT_VA UINT64_C(0xfffffff00572a730)
#define NUWA_HID20_DEVICE_SET_PROPERTY_VA  UINT64_C(0xfffffff00572a53c)
#define NUWA_HID20_DRIVER_SET_PROPERTIES_VA UINT64_C(0xfffffff005742d10)
#define NUWA_HID20_SERVICE_DISPATCH_VA    UINT64_C(0xfffffff00573bdcc)
#define NUWA_HID20_DRIVER_DISPATCH_VA     UINT64_C(0xfffffff005747ff8)
#define NUWA_HID20_DRIVER_INTERRUPT_REPORT_VA UINT64_C(0xfffffff0057444e8)
#define NUWA_HID20_DIGITIZER_REPORT_VA    UINT64_C(0xfffffff0057453dc)
#define NUWA_HID20_COLLECTION_REPORT_VA   UINT64_C(0xfffffff005746944)
#define NUWA_HID20_DIGITIZER_EVENT_VA     UINT64_C(0xfffffff00574969c)
#define NUWA_HID20_EVENT_APPEND_CHILD_VA  UINT64_C(0xfffffff00574a158)
#define NUWA_HID20_EVENT_GET_TYPE_VA      UINT64_C(0xfffffff00574a208)
#define NUWA_HID20_EVENT_GET_INTEGER_VA   UINT64_C(0xfffffff00574a230)
#define NUWA_HID20_EVENT_SET_INTEGER_VA   UINT64_C(0xfffffff00574c09c)
#define NUWA_HID20_EVENT_GET_FIXED_VA     UINT64_C(0xfffffff00574b620)

enum {
    // Verified: 8-byte virtual slots, indexed from the instance vptr.
    NUWA_HID20_DEVICE_SLOTS = 207,
    NUWA_HID20_SERVICE_SLOTS = 218,
    NUWA_HID20_DRIVER_SLOTS = 219,
    NUWA_HID20_EVENT_SLOTS = 37,
    NUWA_HID20_DEVICE_NEW_REPORT_DESCRIPTOR_SLOT = 180, // pure virtual
    NUWA_HID20_DEVICE_HANDLE_REPORT_SLOT = 181,
    NUWA_HID20_DEVICE_TIMESTAMPED_REPORT_SLOT = 197,
    NUWA_HID20_SET_PROPERTY_SYMBOL_OBJECT_SLOT = 23,
    NUWA_HID20_SET_PROPERTY_CSTRING_BOOL_SLOT = 27,
    NUWA_HID20_DRIVER_SET_PROPERTIES_SLOT = 44, // setProperties, not setProperty
    NUWA_HID20_SERVICE_DISPATCH_SLOT = 198,
    NUWA_HID20_DRIVER_INTERRUPT_REPORT_SLOT = 218,
    NUWA_HID20_EVENT_APPEND_CHILD_SLOT = 15,
    NUWA_HID20_EVENT_GET_TYPE_SLOT = 18,
    NUWA_HID20_EVENT_GET_INTEGER_SLOT = 23,
    NUWA_HID20_EVENT_SET_INTEGER_SLOT = 24,
    NUWA_HID20_EVENT_GET_FIXED_SLOT = 25,

    // Verified: instance sizes and data pointers, in bytes.
    NUWA_HID20_DEVICE_SIZE = 0xd0,
    NUWA_HID20_SERVICE_SIZE = 0xc8,
    NUWA_HID20_DRIVER_SIZE = 0x108,
    NUWA_HID20_EVENT_SIZE = 0x50,
    NUWA_HID20_DRIVER_PRIVATE_POINTER = 0x100,
    NUWA_HID20_DRIVER_PRIVATE_COLLECTION_FLAG = 0x69,
    NUWA_HID20_EVENT_DATA_POINTER = 0x10,
    NUWA_HID20_EVENT_CHILDREN_POINTER = 0x18,

    // Verified getter paths plus donor digitizer-event constructor stores.
    // These offsets are relative to *EVENT_DATA_POINTER, NOT the IOHIDEvent.
    NUWA_HID20_DIGITIZER_OPTIONS = 0x08,
    NUWA_HID20_DIGITIZER_X = 0x10,
    NUWA_HID20_DIGITIZER_Y = 0x14,
    NUWA_HID20_DIGITIZER_INDEX = 0x1c,
    NUWA_HID20_DIGITIZER_TYPE = 0x20,
    NUWA_HID20_DIGITIZER_IDENTITY = 0x24,
    NUWA_HID20_DIGITIZER_EVENT_MASK = 0x28,
    NUWA_HID20_DIGITIZER_PRESSURE = 0x34,
    NUWA_HID20_DIGITIZER_TOUCH_OPTIONS_BIT = 17,
};

// Inferred; do not use as a qualified touch ABI:
// - Contact Identifier report field -> digitizer index/identity mapping:
//   UNKNOWN. Trace 20H392 element parsing through the transducer path.
// - Exact method prototypes, all inherited NativeHidInput overrides and
//   metaclass/prelink relocations: UNKNOWN until target-TU/link qualification.
// - Report 3's ten-contact behavior and backboardd consumption: UNKNOWN until
//   the real 20H392 descriptor/matching path is exercised.
// - Safe per-instance vtable replacement, ownership and synchronization:
//   UNKNOWN; the upstream edge wrapper must not be enabled on this evidence.
