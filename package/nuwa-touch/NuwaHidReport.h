// SPDX-License-Identifier: BSD-2-Clause-Patent
#ifndef NUWA_HID_REPORT_H
#define NUWA_HID_REPORT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
    NUWA_HID_REPORT_ID = 3,
    NUWA_HID_MAX_CONTACTS = 10,
    NUWA_HID_FINGER_BYTES = 7,
    NUWA_HID_REPORT_BYTES = 1 + NUWA_HID_MAX_CONTACTS * NUWA_HID_FINGER_BYTES + 1,
    NUWA_HID_LOGICAL_MAX = 32767,
};

struct nuwa_hid_contact {
    uint16_t x;
    uint16_t y;
    uint8_t id;
    uint8_t tip;       // 1 = down, 0 = explicit lift
    uint8_t pressure;  // caller-supplied logical value 0..255
};

// Zero-initialize before first use. Copyable for preparing an uncommitted
// candidate; do not share or mutate concurrently.
struct nuwa_hid_report_state {
    struct nuwa_hid_contact active[NUWA_HID_MAX_CONTACTS];
    size_t active_count;
};

enum {
    NUWA_HID_REPORT_OK = 0,
    NUWA_HID_REPORT_INVALID = -1,
    NUWA_HID_REPORT_NEEDS_SPLIT = -2,
};

extern const uint8_t nuwa_hid_report_descriptor[];
extern const size_t nuwa_hid_report_descriptor_length;

// contacts is the complete current down set plus any explicit tip=0 entries.
// Absent previous down IDs are appended once as tip=0 at their last position.
// Unique IDs and tip values 0/1 are required. A zero-count set may use NULL.
// Native x/y are clamped, then scaled to 0..32767 with truncation. Orientation
// is fixed: x->x, y->y, without rotation, inversion or swapping.
//
// On success writes exactly NUWA_HID_REPORT_BYTES and advances state. If the
// current entries and missing-ID releases exceed ten, NEEDS_SPLIT is returned;
// emit an intermediate complete set containing the necessary releases first.
// INVALID and NEEDS_SPLIT leave both state and output unchanged. Inputs, state
// and output must not overlap. The state reflects encoding, not delivery:
// an eventual sender must manage a separate candidate and completion policy.
int nuwa_hid_encode_report(struct nuwa_hid_report_state *state,
                           const struct nuwa_hid_contact *contacts,
                           size_t contact_count, uint8_t *output,
                           size_t output_size);

#ifdef __cplusplus
}
#endif
#endif
