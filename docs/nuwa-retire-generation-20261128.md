# Display retirement generation probe — 2026-11-28

Host **self-checked**; independent verifier rerun remains pending.

2026-11-28 最终候选 reviewer 结论（主控转述）：

- 结论：`PASS WITH CONDITIONS`，接受 `out/nuwa-retire-generation-20261128-package/vendor_boot.img`，SHA-256 `dcc8d9e8137d5154b86e7cd3f545dfd12e2484408ac1078de2f824312d4661a2`。
- 性质：ordinary reviewer（普通审查），**未经 deep_reviewer**；仅限上述 SHA-256，换包须重审。
- 主要内容：RG 观测点落在 `activateOnlyPendingSwap(request)` 成功之后、`completeCurrentSwap()` 之前，未改变队列/所有权语义；无 `D1/D2/D3` 与持久层二进制错配（直接链接 r3 的 `libObserveNativeUfs.a`/`libNativeRamBlock.a`，哈希与 r3 pin 一致）；ASan SIGSEGV 不阻断；该构建为保留原二进制输入的重放，非源码独立复建。
- 限制：`ret` 只证明函数返回，不证明完成通知已发送或用户态已消费。

## Hook and field

The driver comes from UniXNU/GopFramebuffer
`e47c1b8de169cd2bd0b885c7d85e433010e3cdf2` (BSD-2-Clause-Patent), not a
device-owned `package/NativeLegacyDisplay.cpp`. The existing host adapter makes
a pinned CPU-only copy. Under `--pixsig`, it inserts a generation allocation
immediately after `activateOnlyPendingSwap(request)` succeeds, carries the
value in a local over `completeCurrentSwap()`, and records its return. The
existing `stat`, `note`, `removeValidated`, family completion, retirement
callback, latch and queue calls are otherwise unchanged. The request is not
read after completion. The hot-path additions use inline relaxed atomic
operations on three preallocated 32-bit scalars, with no new call, allocation,
log, notification, enqueue or lock.

The separate page row 9 and priority-0 live-banner row are:

```text
RG en=<entered> ret=<returned> g=<latest-entered-generation> last=<last-return-generation>
```

- `en` counts requests that were submitted and have **entered retirement**,
  not all successful validations or all submissions. A rejected activation,
  failed submission or cancellation does not create a retirement record.
- `ret` counts returns from the family completion call. `g` is the latest
  allocated generation and numerically equals `en`; `last` is the generation
  carried by the last recorder to execute after a completion returns.
  These are independent relaxed samples, **not a coherent pair**. A reentrant
  outer return can leave `g=2,last=1`. Counters and generation wrap modulo
  2^32. They do not represent the currently in-flight request.
- **Completion notification sent = UNKNOWN; userspace consumption = UNKNOWN.**
  The probe implements and infers neither. Returning from the family function
  is not proof of a panel vblank, fence, notification or consumer action.

The row is not part of the critical-panic safe band. Page handoff, banner
disable, yield and finite banner budget can prevent a physical paint even if
the counters changed. No runtime or display-acceptance claim follows.

## Isolation and artifacts

The shared working tree contains another task's uncommitted persistence,
reset and post-event changes. To avoid incorporating them, the dedicated
replay uses the already-built V1-NODUR diagnostic r3 renderer, RamBlock archive,
retained UFS archive and remaining r3 link inputs. It first replays the r3
link and requires native bytes equal after masking only LC_UUID and map output
path. The candidate link replaces exactly the display and renderer archives;
the renderer is the r3 text plus the RG transform. The existing emitter,
renderer, display/HID ABI audits and packager are reused.

This is a **binary-input replay**, not a source-only rebuild of r3. It requires
the retained local r3 artifacts and the original XNU build inputs. The actual
`unixnu.toml` compares byte-for-byte with the r3 daily package. No
`sheng-data-reset` argument is present; this does not remove the old r3 reset
implementation. `D1/D2/D3` text and the post-event generator are unchanged.

| Input/output | SHA-256 |
|---|---|
| r3 `BootProgress.c` | `8e03abee2d32d43b31dee24db9012d10454cbe5cc2b5fc1f6a1a691f59adca51` |
| r3 `libNativeRamBlock.a` | `3e163e822bad5bc6f32881ac08bf2967f4e13ad5e80a817b947085819de84f38` |
| r3 `libObserveNativeUfs.a` | `d5e17e7a1bab9bef237160f62d8b747e92fd2221dfe648f5bb375dc600c19976` |
| candidate `kernel.macho` | `53c75a57020c9a2db4b5d91d7230fd79e8bfe87c3eac467b0d97943315e12254` |
| candidate `vendor_boot.img` | `dcc8d9e8137d5154b86e7cd3f545dfd12e2484408ac1078de2f824312d4661a2` |
| readback FAT | `1389db68d4ce04a91a891c53a6fab75dd65d26a83b87322af19a34dcf2148134` |

Outer is `out/nuwa-retire-generation-20261128-package/vendor_boot.img`
(100663296 bytes). CHMH SHA-384 is
`27d40dd5722b7ba59de86fab3761e494bd6c6f7228e64b6986259ba083aa5e02caba1ed8fa635994b5992c30f15e07d3`;
FAT free is 11021824 bytes. Package audit reports `v1-retained`,
`V1-NODUR`, `reset=false`, `device_release=false`; CHMH is experimental and
authentication remains NOT REACHED.

UniXNU local pin is `693f5d9cae8a408dd18b39f3f9fdc4228c934241`.
Remote UniXNU main before/after was `fdf81eaa832ce5c850d3c53c698407aa722a4653`
and device main `fe6b859367cc7b0641e9ae7dda46d8b5c6fc4fb0`; neither was merged.

## Self-check and independent rerun

`tests/test-nuwa-retire-generation.py` compiles the actual adapted retirement
body in a host mock with ASan/UBSan and makes the request inaccessible when
the mocked family completes. Results:

| Host case | Result |
|---|---|
| validation success, failed submit; rejected activation/cancel | `en=0 ret=0` |
| successful retirement | `en=1 ret=1 g=1 last=1` |
| completion reenters with a second retirement | `en=2 ret=2 g=2 last=1` |

The fixture also exercises the actual formatter and selector (maximum 60
columns) and compares the generated candidate renderer to the exact r3 text
plus the RG transform. The mock is not the IOKit scheduler or donor.
`test-nuwa-dspcount.py`, `test-nuwa-display-teardown.py` (10 cases),
`test-nuwa-pixsig.py`, host ABI archive, link control, candidate build, package
audit and `fsck.fat -vn` all ran successfully here. ARM64 object disassembly
shows the entry fetch-add before the family completion, generation carried in
`w21`, and the returned-generation store/fetch-add after it; no probe calls or
request reads were added after completion.

One later fixture rerun exited with SIGSEGV while starting the ASan/UBSan
executable (`tests/test-nuwa-retire-generation.py`, subprocess invocation);
it emitted no sanitizer diagnosis. The fixture now uses the repository's
existing `-no-pie` sanitizer build convention and three consecutive reruns
completed; the original SIGSEGV's cause was not established.

Independent `verifier` should use fresh directories and rerun on the same
source snapshot and local inputs (WSL Ubuntu-22.04 root, device worktree):

```sh
p=/home/wh1stl3/.local/bin/python3.11
base=/mnt/d/Code/PortingiOS/UniXNU
cpo=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json
template=../worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-package/vendor_boot.img
host=out/nuwa-retire-generation-verifier-host
b=out/nuwa-retire-generation-verifier-build
pkg=out/nuwa-retire-generation-verifier-package
test ! -e "$host" && test ! -e "$b" && test ! -e "$pkg"
$p -B scripts/verify-nuwa-display-host-abi.py --base "$base" --cpo "$cpo" \
  --cpu-only --no-software-vsync --pixsig --bringup-diag --strip-debug --out "$host"
$p -B scripts/build-nuwa-retire-generation.py --base "$base" --cpo "$cpo" --out "$b"
$p -B tests/test-nuwa-retire-generation.py --build "$b"
$p -B tests/test-nuwa-dspcount.py
$p -B scripts/test-nuwa-display-teardown.py
$p -B tests/test-nuwa-pixsig.py
$p -B scripts/package-nuwa-crashcap.py --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --v1-retained-template "$template" --post-event
$p -B scripts/package-nuwa-crashcap.py --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --v1-retained-template "$template" --post-event --audit-only
fsck.fat -vn "$pkg/readback-fat.img"
sha256sum "$b/kernel.macho" "$pkg/vendor_boot.img"
```

The FAT packager can change timestamps on a new run, so a differing outer
hash is not automatically a payload difference. Inspect and compare actual
contents; this self-check is not independent verification.
