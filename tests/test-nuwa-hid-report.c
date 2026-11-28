// SPDX-License-Identifier: BSD-2-Clause-Patent
// Host-only descriptor/encoder checks; no IOHIDFamily or hardware involved.
#include "NuwaHidReport.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { \
    fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #x); exit(1); \
} } while (0)

struct field {
    unsigned bit, size, count, page, usage, flags, minimum, maximum;
};

// Parse the HID short items independently of the encoder's layout constants.
static void test_descriptor(void) {
    struct field fields[71];
    unsigned nfields = 0, bit = 8, page = 0, usage = 0, has_usage = 0;
    unsigned minimum = 0, maximum = 0, size = 0, count = 0, report_id = 0;
    unsigned depth = 0, fingers = 0;
    size_t at = 0;

    while (at < nuwa_hid_report_descriptor_length) {
        unsigned prefix = nuwa_hid_report_descriptor[at++];
        CHECK(prefix != 0xfe);
        unsigned bytes = prefix & 3u;
        if (bytes == 3) bytes = 4;
        CHECK(at + bytes <= nuwa_hid_report_descriptor_length);
        unsigned value = 0;
        for (unsigned i = 0; i < bytes; ++i)
            value |= (unsigned)nuwa_hid_report_descriptor[at++] << (8 * i);
        unsigned type = (prefix >> 2) & 3u, tag = prefix >> 4;
        if (type == 1) {
            switch (tag) {
            case 0: page = value; break;
            case 1: minimum = value; break;
            case 2: maximum = value; break;
            case 7: size = value; break;
            case 8: CHECK(!report_id); report_id = value; break;
            case 9: count = value; break;
            default: CHECK(0);
            }
        } else if (type == 2) {
            CHECK(tag == 0 && !has_usage);
            usage = value;
            has_usage = 1;
        } else {
            CHECK(type == 0);
            if (tag == 10) {
                CHECK(has_usage && page == 0x0d);
                if (!depth) CHECK(usage == 4 && value == 1);
                else {
                    CHECK(depth == 1 && usage == 0x22 && value == 2);
                    ++fingers;
                }
                ++depth;
            } else if (tag == 12) {
                CHECK(depth);
                --depth;
            } else {
                CHECK(tag == 8 && report_id == 3 && nfields < 71);
                CHECK(depth == 2 || (depth == 1 && has_usage && usage == 0x54));
                fields[nfields++] = (struct field){
                    bit, size, count, page, has_usage ? usage : 0,
                    value, minimum, maximum
                };
                bit += size * count;
            }
            usage = 0;
            has_usage = 0;
        }
    }
    CHECK(depth == 0 && fingers == 10 && nfields == 71);
    CHECK(bit == 72 * 8 && NUWA_HID_REPORT_BYTES == 72);
    const unsigned sizes[] = {1, 1, 6, 8, 16, 16, 8};
    const unsigned offsets[] = {0, 1, 2, 8, 16, 32, 48};
    const unsigned pages[] = {0x0d, 0x0d, 0x0d, 0x0d, 1, 1, 0x0d};
    const unsigned usages[] = {0x42, 0x47, 0, 0x51, 0x30, 0x31, 0x30};
    const unsigned maxima[] = {1, 1, 1, 255, 32767, 32767, 255};
    for (unsigned i = 0; i < 10; ++i) {
        for (unsigned j = 0; j < 7; ++j) {
            const struct field *f = &fields[i * 7 + j];
            CHECK(f->bit == 8 + i * 56 + offsets[j]);
            CHECK(f->size == sizes[j] && f->count == 1);
            CHECK(f->page == pages[j] && f->usage == usages[j]);
            CHECK(f->minimum == 0 && f->maximum == maxima[j]);
            CHECK(f->flags == (j == 2 ? 3u : 2u));
        }
    }
    const struct field *last = &fields[70];
    CHECK(last->bit == 568 && last->size == 8 && last->count == 1);
    CHECK(last->page == 0x0d && last->usage == 0x54 && last->flags == 2);
    CHECK(last->minimum == 0 && last->maximum == 10);
}

static void check_finger(const uint8_t *report, unsigned slot, uint8_t flags,
                         uint8_t id, uint16_t x, uint16_t y, uint8_t pressure) {
    const uint8_t *p = report + 1 + slot * 7;
    CHECK(p[0] == flags && p[1] == id);
    CHECK(p[2] == (uint8_t)x && p[3] == (uint8_t)(x >> 8));
    CHECK(p[4] == (uint8_t)y && p[5] == (uint8_t)(y >> 8));
    CHECK(p[6] == pressure);
}

static void check_tail(const uint8_t *report, unsigned used) {
    CHECK(report[0] == 3 && report[71] == used);
    for (unsigned i = 1 + used * 7; i < 71; ++i) CHECK(report[i] == 0);
}

static void encode(struct nuwa_hid_report_state *state,
                   const struct nuwa_hid_contact *contacts, size_t count,
                   uint8_t *out) {
    memset(out, 0xa5, NUWA_HID_REPORT_BYTES);
    CHECK(nuwa_hid_encode_report(state, contacts, count, out,
                                 NUWA_HID_REPORT_BYTES) == NUWA_HID_REPORT_OK);
}

static void test_single_move_lift_reuse(void) {
    struct nuwa_hid_report_state state = {0};
    uint8_t out[NUWA_HID_REPORT_BYTES];
    struct nuwa_hid_contact c = {0, 31999, 0xa7, 1, 0x34};
    encode(&state, &c, 1, out);
    uint8_t golden[72] = {3, 3, 0xa7, 0, 0, 0xff, 0x7f, 0x34};
    golden[71] = 1;
    CHECK(!memcmp(out, golden, sizeof golden));

    c.x = 14399; c.y = 0; c.pressure = 0xa4;
    encode(&state, &c, 1, out);
    check_finger(out, 0, 3, 0xa7, 32767, 0, 0xa4);
    check_tail(out, 1);

    c.x = 7200; c.y = 16000; c.tip = 0; c.pressure = 0xff;
    encode(&state, &c, 1, out);
    check_finger(out, 0, 2, 0xa7, 16384, 16384, 0);
    check_tail(out, 1);
    CHECK(state.active_count == 0);
    encode(&state, NULL, 0, out);
    check_tail(out, 0);

    c.tip = 1; c.pressure = 0x55;
    encode(&state, &c, 1, out); // same report ID is a new contact
    check_finger(out, 0, 3, 0xa7, 16384, 16384, 0x55);
    check_tail(out, 1);
    encode(&state, NULL, 0, out); // omitted ID gets one explicit lift
    check_finger(out, 0, 2, 0xa7, 16384, 16384, 0);
    check_tail(out, 1);
    encode(&state, NULL, 0, out);
    check_tail(out, 0);
}

static void test_two_alternating(void) {
    struct nuwa_hid_report_state state = {0};
    uint8_t out[NUWA_HID_REPORT_BYTES];
    struct nuwa_hid_contact c[] = {
        {14399, 0, 128, 1, 9}, {0, 31999, 5, 1, 11}
    };
    encode(&state, c, 1, out);
    check_finger(out, 0, 3, 128, 32767, 0, 9);
    check_tail(out, 1);
    encode(&state, c, 2, out);
    check_finger(out, 0, 3, 128, 32767, 0, 9);
    check_finger(out, 1, 3, 5, 0, 32767, 11);
    check_tail(out, 2);

    struct nuwa_hid_contact reversed[] = {c[1], c[0]};
    encode(&state, reversed, 2, out);
    check_finger(out, 0, 3, 5, 0, 32767, 11);
    check_finger(out, 1, 3, 128, 32767, 0, 9);
    check_tail(out, 2);
    encode(&state, reversed, 1, out);
    check_finger(out, 0, 3, 5, 0, 32767, 11);
    check_finger(out, 1, 2, 128, 32767, 0, 0);
    check_tail(out, 2);
    reversed[0].tip = 0;
    encode(&state, reversed, 1, out);
    check_finger(out, 0, 2, 5, 0, 32767, 0);
    check_tail(out, 1);
    encode(&state, NULL, 0, out);
    check_tail(out, 0);
}

static void test_boundaries(void) {
    struct nuwa_hid_report_state state = {0};
    uint8_t out[NUWA_HID_REPORT_BYTES];
    struct nuwa_hid_contact c = {1, 1, 255, 1, 255};
    encode(&state, &c, 1, out);
    check_finger(out, 0, 3, 255, 2, 1, 255);
    c.x = 7199; c.y = 15999;
    encode(&state, &c, 1, out);
    check_finger(out, 0, 3, 255, 16382, 16382, 255);
    c.x = 14398; c.y = 31998;
    encode(&state, &c, 1, out);
    check_finger(out, 0, 3, 255, 32764, 32765, 255);
    c.x = 65535; c.y = 65535;
    encode(&state, &c, 1, out);
    check_finger(out, 0, 3, 255, 32767, 32767, 255);
    check_tail(out, 1);
}

static void test_ten_and_split(void) {
    struct nuwa_hid_report_state state = {0}, before;
    uint8_t out[NUWA_HID_REPORT_BYTES], sentinel[NUWA_HID_REPORT_BYTES];
    struct nuwa_hid_contact c[10];
    for (unsigned i = 0; i < 10; ++i)
        c[i] = (struct nuwa_hid_contact){i & 1 ? 14399 : 0,
                                        i & 1 ? 0 : 31999, 240 - i, 1, i};
    encode(&state, c, 10, out);
    CHECK(state.active_count == 10 && out[71] == 10);
    for (unsigned i = 0; i < 10; ++i)
        check_finger(out, i, 3, 240 - i, i & 1 ? 32767 : 0,
                     i & 1 ? 0 : 32767, i);

    // Nine survivors and a new contact need eleven entries including a lift.
    struct nuwa_hid_contact replacement[10];
    memcpy(replacement, c, sizeof c);
    replacement[9].id = 12;
    before = state;
    memset(out, 0xa5, sizeof out);
    memcpy(sentinel, out, sizeof out);
    CHECK(nuwa_hid_encode_report(&state, replacement, 10, out, sizeof out)
          == NUWA_HID_REPORT_NEEDS_SPLIT);
    CHECK(!memcmp(&state, &before, sizeof state));
    CHECK(!memcmp(out, sentinel, sizeof out));

    c[9].tip = 0; // keep nine down, send the tenth's release first
    encode(&state, c, 10, out);
    check_finger(out, 9, 2, 231, 32767, 0, 0);
    CHECK(out[71] == 10 && state.active_count == 9);
    encode(&state, replacement, 10, out);
    check_finger(out, 9, 3, 12, 32767, 0, 9);
    CHECK(out[71] == 10 && state.active_count == 10);

    encode(&state, NULL, 0, out); // all ten disappear: ten releases fit
    CHECK(out[71] == 10 && state.active_count == 0);
    for (unsigned i = 0; i < 10; ++i)
        check_finger(out, i, 2, replacement[i].id,
                     i & 1 ? 32767 : 0, i & 1 ? 0 : 32767, 0);
    encode(&state, NULL, 0, out);
    check_tail(out, 0);
}

static void test_invalid_no_mutation(void) {
    struct nuwa_hid_report_state state = {0}, before;
    uint8_t out[NUWA_HID_REPORT_BYTES], sentinel[NUWA_HID_REPORT_BYTES];
    struct nuwa_hid_contact c[11] = {{0, 0, 1, 1, 3}, {0, 0, 1, 0, 0}};
    encode(&state, c, 1, out);
    before = state;
    memset(out, 0xa5, sizeof out);
    memcpy(sentinel, out, sizeof out);
    CHECK(nuwa_hid_encode_report(&state, c, 2, out, sizeof out) == NUWA_HID_REPORT_INVALID);
    CHECK(nuwa_hid_encode_report(&state, c, 11, out, sizeof out) == NUWA_HID_REPORT_INVALID);
    CHECK(nuwa_hid_encode_report(&state, NULL, 1, out, sizeof out) == NUWA_HID_REPORT_INVALID);
    CHECK(nuwa_hid_encode_report(&state, c, 1, out, sizeof out - 1) == NUWA_HID_REPORT_INVALID);
    c[0].tip = 2;
    CHECK(nuwa_hid_encode_report(&state, c, 1, out, sizeof out) == NUWA_HID_REPORT_INVALID);
    CHECK(!memcmp(&state, &before, sizeof state));
    CHECK(!memcmp(out, sentinel, sizeof out));
}

int main(void) {
    test_descriptor();
    test_single_move_lift_reuse();
    test_two_alternating();
    test_boundaries();
    test_ten_and_split();
    test_invalid_no_mutation();
    puts("nuwa HID report descriptor and encoder: self-check passed");
    return 0;
}
