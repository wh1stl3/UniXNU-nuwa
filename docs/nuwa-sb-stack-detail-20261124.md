# SpringBoard stackshot detail — host candidate rev 2, 2026-11-24

Host build, package and readback are **self-checked**. No device access or
write. Authentication **NOT REACHED**. Reviewer re-review is pending. Rev 2
supersedes `99fc672`, addressing the wait-only selection and record-presence findings.

`nuwa-sb-stack=360` keeps the one-shot paint gate and static 1 MiB capture
buffer, with no retry on `r=52`. The flags add `STACKSHOT_SAVE_LOADINFO`
(`0x02`). `xnu-8796.141.3` (local source `1b191cb58250d0705d8a51287127505aa4bc0789`,
APSL-2.0), `osfmk/kern/{kern_stackshot.c,kcdata.h,debug.h}` and
`osfmk/kdp/ml/arm/kdp_machdep.c`, are the producer and layout references.
KCData array type/count/padding are checked, frames are scoped to their
thread container, and invalid buffers are not published.

* `ks` is `vm_kernel_slide`, `sc` is the shared-cache slide (task record,
  or the system record only when the task declares the system shared region),
  `sb` is the first `LOADINFO64` image-load address (not a slide). No element
  (including a zero-count array) means `sb=-`; a present zeroed element means
  `sb=0!`. `sc` has its own presence bit: zero slide prints `sc=00000000`.
  `SHOT2` restores all bits of `ks` and `sb` when any field overflows 32 bits,
  with `sc=` appended if its upper bits are also needed.
* Only threads with `TH_WAIT` fill `T0` through `T3`, in KCData order.
  The number of populated thread rows is `min(w,4)`; `Tn -` fills the
  remaining slots. The list is all threads only if `n==w` **and** `n<=4`.
  `C` is the full continuation as emitted by XNU, already unslid. With no
  continuation, `K` uses the low 40 bits of up to two unslid kernel LRs
  (`ffffff` prefix implicit for kernel addresses on this target). `U` uses
  up to four recorded iOS user PCs/LRs, with the full 36-bit user VA in nine
  hex digits. `f` counts all recorded synchronous user frames, not the
  number displayed. No user-frame record is `U=- f=-`; an explicitly empty
  array is `U=- f=0`. A recorded zero address is `000000000`, not missing.
  `!` means more than four display slots are needed or the producer set
  the user-truncation bit (even with no frame record); it gives no cause.
  The parser performs no task-memory reads; the producer can still access
  task memory and holds interrupts off during capture.
* `SHOT*` and `T0..T3` are **temporarily** priority 0 and emitted first, so
  normal priority-0 diagnostics cannot displace them within the row budget.
  `SHOT pending <seq>` is unchanged. A successful result occupies five rows
  (six with `SHOT2`); an error occupies one. Restore normal priority after
  the diagnostic round.

The host fixtures exercise runnable-before-waiting ordering, padding with
fewer than four waiters, the four load-info and five user-frame cases, and
the one-row capacity failure. Measured widths: summary 38–55, populated
thread rows 16–78, placeholders 4, `SHOT2` 31–65, `r=52` 32 columns.
The 78-column case synthesizes a six-digit frame count. Physical panel
rendering is unobserved.

## Repeat commands

From the device worktree in WSL Ubuntu-22.04 as root, use fresh output paths:

```sh
PY=/home/wh1stl3/.local/bin/python3.11
BASE=/mnt/d/Code/PortingiOS/UniXNU
CPO=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json
B=out/nuwa-sb-stack-detail-20261124-r2-build
P=out/nuwa-sb-stack-detail-20261124-r2-package
A=out/nuwa-sb-stack-detail-20261124-r2-audit
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
`fsck.fat -vn`: 9 files, 106,271/129,022 clusters. `mdir`: 11,648,512 bytes free.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 (52,203,520 B) | `f2841146dbdea044fd289795b946ed12f4c303316d62f864e4dc70682fdab786` |
| Outer SHA-256 (100,663,296 B) | `a26b2655d71e35fb5e6e1b63c1a3dd107a4df7b54f15be46ef9a3224f65b2b4c` |
| CHMH SHA-384 | `08cf510e6ee49d582058b40eaa599addf2f44267ccd5303ed4c5d850536bedf3e0b91e5d30cff6e23b53d10bfa9b5123` |
| Outer-readback FAT SHA-256 (67,108,864 B) | `11fc024cee60df5a888b171d8401ba900089c05b4a125ce2049cfbb92cb76554` |

Local package: `out/nuwa-sb-stack-detail-20261124-r2-package/vendor_boot.img`.
Reviewer: recheck wait-only selection, missing/empty/zero records, frame
counts and truncation, and the five/six/one-row layout. Independent verifier:
rerun the commands above.
