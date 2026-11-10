# nuwa panic fallback: host build, 2026-11-10

Status: final payload **self-checked**; final injection awaits independent verifier.
Parent reports Deep Reviewer **APPROVE WITH CONDITIONS** and independent verifier
PASS for the b-round kernel/prelink artifact audit (not a kernel/prelink rebuild).
No hardware release or acceptance is implied.
Device HEAD: `bea5465d4e599f773baf3f4985aef5e5408ab467`, plus the uncommitted
fallback patch, series, defconfig and porting record. Base HEAD:
`693f5d9cae8a408dd18b39f3f9fdc4228c934241`. No base source, firmware submodule,
device changes. This completion changes the board probe and builds payload only;
no kernel/prelink rebuild, base source edit, device operation or push.

## Commands and results

WSL Ubuntu-22.04, cwd `/mnt/d/Code/PortingiOS/UniXNU`; PATH includes
`$HOME/.local/bin`, `/opt/unixnu-linux/bin`, `/opt/unixnu-linux/llvm/bin`.
Executed in background through device `.cache/run-panic-host-20261110-{a,b}.sh`:

```sh
./unixnu defconfig nuwa_defconfig -D ../nuwa/UniXNU-nuwa
./unixnu build kernel -D ../nuwa/UniXNU-nuwa
./unixnu build prelink -D ../nuwa/UniXNU-nuwa
```

Initial a round: all rc=0, but invalid fallback candidate: actual compile record
lacked the guard. `makedefs/MakeInc.def` in 8796 ignored `CFLAGS_EXTRA`, which
`scripts/build-xnu-4k-baseline.sh:828` already passes. Added its consumption to
the device patch, without changing the fallback guard or lifetime design.
Final b round reused defconfig; apply check, kernel and prelink all rc=0;
kernel 01:16:10–02:18:26 +08:00, prelink finished 02:18:51.
Logs: device `.cache/panic-host-20261110-b/driver.log:3-15` and
`{kernel,prelink}.log`.

The MakeInc fix also restores existing script defines `XNU_NATIVE_PAN=1`,
`XNU_SOURCE_CORECRYPTO14=1`, `XNU_BOOT_PROGRESS=0`. These are not new defconfig
choices, but their newly effective compilation must be included in independent
review; this is not a claim that the only binary difference is panic storage.
PAN is effective before console; source corecrypto EARLY_BOOT is after this
terminating probe and has not executed at its stop. Guard absent/0 preserves only
the panic branches, not the behavior of the entire MakeInc wiring.

Old native/prelink/manifest/config inputs were copied and SHA-compared before
each round to unique base `out/nuwa/ios-16.7.16-20H392/nuwa/` directories
`before-panic-host-20261110-a/` and `before-panic-host-20261110-b/` (seven files
each, `backup-manifest.json`). No old `.v*` backup was overwritten.

Final paths below are relative to that same base out directory:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped` | 17316552 | `1b5ca08125ac1e5e10b5487bdd3b01fdc1f61d60b730d94fba5170f105996a27` |
| `kernel/kernel.macho` | 55357440 | `da0d660f8336fa87825ec34ce1f48b653d728a6277aaf7d4b03784cf4f73c969` |

## Four conditions: static evidence

Evidence directory E = device `.cache/panic-host-20261110-b/` (local, ignored).
Read-only audit command, rc=0:

```sh
python3 ../nuwa/UniXNU-nuwa/.cache/audit-panic-host-20261110-a.py
```

1. **Actual compiler arguments:** `E/01-compile.txt:24-38,447` and original
   `E/pe_init.compile-record.json:1`. Exactly one effective
   `-DXNU_NUWA_PANIC_FALLBACK=1`; no undefine/redefinition. All seven default
   warning flags are present. The two pre-existing warning flags also occur
   in CFLAGS_GEN; uniqueness is required for the fallback macro, not warnings.
2. **Storage and fixups:** `E/02-storage-fixups.txt` records both images.
   Buffer VA `0xfffffff007ab4448`, `__DATA,__bss`, max/initprot=3, divisible by
   eight; not BOOTDATA/KLD/DATA_CONST. DWARF `E/pe_init.dwarf.txt:4331-4355`
   gives union size `0x4000` and header at offset zero; header size is `0xa1`
   (`E/header.dwarf.txt`). `panic_text_len` is optimized to constant `16223`
   (`0x3f5f`), not a linked variable (`E/pe_init.dwarf.txt:4434-4439`).
   `gPanicSize` at `0xfffffff0079d07d8` contains `0x4000`.
   `gPanicBase` at `0xfffffff0079d07d0` and `panic_info` at
   `0xfffffff0079d07e0` both resolve to the buffer. Their local relocation
   indices are 48784/48785, r_address `0x9cc7d0`/`0x9cc7e0`, info `0x06000024`:
   ARM64_RELOC_UNSIGNED, eight-byte, nonexternal, non-PC-relative, target
   section 36 (`__DATA,__bss`). Each occurs once among 58052 local sites.
   This image has an **empty** `__thread_starts` and no LC_DYLD_CHAINED_FIXUPS;
   these words are full addresses only after establishing that actual format,
   not interpreting a threaded/chained encoded word as a VA. Native VAs and
   fixups are unchanged by prelink; neither site is among 48371 unique kext
   KASLR sites. Current DarwinBoot retains link VAs (`DarwinBoot.c:739-745`),
   so native slide is zero, with neither missing nor duplicate adjustment on
   that path. No nonzero KASLR execution is validated. Source lifetime mapping
   evidence: `E/05-source-lifecycle.txt`, XNU `arm_vm_init.c:1422,1652-1672`:
   ordinary DATA is RWNX; the discarded regions are BOOTDATA/KLD/KLDDATA.
3. **Normal flow preserved:** `E/03-console-debug-header.disasm.txt:1-14`
   contains the complete seven-instruction `_PE_create_console`, ending in
   a tail branch to `_initialize_screen` at `0xfffffff0073bc370`, with the
   normal display-mode selection and no fixed-PA mapping or panic-buffer clear.
   It does not materialize `0x3c0fc000` or call `_ml_io_map_wcomb`.
   `_debug_log_init` remains at `0xfffffff00726b0e4` (lines 105–130), uses
   base+`0xa1` and size−`0xa1`, and is called from `_machine_init` (line 249).
   `_PE_init_panicheader` remains at `0xfffffff0079691fc` (lines 132–191),
   clearing only the header and setting offset/magic/version; retained BL
   sites are appended under `PANIC HEADER CALL SITE` in the same file.
4. **New probe site:** `E/04-new-probe-site.txt:2-5`:
   `_arm_init` BL at `0xfffffff0079993bc` calls `_PE_create_console` at
   `0xfffffff007968f5c`; continuation `0xfffffff0079993c0`, occurrence 1.
    The final payload uses this post-return selector, before=false, delay=6,
    occurrence=1, panic_screen=false. The script reparses the b-round kernel;
    the old fixed-PA map and post-map selector no longer exist.

## Final diagnostic assembly (2026-11-10)

WSL Ubuntu-22.04, cwd `/mnt/d/Code/PortingiOS/UniXNU`,
`PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin`. Both commands rc=0:

```sh
./unixnu build payload -D ../nuwa/UniXNU-nuwa --uefi ../nuwa/uefi-nuwa --trust-cache out/ipsw/20H392/087-86698-044.dmg.trustcache.bundle
./unixnu vendor_boot --stock ../nuwa/UniXNU-nuwa/.cache/stock/vendor_boot_b.img --ramdisk out/nuwa/ios-16.7.16-20H392/nuwa/payload/payload.img -o out/nuwa/ios-16.7.16-20H392/nuwa/vendor_boot/vendor_boot.img
```

Before assembly, all four old payload/vendor_boot IMG/JSON files were exclusively
created and byte-compared as `.v9`; `.v1`–`.v8` untouched. Backup hashes are in
`out/nuwa/ios-16.7.16-20H392/nuwa/console-after-fallback-backup-20261110.json`.
Temp LF driver: `%LOCALAPPDATA%/Temp/opencode/nuwa-final-payload-20261110.sh`;
its `.log` ends `FINAL ASSEMBLY RC=0` (background completion received).

Paths below are relative to `UniXNU/out/nuwa/ios-16.7.16-20H392/nuwa/`:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `payload/payload.img` | 67108864 | `ce67228d9ea6588aedecc5af1b74faf428c91a15c203f5c35856fe4bef388be2` |
| `vendor_boot/vendor_boot.img` | 100663296 | `3f46e8a8dd213babec939e081d3273d17a03023e4fab107e22b07922d625a02a` |
| `console-after-fallback-audit-20261110/kernel.macho` | 55357440 | `8f727f1093da34dda97bf047c68d97d9c54c23a846bbe210f3f92d1b332afef7` |
| `payload/payload.json` | 645 | `4ba840bf6c8a9f0c1dcea096bc68bf03414472cd6c749676cd1ea0de64e93a90` |
| `vendor_boot/vendor_boot.json` | 411 | `092634e34e0b20d2e16968e46158fa46b973c49bf8da28db8f3796e50bbd7257` |

Self-check command (rc=0):
`python3 -u /mnt/c/Users/Administrator/AppData/Local/Temp/opencode/nuwa-final-console-audit-20261110.py`.
Same-name `.log` contains disassembly and manifest comparison; local out audit
directory retains the FAT-extracted kernel and `artifact-hashes.json`.
The check confirms source prelink remains 55357440 B / `da0d660f...` (full hash
above); final FAT kernel agrees with payload manifest, and payload/vendor image
sizes/hashes agree with manifests. Vendor ramdisk is byte-for-byte the payload;
64 MiB payload <96 MiB partition, stock-padded vendor image =96 MiB.
ADT/trustcache content validation is reused from b-round/previous verifier
evidence, not claimed as a fresh full audit; ADT random-seed changes per build.

New instruction evidence for independent verifier (check final extracted bytes
only; do not rebuild kernel/prelink or repeat the full b-round artifact audit):

- `0xfffffff0079993bc`: `0x17e95499` B `0xfffffff0073ee620`.
- `0xfffffff0073ee620`: `0x9415ea4f` BL `0xfffffff007968f5c`.
- Cave `+4`/`+0x14`: CNTPCT_EL0 reads; `+8` loads literal at
  `0xfffffff0073ee660` = `115200000` (`0x06ddd000`); unsigned wait loop.
- `0xfffffff0073ee640/644`: construct `w0=0x84000009`; `+0x34`
  (`0xfffffff0073ee654`) word `0xd4000003` = SMC #0 (system objdump prints
  unknown, checked by exact encoding). `0xfffffff0073ee658/65c`: WFE / B WFE.
- Original continuation `0xfffffff0079993c0` is unchanged, but never resumed.
  A reset would establish only that console returned, not complete boot success;
  absence of reset is inconclusive. This is a terminating diagnostic, not a
  continuation hook.

For the final independent increment, verifier should disassemble the site/cave
above with `llvm-objdump -d --start-address=... --stop-address=... <final kernel>`
and independently decode/compare those bytes and tick literal. The self-check
script's exclusive output directory deliberately prevents accidental overwrite;
it is not a rerunnable verifier command without a fresh output directory.

The parent-reported host review/audit does not validate early/nested panic,
coredump, nonzero slide, persistence or device behavior. Fallback is volatile,
not persistent panic storage. Final payload remains **self-checked** only until
verifier checks this final injection. Integration and acceptance belong to parent.
