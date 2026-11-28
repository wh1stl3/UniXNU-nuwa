// SPDX-License-Identifier: BSD-2-Clause-Patent
// nuwa recovery FDT and input capability declarations; not runtime readiness.
#ifndef NUWA_TOUCH_BOARD_H
#define NUWA_TOUCH_BOARD_H

#define NUWA_TOUCH_DEFAULT_STAGE 0u
#define NUWA_TOUCH_STAGE_INFO 1u
#define NUWA_TOUCH_STAGE_ID 2u

#define NUWA_TOUCH_WRAPPER_BASE 0x00ac0000ULL
#define NUWA_TOUCH_WRAPPER_SIZE 0x2000u
#define NUWA_TOUCH_SE_BASE 0x00a90000ULL
#define NUWA_TOUCH_SE_SIZE 0x4000u
#define NUWA_TOUCH_SPI_MAX_HZ 12000000u
#define NUWA_TOUCH_SPI_CS 0u

// FDT pinctrl node names distinguish MISO from MOSI; they are not inferred
// from the numeric order of the pins.
#define NUWA_TOUCH_GPIO_MISO 44u
#define NUWA_TOUCH_GPIO_MOSI 45u
#define NUWA_TOUCH_GPIO_CLK 46u
#define NUWA_TOUCH_GPIO_CS 47u
#define NUWA_TOUCH_GPIO_IRQ 25u
#define NUWA_TOUCH_GPIO_RESET 24u

#define NUWA_TOUCH_AVDD "pm8010m_l6"
#define NUWA_TOUCH_AVDD_MIN_UV 1800000u
#define NUWA_TOUCH_AVDD_MAX_UV 3200000u
#define NUWA_TOUCH_VDD "pm_humu_l12"
#define NUWA_TOUCH_VDD_UV 1800000u
#define NUWA_TOUCH_COMPATIBLE "st,spi"
#define NUWA_TOUCH_VENDOR 0x38u
#define NUWA_TOUCH_FIRMWARE "st_fts_m2.ftb"
#define NUWA_TOUCH_CONTACTS 10u
#define NUWA_TOUCH_X_MAX 14399u
#define NUWA_TOUCH_Y_MAX 31999u

#endif
