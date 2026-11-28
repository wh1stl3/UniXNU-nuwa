// SPDX-License-Identifier: BSD-2-Clause-Patent
#ifndef NUWA_TOUCH_PROBE_H
#define NUWA_TOUCH_PROBE_H

#include <stdint.h>
#include "GeniSpi.h"
#include "NuwaTouchBoard.h"

#ifdef __cplusplus
extern "C" {
#endif

// Before either enabled stage, the actual resource owner must already hold
// exclusive ownership and maintain live readiness through the entire call.
// A zero return certifies both rails, all necessary clocks, active pinmux,
// released reset and the known source rate/selection under that ownership.
// Neither stage 1 nor probe MMIO can itself establish readiness or ownership;
// DT declarations and build-time flags are not live checks. If readiness is
// denied before probe MMIO, the provider and log callback must not use MMIO;
// buffer any diagnostic for later publication.
//
// If stage 2 may have made controller writes, the owner must retain exclusive
// ownership after return until quiescence and safe controller configuration
// are established; otherwise quarantine it. A timeout/error return does not
// prove cancellation or permit handoff. This probe implements neither that
// verification nor controller restoration.
struct nuwa_touch_ready {
    unsigned source_hz;
    unsigned clock_select;
};

struct nuwa_touch_platform {
    void *ctx;
    int (*confirm_ready)(void *ctx, struct nuwa_touch_ready *ready);
    struct geni_io se;
    struct geni_io wrapper;
    void (*log_line)(void *ctx, const char *line);
};

struct nuwa_touch_result {
    unsigned requested;
    unsigned completed;
    int status;                 // 1: info only, 0: transfer complete, <0: error
    int id_valid;               // raw bytes valid only if the transfer succeeded
    uint8_t id[2];
    struct geni_spi_info info;
};

// Each call performs at most one full-duplex transfer; another call may submit
// another transfer. There is no per-boot guard. Stage 0 does nothing.
// A log callback is mandatory for an enabled call; stage 2 also requires a
// real microsecond delay callback. No provider or caller is supplied here.
int nuwa_touch_probe_run(unsigned stage, const struct nuwa_touch_platform *platform,
                         struct nuwa_touch_result *result);

#ifdef __cplusplus
}
#endif
#endif
