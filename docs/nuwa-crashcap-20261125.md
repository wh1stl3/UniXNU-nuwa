# lsd saved-register capture — 2026-11-25

Host candidate, **self-checked** only. No device command or flash. Deep
review and independent verifier pending; authentication NOT REACHED.

## Capture point and decisions

- XNU 8796.141.3 (`1b191cb58250d0705d8a51287127505aa4bc0789`, APSL 2.0):
  `osfmk/kern/ux_handler.c:catch_mach_exception_raise()` takes the target
  thread reference and forwards it. The actual `handle_ux_exception()` is
  in `bsd/uxkern/ux_exception.c`. Use its existing process reference and
  exact NUL-inclusive `p_comm == "lsd"` test, after the stack-overflow signal
  adjustment and immediately before `threadsignal()`. Ignore zero signals.
  The earlier r35l SpringBoard branch is unchanged.
- BSD passes the target, PID, final signal, Mach code and, only for
  `EXC_BAD_ACCESS`, the Mach subcode (the address carried by ARM64
  `handle_user_abort()` in `osfmk/arm64/sleh.c`). Other exceptions get `fa=0`.
  A helper in `osfmk/kern/ux_handler.c` reads PC/LR/SP/FP using XNU's
  `get_user_regs(thread)` and saved-state accessors; absent state yields
  four zeroes. `k` is the target's next-dispatch continuation, not a live
  kernel PC. Use `VM_KERNEL_UNSLIDE`, like `kern_stackshot.c:2186`; preserve
  zero. Keeping this helper in osfmk avoids exposing private `struct thread`
  layout to the BSD build (the initial BSD-only compile failed at that field).
- No `copyin`, user-memory dereference, mapping switch or stack walk.
  `bsd/netinet/tcp_usrreq.c:2213–2216` notes that a `copyin/out` page fault
  can block; the recorder needs only the already saved kernel context.
  It sees exceptions that reach the BSD path, not every signal or exit;
  recording a delivered signal does not prove the process subsequently died.
- Two static slots: low two metadata bits are free/writing/valid (0/1/2);
  the remaining bits are the generation. Each of two rounds tries free
  slot 0 then 1, then tries the lowest-generation valid slot (writing is
  ineligible; equal keys favor slot 0). CAS includes generation to reject
  a stale valid→writing claim. An exhausted attempt increments `dr` once.
  Successful writes take `fetch_add(wr_seq)+1` after storing the payload and
  publish valid with a release-capable sequentially consistent store.
  Payload and metadata atomics share one SC order; the reader compares the
  full metadata tuple around the payload, at most three attempts per slot.
  Independent stable samples are ordered by generation, not PID or timestamp.
- Print literal `lsd` because the producer already exact-matches it; no
  copied name. Use full 64-bit hex PC/LR/SP/FP/FA/k, hex Mach code, decimal
  PID/signal/drop count. Render signal in the same seven bits as the existing
  exit banner (all BSD signals fit); the initial full unsigned width failed
  the extreme-value fixture. Mark a failed read `torn` on the surviving
  record or in a standalone row; never print torn registers.
- Reserve four rows as a unit before `SHOT`/`EXIT`/`PROC`, adding `CR2`
  only with a second stable sample and a fifth row. When fewer than four
  fit, omit all four. Once the renderer starts that group under its
  existing framebuffer ownership, defer yield until it completes. No
  change to stackshot scheduling or to the existing render lock.
- Build-only `--crashcap` is explicit and rejects `--smp-gate`. No new boot
  args. Reuse the r35l/PEER native link and stack900 outer, with single-CPU
  host affinity and no `sheng-smp` argument. Only kernel and the existing
  CHMH field in its ADT are allowed to change in FAT contents. Reuse the
  repository's experimental identity derivation, not a signed manifest.

## Fixture (synthetic values, host console)

```text
PASS no crash: no CR rows
CR p92 lsd sig=11 code=1 dr=0
CR+ pc=00000001adf63478 lr=0000000000001048
CR+ sp=0000000000002080 fp=00000000000030a0
CR+ fa=0000000000000008 k=fffffff007123456
PASS once: slot0 gen=1
CR2 p92 lsd sig=11 pc=00000001adf63478
PASS twice: slot1 gen=2; newest first
PASS third: overwrite slot0 (oldest), retain slot1
PASS CAS contention: six failed CAS over two rounds, dr=1
PASS CAS retry: second round succeeds without incrementing dr
PASS torn: reject changing generation after 3 tries; mark stable survivor or standalone
PASS SHOT pending, EXIT and PROC survive alongside CR on full panel
PASS full panel: CR stays contiguous; 0..3 rows omit it; mid-group yield deferred
width[0]=77
width[1]=43
width[2]=43
width[3]=42
PASS maximum CR line width=77/78
PASS maximum CR2 line width=47/78
PASS linked: BSD -> osfmk capture -> recorder, before threadsignal; no recorder calls out
```

Widths are from the extreme-value/torn host case, not measured on glass.

## Package and readback

`out/nuwa-crashcap-20261125-package/vendor_boot.img` (100,663,296 B).
Its outer-readback FAT is 67,108,864 B with **11,025,920 B free** (floor
8 MiB). Outer bytes outside the FAT match rollback; FAT config and 561-byte
args, seed and trust cache match rollback byte-for-byte. Only kernel and
its ADT changed; the latter differs only in `/chosen/boot-manifest-hash`.
The separate pure-Python readback audit, `fsck.fat -vn`, and `mdir` agreed.
`mcopy` records FAT timestamps, so a fresh repack can differ in FAT/outer
hashes even when the payloads match. PEER, SHOT row, SHOT paint gate, banner
budget and short-value regressions all exited 0.

| Artifact | Digest |
|---|---|
| Kernel SHA-256 | `9d30f2e6b47a25c6d307266ede95cdd70bfcaa3564385a923c96814f2af05d9f` |
| Outer SHA-256 | `4a83a8e4b5ba6feeef761dd6cfa65697a5e8325e71694057857d7e15f784b4d9` |
| CHMH SHA-384 | `82d7bbc013e27183d9cd55e886d4f0e09fad86a742e108acce39debd4597fcffa49027336136b1ddeec293fe0ab9e9f7` |
| Outer-readback FAT SHA-256 | `f5ac608cc43eae7fe3edd11373adb640d91c4ab1d781c3ed9165c109378e1bcf` |
| Seed SHA-256 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

## Reproduction

Use pinned inputs from [the previous build](nuwa-sb-stack-detail-20261124.md)
and [packaging](nuwa-stack900-20261125.md). The UniXNU checkout is
`693f5d9cae8a408dd18b39f3f9fdc4228c934241`; upstream HEAD before and after build
was `8542980d02b4d2cc5c32ee3542de1760b2562aac` and was not adopted.

```sh
# WSL root, cwd = device worktree. For verifier, choose fresh B and P.
PY=/home/wh1stl3/.local/bin/python3.11
BASE=/mnt/d/Code/PortingiOS/UniXNU
CPO=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json
B=out/nuwa-crashcap-20261125-build-r3
P=out/nuwa-crashcap-20261125-package
MAKEFLAGS=-j1 taskset -c 0 "$PY" -B scripts/build-nuwa-display-native.py \
  --base "$BASE" --cpo "$CPO" --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 --r35l-dir out/nuwa-r35l-regs-full-20261121 \
  --cpu-only --no-software-vsync --candidate --mg-reset --hid-standin --crashcap --out "$B"
"$PY" -B tests/test-nuwa-crashcap.py "$B/kernel.macho"
MAKEFLAGS=-j1 taskset -c 0 "$PY" -B scripts/package-nuwa-crashcap.py \
  --base "$BASE" --kernel "$B/kernel.macho" --out "$P"
"$PY" -B scripts/package-nuwa-crashcap.py --audit-only \
  --base "$BASE" --kernel "$B/kernel.macho" --out "$P"
fsck.fat -vn "$P/readback-fat.img"
mdir -i "$P/readback-fat.img" ::/EFI/UniXNU/Payloads
```

Rollback outer SHA-256:
`66efdc7164d1385978309967f40f0495497237c3c7a92c43b7697496a55f6486`.
