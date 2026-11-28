# retained v1 reset：旧 disposable 锚点清理

**r1 已由 deep_reviewer 判定 CHANGES REQUIRED，禁止作为设备候选。** 弱标记不足以
授权擦除，且清理后 reset 中断可能使 daily 误放行；后续修订另记于
`docs/nuwa-v1-legacy-reset-r2-20261128.md`。

**以下为审查前的 r1 主机 self-checked 记录，未操作设备；独立 verifier 未复跑。**
工作树基座 `68ec8b2c0019bab13268f996ac5c19662131c74b`
另含此前未提交的 V1 诊断增量和并行显示任务增量；不能把完整工作树 diff
全部归因于本次。没有修改并行显示生成、验证或 workloop 文件。

## 控制流

- 仅 `sheng-data-reset=1/2` 请求允许清理；`nuwa-mg-reset` 不是 Data reset。
  现有 seed、userdata 身份、主/备 GPT、v1 窗口 placement 和 retained
  Slot/ownership 检查仍在提交前。reset 清理前读取并分类**两个**旧锚点；
  遇到 `legacy-v3`（包括无法区分的撕裂标记）、旧锚点读取失败，或未请求
  reset 但发现 disposable 标记时拒绝且零写。未发现旧标记的 daily 路径不变。
- 如有可识别的 disposable 标记，还须匹配固定 v1 页数对应的窗口块数，
  并用原 `placement()` 独立验证整个旧 disposable 窗口的 root-image
  guard 和 reserve；使用现有 `retainedOwnershipLocked()` 与
  `persistWriteLocked()`。额外目标严格是 LU0 的 4 KiB LBA `57393401`
  和 `57393402`，每次单块，只清零实际匹配的锚点；普通 v1 窗口仍为
  `[59491258, 61588475)`。
- 若清理完成后 overlay 打开成功，沿用上游 v1 reset 的 bitmap、header
  初始化。主机同介质模型测试了 Fresh 后模拟下一次 daily 为 Resumed
  且不写。清理前的 GPT/锚点读取失败零写；**清理完成后**才发生的 v1
  overlay 读取失败无法撤销已完成的清理。清理写失败允许部分完成，失败的
  命令自身也可能已改变介质，后续不再提交本次 v1 写。
- 复用已有 D1 的 `why` 文本增加独立 `rst=` token，原 D1 的 `why=ok` /
  `why=window` 及 D2/D3 含义不变。`rst=0/1/2` 是底层已完成的清理
  写命令数；`rst=read/guard/fail0/fail1` 分别为预检读取、资格检查、
  写入失败时确认已完成 0/1 个。`why=legacy-v3` 和 daily 的
  `why=legacy-disposable` 仍保留。可见性为 host 80 列和 panic 带模型
  检查，实际画面未观察。

沿用本仓 `DualBankLogOverlay.h` 的 `hasSuperblockMarker`（识别而非校验
重放，识别不要求 seed/CRC）、`Gate.h` 的 `placement()` 和
`RetainedPersist.inc` 的既有写入路径；未引入第三方代码。复用的上游 v1
overlay 来源为 `UniXNU/drivers/RamBlock@4be2d7eb05ef5a98126c91e0302c149140c0e3e1`
（BSD-2-Clause-Patent）。不可区分的部分标记先按 v3 拒绝。

## 审查边界

两块清理目标在原 v1 普通写窗口之外，虽在单独核对的旧 disposable
窗口内，是否超出现有设备写入授权和介质所有权范围须 **deep_reviewer**
判读并由主控确认；本主机实现/出包不构成设备授权。还需审查：
两块均检查后再写、混合格式和部分写失败的次序；仅按标记识别而非 seed
或 CRC，可能使旧 disposable 元数据失效；`WriteVolatile` 无断电耐久或
两块原子性保证，计数不等于介质持久；reset 后仍使用 reset 包重新启动会
再次清空 v1 overlay。实验 CHMH 不证明认证。

## 主机结果

| 项目 | 结果 |
| --- | --- |
| outer | `out/nuwa-v1-legacy-reset-20261128-package-r1/vendor_boot.img`，100663296 B |
| outer SHA-256 | `62e0ea2d4c207ddc6cc2024943e8a017d14d0e3ffb2795069246abf0d8cadd21` |
| kernel SHA-256 | `c01bf7b724b30c090134d19092cdb25fdf9d0c42537be5da11515f09f0ec33b0` |
| FAT SHA-256 / 空闲 | `5ecca8d72786770105260d1883691ec56dee0c6df028911d5d983fb7decdb841` / 11021824 B |
| CHMH SHA-384 | `478bb82edd66d6934d5baadd71fff9f250777fd1a978a728daa5ea766b3d008159049fb9c17efbd48ba37648736585ce` |
| 参数 | FAT audit `reset=true`；`sheng-data-reset=1`；`device_release=false` |

新构建、新包、42 个 ASan/UBSan retained 情形、实际生成的 D1 行字段
及 80 列、panic 安全带/链接反汇编、旧数据 reason fixture、outer
`--audit-only`、`fsck.fat -vn` 均 exit 0（self-checked）。覆盖两锚点各
一块/两块、可区分撕裂 disposable、混合 v3、两次锚点读失败、双 GPT/seed、
root guard/reserve、归属、目标越界、写失败部分完成和模拟下一次 daily。
当前未验证设备运行、介质真实内容、耐久或认证。

构建前后 UniXNU 远端 HEAD `fdf81eaa832ce5c850d3c53c698407aa722a4653`、
nuwa 远端 HEAD `fe6b859367cc7b0641e9ae7dda46d8b5c6fc4fb0`；本地
UniXNU pin `693f5d9cae8a408dd18b39f3f9fdc4228c934241`，未合并。
并行任务修改了 `derive-nuwa-display-abi.py` 的检查；本候选构建期间输入
哈希未变，`derived/` 与先前 V1 诊断 r3 构建逐文件一致（`diff -qr`）。
构建包含此前 V1 诊断增量，审查须看**完整工作树 diff** 和最终 outer hash。

## 独立复跑

WSL Ubuntu-22.04 root，从本设备工作树运行；独立 verifier 使用新的 `$b`
和 `$pkg` 目录，保持代码与输入不变：

```sh
p=/home/wh1stl3/.local/bin/python3.11
base=/mnt/d/Code/PortingiOS/UniXNU
b=out/nuwa-v1-legacy-reset-20261128-verify-build
pkg=out/nuwa-v1-legacy-reset-20261128-verify-package
template=../worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-package/vendor_boot.img
cpo=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json

$p -B scripts/build-nuwa-display-native.py --base "$base" --cpo "$cpo" \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 --r35l-dir out/nuwa-r35l-regs-full-20261121 \
  --cpu-only --no-software-vsync --candidate --mg-reset --hid-standin --crashcap --pixsig \
  --data-persist-diag --data-candidate-gpt ../.cache/device-evidence/20261107-recovery/gpt-sda.bin \
  --data-v1-retained --post-event --out "$b"
$p -B tests/test-nuwa-v1-retained.py "$base" "$b"
$p -B scripts/test-nuwa-postevent.py --renderer "$b/BootProgress.c" --kernel "$b/native-with-stabs.macho"
$p -B tests/test-nuwa-data-persist.py "$base"
$p -B scripts/package-nuwa-crashcap.py --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --v1-retained-template "$template" --post-event --v1-reset
$p -B scripts/package-nuwa-crashcap.py --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --v1-retained-template "$template" --post-event --v1-reset --audit-only
fsck.fat -vn "$pkg/readback-fat.img"
sha256sum "$pkg/vendor_boot.img"
```
