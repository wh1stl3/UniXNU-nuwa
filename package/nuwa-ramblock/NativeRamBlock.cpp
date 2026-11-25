// SPDX-License-Identifier: BSD-2-Clause-Patent
#include <IOKit/IOLib.h>
#include <IOKit/storage/IOBlockStorageDevice.h>
#include <IOKit/IODeviceTreeSupport.h>
#include <libkern/c++/OSData.h>
#include <libkern/c++/OSDictionary.h>
#include <libkern/c++/OSIterator.h>
#include <libkern/c++/OSNumber.h>
#include <libkern/c++/OSString.h>
#include <IOKit/IOBSD.h>
#include <sys/param.h>
#include <libkern/crypto/sha2.h>
#include <mach/machine.h>
#include <machine/machine_routines.h>
#include <vm/vm_kern.h>
#include <kern/clock.h>
#include <pexpert/pexpert.h>
#include "SparseDisk.h"
#include "PersistOverlay.h"
#include "DirectDisk.h"
#include "PersistOpenReason.h"
#if defined(NUWA_DATA_CANDIDATE)
#include "../nuwa-data-write/DualBankLogOverlay.h"
#include "DataView.h"
#endif

extern "C" {
extern unsigned long gPhysBase, gPhysSize;
int native_ram_block_volume_device(const char *, dev_t *, char *, size_t);
volatile uint32_t native_ram_block_ready = 0;
volatile uint64_t native_ram_block_bytes = 0;
volatile uint64_t native_ram_block_reads = 0;
volatile uint64_t native_ram_block_writes = 0;
volatile uint64_t native_ram_block_failures = 0;
volatile uint64_t native_ram_block_resident_bytes = 0;
volatile uint32_t native_ram_block_sparse = 0;
uint8_t native_ram_block_seed_sha256[32];
// Optional persistence of the changed pages through a board-provided store window (see PersistOverlay.h). All weak: a build
// without the provider keeps the volatile disk.
unsigned native_ufs_store_mode(void) __attribute__((weak_import));
int native_ufs_store_open(uint64_t, uint64_t *, const char **) __attribute__((weak_import));
int native_ufs_store_read(uint64_t, uint32_t, void *) __attribute__((weak_import));
int native_ufs_store_write(uint64_t, uint32_t, const void *) __attribute__((weak_import));
int native_ufs_store_sync(void) __attribute__((weak_import));
#if defined(NUWA_DATA_CANDIDATE)
int native_ufs_store_isolated(void) __attribute__((weak_import));
uint32_t native_data_persist_view = 0;
#endif
unsigned native_ufs_store_gpt_check(void) __attribute__((weak_import));
// Diagnostics. state: 0 off, 1 blank (read-only probe), 2 resumed, 3 fresh (Install and boot), 4 refused/failed, 5 degraded after an I/O
// error, 6 resumed read-only (probe), 7 kept: the store holds no Data of this seed and no reset was asked, so it is left untouched and
// this boot's Data runs from the seed alone (header: why). header: persist::checkHeader result.
volatile uint32_t native_data_persist_state = 0, native_data_persist_header = 9, native_data_persist_gpt = 0xff, native_data_persist_gpt_after = 0xff;
const char *volatile nuwa_data_persist_open_why = nullptr;
// r24 (nuwa fork of this upstream driver): why native_ram_block_volume_seed() failed, for the
// DATA row's serr field.  0 = not run or success, 1 = the disk object is not ready,
// 2 = no IOMedia matched the volume UUID, 3 = a match lacks its UUID or BSD properties,
// 4 = no NativeRamBlock in the match's provider chain, 5 = the disk has no usable seed
// (seedInfo()/available() false).
volatile uint32_t native_ram_block_seed_reason = 0;
// r25 (nuwa fork): the last NativeRamBlock::start() rejection code (0 = none yet), drawn on the
// diagnostic page next to ready/init-count.  1..9 as in the "start reject N" console lines.
volatile int32_t nuwa_ram_block_reject = 0;
volatile uint64_t native_data_persist_pages = 0, native_data_persist_loaded = 0, native_data_persist_writes = 0,
                  native_data_persist_syncs = 0, native_data_persist_errors = 0, native_data_persist_first_lba = 0,
                  native_data_persist_present = 0;
}

class NativeRamBlock : public IOBlockStorageDevice {
  OSDeclareDefaultStructors(NativeRamBlock)
  IOLock *gate = nullptr;
  uint8_t *memory = nullptr;
  uint64_t capacity = 0;
  bool online = false;
  RamSparseDisk sparse = {};
  // A disk above 2 GiB keeps only the nonzero seed pages (SeedDisk.h).
  // It can serve seed reads without a store, but has no volatile write path.
  SeedDisk big = {};
  bool isBig = false;
  uint8_t seedHash[32] = {};
  persist::Overlay overlay;
  uint8_t *overlayBits = nullptr, *stage = nullptr;   // stage: kStagePages pages, one write or read run
  static constexpr uint32_t kStagePages = 32;
  bool storeAttached = false;
  // Direct mode (the store is open read-write): changed pages live in the store window only, never in RAM; reads of them go to the
  // window. A failed store write stops all further writes (a page the system was told is written must be on the medium).
  bool direct = false, directFailed = false;
#if defined(NUWA_DATA_CANDIDATE)
  using DataOverlay = NuwaData::DualBankLogOverlay<>;
  DataOverlay dataOverlay;
  DataOverlay::Workspace *dataWorkspace = nullptr;
  bool candidateData = false;
  NuwaDataView dataView = NuwaDataView::SeedOnly;
#endif
  struct StoreOps {
    bool read(uint64_t b, uint32_t n, void *d) { __atomic_fetch_add(&native_data_persist_loaded, n, __ATOMIC_RELAXED); return native_ufs_store_read(b, n, d); }
    bool write(uint64_t b, uint32_t n, const void *s) { return native_ufs_store_write(b, n, s); }
    bool sync() { return native_ufs_store_sync(); }
#if defined(NUWA_DATA_CANDIDATE)
    bool isolated() { return &native_ufs_store_isolated && native_ufs_store_isolated(); }
#endif
  };
  void persistFailed() { overlay.active = false; native_data_persist_state = 5; __atomic_fetch_add(&native_data_persist_errors, 1, __ATOMIC_RELAXED); }
#if defined(NUWA_DATA_CANDIDATE)
  void setDataView(NuwaDataView view) {
    dataView = view;
    __atomic_store_n(&native_data_persist_view, static_cast<uint32_t>(view), __ATOMIC_RELEASE);
  }
  void prepareCandidateView() {
    if (&native_ufs_store_mode && native_ufs_store_mode() == 2) attachStore();
  }
  void isolateCandidate() {
    native_data_persist_state = 5;
    __atomic_fetch_add(&native_data_persist_errors, 1, __ATOMIC_RELAXED);
    setDataView(NuwaDataView::Isolated);
  }
  static bool candidateReadOnly() {
    uint32_t v = 0;
    return PE_parse_boot_argn("nuwa-data-ro", &v, sizeof v) && v;
  }
  // Caller holds gate. Bytes in a write run are acknowledged only after its
  // single commit succeeds. A short descriptor read never submits that run.
  template<class BufferOps>
  IOReturn candidateIO(bool write, uint64_t offset, uint64_t bytes, BufferOps &buffer, uint64_t &actual) {
    actual = 0;
    if (dataView == NuwaDataView::Isolated) return kIOReturnIOError;
    if (write && dataView != NuwaDataView::Writable) return kIOReturnNotWritable;
    StoreOps store;
    const auto seedAt = [&](uint64_t page) {
      static const uint8_t zero[NuwaData::Block] = {};
      const uint8_t *seed = isBig ? big.find(page) :
                            memory ? memory + page * NuwaData::Block : sparse.find(page);
      return seed ? seed : zero;
    };
    const auto readError = [&] {
      if (store.isolated()) isolateCandidate();
      return kIOReturnIOError;
    };
    while (actual < bytes) {
      const uint64_t at = offset + actual;
      if (!write) {
        const uint64_t page = at / NuwaData::Block;
        const uint64_t skip = at % NuwaData::Block;
        uint64_t n = NuwaData::Block - skip;
        if (n > bytes - actual) n = bytes - actual;
        const uint8_t *src;
        if (dataOverlay.has(page)) {
          if (!dataOverlay.read(store, page, stage)) return readError();
          src = stage;
        } else {
          src = seedAt(page);
        }
        const uint64_t got = buffer.copy(actual, src + skip, n);
        actual += got;
        if (got != n) return kIOReturnIOError;
        continue;
      }
      const uint64_t runFirst = at / NuwaData::Block;
      uint64_t runBytes = 0;
      uint32_t runCount = 0;
      while (runCount < kStagePages && runBytes < bytes - actual) {
        const uint64_t skip = (at + runBytes) % NuwaData::Block;
        uint64_t n = NuwaData::Block - skip;
        if (n > bytes - actual - runBytes) n = bytes - actual - runBytes;
        auto *dst = stage + runCount * NuwaData::Block;
        if (skip || n != NuwaData::Block) {
          const uint64_t page = runFirst + runCount;
          if (dataOverlay.has(page)) {
            if (!dataOverlay.read(store, page, dst)) return readError();
          } else {
            memcpy(dst, seedAt(page), NuwaData::Block);
          }
        }
        if (buffer.read(actual + runBytes, dst + skip, n) != n) return kIOReturnIOError;
        runBytes += n;
        ++runCount;
      }
      if (!dataOverlay.writeRun(store, runFirst, runCount, stage)) {
        isolateCandidate();
        return kIOReturnIOError;
      }
      actual += runBytes;
      __atomic_fetch_add(&native_data_persist_writes, runCount, __ATOMIC_RELAXED);
      __atomic_fetch_add(&native_data_persist_syncs, 1, __ATOMIC_RELAXED);
      native_data_persist_present = dataOverlay.presentCount();
      if (!dataOverlay.writable()) {
        native_data_persist_state = 6;
        setDataView(NuwaDataView::ReadOnly);
        if (actual < bytes) return kIOReturnNotWritable;
      }
    }
    return kIOReturnSuccess;
  }
#endif
public:
  // One-shot: the mode-2 candidate calls this before media publication; the
  // legacy path calls it during volume lookup. Seed identity never changes.
  // Install and boot permits blank v3 creation; it does not discard a v3 epoch.
  static bool discardRequested() { uint32_t v = 0; return PE_parse_boot_argn("sheng-data-reset", &v, sizeof v) && (v == 1 || v == 2); }
  void attachStore() {
    if (!gate) return;
    IOLockLock(gate);
    if (storeAttached) { IOLockUnlock(gate); return; }
    storeAttached = true;
    unsigned mode = &native_ufs_store_mode ? native_ufs_store_mode() : 0;
#if defined(NUWA_DATA_CANDIDATE)
    if (mode == 2) {
      candidateData = true;
      setDataView(NuwaDataView::SeedOnly);
    }
#endif
    if (mode && (sparse.pages || isBig) && &native_ufs_store_open && &native_ufs_store_read && &native_ufs_store_write &&
        &native_ufs_store_sync && &native_ufs_store_gpt_check) {
      uint64_t pages = (isBig ? big.bytes : sparse.bytes) / 4096, first = 0;
      const char *why = "";
      native_data_persist_pages = pages;
      // The retained Data candidate exports a cached root-layout result, not
      // a diagnostic I/O. Write authorization independently validates both GPTs.
      native_data_persist_gpt = native_ufs_store_gpt_check();
      uint64_t window = persist::windowBlocks(pages);
#if defined(NUWA_DATA_CANDIDATE)
      if (mode == 2) window = DataOverlay::overlayBlocks(pages);
#endif
      int opened = native_ufs_store_open(window, &first, &why);
      nuwa_data_persist_open_why = nuwa_persist_open_reason(opened, why);
      if (!opened) {
        native_data_persist_state = 4;
        IOLog("NativeRamBlock: persistent store refused: %s\n", why);
      } else {
        native_data_persist_first_lba = first;
#if defined(NUWA_DATA_CANDIDATE)
        if (mode == 2) {
          // Once a window is attached, never use the seed-only path for
          // damaged, foreign, or indeterminate overlay state.
          dataWorkspace = static_cast<DataOverlay::Workspace *>(IOMallocZero(sizeof(DataOverlay::Workspace)));
          auto *seenScratch = static_cast<DataOverlay::SeenScratch *>(IOMallocZero(sizeof(DataOverlay::SeenScratch)));
          stage = static_cast<uint8_t *>(IOMallocZero(kStagePages * NuwaData::Block));
          StoreOps ops;
          auto result = stage && seenScratch && dataWorkspace
                       ? dataOverlay.open(ops, seedHash, *dataWorkspace, *seenScratch,
                                          !candidateReadOnly(), discardRequested())
                       : DataOverlay::Open::Failed;
          if (seenScratch) IOFree(seenScratch, sizeof(DataOverlay::SeenScratch));
          native_data_persist_state = result == DataOverlay::Open::Failed ? 4 :
                                      result == DataOverlay::Open::Empty ? 1 :
                                      dataOverlay.writable() ? 2 : 6;
          native_data_persist_present = dataOverlay.presentCount();
          native_data_persist_gpt_after = native_ufs_store_gpt_check();
          setDataView(result == DataOverlay::Open::Failed ? NuwaDataView::Isolated :
                      dataOverlay.writable() ? NuwaDataView::Writable :
                      result == DataOverlay::Open::Empty ? NuwaDataView::SeedOnly : NuwaDataView::ReadOnly);
          IOLockUnlock(gate);
          return;
        }
#endif
        uint64_t bb = persist::bitmapBlocks(pages);
        overlayBits = static_cast<uint8_t *>(IOMallocZero(bb * persist::kBlock));
        stage = static_cast<uint8_t *>(IOMallocZero(kStagePages * persist::kBlock));
        StoreOps ops;
        persist::Open result = overlayBits && stage ? overlay.open(ops, pages, seedHash, mode == 1, overlayBits, discardRequested())
                                                          : persist::Open::Failed;
        native_data_persist_header = static_cast<uint32_t>(overlay.header);
        if (result == persist::Open::Failed) {
          native_data_persist_state = 4;
          overlay.active = false;
        } else if (result == persist::Open::Blank) {
          native_data_persist_state = 1;
        } else if (result == persist::Open::Kept) {
          native_data_persist_state = 7;
          overlay.active = false;
          IOLog("NativeRamBlock: the persistent store holds no Data of this seed (header %d); kept, Data runs from the seed: "
                "use Install and boot to start it over\n", overlay.header);
        } else if (result == persist::Open::Fresh) {
          native_data_persist_state = 3;
          direct = mode == 2;
        } else if (mode == 2) {
          // Resumed read-write: nothing is copied into RAM. The window answers for every page whose bit is set.
          direct = true;
          native_data_persist_state = 2;
        } else {
          struct Loader {
            NativeRamBlock *self;
            bool operator()(uint64_t i, const uint8_t *page) {
              if (i >= self->sparse.bytes / 4096) return false;
              if (!self->sparse.pages[i]) {
                uint8_t *fresh = static_cast<uint8_t *>(IOMallocZero(4096));
                if (!fresh) return false;
                self->sparse.pages[i] = fresh;
                self->sparse.resident += 4096;
              }
              memcpy(self->sparse.pages[i], page, 4096);
              __atomic_fetch_add(&native_data_persist_loaded, 1, __ATOMIC_RELAXED);
              return true;
            }
          } load = { this };
          if (overlay.forEachPresent(ops, load, stage, kStagePages)) {
            native_data_persist_state = mode == 1 ? 6 : 2;
            native_ram_block_resident_bytes = sparse.resident;
          } else {
            // A partly restored disk would be worse than a volatile one, but the pages already copied are consistent
            // overlay content; stop writing back and let the system decide what it can mount.
            native_data_persist_state = 4;
            overlay.active = false;
          }
        }
        native_data_persist_present = overlay.present;
        native_data_persist_gpt_after = native_ufs_store_gpt_check();
      }
    }
    IOLockUnlock(gate);
  }

  bool available() const { return online && (memory || sparse.pages || isBig) && capacity; }
  // Seed/identity discovery only; does not assert overlay admission or durability.
  bool seedInfo(uint64_t *base,uint64_t *bytes,uint8_t hash[32]) {
    if(!gate || !base || !bytes || !hash)return false;
    IOLockLock(gate);bool ready=available();
    if(ready){*base=(sparse.pages||isBig)?0:reinterpret_cast<uint64_t>(memory);*bytes=capacity*512;memcpy(hash,seedHash,32);}
    IOLockUnlock(gate);return ready;
  }
  bool start(IOService *) override;
  void stop(IOService *) override;
  void free() override;
  IOReturn doEjectMedia() override { return kIOReturnUnsupported; }
  IOReturn doFormatMedia(UInt64) override { return kIOReturnUnsupported; }
  UInt32 doGetFormatCapacities(UInt64 *, UInt32) const override { return 0; }
  char *getVendorString() override { return const_cast<char *>("Native"); }
  char *getProductString() override { return const_cast<char *>("Owned RAM block storage"); }
  char *getRevisionString() override { return const_cast<char *>("1.0"); }
  char *getAdditionalDeviceInfoString() override { return const_cast<char *>("volatile storage; no persistent trust claim"); }
  IOReturn reportBlockSize(UInt64 *value) override { *value = 512; return kIOReturnSuccess; }
  IOReturn reportEjectability(bool *value) override { *value = false; return kIOReturnSuccess; }
  IOReturn reportMaxValidBlock(UInt64 *value) override { *value = capacity - 1; return kIOReturnSuccess; }
  IOReturn reportMediaState(bool *present, bool *changed) override {
    *present = online; if (changed) *changed = false; return kIOReturnSuccess;
  }
  IOReturn reportRemovability(bool *value) override { *value = false; return kIOReturnSuccess; }
  IOReturn reportWriteProtection(bool *value) override {
#if defined(NUWA_DATA_CANDIDATE)
    if (gate) {
      IOLockLock(gate);
      *value = candidateData && dataView != NuwaDataView::Writable;
      IOLockUnlock(gate);
      return kIOReturnSuccess;
    }
#endif
    *value = false;
    return kIOReturnSuccess;
  }
  IOReturn doSynchronizeCache() override {
#if defined(NUWA_DATA_CANDIDATE)
    if (!gate) return kIOReturnNotReady;
    IOLockLock(gate);
    IOReturn status = kIOReturnSuccess;
    if (!online) status = kIOReturnNotReady;
    else if (candidateData) {
      if (dataView == NuwaDataView::Writable && StoreOps{}.isolated()) isolateCandidate();
      status = dataView == NuwaDataView::Isolated ? kIOReturnIOError :
               dataView == NuwaDataView::Writable ? kIOReturnSuccess : kIOReturnNotWritable;
    }
    IOLockUnlock(gate);
    return status;
#else
    if (!online) return kIOReturnNotReady;
    // Every changed page is on the medium, with its bitmap bit, before its write completed (PersistOverlay.h): nothing to flush.
    return kIOReturnSuccess;
#endif
  }
  IOReturn doSynchronize(UInt64, UInt64, IOOptionBits) override { return doSynchronizeCache(); }
  IOReturn getWriteCacheState(bool *value) override { *value = false; return kIOReturnSuccess; }
  IOReturn setWriteCacheState(bool) override { return kIOReturnUnsupported; }
  IOReturn doAsyncReadWrite(IOMemoryDescriptor *, UInt64, UInt64, IOStorageAttributes *, IOStorageCompletion *) override;
};
OSDefineMetaClassAndStructors(NativeRamBlock, IOBlockStorageDevice)

// r26 (nuwa fork): the port now creates and starts one instance itself (see
// native_ram_block_start_service below); the IOResources persona may still fire later, and a
// second disk over the same boot memory would duplicate the seed and make the volume UUID
// ambiguous.  Whoever claims this first owns the disk; the loser reports 14 and releases.
static volatile int s_start_claimed = 0;

bool NativeRamBlock::start(IOService *provider)
{
  if (__atomic_exchange_n(&s_start_claimed, 1, __ATOMIC_ACQ_REL) != 0) {
    nuwa_ram_block_reject = 14;
    IOLog("NativeRamBlock: start reject 14: another instance already owns the disk\n");
    return false;
  }
  nuwa_ram_block_reject = 0;
  if (!IOBlockStorageDevice::start(provider)) {
    nuwa_ram_block_reject = 1;
    IOLog("NativeRamBlock: start reject 1: IOBlockStorageDevice::start\n");
    return false;
  }
  IORegistryEntry *map = IORegistryEntry::fromPath("/chosen/memory-map", gIODTPlane);
  if (!map) {
    nuwa_ram_block_reject = 2; IOLog("NativeRamBlock: start reject 2: no /chosen/memory-map\n");
    return false;
  }
  OSData *packed = OSDynamicCast(OSData, map->getProperty("PackedRAMDisk"));
  OSData *range = OSDynamicCast(OSData, map->getProperty("RAMDisk"));
  if(packed && range){nuwa_ram_block_reject = 3;IOLog("NativeRamBlock: start reject 3: both RAMDisk and PackedRAMDisk\n");map->release();return false;}
  if(packed)range=packed;
  bool packedInput=packed!=nullptr;
  uint64_t physical = 0, bytes = 0;
  if (range && range->getLength() == 16) {
    memcpy(&physical, range->getBytesNoCopy(), 8);
    memcpy(&bytes, static_cast<const uint8_t *>(range->getBytesNoCopy()) + 8, 8);
  }
  map->release();
  // r24 (nuwa fork): the one line that says what the kernel was handed.  pa == 0 && bytes == 0
  // means the loader never filled the placeholder; a range outside gphys is rejected below.
  IOLog("NativeRamBlock: start packed=%d pa=%#llx bytes=%#llx gphys=%#llx+%#llx\n",
      packedInput ? 1 : 0, physical, bytes, (uint64_t)gPhysBase, (uint64_t)gPhysSize);
  // Boot memory belongs to the loader/kernel; never allocate or free it here.
  if (!bytes || bytes > 0x80000000 || (physical & 4095) || (!packedInput && (bytes & 4095)) ||
      physical < gPhysBase || bytes > gPhysSize || physical - gPhysBase > gPhysSize - bytes) {
    nuwa_ram_block_reject = 4;
    IOLog("NativeRamBlock: start reject 4: range pa=%#llx bytes=%#llx gphys=%#llx+%#llx\n",
        physical, bytes, (uint64_t)gPhysBase, (uint64_t)gPhysSize);
    return false;
  }
  memory = reinterpret_cast<uint8_t *>(ml_static_ptovirt(physical));
  if (!memory || !(gate = IOLockAlloc())) {
    nuwa_ram_block_reject = 5; IOLog("NativeRamBlock: start reject 5: ptovirt/IOLockAlloc\n");
    return false;
  }
  uint64_t logical=bytes;
  if(packedInput){
    if(!ramPackedLayout(memory,bytes,&logical)){nuwa_ram_block_reject = 6; IOLog("NativeRamBlock: start reject 6: packed layout bytes=%#llx\n",bytes);return false;}
    struct ImportOps {uint8_t *allocate(){return static_cast<uint8_t *>(IOMallocZero(4096));}} ops;
    if(logical>0x80000000ULL){
      uint64_t nonzero=0;
      if(!seedCountNonzero(memory,bytes,&nonzero)){nuwa_ram_block_reject = 7; IOLog("NativeRamBlock: start reject 7: seedCountNonzero\n");return false;}
      big.bytes=logical;big.capacity=nonzero;
      big.index=static_cast<uint64_t *>(IOMallocZero((nonzero?nonzero:1)*sizeof(uint64_t)));
      big.page=static_cast<uint8_t **>(IOMallocZero((nonzero?nonzero:1)*sizeof(uint8_t *)));
      if(!big.index||!big.page||!seedImportSparse(big,memory,bytes,ops)){nuwa_ram_block_reject = 8; IOLog("NativeRamBlock: start reject 8: big sparse import\n");return false;}
      isBig=true;sparse.bytes=logical;
    }else{
      sparse.bytes=logical;
      sparse.pages=static_cast<uint8_t **>(IOMallocZero((logical/4096)*sizeof(uint8_t *)));
      if(!ramSparseImport(sparse,memory,bytes,ops)){nuwa_ram_block_reject = 9; IOLog("NativeRamBlock: start reject 9: sparse import\n");return false;}
    }
  }
  capacity = logical / 512;
  SHA256_CTX context;
  SHA256_Init(&context);
  if(isBig){
    seedIdentity(big,context,[](SHA256_CTX &c){SHA256_Init(&c);},[](SHA256_CTX &c,const void *p,size_t n){SHA256_Update(&c,p,n);},
                 [](SHA256_CTX &c,uint8_t *out){SHA256_Final(out,&c);},seedHash);
    memory=nullptr;
  }else{
  if(sparse.pages){
    static const uint8_t zero[4096]={};
    for(uint64_t i=0;i<logical/4096;++i)SHA256_Update(&context,sparse.pages[i]?sparse.pages[i]:zero,4096);
    memory=nullptr;
  }else SHA256_Update(&context, memory, bytes);
  SHA256_Final(seedHash, &context);
  }
  memcpy(native_ram_block_seed_sha256,seedHash,32);
  native_ram_block_bytes = logical;
  native_ram_block_sparse=(sparse.pages||isBig)?1:0;
  native_ram_block_resident_bytes=isBig?big.resident:sparse.pages?sparse.resident:logical;
#if defined(NUWA_DATA_CANDIDATE)
  // Resolve mode 2 before APFS can probe this disk. UUID selection later
  // does not switch the bytes under the already published media.
  prepareCandidateView();
#endif
  online = true;
  native_ram_block_ready = 1;
  IOLog("NativeRamBlock: ready logical=%llu packed=%d resident=%llu\n",
      logical, packedInput ? 1 : 0, native_ram_block_resident_bytes);
  registerService();
  return true;
}

IOReturn NativeRamBlock::doAsyncReadWrite(IOMemoryDescriptor *buffer, UInt64 block, UInt64 count,
    IOStorageAttributes *, IOStorageCompletion *completion)
{
  if (!buffer || !completion || !completion->action || !count || block >= capacity ||
      count > capacity - block || buffer->getLength() < count * 512 ||
      (buffer->getDirection() != kIODirectionIn && buffer->getDirection() != kIODirectionOut)) return kIOReturnBadArgument;
  if (!gate) return kIOReturnNotReady;
  const uint64_t bytes = count * 512;
  IOLockLock(gate);
  if (!online) { IOLockUnlock(gate); return kIOReturnNotReady; }
#if defined(NUWA_DATA_CANDIDATE)
  if (candidateData) {
    struct BufferOps {
      IOMemoryDescriptor *buffer;
      uint64_t read(uint64_t at, void *p, uint64_t n) { return buffer->readBytes(at, p, n); }
      uint64_t copy(uint64_t at, const void *p, uint64_t n) { return buffer->writeBytes(at, p, n); }
    } bops = {buffer};
    uint64_t actual;
    const bool write = buffer->getDirection() == kIODirectionOut;
    const IOReturn status = candidateIO(write, block * 512, bytes, bops, actual);
    if (write) __atomic_fetch_add(&native_ram_block_writes, 1, __ATOMIC_RELAXED);
    else __atomic_fetch_add(&native_ram_block_reads, 1, __ATOMIC_RELAXED);
    if (status) __atomic_fetch_add(&native_ram_block_failures, 1, __ATOMIC_RELAXED);
    IOLockUnlock(gate);
    completion->action(completion->target, completion->parameter, status, actual);
    return kIOReturnSuccess;
  }
#endif
  uint64_t actual;bool noMemory=false;
  if(isBig && !direct) {
    // Before the store is attached (APFS probes the disk for its volume UUID long before the kernel asks for the Data volume, which is what
    // attaches the store) a disk this size is read from its seed alone; it has no volatile mode, so writes wait.
    if(buffer->getDirection()==kIODirectionIn) {
      struct SeedReadOps {
        IOMemoryDescriptor *buffer;
        uint64_t copy(uint64_t at,const void *p,uint64_t n){return buffer->writeBytes(at,p,n);}
      } rops={buffer};
      static const uint8_t zero[4096]={};
      uint64_t done=0,offset=block*512;
      while(done<bytes) {
        uint64_t at=offset+done,index=at/4096,skip=at&4095,n=4096-skip;
        if(n>bytes-done)n=bytes-done;
        const uint8_t *page=big.find(index);
        uint64_t got=rops.copy(done,(page?page:zero)+skip,n);
        done+=got;if(got!=n)break;
      }
      __atomic_fetch_add(&native_ram_block_reads,1,__ATOMIC_RELAXED);
      IOReturn early=done==bytes?kIOReturnSuccess:kIOReturnIOError;
      if(early)__atomic_fetch_add(&native_ram_block_failures,1,__ATOMIC_RELAXED);
      IOLockUnlock(gate);
      completion->action(completion->target,completion->parameter,early,done);
      return kIOReturnSuccess;
    }
    IOLockUnlock(gate);return kIOReturnNotReady;
  }
  if(sparse.pages||isBig){
    struct Operations {
      IOMemoryDescriptor *buffer;
      uint8_t *allocate(){return static_cast<uint8_t *>(IOMallocZero(4096));}
      uint64_t read(uint64_t at,void *p,uint64_t n){return buffer->readBytes(at,p,n);}
      uint64_t copy(uint64_t at,const void *p,uint64_t n){return buffer->writeBytes(at,p,n);}
    } ops={buffer};
    bool write=buffer->getDirection()==kIODirectionOut;
    if(direct){
      struct BufferOps {
        IOMemoryDescriptor *buffer;
        uint64_t read(uint64_t at,void *p,uint64_t n){return buffer->readBytes(at,p,n);}
        uint64_t copy(uint64_t at,const void *p,uint64_t n){return buffer->writeBytes(at,p,n);}
      } bops={buffer};
      StoreOps store;bool storeError=false;
      if(write && directFailed)actual=0;
      else actual=isBig?directDiskIO(big,overlay,store,stage,kStagePages,write,block*512,bytes,bops,&storeError)
                       :directDiskIO(sparse,overlay,store,stage,kStagePages,write,block*512,bytes,bops,&storeError);
      if(storeError){
        if(write)directFailed=true;
        native_data_persist_state=5;__atomic_fetch_add(&native_data_persist_errors,1,__ATOMIC_RELAXED);
      }
      if(write && actual){__atomic_fetch_add(&native_data_persist_writes,(actual+4095)/4096,__ATOMIC_RELAXED);__atomic_fetch_add(&native_data_persist_syncs,1,__ATOMIC_RELAXED);native_data_persist_present=overlay.present;}
    } else {
    actual=ramSparseIO(sparse,write,block*512,bytes,ops,noMemory);
    }
    if(!direct && write && actual==bytes && overlay.active && !overlay.readOnly){
      StoreOps store;
      uint64_t firstPage=block*512/4096,lastPage=(block*512+bytes-1)/4096;
      for(uint64_t i=firstPage;i<=lastPage && overlay.active;){
        uint32_t n=0;
        while(n<kStagePages && i+n<=lastPage && sparse.pages[i+n]){memcpy(stage+(uint64_t)n*persist::kBlock,sparse.pages[i+n],persist::kBlock);++n;}
        if(!n || !overlay.writeRun(store,i,n,stage)){persistFailed();break;}
        __atomic_fetch_add(&native_data_persist_writes,n,__ATOMIC_RELAXED);
        __atomic_fetch_add(&native_data_persist_syncs,1,__ATOMIC_RELAXED);   // one run = one durable commit
        native_data_persist_present=overlay.present;
        i+=n;
      }
    }
    if(write)__atomic_fetch_add(&native_ram_block_writes,1,__ATOMIC_RELAXED);
    else __atomic_fetch_add(&native_ram_block_reads,1,__ATOMIC_RELAXED);
    native_ram_block_resident_bytes=isBig?big.resident:sparse.resident;
  }else if (buffer->getDirection() == kIODirectionIn) {
    actual = buffer->writeBytes(0, memory + block * 512, bytes);
    __atomic_fetch_add(&native_ram_block_reads, 1, __ATOMIC_RELAXED);
  } else {
    actual = buffer->readBytes(0, memory + block * 512, bytes);
    __atomic_fetch_add(&native_ram_block_writes, 1, __ATOMIC_RELAXED);
  }
  IOReturn status = actual == bytes ? kIOReturnSuccess : noMemory ? kIOReturnNoMemory : kIOReturnIOError;
  if (status) __atomic_fetch_add(&native_ram_block_failures, 1, __ATOMIC_RELAXED);
  IOLockUnlock(gate);
  completion->action(completion->target, completion->parameter, status, actual);
  return kIOReturnSuccess;
}

void NativeRamBlock::stop(IOService *provider)
{
  if (gate) { IOLockLock(gate); online = false; IOLockUnlock(gate); }
  IOBlockStorageDevice::stop(provider);
}

void NativeRamBlock::free()
{
#if defined(NUWA_DATA_CANDIDATE)
  if (dataWorkspace) { IOFree(dataWorkspace, sizeof(DataOverlay::Workspace)); dataWorkspace = nullptr; }
#endif
  if (overlayBits) { IOFree(overlayBits, persist::bitmapBlocks(sparse.bytes / 4096) * persist::kBlock); overlayBits = nullptr; }
  if (stage) { IOFree(stage, kStagePages * persist::kBlock); stage = nullptr; }
  if (isBig) {
    for (uint64_t k = 0; k < big.count; ++k) IOFree(big.page[k], 4096);
    if (big.index) IOFree(big.index, (big.capacity ? big.capacity : 1) * sizeof(uint64_t));
    if (big.page) IOFree(big.page, (big.capacity ? big.capacity : 1) * sizeof(uint8_t *));
    big = {}; isBig = false;
  }
  if (gate) { IOLockFree(gate); gate = nullptr; }
  if(sparse.pages){
    for(uint64_t i=0;i<sparse.bytes/4096;++i)if(sparse.pages[i])IOFree(sparse.pages[i],4096);
    IOFree(sparse.pages,(sparse.bytes/4096)*sizeof(uint8_t *));sparse={};
  }
  // Dense boot allocation and packed input remain owned until reboot.
  IOBlockStorageDevice::free();
}

static int selectVolumeSeed(const char *uuid, dev_t *device, char *path, size_t size,
    uint64_t *seedBase,uint64_t *seedBytes,uint8_t seedDigest[32])
{
  native_ram_block_seed_reason = 0;
  if (!uuid || strlen(uuid) != 36 || !device || !path || size < 6) return 0;
  *device = NODEV;
  path[0] = 0;
  if (!native_ram_block_ready) {
    // r24 (nuwa fork): the disk object never came up (see start()'s reject line).
    native_ram_block_seed_reason = 1;
    IOLog("NativeRamBlock: seed: driver not ready\n");
  }
  OSDictionary *matching = IOService::serviceMatching("IOMedia");
  OSDictionary *properties = OSDictionary::withCapacity(1);
  OSString *wanted = OSString::withCString(uuid);
  if (!matching || !properties || !wanted) {
    native_ram_block_seed_reason = 2;
    IOLog("NativeRamBlock: seed: cannot build the IOMedia match\n");
    OSSafeReleaseNULL(wanted); OSSafeReleaseNULL(properties); OSSafeReleaseNULL(matching);
    return 0;
  }
  bool ready = properties->setObject("UUID", wanted) && matching->setObject("IOPropertyMatch", properties);
  wanted->release(); properties->release();
  OSIterator *iterator = ready ? IOService::getMatchingServices(matching) : nullptr;
  matching->release();
  if (!iterator) {
    native_ram_block_seed_reason = 2;
    IOLog("NativeRamBlock: seed: no IOMedia service matched\n");
    return 0;
  }
  bool selected = false;
  unsigned matches = 0;
  dev_t candidate = NODEV;
  char candidatePath[64] = {};
  uint64_t base=0,bytes=0;uint8_t hash[32]={};
  while (OSObject *object = iterator->getNextObject()) {
    IOService *media = OSDynamicCast(IOService, object);
    if (!media) continue;
    if (++matches != 1) { selected = false; break; }
    OSString *identity = OSDynamicCast(OSString, media->getProperty("UUID"));
    OSString *name = OSDynamicCast(OSString, media->getProperty(kIOBSDNameKey));
    OSNumber *mjr = OSDynamicCast(OSNumber, media->getProperty(kIOBSDMajorKey));
    OSNumber *mnr = OSDynamicCast(OSNumber, media->getProperty(kIOBSDMinorKey));
    if (!identity || strcmp(identity->getCStringNoCopy(), uuid) || !name || !mjr || !mnr ||
        !name->getLength() || name->getLength() >= sizeof(candidatePath) - 6 || name->getLength() >= size - 6 ||
        mjr->unsigned64BitValue() > 255 || mnr->unsigned64BitValue() > 0xffffff) {
      if (matches <= 5) {
        IOLog("NativeRamBlock: seed: match %u rejected (identity=%d name=%d maj=%d min=%d)\n",
            matches, identity ? 1 : 0, name ? 1 : 0, mjr ? 1 : 0, mnr ? 1 : 0);
      }
      native_ram_block_seed_reason = 3;
      continue;
    }
    unsigned depth = 0;
    for (IOService *provider = media; provider && depth++ < 64; provider = provider->getProvider()) {
      NativeRamBlock *ram = OSDynamicCast(NativeRamBlock, provider);
      if (!ram) continue;
      ram->attachStore();
      if (!ram->seedInfo(&base,&bytes,hash)) {
        native_ram_block_seed_reason = 5;
        if (matches <= 5) IOLog("NativeRamBlock: seed: match %u has no usable seed\n", matches);
        continue;
      }
      candidate = static_cast<dev_t>(makedev(mjr->unsigned32BitValue(), mnr->unsigned32BitValue()));
      snprintf(candidatePath, sizeof(candidatePath), "/dev/%s", name->getCStringNoCopy());
      selected = true;
      break;
    }
  }
  iterator->release();
  if (!selected || matches != 1) {
    if (!native_ram_block_seed_reason) native_ram_block_seed_reason = matches == 0 ? 2 : 4;
    IOLog("NativeRamBlock: seed: matches=%u selected=%d reason=%u\n",
        matches, selected ? 1 : 0, native_ram_block_seed_reason);
    return 0;
  }
  IOLog("NativeRamBlock: seed: matches=%u selected=%d base=%#llx bytes=%#llx\n",
      matches, selected ? 1 : 0, base, bytes);
  *device = candidate;
  strlcpy(path, candidatePath, size);
  if(seedBase)*seedBase=base;
  if(seedBytes)*seedBytes=bytes;
  if(seedDigest)memcpy(seedDigest,hash,32);
  return 1;
}

extern "C" int native_ram_block_volume_device(const char *uuid,dev_t *device,char *path,size_t size) {
  return selectVolumeSeed(uuid,device,path,size,nullptr,nullptr,nullptr);
}
// The GPU addon the loader placed after the trust caches (/chosen/memory-map/GpuAddon, scripts/make-gpu-addon.py), for the kernel's
// boot-time addon install (kern_exec.c). Boot memory, like the seed: never freed here. Returns 0 without one.
extern "C" int native_ram_block_gpu_addon(const uint8_t **data,uint64_t *bytes) {
  if(!data || !bytes)return 0;
  *data=nullptr;*bytes=0;
  IORegistryEntry *map=IORegistryEntry::fromPath("/chosen/memory-map",gIODTPlane);
  if(!map)return 0;
  OSData *range=OSDynamicCast(OSData,map->getProperty("GpuAddon"));
  uint64_t physical=0,size=0;
  if(range && range->getLength()==16){
    memcpy(&physical,range->getBytesNoCopy(),8);
    memcpy(&size,static_cast<const uint8_t *>(range->getBytesNoCopy())+8,8);
  }
  map->release();
  if(!size || size>(UINT64_C(64)<<20) || (physical&4095) || physical<gPhysBase || size>gPhysSize || physical-gPhysBase>gPhysSize-size)return 0;
  *data=reinterpret_cast<const uint8_t *>(ml_static_ptovirt(physical));
  if(!*data)return 0;
  *bytes=size;
  return 1;
}

// r26 (nuwa fork): create the disk explicitly instead of waiting for the IOResources persona.
// On this port the persona is present in the built-in table (IOClass=NativeRamBlock,
// IOProviderClass=IOResources, IOResourceMatch=IOBSD) and the class is registered at boot, yet
// no instance was ever started (the diagnostic page showed ready=0, start() never entered) -
// the platform's asynchronous IOResources matching never reaches this class.  Doing what
// IOService::startCandidate() would do (alloc, init with no personality, attach to
// IOResources, start) removes that dependency; the resource gating startCandidate applies is
// skipped for gIOResources anyway, so nothing is bypassed that would have gated the disk.
// Returns 1 when the disk is started (start() sets native_ram_block_ready and registers the
// service, so IOStorageFamily can publish the media).  Failure codes go to
// nuwa_ram_block_reject: 10 alloc/init, 11 attach, 12 start() refused (its own code 1..9/14 is
// kept when it set one), 13 no IOResources.
// r28 (nuwa fork): the class registration has to happen between OSMetaClass::preModLoad() and
// OSMetaClass::postModLoad().  OSMetaClass::OSMetaClass() only stores the raw class-name
// string ("className = (const OSSymbol *)inClassName", OSMetaClass.cpp) and queues the
// metaclass; postModLoad() is what converts the name to a registered OSSymbol and records the
// class under the kext.  Calling __GLOBAL__sub_I_NativeRamBlock.cpp bare left className a
// plain char*, so OSMetaClass::getClassName() dereferenced the string as an object - the
// r26/r27 "Kernel data abort" (far inside the "NativeRamBlock" literal).  "__kernel__" is
// kOSKextKernelIdentifier (libkern/libkern/OSKextLib.h), the identifier the kernel's own
// OSRuntimeInitializeCPP() uses; OSKext::initialize() registers that kext object in
// sKextsByID, so postModLoad() can record the class under it.
extern "C" void nuwa_ram_block_ctor(void) __asm__("__GLOBAL__sub_I_NativeRamBlock.cpp");

extern "C" int native_ram_block_register_class(void)
{
  void *handle = OSMetaClass::preModLoad("__kernel__");
  OSReturn result;

  if (!handle) {
    IOLog("NativeRamBlock: register: preModLoad failed\n");
    return 0;
  }
  nuwa_ram_block_ctor();
  result = OSMetaClass::postModLoad(handle);
  IOLog("NativeRamBlock: register: postModLoad=%d\n", (int)result);
  return result == kOSReturnSuccess ? 1 : 0;
}

extern "C" int native_ram_block_start_service(void)
{
  IOService *resources = IOService::getResourceService();
  NativeRamBlock *ram;

  if (!resources) {
    nuwa_ram_block_reject = 13;
    IOLog("NativeRamBlock: create reject 13: no IOResources service\n");
    return 0;
  }
  ram = new NativeRamBlock;
  if (!ram || !ram->init(NULL)) {
    nuwa_ram_block_reject = 10;
    IOLog("NativeRamBlock: create reject 10: instance init failed\n");
    if (ram) ram->release();
    return 0;
  }
  if (!ram->attach(resources)) {
    nuwa_ram_block_reject = 11;
    IOLog("NativeRamBlock: create reject 11: attach(IOResources) failed\n");
    ram->release();
    return 0;
  }
  if (!ram->start(resources)) {
    if (!nuwa_ram_block_reject) nuwa_ram_block_reject = 12;
    IOLog("NativeRamBlock: create reject 12: start(IOResources) returned false (code %d)\n",
        nuwa_ram_block_reject);
    ram->detach(resources);
    ram->release();
    return 0;
  }
  // attach() keeps the provider's reference, as in IOService::probeCandidates(); the creator
  // drops its own reference here and the instance stays published under IOResources.
  ram->release();
  IOLog("NativeRamBlock: create ok: attached to IOResources and started\n");
  return 1;
}

extern "C" int native_ram_block_volume_seed(const char *uuid,dev_t *device,char *path,size_t size,
    uint64_t *base,uint64_t *bytes,uint8_t digest[32]) {
  if(!base || !bytes || !digest)return 0;
  *base=0;*bytes=0;memset(digest,0,32);
  return selectVolumeSeed(uuid,device,path,size,base,bytes,digest);
}
