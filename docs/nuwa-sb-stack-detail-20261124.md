# SpringBoard stackshot detail — host candidate, 2026-11-24

Host build, package and readback are **self-checked**. No device access or
write. Authentication **NOT REACHED**. Reviewer re-review is pending.

`nuwa-sb-stack=360` keeps the one-shot paint gate and static 1 MiB capture
buffer, with no retry on `r=52`. The flags add `STACKSHOT_SAVE_LOADINFO`
(`0x02`). `xnu-8796.141.3` (local source `1b191cb58250d0705d8a51287127505aa4bc0789`,
APSL-2.0), `osfmk/kern/{kern_stackshot.c,kcdata.h,debug.h}` and
`osfmk/kdp/ml/arm/kdp_machdep.c`, are the producer and layout references.
KCData array type/count/padding are checked, frames are scoped to their
thread container, and invalid buffers are not published.

* `ks` is `vm_kernel_slide`, `sc` is the shared-cache slide (task record,
  or the system record only when the task declares the system shared region),
  `sb` is the first `LOADINFO64` image-load address (not a slide). Zeroed or
  absent load-info yields `sb=-`; a reported zero shared-cache slide is valid.
  `SHOT2` restores all bits of `ks` and `sb` when any field overflows 32 bits,
  with `sc=` appended if its upper bits are also needed.
* The first four thread records in KCData order become `T0` through `T3`.
  `C` is the full continuation as emitted by XNU, already unslid. With no
  continuation, `K` uses the low 40 bits of up to two unslid kernel LRs
  (`ffffff` prefix implicit for kernel addresses on this target). `U` uses
  up to four recorded iOS user PCs/LRs, with the full 36-bit user VA in nine
  hex digits. `f` counts all recorded synchronous user frames; `!` means
  display capping or producer-reported user-backtrace truncation. Missing
  thread/frame fields use `-`; `f=0` means a thread with no user frames.
  The parser performs no task-memory reads; the producer can still access
  task memory and holds interrupts off during capture.
* `SHOT*` and `T0..T3` are **temporarily** priority 0 and emitted first, so
  normal priority-0 diagnostics cannot displace them within the row budget.
  `SHOT pending <seq>` is unchanged; the terminal block replaces the old
  redundant done row. Restore normal priority after the diagnostic round.

Measured host fixture widths: `SHOT` 38/52/55, `T0` 16/68, `T1` 16/53/78,
absent `T2`/`T3` 14 each, `SHOT2` 45/65 columns. The 78-column case
synthesizes a six-digit frame count. Physical panel rendering is unobserved.

## Repeat commands

From the device worktree in WSL Ubuntu-22.04 as root, use fresh output paths:

```sh
PY=/home/wh1stl3/.local/bin/python3.11
BASE=/mnt/d/Code/PortingiOS/UniXNU
CPO=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json
B=out/nuwa-sb-stack-detail-20261124-build
P=out/nuwa-sb-stack-detail-20261124-package
A=out/nuwa-sb-stack-detail-20261124-audit
"$PY" -B scripts/build-nuwa-display-native.py --base "$BASE" --cpo "$CPO" \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 --r35l-dir out/nuwa-r35l-regs-full-20261121 \
  --cpu-only --no-software-vsync --candidate --mg-reset --hid-standin --out "$B"
for t in test-sb-stack-row test-sb-stack-paint test-banner-budget test-banner-short-values; do
  "$PY" -B "scripts/$t.py"
done
for t in test-r35g-ux-linked test-r35k-regs-linked test-r35e-irqguard-linked; do
  "$PY" -B "scripts/$t.py" "$B/kernel.macho"
done
"$PY" -B scripts/repack-nuwa-smp-gate.py --sb-stack --kernel "$B/kernel.macho" \
  --kernel-sha256 "$(sha256sum "$B/kernel.macho" | cut -d' ' -f1)" \
  --output "$P" --audit "$A"
fsck.fat -vn "$A/actual-vendor-ramdisk.img"
mdir -i "$A/actual-vendor-ramdisk.img" ::/EFI/UniXNU/Payloads
```

Base UniXNU checkout `693f5d9cae8a408dd18b39f3f9fdc4228c934241`;
upstream HEAD before/after `8542980d02b4d2cc5c32ee3542de1760b2562aac`,
not adopted. No `--smp-gate` or `--smp-observe` used.

The outer-readback boot config is byte-identical to the pinned sb-stack3
baseline (507 args bytes, 26 tokens, SHA-256
`58dc839e9a1a06528ed53304a594d1732cbe85da533af2bb48a51662dabf0d5e`).
It includes `nuwa-hid-standin=1` and `nuwa-sb-stack=360` and has no
`nuwa-sb-restart*`, `sheng-smp`, or `sheng-data-reset`. The new CHMH is the
only ADT change; bytes outside the FAT are unchanged. The embedded seed
read back as `692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`.
`fsck.fat -vn`: 9 files, 106,239/129,022 clusters. `mdir`: 11,664,896 bytes free.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 (52,187,136 B) | `29e587209acaa60df0a5ca1e1eda1b49f765082119363d56a81c2ba0d73bc025` |
| Outer SHA-256 (100,663,296 B) | `959814ccb3864eb147ce30e47440337e5330e8273efa7b4a3434354c14f906e4` |
| CHMH SHA-384 | `21b4e33c09fddbd3261170da1adc8cdcd6350f23b723441377d3a253f80a624a3bd0f047bca2ddc6bccebb52b655e4db` |
| Outer-readback FAT SHA-256 (67,108,864 B) | `a9f357b12b5c128783bc13c74878c4d46b56087df912d8ddfa307e9d066f220b` |

Local package: `out/nuwa-sb-stack-detail-20261124-package/vendor_boot.img`.
Reviewer: recheck array scope and stride, main-image/load-info ordering,
address encoding, and visibility of the temporary priority block before
device use. Independent verifier: rerun the commands above.
