# retained v1 reset r4：仅准擦完整 SB0

**主机 self-checked，未操作设备；独立 verifier 待完成。**
主控转述 r4 deep_reviewer **PASS**，仅绑定 outer SHA-256
`ef25640161abb9569a25c7614c6f51091c46c37739887d06d4cd5edcfec4f7cf`；
此审查不构成设备写入授权。
主控转述 deep_reviewer 对 r3 outer
`2d38ae746311cdd6b7a10cbe4a0cb7277753f3f16dfcd59efd00a78989d4ab9f`
判定 **FAIL**：disposable 初始化只生成 SB0，且 `open()` 要求 SB1 全零；
可独立通过 CRC 的 slot-1 头不证明第二块属于 disposable 对象。r3 禁用，见
`nuwa-v1-legacy-reset-r3-20261128.md`。

## r4 合同

- 自动清理仅在完整初始 SB0 与全零 SB1 同时成立时，对 LBA `57393401`
  单块清零。SB0 继续强校验固定 seed、slot 0、格式/保留字段、header CRC、
  整块 CRC、零 generation/head/count 和预期零 map CRC `75660aac`。这仅检查
  头中的 map CRC，不声称读取或验证了旧 maps。
- 两槽全零无需清理旧锚点，正常继续显式 v1 reset；这里的“零写”仅指旧锚点，
  v1 reset 仍写 in-progress 标记、bitmap 和 header。reset 扫描到 SB1 任意
  非零时，在标记写前拒绝且零写，包括合法 slot-1 头、双头和非零垃圾；
  可识别 v3 仍以 `legacy-v3` 拒绝。daily 的原弱标记拒写谓词不变。
- 清理 helper 的目标白名单也收窄至 SB0，SB1 不再是清理写目标。原 v1 窗口
  `[59491258,61588475)`、身份/双 GPT/范围/归属检查及既有锁和 DMA 路径不变。
  in-progress 标记和 daily 检查沿用 r3，参见
  `nuwa-v1-legacy-reset-r3-20261128.md`。
- 现有 D1 `rst=` 状态保留；新增 `rst=sb1` 表示 reset 遇非零 SB1。
  `clean2/fail2/in2/in3/done2/done3` 的原映射保留兼容，但 r4 的自动清理路径
  不会产生第二槽清理结果。`done0/done1` 分别表示无旧锚点清理/完成 SB0 清理
  后清标记命令和 sync 完成，不表示介质耐久。

**掉电限制：**`WriteVolatile` 不保证落盘次序。掉电后可能同时出现：
原 v1 头仍有效、旧锚点已无标记、部分清零 bitmap 已落盘，而带进度标记的头
未落盘；daily 因此仍可能接受旧头与混合 bitmap。`commitfail` 后 daily 放行
同样不能证明视图完整或 reset 成功。失败命令也可能已改变介质；真实 UFS
写入顺序、掉电恢复、介质归属和设备上当前锚点内容均未验证。

SB0 仍在原普通 v1 写窗口之外；其单块写入是否覆盖现有设备写入授权、实际
介质所有权及完整 diff 必须由 deep_reviewer 和主控确认。实验 CHMH 不证明认证。
沿用本仓 disposable 头解析与 placement、既有 retained Slot/写入路径和上游
`UniXNU/drivers/RamBlock@4be2d7eb05ef5a98126c91e0302c149140c0e3e1`
（BSD-2-Clause-Patent）；未引入第三方代码。

## 产物与 self-check

| 项目 | 值 |
| --- | --- |
| outer | `out/nuwa-v1-legacy-reset-r4-20261128-package/vendor_boot.img`，100663296 B |
| outer SHA-256 | `ef25640161abb9569a25c7614c6f51091c46c37739887d06d4cd5edcfec4f7cf` |
| kernel SHA-256 | `0f6836de7bf1b5709c05b3ef224c60bc13b32eeb603723aa7a5511fec279b39a` |
| FAT SHA-256 / 空闲 | `c7412a015a6e20cbdf35ba28bb250f2089e481d87009e8fdb1a3408a56186f00` / 11005440 B |
| CHMH SHA-384 | `5cc7513476de668f79fdfdacdbcc9d98d81130fa6503b56e11f183207fd95b35ee64adfdc49322c44bb916de765c6f04` |
| audit | `reset=true`、`sheng-data-reset=1`、`device_release=false` |

新构建、74 个 retained ASan/UBSan 情形、dualbank/disposable ASan/UBSan
回归、D1 80 列、panic 安全带/链接反汇编、旧 reason fixture、outer
`--audit-only`、`fsck.fat -vn` 均 exit 0（self-checked）。覆盖完整 SB0 + 零
SB1、SB1 合法 slot-1 头/垃圾/末字节非零、双头、仅 SB1 非零、两槽全零、
原强校验负例、SB0 失败但实际落块及模拟 daily、v1 reset 各阶段故障。
原针对 SB1 清理写失败的场景保留，但现在断言在写前拒绝；新增 SB0 清理失败
且实际落块场景覆盖失败恢复。

复用 `out/nuwa-v1-legacy-reset-r2-20261128-input/` 隔离构建脚本，不改并行
显示文件；r4 的显示 archive SHA-256
`e9b8ec5d6e99bca9b0838ee6fdbd8b1608b53d2ca41e33ef283d782d5ae4e89e`、
`BootProgress.c` 和 `derived/` 与 r1 逐字节相同。构建输入
`out/nuwa-v1-legacy-reset-r4-20261128-sources.sha256` 构建前后核对一致。
UniXNU 远端 HEAD `fdf81eaa832ce5c850d3c53c698407aa722a4653` 与 nuwa
远端 HEAD `fe6b859367cc7b0641e9ae7dda46d8b5c6fc4fb0` 前后不变；本地 UniXNU
pin `693f5d9cae8a408dd18b39f3f9fdc4228c934241`，未合并。

## 独立复跑

WSL Ubuntu-22.04 root，从设备工作树执行；输入哈希不匹配则停止。独立
verifier 使用新的 `$b`、`$pkg`：

```sh
p=/home/wh1stl3/.local/bin/python3.11
base=/mnt/d/Code/PortingiOS/UniXNU
stage=out/nuwa-v1-legacy-reset-r2-20261128-input
b=out/nuwa-v1-legacy-reset-r4-20261128-verify-build
pkg=out/nuwa-v1-legacy-reset-r4-20261128-verify-package
template=../worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-package/vendor_boot.img
cpo=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json

sha256sum -c out/nuwa-v1-legacy-reset-r4-20261128-sources.sha256
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
