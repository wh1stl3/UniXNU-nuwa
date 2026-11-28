# retained v1 reset r3：完整准擦与中断标记

**r3 已由 deep_reviewer 判定 FAIL（主控转述），禁止作为设备候选。**
阻断项是独立接受 slot-1 头：disposable 初始化仅生成 SB0，且 `open()` 要求
SB1 全零；合法 slot-1 头和双头均不能证明第二块可擦。修订见
`nuwa-v1-legacy-reset-r4-20261128.md`。

`WriteVolatile` 不保证落盘次序：掉电后可能同时出现原 v1 头有效、旧锚点
已无标记、部分清零 bitmap 已落盘、带进度标记的头未落盘；daily 此时仍可能
接受旧头与混合 bitmap。`commitfail` 后 daily 放行也不能证明视图完整或 reset
成功。

**以下为审查前的 r3 主机 self-checked 记录，未操作设备，独立 verifier 未复跑。**
主控转述 deep_reviewer 对 r1
`62e0ea2d4c207ddc6cc2024943e8a017d14d0e3ffb2795069246abf0d8cadd21`
判定 **CHANGES REQUIRED**。r2
`9d253991b8e3d7ded0f768ec557dee1d98c222b81ddee386138801eff87078bc`
随后由实现方撤回：其通用头校验未额外限定 disposable 的初始字段。二者均不是
设备候选；r2 的详细设计沿革见 `nuwa-v1-legacy-reset-r2-20261128.md`。

## r3 合同

- 原拒写谓词 `hasSuperblockMarker()` 不变。自动清理需要完整头解析通过：
  固定 seed、目标 slot、格式/保留字段、header CRC、整块 CRC 均匹配，且
  generation、head、count 为零；头内 map CRC 必须是 524288 个零字节的
  IEEE CRC32 `75660aac`。这是 disposable 初始化且不 checkpoint 的格式；
  不声称实际读取或验证了旧 maps。magic-only、撕裂、错 seed/slot/字段/CRC
  或非初始头均拒绝且零写。两锚点均判定后才写。
- 已有 seed、双 GPT、v1 placement 和 retained 归属检查继续执行；旧 disposable
  整窗再单独做 placement，锚点写入仅 4 KiB LBA `57393401/57393402`。
  普通 v1 窗口 `[59491258,61588475)` 不变，没有新增写入 LBA、锁或 DMA 路径。
- 复用上游 v1 头块保留区 `[64,96)` 写入 reset-in-progress 标记：读取两
  锚点和 v1 头后先写标记，再按块清理；首次失败即停、不回滚、不提交后续
  锚点或 bitmap/header。v1 reset 写出的 header 保留标记；`overlay.open()`
  的 bitmap/header 和 sync 完成后才写回无标记头并检查 sync。
  daily 见该保留区任一非零字节即拒绝且零写；显式 reset 可重新开始。
  正常上游编码头此范围为零；此检查也会拒绝以前被头解析器忽略的非零保留区。
- D1 `rst=`：`ready` 资格已过、`progress` 标记命令完成、`clean1/clean2`
  分别表示第一/第二锚点命令完成、`fail1/fail2` 表示对应块失败；
  `inN/doneN` 的 N 是锚点位掩码（0 无、1 第一、2 第二、3 两者），表示
  标记仍在/清标记命令和 sync 完成。另有 `invalid`、`pending`、`read`、
  `guard`、`markfail`、`commitfail`。只更新现有诊断指针，不引入日志、
  分配或新锁。

`WriteVolatile`/`store_sync` 不保证掉电落盘次序或两块原子性，失败的命令也
可能已改变介质；**不能把掉电后 daily 放行视为 reset 成功**。未验证真实
UFS 落盘、归属或恢复。尤其两旧锚点在原 v1 窗口外，其授权范围、第二槽
格式资格、诊断采样及 reset commit 语义须 deep_reviewer 审查；认证仍未证。

复用本仓完整 v3 头解析及 `Gate.h` placement；v1 overlay 来自
`UniXNU/drivers/RamBlock@4be2d7eb05ef5a98126c91e0302c149140c0e3e1`
（BSD-2-Clause-Patent）。未引入第三方实现。

## 产物与自检

| 项目 | 值 |
| --- | --- |
| outer | `out/nuwa-v1-legacy-reset-r3-20261128-package/vendor_boot.img`，100663296 B |
| outer SHA-256 | `2d38ae746311cdd6b7a10cbe4a0cb7277753f3f16dfcd59efd00a78989d4ab9f` |
| kernel SHA-256 | `365c67d596f07af279e44c8587d355568927eead6793f8aaddee85e3429ac0e0` |
| FAT SHA-256 / 空闲 | `f15b8e9e62e114dc877d878b2d8579d32f2c964ee2e783002ac45a1a1e933c87` / 11005440 B |
| CHMH SHA-384 | `dfb12e62b446fd854d5ab214e603ea132b302c72f47642a892d73ecc7c0a1b78aa5f248cfc97ab54f4ef44a561cf3a0e` |
| audit | `reset=true`、`sheng-data-reset=1`、`device_release=false` |

新构建、68 个 retained ASan/UBSan 情形、dualbank 与 disposable ASan/UBSan
回归、D1 80 列、panic 安全带/链接反汇编、旧 reason fixture、outer
`--audit-only`、`fsck.fat -vn` 均 exit 0（self-checked）；porting-record
检查在文档变更后重跑。覆盖完整合法头、magic-only、撕裂、seed/slot/格式/
双 CRC、非初始四字段、第二锚点无效、预检读失败、清理失败但已落块、
分配/读头/首中末 bitmap/header/清标记故障及模拟下一次 daily 拒绝。

复用 r2 的隔离脚本副本 `out/nuwa-v1-legacy-reset-r2-20261128-input/`，
不改并行显示文件；r3 的显示 archive SHA-256
`e9b8ec5d6e99bca9b0838ee6fdbd8b1608b53d2ca41e33ef283d782d5ae4e89e`、
`BootProgress.c` 和 `derived/` 与 r1 逐字节相同。构建输入哈希
`out/nuwa-v1-legacy-reset-r3-20261128-sources.sha256` 前后核对一致。
UniXNU 远端 HEAD `fdf81eaa832ce5c850d3c53c698407aa722a4653` 和 nuwa
远端 HEAD `fe6b859367cc7b0641e9ae7dda46d8b5c6fc4fb0` 前后不变；本地
UniXNU pin `693f5d9cae8a408dd18b39f3f9fdc4228c934241`，未合并。

## 独立复跑

WSL Ubuntu-22.04 root，从设备工作树执行；输入哈希不匹配则停止。独立
verifier 使用新的 `$b`、`$pkg`：

```sh
p=/home/wh1stl3/.local/bin/python3.11
base=/mnt/d/Code/PortingiOS/UniXNU
stage=out/nuwa-v1-legacy-reset-r2-20261128-input
b=out/nuwa-v1-legacy-reset-r3-20261128-verify-build
pkg=out/nuwa-v1-legacy-reset-r3-20261128-verify-package
template=../worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-package/vendor_boot.img
cpo=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json

sha256sum -c out/nuwa-v1-legacy-reset-r3-20261128-sources.sha256
$p -B "$stage/scripts/build-nuwa-display-native.py" --base "$base" --cpo "$cpo" \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 --r35l-dir out/nuwa-r35l-regs-full-20261121 \
  --cpu-only --no-software-vsync --candidate --mg-reset --hid-standin --crashcap --pixsig \
  --data-persist-diag --data-candidate-gpt ../.cache/device-evidence/20261107-recovery/gpt-sda.bin \
  --data-v1-retained --post-event --out "$b"
$p -B tests/test-nuwa-v1-retained.py "$base" "$b"
g++ -std=c++17 -Wall -Wextra -Werror -O2 -g -fsanitize=undefined,address \
  -fno-sanitize-recover=all -fno-omit-frame-pointer -no-pie tests/test-nuwa-dualbank.cpp -o "$b/test-dualbank"
"$b/test-dualbank"
g++ -std=c++17 -Wall -Wextra -Werror -O2 -g -fsanitize=undefined,address \
  -fno-sanitize-recover=all -fno-omit-frame-pointer -no-pie tests/test-nuwa-disposable-data.cpp -o "$b/test-disposable"
"$b/test-disposable"
cmp scripts/test-nuwa-postevent.py "$stage/scripts/test-nuwa-postevent.py"
cmp scripts/generate_nuwa_postevent.py "$stage/scripts/generate_nuwa_postevent.py"
$p -B scripts/test-nuwa-postevent.py --renderer "$b/BootProgress.c" --kernel "$b/native-with-stabs.macho"
$p -B tests/test-nuwa-data-persist.py "$base"
$p -B scripts/package-nuwa-crashcap.py --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --v1-retained-template "$template" --post-event --v1-reset
$p -B scripts/package-nuwa-crashcap.py --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --v1-retained-template "$template" --post-event --v1-reset --audit-only
fsck.fat -vn "$pkg/readback-fat.img"
sha256sum "$pkg/vendor_boot.img"
GIT_DIR=/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/.git/worktrees/worktree-ufs-owner-api-20261126 \
GIT_WORK_TREE=/mnt/d/Code/PortingiOS/nuwa/worktree-ufs-owner-api-20261126 \
  "$p" -B "$base/scripts/porting-record.py" check \
  --device /mnt/d/Code/PortingiOS/nuwa/worktree-ufs-owner-api-20261126 --base origin/main
```
