// Fixed IOStorageFamily reference headers predate current kernel style checks.
// Original diagnostics are preserved in CI 40856339167. Suppress only these
// two header style categories; restore the caller's -Werror policy immediately.
#pragma once
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wzero-as-null-pointer-constant"
#pragma clang diagnostic ignored "-Wshadow-field"
#include <IOKit/storage/IOBlockStorageDevice.h>
#pragma clang diagnostic pop

#include <sys/types.h>
#include <stdint.h>
extern "C" int native_ram_block_gpu_addon(const uint8_t **data, uint64_t *bytes);
extern "C" int native_ram_block_volume_seed(const char *uuid, dev_t *device,
    char *path, size_t size, uint64_t *base, uint64_t *bytes, uint8_t digest[32]);
