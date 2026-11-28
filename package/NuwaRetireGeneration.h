// SPDX-License-Identifier: BSD-2-Clause-Patent
// Diagnostic scalars only: no request ownership, notification or userland state.
#pragma once
#include <stdint.h>

extern "C" {
extern volatile uint32_t nuwa_rg_entered;
extern volatile uint32_t nuwa_rg_returned;
extern volatile uint32_t nuwa_rg_returned_generation;
}

static inline __attribute__((always_inline)) uint32_t nuwa_retire_entered(void) {
    // The entered count also allocates the latest generation, modulo 2^32.
    return __atomic_fetch_add(&nuwa_rg_entered, 1u, __ATOMIC_RELAXED) + 1u;
}

static inline __attribute__((always_inline)) void nuwa_retire_returned(uint32_t generation) {
    __atomic_store_n(&nuwa_rg_returned_generation, generation, __ATOMIC_RELAXED);
    __atomic_fetch_add(&nuwa_rg_returned, 1u, __ATOMIC_RELAXED);
}
