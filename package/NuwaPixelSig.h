/* SPDX-License-Identifier: BSD-2-Clause-Patent */
#ifndef NUWA_PIXEL_SIG_H
#define NUWA_PIXEL_SIG_H

#include <stdint.h>

#define NUWA_PIX_FIELDS(F) \
    F(uint32_t, bk) F(uint32_t, so) F(uint32_t, unk) F(uint32_t, chg) \
    F(uint32_t, w) F(uint32_t, h) F(uint64_t, st) F(uint32_t, fmt) \
    F(uint64_t, ticks) F(uint32_t, crc) F(uint32_t, nz) F(uint32_t, uc) \
    F(uint32_t, valid)

struct nuwa_pix {
#define NUWA_PIX_FIELD(type, name) type name;
    NUWA_PIX_FIELDS(NUWA_PIX_FIELD)
#undef NUWA_PIX_FIELD
};

struct nuwa_pix_state {
    uint32_t epoch;
    struct nuwa_pix last; /* so is also the last surface sample's ordinal. */
};

#ifdef __cplusplus
extern "C" {
#endif
extern struct nuwa_pix_state nuwa_pix_state;
#ifdef __cplusplus
}
#endif

static inline int nuwa_pix_read(const struct nuwa_pix_state *state, struct nuwa_pix *p)
{
    uint32_t epoch = __atomic_load_n(&state->epoch, __ATOMIC_ACQUIRE);
    if (epoch & 1) return 0;
#define NUWA_PIX_LOAD(type, name) p->name = __atomic_load_n(&state->last.name, __ATOMIC_RELAXED);
    NUWA_PIX_FIELDS(NUWA_PIX_LOAD)
#undef NUWA_PIX_LOAD
    __atomic_thread_fence(__ATOMIC_ACQUIRE);
    return __atomic_load_n(&state->epoch, __ATOMIC_RELAXED) == epoch;
}

/* Only the primary CPU swap kick writes. A panel read never spins. */
static inline void nuwa_pix_publish(struct nuwa_pix_state *state, const struct nuwa_pix *p)
{
    __atomic_add_fetch(&state->epoch, 1, __ATOMIC_ACQ_REL);
#define NUWA_PIX_STORE(type, name) __atomic_store_n(&state->last.name, p->name, __ATOMIC_RELAXED);
    NUWA_PIX_FIELDS(NUWA_PIX_STORE)
#undef NUWA_PIX_STORE
    __atomic_add_fetch(&state->epoch, 1, __ATOMIC_RELEASE);
}
#undef NUWA_PIX_FIELDS

static inline void nuwa_pix_blank(struct nuwa_pix_state *state)
{
    struct nuwa_pix p = state->last;
    ++p.bk;
    nuwa_pix_publish(state, &p);
}

static inline unsigned nuwa_pix_half(const uint8_t *p)
{
    unsigned bits = p[0] | ((unsigned)p[1] << 8);
    /* Treat signed zero alike and canonicalize NaNs. Retain source precision. */
    if (!(bits & 0x7fff)) return 0;
    return (bits & 0x7fff) > 0x7c00 ? 0x7e00 : bits;
}

static inline uint32_t nuwa_pix_crc_byte(uint32_t crc, unsigned byte)
{
    crc ^= byte;
    for (unsigned i = 0; i < 8; ++i)
        crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1)));
    return crc;
}

static inline void nuwa_pix_surface(struct nuwa_pix_state *state, const uint8_t *src,
    uint64_t bytes, uint32_t w, uint32_t h, uint64_t st, uint32_t fmt, uint32_t planes,
    uint64_t ticks)
{
    struct nuwa_pix prev = state->last, p = prev;
    ++p.so;
    p.w = w; p.h = h; p.st = st; p.fmt = fmt; p.ticks = ticks;
    p.crc = p.nz = p.uc = p.valid = 0;
    /* &BGA is not assumed linear on this CPU-only path. */
    unsigned bpp = planes ? 0 : fmt == 0x42475241 ? 4 : fmt == 0x52476841 ? 8 : 0;
    if (!bpp) {
        ++p.unk;
    } else if (src && w && h && st >= (uint64_t)w * bpp && h <= bytes / st) {
        unsigned cw = w < 16 ? w : 16, ch = h < 16 ? h : 16;
        unsigned x0 = (w - cw) / 2, y0 = (h - ch) / 2;
        uint64_t colors[64];
        uint32_t crc = UINT32_MAX;
        for (unsigned y = 0; y < ch; ++y) {
            const uint8_t *row = src + (y0 + y) * st + (uint64_t)x0 * bpp;
            for (unsigned x = 0; x < cw; ++x) {
                const uint8_t *pixel = row + x * bpp;
                unsigned r, g, b;
                if (bpp == 4) {
                    r = pixel[2]; g = pixel[1]; b = pixel[0];
                } else {
                    r = nuwa_pix_half(pixel); g = nuwa_pix_half(pixel + 2);
                    b = nuwa_pix_half(pixel + 4);
                }
                p.nz += (r && r != 0x7e00) || (g && g != 0x7e00) || (b && b != 0x7e00);
                uint64_t rgb = r | ((uint64_t)g << 16) | ((uint64_t)b << 32);
                for (unsigned i = 0; i < 3; ++i) {
                    unsigned channel = (unsigned)(rgb >> (16 * i));
                    crc = nuwa_pix_crc_byte(crc, channel & 255);
                    if (bpp == 8) crc = nuwa_pix_crc_byte(crc, (channel >> 8) & 255);
                }
                if (p.uc < 64) {
                    unsigned i = 0;
                    while (i < p.uc && colors[i] != rgb) ++i;
                    if (i == p.uc) colors[p.uc++] = rgb;
                }
            }
        }
        p.crc = ~crc;
        p.valid = 1;
        if (prev.valid && prev.w == w && prev.h == h && prev.st == st &&
            prev.fmt == fmt && prev.crc != p.crc) ++p.chg;
    }
    nuwa_pix_publish(state, &p);
}

#endif
