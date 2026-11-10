# nuwa stage5 + panic screen, 2026-11-10

Status: **independent verifier PASS** (parent-delivered result), **not device-tested**.
Device HEAD `982e92e67c0e266987a786865f53e9cd120a159c` plus current board/docs
changes; base `693f5d9cae8a408dd18b39f3f9fdc4228c934241`. No source changes,
crypto-mode switch, kernel/prelink rebuild, device command, commit or push.
Shared SESSION-HANDOFF is updated only during final handoff, outside this device commit.

## Observation and experiment boundary

Prior authorised run: `.cache/media/stage4-console-after-20261110-180641/execution.log`.
Lines 1-98 record vendor_boot SHA256
`3f46e8a8dd213babec939e081d3273d17a03023e4fab107e22b07922d625a02a`,
nuwa identity, B-only write/full readback and one r4 boot, commands rc=0.
User observation at line 100: three bars then approximately six-second reset.
This proves **b-round console returned only**, not normal boot. Lines 143-155
record A/TWRP current/active=0; no new device query in this task.

Parent relays Reviewer **PASS WITH CONDITIONS** for this existing configuration:
`kernel_args=["-v","serial=3","sheng-platform-stage=5"]`, `panic_screen=true`,
`entry_probe_reset_delay=0`; remove after/in/occurrence/before selectors.
Assembly actually invokes `--panic-screen --no-reset`.
Existing `drivers/ArmDTPlatform/ArmDTPlatform.cpp:191-208` creates nubs then
calls `registerService()`; stage5 resets immediately after that call returns.
There is **no six-second delay**, and no `sheng-platform-panic` argument.

Hypothesis: continue past console toward platform-service publication, while
rendering a panic if one occurs earlier. Positive stage5 reset proves only the
return after `registerService()`; capture/rendered panic text would identify a
different failure. No reset/text is ambiguous (unreached stage, stalled call,
exception/renderer/mapping failure); do not equate it with a unique root cause
or schedule further low-value function probes. Parent decides subsequent action.

## One assembly, separate ext4 output

WSL Ubuntu-22.04, cwd `/mnt/d/Code/PortingiOS/UniXNU`.
PATH `/home/wh1stl3/.local/bin:/opt/unixnu-linux/bin:/opt/unixnu-linux/llvm/bin:/usr/local/bin:/usr/bin:/bin`;
TMPDIR `/home/wh1stl3/nuwa-stage5-panic-20261110/tmp`.
Driver `.cache/run-stage5-panic-host-20261110.sh` ran once, rc=0,
18:19:59–18:20:19 +08:00; `payload_rc=0`, `vendor_boot_rc=0`.
Exact assembly commands (variables expanded here):

```sh
./unixnu build payload -D /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa --out /home/wh1stl3/nuwa-stage5-panic-20261110/out --kernel /mnt/d/Code/PortingiOS/UniXNU/out/nuwa/ios-16.7.16-20H392/nuwa/kernel/kernel.macho --uefi /mnt/d/Code/PortingiOS/nuwa/uefi-nuwa --trust-cache /mnt/d/Code/PortingiOS/UniXNU/out/ipsw/20H392/087-86698-044.dmg.trustcache.bundle
./unixnu vendor_boot --stock /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/.cache/stock/vendor_boot_b.img --ramdisk /home/wh1stl3/nuwa-stage5-panic-20261110/out/nuwa/ios-16.7.16-20H392/nuwa/payload/payload.img -o /home/wh1stl3/nuwa-stage5-panic-20261110/out/nuwa/ios-16.7.16-20H392/nuwa/vendor_boot/vendor_boot.img
```

The unique ext4 output reuses existing `out/feeds` via symlink and copies the
existing `.config`; it does not replace the tested candidate. Cached module
preparation did not rebuild kernel/prelink. Source files were not edited.
Original prelink remains 55357440 B SHA256
`da0d660f8336fa87825ec34ce1f48b653d728a6277aaf7d4b03784cf4f73c969`.
Tested payload `ce67228d9ea6588aedecc5af1b74faf428c91a15c203f5c35856fe4bef388be2`
and vendor_boot `3f46e8a8dd213babec939e081d3273d17a03023e4fab107e22b07922d625a02a`
remain intact in base `out/nuwa/ios-16.7.16-20H392/nuwa/` (hash-checked before/after).

## Final FAT audit (rc=0, self-checked)

`.cache/run-stage5-panic-check-20261110.sh` runs
`.cache/check-stage5-panic-host-20261110.py`; final log `audit-final.log`.
First audit attempt stopped at renderer comparison because direct API use lacked
`UNIXNU_UEFI` (exit 1); the audit now sets it explicitly. No candidate rebuild.

- FAT-extracted console site `0xfffffff0079993bc`: word `0x97ff3ee8`, original
  BL `0xfffffff007968f5c`; post-MMU `0xfffffff0073f0370` remains `0xd2a00600`.
  All byte changes from source are confined to entry/MMU bars and panic hooks/code,
  **no stage3/4 reset**. Stage3/4's old cave addresses now lie inside the renderer,
  so they must not be checked for zero padding as in the old reset-only candidate.
- Renderer recompiled freestanding for byte comparison only (not kernel/prelink):
  **0xa0f B** at `0xfffffff0073ee5c0`, exclusive end `0xfffffff0073eefcf`,
  fixed boundary `0xfffffff0073eeff0`, capacity **0xa30**, spare **0x21 B**.
  Final FAT bytes equal renderer binary; unused tail is zero; source padding
  was zero. No boundary or cave change/check bypass. Historical `0xa2f` is not
  substituted for this actual toolchain measurement.
- `_panic=0xfffffff00798d8bc`: word `0x17e98341` branches to ordinary entry
  `0xfffffff0073ee5c0` (`mov x1,sp`, Darwin variadic stack slots).
  `_panic_trap_to_debugger=0xfffffff00726c174`: word `0x14060915` branches to
  common entry `0xfffffff0073ee5c8` (`ldr x1,[x1]`, Darwin `va_list*`). Both
  branch to main `0xfffffff0073ee8ac`; ordinary/common ABI bytes checked.
- `_vinfo=0xfffffff007a3d738` is resolved from this prelink, no board observer
  override. Renderer compiled against that value; retained ELF/disassembly in
  `audit-final/renderer/` and `audit-final/renderer.disasm.txt`.
- FAT `unixnu.toml` has exactly one XNU entry and exact arguments
  `-v serial=3 sheng-platform-stage=5`; no old stage/panic argument.
- Payload/vendor manifests match actual hashes, including original/patched kernel;
  vendor ramdisk is byte-identical to payload, 67108864 B; padded vendor image
  100663296 B equals stock/recorded partition size.
- ADT/trust content evidence reused from b-round/prior verifier; not a new full
  validation. ADT random seed can differ per assembly. No normal boot,
  early/nested panic, persistence, coredump or nonzero slide validation.

## Crypto correction

`configs/nuwa_defconfig:3,7` retains source library selection but
`CONFIG_XNU_CRYPTO_BOOTSTRAP="prelinked"`. Actual b-round compile record
`tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/osfmk/DEVELOPMENT/prng_random.o.json`
contains `XNU_SOURCE_CORECRYPTO14=1` earlier, then **final `-U XNU_SOURCE_CORECRYPTO14`**
(arguments indices 34 and 398). Symbol table and bytes of the source prelink
contain no `_source_corecrypto14_bootstrap`. Therefore the prior assertion that
source corecrypto EARLY_BOOT must follow console was incorrect. No crypto switch.

## Artifacts and verifier commands

Primary ext4 root: `/home/wh1stl3/nuwa-stage5-panic-20261110/`.
Host copy: `D:/Code/PortingiOS/nuwa/UniXNU-nuwa/out/stage5-panic-20261110/`.
Export driver rc=0; five candidate/manifest/kernel copies SHA-compared.
Below paths relative to host copy; ext4 payload/vendor are under
`out/nuwa/ios-16.7.16-20H392/nuwa/`, audit under ext4 root.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| `payload/payload.img` | 67108864 | `229abb3fc45b088a8daebb7350e56cf7690aa494c7a6d8304c66da1841391b4f` |
| `vendor_boot/vendor_boot.img` | 100663296 | `998d284ad4959aebdb1a7f26d161eea5b2a49fe169264a843f19708ec522bea5` |
| `audit-final/kernel.macho` | 55357440 | `fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd` |
| `payload/payload.json` | 667 | `a6114feab4ad3d266d90ad738d56bcb3f1a600f0c2c9f659ebbff348f447f8b5` |
| `vendor_boot/vendor_boot.json` | 411 | `c13d257d07ff76fcfa531c8b8ca4feffe05e72751c16b3894bb58c58d9264668` |

Evidence: copied `assembly.log`, `audit-final.log`, `audit-final/artifact-hashes.json`,
`audit-final/measurement.json`, ELF/disassembly, and audit/driver scripts. Generated
files are ignored/local only; no Apple-containing artifact may be uploaded.

Verifier: **do not rerun assembly or any device script**. Rerun only final
read-only candidate audit into a fresh directory (freestanding renderer comparison
is allowed; kernel/prelink build is not), then record/diff checks:

```powershell
wsl -d Ubuntu-22.04 -- env PATH=/home/wh1stl3/.local/bin:/opt/unixnu-linux/bin:/opt/unixnu-linux/llvm/bin:/usr/local/bin:/usr/bin:/bin TMPDIR=/home/wh1stl3/nuwa-stage5-panic-20261110/tmp python3 -u /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/.cache/check-stage5-panic-host-20261110.py /home/wh1stl3/nuwa-stage5-panic-20261110/verifier-audit
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/UniXNU -- /home/wh1stl3/.local/bin/python3 scripts/porting-record.py check --device ../nuwa/UniXNU-nuwa --base origin/main
git -C D:/Code/PortingiOS/nuwa/UniXNU-nuwa diff --check
```

Also independently hash the host copies against the table (audit reads ext4), and
inspect the retained disassembly/ABI/bounds rather than relying only on PASS text.
Host record check above ran from base cwd, rc=0: `nuwa: 14 structured areas checked`;
`git diff --check` from device cwd rc=0. Both are **self-checked**, not an
independent verifier result. `git check-ignore` confirms candidate output and
local audit scripts are ignored. Existing unrelated dirty items were not cleaned.
Final integration and device authorisation remain with parent; independent host
verification completion is recorded below.

## Independent verification completion

Parent delivered Verifier **PASS** on 2026-11-10: the documented read-only audit
was independently rerun into `verifier-audit`, rc=0. It confirmed original
console BL/post-MMU instructions, no stage3/4 reset, ordinary `mov x1,sp` and
common `ldr x1,[x1]` entries branching to main, correct vinfo, renderer 0xa0f
with 0x21 spare, and matching manifests/hashes. Source prelink hash matches.
`porting-record.py check` independently checked 14 areas, rc=0;
device `git diff --check` independently rc=0. No kernel/prelink rebuild.

ADT/trust evidence was reused. Old candidates exist, but Verifier did **not**
rehash them this pass; their unchanged hashes above are implementer self-checks.
This PASS is a host incremental validation only, not runtime/panic-rendering or
stage5 acceptance. New candidate remains unbooted; area levels are unchanged.
The subsequent documentation/status-only edits receive implementer checks;
they are not claimed as a new independent verifier run.
