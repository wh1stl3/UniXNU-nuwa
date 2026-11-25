# nuwa display-client thread stage channel — 2026-11-25

**Host-only, self-checked.** No device access, flash, client deployment, or
change to initproc's program selection. The packaged PIX args have no
`nuwa-init`, so this package keeps `STAGE` dormant. The r17 binary is a separate
input (`c409ebba9e71dabb3f996d85ae175f18513441b118d116812c6af09123d67461`),
verified on the host but not embedded. Runtime behavior, display acceptance,
and authentication are not established. Startup/locking deep review and
independent rerun are pending.

## Wiring and checks

- `stage_channel()` generates the state, publisher and name snapshot from
  the pinned r35l banner. The channel owns one thread reference; replacement
  or the first action in `boot_progress_exit` detaches it and drops it outside
  the mutex. The banner samples an existing XNU thread name, displays the
  printable 40-character prefix, and hashes the same prefix into the repaint
  signature. Samples are best effort, not a receipt for each transition.
- `8796-nuwa-boot-progress.patch` gates the publisher in `kern_exec.c` before
  `proc_process_signature`: initproc, non-null `ip_new_thread`, exact
  `nuwa-init=display-client`. It does not change any exec decision.
- `--stage-channel` replays only those added source/header lines onto the
  recorded r35l inputs, uses a staged `-I` and `-ffile-prefix-map`, and
  changes one `kern_exec.o` link-list entry. Against the earlier PIX build,
  the 962-entry list has no other non-debug object differences:
  `bsd_init.o`, `ux_exception.o` and `ux_handler.o` contain output-path DWARF
  drift but are byte-identical after `llvm-strip --strip-debug`.
- The source/host fixture covers absent and extended boot-arg values,
  non-initproc, unpublished and unnamed threads, replacement/exit references,
  40-character rendering and name-sensitive repaint. PIX, DSP, PEER, banner
  budget, short values and linked crashcap regressions passed. ARM64
  disassembly and undefined-symbol deltas show that the new path parses and
  compares the arg, reads the existing thread name, and writes only diagnostic
  RAM/refcount/lock state and the existing framebuffer banner. No added
  filesystem, block-storage, DMA or MMIO write path.

## Package

`out/nuwa-stage-channel-20261125-package/vendor_boot.img` (100,663,296 B).
The audited outer head/tail and all unrelated FAT files match PIX. Only
`kernel.macho` and its ADT CHMH field changed. The 561-byte args and seed
match byte-for-byte; neither `sheng-smp` nor `nuwa-init` is present.
FAT remaining **11,021,824 B** (8 MiB floor); `fsck.fat -vn` agrees.
Rollback outer is the unmodified PIX package, SHA-256
`28d45ab6c3d7c5ec79cf14543af4836dadf04de7eddaa91fd876b36bc831dbcc`.

| Artifact | Digest |
|---|---|
| Kernel SHA-256 | `3279845f5bf6dc103cca8eabc19b6cf77537214c9b280941527a94b9d8d42f76` |
| Outer SHA-256 | `76d13854cceb7603798f3650c76aa6ab7d41dd63f5b2394a90c1631be08f2a5d` |
| CHMH SHA-384 | `d8098fe2a2d54365fc10f50d7189b5b2fcdbc104c0bea8ba9f9458d29017c97fa748314f31e1ef79b658f6467f21b2f3` |
| Outer-readback FAT SHA-256 | `74ed3d793559a7b5f8476725ef6e2abfd6ee72768c0a11311b367d8aa4ce3425` |
| Seed SHA-256 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

## Independent rerun

Use the single-core build command and pinned inputs from
[crashcap](nuwa-crashcap-20261125.md#reproduction) with `--pixsig --stage-channel`
and a fresh `B` (this run used `out/nuwa-stage-channel-20261125-build-r2`).
Retained UniXNU checkout: `693f5d9cae8a408dd18b39f3f9fdc4228c934241`; upstream
HEAD before/after build: `b04f131da9151182dbb26ce4e638fa8acc2933ac`.
For a fresh package choose a fresh `P`; FAT/outer hashes can vary with mtools
timestamps.

```sh
"$PY" -B tests/test-nuwa-stage-channel.py
"$PY" -B tests/test-nuwa-crashcap.py "$B/kernel.macho"
llvm-objdump --macho --disassemble --symbolize-operands "$B/kern_exec.o"
llvm-objdump --macho --disassemble --symbolize-operands "$B/BootProgress.o"
MAKEFLAGS=-j1 taskset -c 0 "$PY" -B scripts/package-nuwa-crashcap.py \
  --stage-channel --base "$BASE" --kernel "$B/kernel.macho" --out "$P"
"$PY" -B scripts/package-nuwa-crashcap.py --stage-channel --audit-only \
  --base "$BASE" --kernel "$B/kernel.macho" --out "$P"
fsck.fat -vn "$P/readback-fat.img"
```
