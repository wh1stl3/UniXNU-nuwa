// SPDX-License-Identifier: BSD-2-Clause-Patent
// Candidate register-read frame: no reset, event FIFO read or ICR write is
// explicitly requested; its chip-side effects on nuwa remain unverified.
#include "NuwaTouchProbe.h"

#define NUWA_TOUCH_BUSY (-16)
#define NUWA_TOUCH_POLL_LIMIT 10000u

static void append_text(char **p, const char *text) {
    while (*text) *(*p)++ = *text++;
}

static void append_unsigned(char **p, unsigned value) {
    char digits[10];
    unsigned n = 0;
    do {
        digits[n++] = (char)('0' + value % 10u);
        value /= 10u;
    } while (value);
    while (n) *(*p)++ = digits[--n];
}

static void report(const struct nuwa_touch_platform *platform,
                   const struct nuwa_touch_result *result) {
    static const char hex[] = "0123456789ABCDEF";
    char line[80];
    char *p = line;
    append_text(&p, "TP id=");
    if (result->id_valid) {
        for (unsigned i = 0; i < 2; ++i) {
            *p++ = hex[result->id[i] >> 4];
            *p++ = hex[result->id[i] & 15u];
        }
    } else {
        append_text(&p, "----");
    }
    append_text(&p, " st=");
    if (result->status < 0) {
        *p++ = '-';
        append_unsigned(&p, (unsigned)(-(int64_t)result->status));
    } else {
        append_unsigned(&p, (unsigned)result->status);
    }
    append_text(&p, " phase=");
    append_unsigned(&p, result->completed);
    *p++ = '/';
    append_unsigned(&p, result->requested);
    *p = '\0';
    platform->log_line(platform->ctx, line);
}

int nuwa_touch_probe_run(unsigned stage, const struct nuwa_touch_platform *platform,
                         struct nuwa_touch_result *result) {
    if (!result) return GENI_ERR_PARAM;
    *result = (struct nuwa_touch_result){0};
    result->requested = stage;
    if (stage == NUWA_TOUCH_DEFAULT_STAGE) return 0;
    if (!platform || !platform->log_line) {
        result->status = GENI_ERR_PARAM;
        return result->status;
    }

    int rc = GENI_ERR_PARAM;
    struct nuwa_touch_ready ready = {0};
    struct geni_spi spi = {0};
    if (stage > NUWA_TOUCH_STAGE_ID || !platform->confirm_ready ||
        !platform->se.rd || !platform->wrapper.rd ||
        (stage == NUWA_TOUCH_STAGE_ID &&
         (!platform->se.wr || !platform->se.delay_us))) goto done;

    rc = platform->confirm_ready(platform->ctx, &ready);
    if (rc) {
        if (rc > 0) rc = GENI_ERR_PARAM;
        goto done;
    }
    if (!ready.source_hz || ready.clock_select > 7u) {
        rc = GENI_ERR_PARAM;
        goto done;
    }

    spi.se = platform->se;
    spi.wrapper = platform->wrapper;
    rc = geni_spi_read_info(&spi);
    result->info = spi.info;
    if (rc) goto done;
    if (spi.info.protocol != GENI_PROTO_SPI) {
        rc = GENI_ERR_PROTO;
        goto done;
    }
    if (spi.info.fifo_disabled) {
        rc = GENI_ERR_NOTSUP;
        goto done;
    }
    if (spi.info.tx_fifo_depth < 4u || spi.info.fifo_width_bits != 32u) {
        rc = GENI_ERR_NODEV;
        goto done;
    }
    if (spi.info.geni_status & GENI_STATUS_M_ACTIVE) {
        rc = NUWA_TOUCH_BUSY;
        goto done;
    }
    // Do not change an engine already in DMA mode to make PIO possible.
    if (spi.se.rd(spi.se.ctx, SE_GENI_DMA_MODE_EN) & GENI_DMA_MODE_EN) {
        rc = GENI_ERR_NOTSUP;
        goto done;
    }
    result->completed = NUWA_TOUCH_STAGE_INFO;
    if (stage == NUWA_TOUCH_STAGE_INFO) {
        rc = 1;
        goto done;
    }

    // The private zeroed spi never opts into DMA or disabled-FIFO fallback.
    spi.poll_limit = NUWA_TOUCH_POLL_LIMIT;
    spi.poll_only = 1;
    rc = geni_spi_init(&spi);
    if (rc) goto done;
    rc = geni_spi_set_clock(&spi, NUWA_TOUCH_SPI_MAX_HZ, ready.source_hz,
                            ready.clock_select);
    if (rc) goto done;
    // The fts@0 DT node has neither spi-cpol nor spi-cpha: mode 0.
    rc = geni_spi_setup(&spi, 0, NUWA_TOUCH_SPI_CS);
    if (rc) goto done;
    {
        const uint8_t tx[8] = {0xfb, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
        uint8_t rx[8] = {0};
        rc = geni_spi_transfer(&spi, tx, rx, sizeof tx, 0);
        if (rc) goto done;
        result->id[0] = rx[6];
        result->id[1] = rx[7];
        result->id_valid = 1;
        result->completed = NUWA_TOUCH_STAGE_ID;
    }

done:
    result->status = rc;
    report(platform, result);
    return rc;
}
