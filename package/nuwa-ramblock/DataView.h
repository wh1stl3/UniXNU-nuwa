// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
#include <stdint.h>

// PU1 ABI: 0 is legacy/off (no candidate view); the others are explicit.
enum class NuwaDataView : uint32_t { SeedOnly = 1, ReadOnly = 2, Writable = 3, Isolated = 4 };
