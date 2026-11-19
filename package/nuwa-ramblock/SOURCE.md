# package/nuwa-ramblock — fork of the upstream RamBlock driver

Upstream: `UniXNU/drivers/RamBlock` @ `4be2d7eb05ef5a98126c91e0302c149140c0e3e1`
("fix(persist): make the Data store anew only on Install and boot"), BSD-2-Clause-Patent
(that component's `LICENSE`). Only `NativeRamBlock.cpp` is copied here; `SparseDisk.h`,
`PersistOverlay.h`, `DirectDisk.h` and `SeedDisk.h` are used from the upstream checkout,
which stays on the compiler's include path.

Fork reason (r24): diagnostics only. The Data volume has never mounted on nuwa; the r23 row
(`DATA mnt st=0 err=2 ro=-1 dev=ffffffff seed=0 devpath=- pub=0 serr=1`) can only say "the
seed lookup failed", and the packaged ADT carries `PackedRAMDisk = {0,0}` while the loader is
the only writer of that entry. The fork adds:

* `IOLog("NativeRamBlock: start packed=%d pa=… bytes=… gphys=…")` before the range check, so
  one line says exactly what the kernel was handed;
* a coded `IOLog` at every `return false` of `NativeRamBlock::start()` (1 base-class start,
  2 no `/chosen/memory-map`, 3 both RAMDisk and PackedRAMDisk, 4 range, 5 ptovirt/lock,
  6 packed layout, 7 seedCountNonzero, 8 big sparse import, 9 sparse import) and one line on
  success (`ready logical=… packed=… resident=…`);
* `native_ram_block_seed_reason` (1 driver not ready, 2 no matching IOMedia, 3 match without
  UUID/BSD properties, 4 no NativeRamBlock provider, 5 no usable seed) plus `matches/selected`
  lines in `selectVolumeSeed()`, which the kernel-side mount reports as the DATA row's `serr`.

No behaviour change: every added statement is an `IOLog` or a write to the reason variable; no
branch condition, allocation, lock or ordering changed. The fork can be dropped once the Data
seed path is understood — keep the two files identical otherwise so a diff stays one screen.
