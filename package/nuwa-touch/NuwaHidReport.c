// SPDX-License-Identifier: BSD-2-Clause-Patent
/*
 * Report 3 descriptor adapted from UniXNU/ShengHidInput,
 * NativeHidInput.cpp at 71a40e76daeae1bb4127546f96ffa7339c7a06ff.
 *
 * Copyright (c) 2026, NativeHidInput contributors. All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice,
 *    this list of conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 *
 * Subject to the terms and conditions of this license, each copyright holder
 * and contributor hereby grants to those receiving rights under this license
 * a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable
 * (except for failure to satisfy the conditions of this license) patent
 * license to make, have made, use, offer to sell, sell, import, and otherwise
 * transfer this software, where such license applies only to those patent
 * claims, already acquired or hereafter acquired, licensable by such copyright
 * holder or contributor that are necessarily infringed by:
 *
 * (a) their Contribution(s) (the licensed copyrights of copyright holders and
 *     non-copyrightable additions of contributors, in source or binary form)
 *     alone; or
 *
 * (b) combination of their Contribution(s) with the work of authorship to
 *     which such Contribution(s) was added by such copyright holder or
 *     contributor, if, at the time the Contribution is added, such addition
 *     causes such combination to be necessarily infringed. The patent license
 *     shall not apply to any other combinations which include the
 *     Contribution.
 *
 * Except as expressly stated above, no rights or licenses from any copyright
 * holder or contributor is granted under this license, whether expressly, by
 * implication, estoppel or otherwise.
 *
 * DISCLAIMER
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDERS OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

#include "NuwaHidReport.h"
#include "NuwaTouchBoard.h"

// One finger physical collection. The last input is the added Tip Pressure.
#define NUWA_FINGER_DESC \
    0x09, 0x22, 0xa1, 0x02, \
    0x09, 0x42, 0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x01, 0x81, 0x02, \
    0x09, 0x47, 0x81, 0x02, 0x75, 0x06, 0x95, 0x01, 0x81, 0x03, \
    0x09, 0x51, 0x75, 0x08, 0x95, 0x01, 0x15, 0x00, 0x26, 0xff, 0x00, 0x81, 0x02, \
    0x05, 0x01, 0x09, 0x30, 0x15, 0x00, 0x26, 0xff, 0x7f, 0x75, 0x10, 0x95, 0x01, 0x81, 0x02, \
    0x09, 0x31, 0x81, 0x02, \
    0x05, 0x0d, 0x09, 0x30, 0x15, 0x00, 0x26, 0xff, 0x00, 0x75, 0x08, 0x95, 0x01, 0x81, 0x02, \
    0xc0,

const uint8_t nuwa_hid_report_descriptor[] = {
    0x05, 0x0d, 0x09, 0x04, 0xa1, 0x01, 0x85, 0x03,
    NUWA_FINGER_DESC NUWA_FINGER_DESC NUWA_FINGER_DESC NUWA_FINGER_DESC NUWA_FINGER_DESC
    NUWA_FINGER_DESC NUWA_FINGER_DESC NUWA_FINGER_DESC NUWA_FINGER_DESC NUWA_FINGER_DESC
    0x09, 0x54, 0x75, 0x08, 0x95, 0x01, 0x15, 0x00, 0x25, 0x0a, 0x81, 0x02,
    0xc0,
};
const size_t nuwa_hid_report_descriptor_length = sizeof nuwa_hid_report_descriptor;

_Static_assert(NUWA_TOUCH_CONTACTS == NUWA_HID_MAX_CONTACTS, "contact count");
_Static_assert(NUWA_HID_REPORT_BYTES == 72, "report length");

static unsigned scale_coordinate(unsigned value, unsigned maximum) {
    if (value > maximum) value = maximum;
    return value * NUWA_HID_LOGICAL_MAX / maximum;
}

static void encode_finger(uint8_t *out, const struct nuwa_hid_contact *contact) {
    unsigned x = scale_coordinate(contact->x, NUWA_TOUCH_X_MAX);
    unsigned y = scale_coordinate(contact->y, NUWA_TOUCH_Y_MAX);
    out[0] = (uint8_t)(2u | contact->tip); // valid on down and lift
    out[1] = contact->id;
    out[2] = (uint8_t)x;
    out[3] = (uint8_t)(x >> 8);
    out[4] = (uint8_t)y;
    out[5] = (uint8_t)(y >> 8);
    out[6] = contact->tip ? contact->pressure : 0;
}

int nuwa_hid_encode_report(struct nuwa_hid_report_state *state,
                           const struct nuwa_hid_contact *contacts,
                           size_t contact_count, uint8_t *output,
                           size_t output_size) {
    size_t missing = 0;
    struct nuwa_hid_report_state next = {0};

    if (!state || !output || (contact_count && !contacts) ||
        contact_count > NUWA_HID_MAX_CONTACTS ||
        state->active_count > NUWA_HID_MAX_CONTACTS ||
        output_size < NUWA_HID_REPORT_BYTES) {
        return NUWA_HID_REPORT_INVALID;
    }
    for (size_t i = 0; i < contact_count; ++i) {
        if (contacts[i].tip > 1) return NUWA_HID_REPORT_INVALID;
        for (size_t j = 0; j < i; ++j) {
            if (contacts[i].id == contacts[j].id) return NUWA_HID_REPORT_INVALID;
        }
    }
    for (size_t i = 0; i < state->active_count; ++i) {
        size_t j = 0;
        while (j < contact_count && contacts[j].id != state->active[i].id) ++j;
        if (j == contact_count) ++missing;
    }
    if (contact_count + missing > NUWA_HID_MAX_CONTACTS) {
        return NUWA_HID_REPORT_NEEDS_SPLIT;
    }

    for (size_t i = 0; i < NUWA_HID_REPORT_BYTES; ++i) output[i] = 0;
    output[0] = NUWA_HID_REPORT_ID;
    size_t slot = 0;
    for (size_t i = 0; i < contact_count; ++i) {
        encode_finger(output + 1 + slot++ * NUWA_HID_FINGER_BYTES, &contacts[i]);
        if (contacts[i].tip) next.active[next.active_count++] = contacts[i];
    }
    for (size_t i = 0; i < state->active_count; ++i) {
        size_t j = 0;
        while (j < contact_count && contacts[j].id != state->active[i].id) ++j;
        if (j == contact_count) {
            struct nuwa_hid_contact lift = state->active[i];
            lift.tip = 0;
            encode_finger(output + 1 + slot++ * NUWA_HID_FINGER_BYTES, &lift);
        }
    }
    output[NUWA_HID_REPORT_BYTES - 1] = (uint8_t)slot;
    *state = next;
    return NUWA_HID_REPORT_OK;
}
