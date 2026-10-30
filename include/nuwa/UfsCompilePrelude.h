#pragma once
#include "RamBlockCompilePrelude.h"
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Woverloaded-virtual"
#include <IOKit/IOPlatformExpert.h>
#pragma clang diagnostic pop
// Exact declarations for the fixed NativeUfs provider, not implementations.
extern "C" {
unsigned native_ufs_store_mode(void);
int native_ufs_store_open(uint64_t, uint64_t *, const char **);
int native_ufs_store_read(uint64_t, uint32_t, void *);
int native_ufs_store_write(uint64_t, uint32_t, const void *);
int native_ufs_store_sync(void);
unsigned native_ufs_store_gpt_check(void);
int native_ufs_log_open(uint64_t *, uint64_t *, const char **);
int native_ufs_log_write(uint64_t, uint32_t, const void *);
uint64_t native_ufs_export_blocks(void);
int native_ufs_export_write(uint64_t, uint32_t, const void *);
int native_ufs_log_sync(void);
void native_ufs_progress_text(char *, size_t);
int native_ufs_block_authenticates(IOService *, const char *, uint8_t *);
}
