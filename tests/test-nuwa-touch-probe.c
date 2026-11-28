// SPDX-License-Identifier: BSD-2-Clause-Patent
// Host-only register model; NuwaTouchProbe.c uses the real pinned GeniSpi.c.
#include "NuwaTouchProbe.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { \
    fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #x); exit(1); \
} } while (0)

struct model {
    uint32_t regs[0x1000 / 4];
    uint32_t wrapper_version;
    uint32_t rx_words[2];
    unsigned rx_count;
    uint32_t tx_words[2];
    unsigned tx_count;
    unsigned commands, reads, writes, forbidden_dma_writes, confirmations, logs;
    int ready_rc, behavior;
    int owner_held, quarantined, idle_verified, config_restored;
    unsigned source_hz, source_select;
    char log[80];
};

enum { FINISH, TIMEOUT, IO_ERROR };

static uint32_t read_se(void *ctx, uint32_t reg) {
    struct model *m = ctx;
    CHECK(m->owner_held);
    CHECK(reg < sizeof m->regs);
    ++m->reads;
    if (reg == SE_GENI_M_IRQ_STATUS && m->commands) {
        if (m->behavior == TIMEOUT) return 0;
        if (m->behavior == IO_ERROR) return GENI_M_CMD_OVERRUN;
        return GENI_M_CMD_DONE | GENI_M_RX_FIFO_LAST;
    }
    if (reg == SE_GENI_RX_FIFO_STATUS) return 2u - m->rx_count;
    if (reg == SE_GENI_RX_FIFOn) {
        CHECK(m->rx_count < 2u);
        return m->rx_words[m->rx_count++];
    }
    return m->regs[reg / 4];
}

static void write_se(void *ctx, uint32_t reg, uint32_t value) {
    struct model *m = ctx;
    CHECK(m->owner_held);
    CHECK(reg < sizeof m->regs);
    ++m->writes;
    if (reg == SE_DMA_TX_PTR_L || reg == SE_DMA_TX_PTR_H || reg == SE_DMA_TX_LEN ||
        reg == SE_DMA_RX_PTR_L || reg == SE_DMA_RX_PTR_H || reg == SE_DMA_RX_LEN ||
        reg == SE_DMA_TX_FSM_RST || reg == SE_DMA_RX_FSM_RST) {
        ++m->forbidden_dma_writes;
    }
    if (reg == SE_GENI_M_CMD0) {
        ++m->commands;
        m->tx_count = 0;
        m->rx_count = 0;
    }
    if (reg == SE_GENI_TX_FIFOn) {
        CHECK(m->tx_count < 2u);
        m->tx_words[m->tx_count++] = value;
    }
    m->regs[reg / 4] = value;
}

static uint32_t read_wrapper(void *ctx, uint32_t reg) {
    struct model *m = ctx;
    CHECK(m->owner_held);
    CHECK(reg == QUPV3_HW_VER_REG);
    ++m->reads;
    return m->wrapper_version;
}

static int confirm_ready(void *ctx, struct nuwa_touch_ready *ready) {
    struct model *m = ctx;
    ++m->confirmations;
    if (!m->owner_held || m->quarantined) return -16;
    ready->source_hz = m->source_hz;
    ready->clock_select = m->source_select;
    return m->ready_rc;
}

static void delay_us(void *ctx, unsigned us) {
    (void)ctx;
    CHECK(us == 1u);
}

static void log_line(void *ctx, const char *line) {
    struct model *m = ctx;
    ++m->logs;
    CHECK(snprintf(m->log, sizeof m->log, "%s", line) < (int)sizeof m->log);
}

static struct nuwa_touch_platform make(struct model *m) {
    memset(m, 0, sizeof *m);
    m->owner_held = 1;
    m->regs[GENI_FW_REVISION_RO / 4] = GENI_PROTO_SPI << GENI_FW_PROTO_SHIFT;
    m->regs[SE_HW_PARAM_0 / 4] = (32u << 24) | (16u << 16);
    m->wrapper_version = 0x40010000u;
    m->source_hz = 100000000u;
    m->rx_words[0] = 0x44332211u;
    m->rx_words[1] = 0x7ca56655u;
    struct nuwa_touch_platform platform = {
        m, confirm_ready, {m, read_se, write_se, delay_us},
        {m, read_wrapper, NULL, NULL}, log_line
    };
    return platform;
}

// A test-only owner model: these flags stand for external evidence; neither
// they nor this helper inspect or restore a real controller.
static int owner_release(struct model *m) {
    CHECK(m->owner_held);
    if (m->writes && (!m->idle_verified || !m->config_restored)) return -16;
    m->owner_held = 0;
    return 0;
}

static void check_failed_handoff(struct model *m, const struct nuwa_touch_platform *p) {
    struct nuwa_touch_result r;
    unsigned reads = m->reads, writes = m->writes, commands = m->commands;
    CHECK(m->owner_held && writes && commands == 1);
    m->quarantined = 1; // simulated caller policy, not implemented by the probe
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_ID, p, &r) == -16);
    CHECK(m->reads == reads && m->writes == writes && m->commands == commands);
    CHECK(owner_release(m) == -16 && m->owner_held);
    m->idle_verified = 1; // simulated separate evidence, not an MMIO read
    CHECK(owner_release(m) == -16 && m->owner_held);
    m->config_restored = 1; // simulated separate restoration evidence
    CHECK(owner_release(m) == 0 && !m->owner_held);
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_ID, p, &r) == -16);
    CHECK(m->reads == reads && m->writes == writes && m->commands == commands);
}

static void check_id(uint8_t first, uint8_t second) {
    struct model m;
    struct nuwa_touch_platform p = make(&m);
    struct nuwa_touch_result r;
    m.rx_words[1] = (uint32_t)first << 16 | (uint32_t)second << 24 | 0x6655u;
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_ID, &p, &r) == 0);
    CHECK(r.status == 0 && r.completed == 2 && r.id_valid);
    CHECK(r.id[0] == first && r.id[1] == second);
    CHECK(m.commands == 1 && m.tx_count == 2 && m.rx_count == 2);
    CHECK(m.tx_words[0] == 0x000020fbu && m.tx_words[1] == 0);
    CHECK(m.regs[SE_SPI_TX_TRANS_LEN / 4] == 8);
    CHECK(m.regs[SE_SPI_RX_TRANS_LEN / 4] == 8);
    CHECK(m.regs[SE_GENI_M_CMD0 / 4] == GENI_M_CMD_TX_RX << GENI_M_OPCODE_SHIFT);
    CHECK(m.regs[GENI_SER_M_CLK_CFG / 4] == (9u << GENI_CLK_DIV_SHIFT) + 1u);
    CHECK(!m.forbidden_dma_writes && m.logs == 1);
}

int main(void) {
    struct model m;
    struct nuwa_touch_platform p = make(&m);
    struct nuwa_touch_result r;
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_DEFAULT_STAGE, &p, &r) == 0);
    CHECK(!m.confirmations && !m.reads && !m.writes && !m.logs);
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_DEFAULT_STAGE, NULL, &r) == 0);
    CHECK(!m.confirmations && !m.reads && !m.writes && !m.logs);

    p = make(&m);
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_INFO, &p, &r) == 1);
    CHECK(r.completed == 1 && !r.id_valid && !m.writes && !m.commands);
    CHECK(!strcmp(m.log, "TP id=---- st=1 phase=1/1"));

    for (unsigned stage = NUWA_TOUCH_STAGE_INFO; stage <= NUWA_TOUCH_STAGE_ID; ++stage) {
        p = make(&m);
        m.ready_rc = -110;
        CHECK(nuwa_touch_probe_run(stage, &p, &r) == -110);
        CHECK(m.confirmations == 1 && m.logs == 1);
        CHECK(!m.reads && !m.writes && !m.commands && !r.id_valid);
    }
    CHECK(!strcmp(m.log, "TP id=---- st=-110 phase=0/2"));

    for (unsigned stage = NUWA_TOUCH_STAGE_INFO; stage <= NUWA_TOUCH_STAGE_ID; ++stage) {
        p = make(&m);
        m.owner_held = 0;
        CHECK(nuwa_touch_probe_run(stage, &p, &r) == -16);
        CHECK(m.confirmations == 1 && m.logs == 1);
        CHECK(!m.reads && !m.writes && !m.commands && !r.id_valid);
    }

    p = make(&m);
    p.confirm_ready = NULL;
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_ID, &p, &r) == GENI_ERR_PARAM);
    CHECK(!m.reads && !m.writes && !m.commands);

    p = make(&m);
    p.se.delay_us = NULL;
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_ID, &p, &r) == GENI_ERR_PARAM);
    CHECK(!m.reads && !m.writes && !m.commands);

    p = make(&m);
    m.source_hz = 0;
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_ID, &p, &r) == GENI_ERR_PARAM);
    CHECK(!m.reads && !m.writes && !m.commands);

    p = make(&m);
    m.regs[GENI_FW_REVISION_RO / 4] = 2u << GENI_FW_PROTO_SHIFT;
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_ID, &p, &r) == GENI_ERR_PROTO);
    CHECK(!m.writes && !m.commands);

    p = make(&m);
    m.regs[GENI_IF_DISABLE_RO / 4] = GENI_FIFO_IF_DISABLE;
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_ID, &p, &r) == GENI_ERR_NOTSUP);
    CHECK(!m.writes && !m.commands && !r.id_valid);
    CHECK(!strcmp(m.log, "TP id=---- st=-95 phase=0/2"));

    p = make(&m);
    m.regs[SE_GENI_DMA_MODE_EN / 4] = GENI_DMA_MODE_EN;
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_ID, &p, &r) == GENI_ERR_NOTSUP);
    CHECK(!m.writes && !m.commands);

    p = make(&m);
    m.regs[SE_GENI_STATUS / 4] = GENI_STATUS_M_ACTIVE;
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_ID, &p, &r) == -16);
    CHECK(!m.writes && !m.commands);

    p = make(&m);
    m.regs[SE_HW_PARAM_0 / 4] = (16u << 24) | (16u << 16);
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_ID, &p, &r) == GENI_ERR_NODEV);
    CHECK(!m.writes && !m.commands);

    p = make(&m);
    m.behavior = TIMEOUT;
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_ID, &p, &r) == GENI_ERR_TIMEOUT);
    CHECK(m.commands == 1 && !r.id_valid && !m.forbidden_dma_writes);
    CHECK(!strcmp(m.log, "TP id=---- st=-110 phase=1/2"));
    check_failed_handoff(&m, &p);

    p = make(&m);
    m.behavior = IO_ERROR;
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_ID, &p, &r) == GENI_ERR_IO);
    CHECK(m.commands == 1 && !r.id_valid && !m.forbidden_dma_writes);
    CHECK(!strcmp(m.log, "TP id=---- st=-5 phase=1/2"));
    check_failed_handoff(&m, &p);

    check_id(0xa5, 0x7c);
    check_id(0x36, 0x40);
    check_id(0, 0);
    p = make(&m);
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_ID, &p, &r) == 0);
    CHECK(m.commands == 1 && m.tx_count == 2 && m.rx_count == 2);
    CHECK(!strcmp(m.log, "TP id=A57C st=0 phase=2/2"));
    // The same still-held owner admits a second call: one new submit, not a
    // retry within either call and not a per-boot suppression.
    CHECK(nuwa_touch_probe_run(NUWA_TOUCH_STAGE_ID, &p, &r) == 0);
    CHECK(m.commands == 2 && m.tx_count == 2 && m.rx_count == 2);
    CHECK(m.tx_words[0] == 0x000020fbu && m.tx_words[1] == 0);
    CHECK(m.confirmations == 2 && m.logs == 2 && !m.forbidden_dma_writes);
    puts("nuwa touch PIO model: self-check passed");
    return 0;
}
