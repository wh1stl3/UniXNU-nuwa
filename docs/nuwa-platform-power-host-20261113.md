# Nuwa guarded PMGR provider host build — self-checked

Historical r2 archive record below is preserved. Current source now takes an
explicit borrowed root-publication parent; the isolated kernel delivery and
incremental checks are in [the kernel checkpoint](nuwa-platform-power-kernel-20261113.md).
That new link is self-checked, not covered by the old archive's acceptance.

Guarded software provider + original nub for the pinned iOS16 nuwa carrier.
Default off (`nuwa-pmgr` boot-arg). No power hardware, no publication runtime,
no device run. This unit is host code / build artifact / test evidence only; no
outer packaging or executor, and no CHMH recompute (that is a separate unit
after the kernel changes).

## r2 changes (review CHANGES REQUIRED, two fixed issues)

1. **LC_DYSYMTAB partition fix** (`late_transform`): the r1 edit only flipped
   N_EXT on the static-initializer symbol (index 6) while LC_DYSYMTAB still
   listed it in the local partition (0–172), leaving an external symbol inside
   the local range. r2 moves the symbol to the last local slot (index 172) by
   swap, remaps every relocation referencing either swapped index, sets N_EXT,
   and tightens the local partition (nlocalsym 173→172, iextdefsym 173→172,
   nextdefsym 21→22) so exactly one symbol crosses the boundary. The late object
   is then re-parsed to assert every symbol's N_EXT is consistent with its
   partition, `__GLOBAL__sub_I_NuwaPlatformPower.cpp` is an external defined
   symbol in the extdef partition, `__mod_init_func` has nreloc=0, and `__text`
   is byte-identical to the compiled object.
2. **Test coverage wording and `write_aon_empty_return`**: the test now reports
   exactly what it does — 4 carrier instruction-stream cases executed under
   unicorn (mock object data only), 2 compiled-object symbol-presence checks,
   1 JSON bindings check — and states that the 325-slot vtable resolution is a
   build-time static check, not executed here. `write_aon_empty_return` asserts
   final PC == return slot, x0 untouched, and mock memory unchanged.

## Carrier and ABI

- Carrier: `out/pthread-renderer-20261112-r1/renderer-baseline.macho`,
  SHA256 `e0c235f1de499c858d6eb672f989de7692f1d97140e1064da59391642fa11f5d`.
- ApplePMGR provider: 0x36968 storage, 325 vtable slots at
  `0xfffffff005c9faf8`. Slot 312 readAon = `0xfffffff004681e04` (returns
  0xffffffff), slot 313 writeAon = `0xfffffff004681e0c` (empty return), slot
  325 = 0 (table end).
- AMFI imports the original nub read/write through `0xfffffff005cb56b8` and
  `0xfffffff005cb56c0`.
- The fuxi iOS16 hint (provider 0x36968 / 325 slots) was verified against this
  carrier; the fuxi build script's old verifier/AMFI addresses and iOS17 target
  are not reused.

## Deliverables

- `package/NuwaPlatformPower.cpp` — the guarded provider subclass of ApplePMGR.
  All power slots 168-324 except 312/313 panic on `unavailable(slot)`; readAon
  and writeAon inherit the carrier's real implementations. Empty
  devices/soc-devices (description setName only). Real metaclass and the AMFI
  consumer are untouched.
- `scripts/build-nuwa-platform-power.py` — verifies the carrier ABI, generates
  `OriginalPMGRABI.h` + `GuardedPMGRSlots.inc`, compiles with the native Linux
  clang-24 toolchain (compile record `IOPMGR.cpo.json`), checks all 325 vtable
  relocations against original/native symbols, and emits `libNuwaPlatformPower.a`
  + `build-report.json`. The system llvm-objcopy (LLVM 14) lacks Mach-O
  `--remove-section`/`--globalize-symbol`, so the symbol move and `__mod_init_func`
  disable are done in place and re-verified. `--out` selects a fresh directory
  (default `out/nuwa-platform-power-20261113-r2`).
- `scripts/test-nuwa-platform-power.py` — unicorn executes the carrier's actual
  nub read/write and readAon/writeAon bytes with only the provider/nub object
  data mocked, plus re-checks the compiled object symbols and bindings.

## Artifacts (under `out/`)

| File | SHA256 |
| --- | --- |
| `nuwa-platform-power-20261113-r2/libNuwaPlatformPower.a` | `568885fd698489843701907e5d8216f3c9b377c678a2d6710bd8652bad93d29e` |
| `nuwa-platform-power-20261113-r2/NuwaPlatformPower.o` | `abec6ed6c37fddb6bffeea527e1568c98ff826b7496326676aebe9e16fc97eb1` |
| `nuwa-platform-power-20261113-r2/NuwaPlatformPower.late.o` | `6b719ab5ad506021f5fe461cbc7ee223db76103830b8df5aee45b2baf75596b2` |
| `nuwa-platform-power-tests-20261113-r2/tests.json` | 7/7 passed |

## Reproducibility note (archive SHA differs by output path)

An independent rebuild into a different `--out` directory can change DWARF
content and object layout because debug information includes the generated-header
path. The r2 verifier observed changes in both `__debug_line` and `__debug_info`,
including section-address and symbol-value offsets; debug section sizes need not
stay fixed. `__text`, every non-debug section's contents, and `original-bindings.o`
were byte-identical in that independent comparison
(`original-bindings.o` SHA256 `98c02ab274fd83a6a90a7c61dde043a6d6ddf78380698844977cb0afa7e44e26`
in both r1 and r2). The archive SHA therefore differs across output paths; the
verifier should compare non-debug contents, relocation semantics (including target
symbol identity), and the 8 bindings, not require a
full-archive hash match. No `-fdebug-prefix-map` exists in the compile record, so
no prefix map is added.

## Commands (WSL Ubuntu-22.04 root, cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`)

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/build-nuwa-platform-power.py --out out/nuwa-platform-power-20261113-r2
/home/wh1stl3/.local/bin/python3.11 -B scripts/test-nuwa-platform-power.py --build out/nuwa-platform-power-20261113-r2 --output out/nuwa-platform-power-tests-20261113-r2/tests.json --python-tools /home/wh1stl3/.local/lib/python3.10/site-packages
```

Both exit 0 (self-checked). `py_compile` and `git diff --check` exit 0.

## Limits

- Publish/refusal lifecycle is not executed; the test only runs the carrier
  instruction streams and the compiled object symbol-presence/bindings checks.
  The 325-slot vtable resolution is a build-time static check.
- No power hardware is claimed; no guessed MMIO; the original executable is
  unmodified.
- The new kernel must recompute CHMH before packaging; this unit does not build
  an outer image and does not touch the executor.
- Ordinary review and independent verifier are arranged by the parent; this is
  self-checked, not accepted.
