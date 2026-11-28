# retained v1 reset r2：强准擦与中断标记

**r2 已由实现方撤回，不作为设备候选。** 完整复核发现 r2 的准擦谓词尚未
额外约束 disposable 初始 generation/head/count 和零 map CRC；r3 已补约束与负例，
见 `nuwa-v1-legacy-reset-r3-20261128.md`。

**主机 self-checked，未操作设备，复审和独立 verifier 待完成。** 主控转述
deep_reviewer 对 r1 outer `62e0ea2d…0d8cadd21` 判为 **CHANGES REQUIRED**：
弱格式标记不能授权擦除；清理后的 v1 reset 失败不能让 daily 误认旧视图。
r1 作废，见 `nuwa-v1-legacy-reset-20261128.md`。

## 实现与边界

- 原 `hasSuperblockMarker()` 拒写谓词不变；daily 遇旧 disposable 标记仍拒。
  reset 仅对通过原 v3 头解析器的完整 disposable 头准擦：固定 seed、
  目标 slot、版本/页数/map/ring/计数等结构、header CRC 和整块 CRC 均匹配。
  magic-only、可识别的撕裂、错 seed/slot、CRC 损坏或格式冲突均拒绝且零写；
  不因 reset 自动回收损坏头。两个锚点均完成判定后才发起任何写入。
- 继续独立核对旧 disposable 全窗口 `placement()`；清理目标仅原两个 4 KiB
  LBA `57393401/57393402`。普通 v1 写窗口不扩大，仍为
  `[59491258,61588475)`；GPT、seed、范围及现有 retained 归属检查均在写前。
  没有新增锁、DMA/IOMMU 路径或新的写入 LBA。
- reset 前读取 v1 头块，在已验证的 v1 头块保留区 `[64,96)` 写入
  `NUWARST1`/非零 in-progress 标记，再清理符合资格的锚点。上游 v1
  `encodeHeader()` 清零整块并仅使用 `[0,64)`；reset 最终写头时保留该标记。
  只有 `overlay.open()` 返回 Fresh、其 bitmap/header 写及既有 sync 已完成，
  才额外写回清除标记的 v1 头并检查 sync。
- daily 预检该保留区，**任一非零字节**均拒绝并要求显式 reset；包含部分标记。
  这也会拒绝过去被 v1 头解析器忽略的非零保留区，正常由上游编码的头该区域
  为零。标记存在时 reset 可重做。预检读取失败及可识别 v3 均零写；清理写
  首错即停，已完成的清理不回滚。清理后分配失败、再次读头失败及 bitmap/
  header 故障的下一次 daily 拒绝在主机模型中覆盖。
- D1 复用已有 `why` 文本追加 `rst=`：`ready` 判定完成待标记，
  `progress` 标记命令完成，`clean1/clean2` 分别为物理锚点 0/1 的清理命令完成，
  `fail1/fail2` 为对应锚点清理失败；`inN/doneN` 的 N 是已清理锚点位掩码
  （0 无、1 第一块、2 第二块、3 两块），分别表示 reset 进行中/标记清除
  命令和 sync 完成。另有 `invalid`、`pending`、`read`、`guard`、
  `markfail`、`commitfail`。这是诊断采样，不参与控制流。

`WriteVolatile` 和 `store_sync` 不保证掉电时标记、bitmap、header 的落盘顺序、
两块原子性或最终持久性；失败命令也可能已改变介质。**不能把掉电后的 daily
放行视为 reset 成功**。上述拒绝保证仅在主机模型所施加的命令完成/失败与
模拟重启下自检，不证明真实介质写入顺序。额外的头块标记和 reset 完成次序
须由 deep_reviewer 复审；两旧锚点仍位于原 v1 窗口之外，旧设备写入授权是否
涵盖它们仍待主控确认。实验 CHMH 不证明认证。

复用本仓 `DualBankLogOverlay.h` 的完整 superblock 解析和 `Gate.h` placement；
v1 overlay 来自 `UniXNU/drivers/RamBlock@4be2d7eb05ef5a98126c91e0302c149140c0e3e1`
（BSD-2-Clause-Patent）。未引入第三方代码。

## 产物与自检

| 项目 | 值 |
| --- | --- |
| outer | `out/nuwa-v1-legacy-reset-r2-20261128-package/vendor_boot.img`，100663296 B |
| outer SHA-256 | `9d253991b8e3d7ded0f768ec557dee1d98c222b81ddee386138801eff87078bc` |
| kernel SHA-256 | `533e5dcf814db69a8cc1990389ee0224a07d125d1e7805a473a80c8e5ab54071` |
| FAT SHA-256 / 空闲 | `8819d0407333d2b61981bb32edc2e87643d1056b84cb9d7ada164203827c9a55` / 11005440 B |
| CHMH SHA-384 | `9d7047917b8f850ab1e9b434fac26066b87b490bf9538dbaada123bbcf5d9fdcd1109b303b53aae7d9060050bcc13628` |
| audit | `reset=true`、`sheng-data-reset=1`、`device_release=false` |

新构建、64 个 ASan/UBSan 情形、D1 状态与 80 列、panic 安全带/链接反汇编、
旧 reason fixture、outer `--audit-only`、`fsck.fat -vn` 均 exit 0
（self-checked）。覆盖 magic-only、可区分撕裂、错误 seed/slot/结构/两种 CRC、
第二锚点无效时零写、首/次锚点读取失败、清理部分成功或失败但实际落块、
分配/重读/首中末 bitmap/header/清标记故障、模拟 daily 零写拒绝和 reset
重做成功。模型不代表掉电或设备执行。

为隔离并行显示任务，在 `out/nuwa-v1-legacy-reset-r2-20261128-input/` 下复制
构建脚本，仅将副本中的 `generate_r35_display_diag.py`、
`derive-nuwa-display-abi.py`、`verify-nuwa-display-host-abi.py` 还原为本仓
`68ec8b2c0019bab13268f996ac5c19662131c74b` 对应文件；package/patches/out
为指向本工作树的链接。未改原显示文件。构建输入哈希记录
`out/nuwa-v1-legacy-reset-r2-20261128-sources.sha256`，构建前后核对一致。
显示 archive SHA-256 `e9b8ec5d6e99bca9b0838ee6fdbd8b1608b53d2ca41e33ef283d782d5ae4e89e`、
`BootProgress.c` 和 `derived/` 均与 r1 构建逐字节一致。

从隔离副本直接运行 panic 测试时，其 `ROOT/..` 找不到 `Font.h`；改用原工作树
中的同内容测试脚本运行后 exit 0。UniXNU 远端 HEAD
`fdf81eaa832ce5c850d3c53c698407aa722a4653`、nuwa 远端 HEAD
`fe6b859367cc7b0641e9ae7dda46d8b5c6fc4fb0` 构建前后相同；本地 UniXNU
pin `693f5d9cae8a408dd18b39f3f9fdc4228c934241`，未合并。

## 独立复跑

WSL Ubuntu-22.04 root，从本设备工作树执行；输入哈希不匹配则停止。
独立 verifier 使用新的 `$b`、`$pkg` 目录：

```sh
p=/home/wh1stl3/.local/bin/python3.11
base=/mnt/d/Code/PortingiOS/UniXNU
stage=out/nuwa-v1-legacy-reset-r2-20261128-input
b=out/nuwa-v1-legacy-reset-r2-20261128-verify-build
pkg=out/nuwa-v1-legacy-reset-r2-20261128-verify-package
template=../worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-package/vendor_boot.img
cpo=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json

sha256sum -c out/nuwa-v1-legacy-reset-r2-20261128-sources.sha256
$p -B "$stage/scripts/build-nuwa-display-native.py" --base "$base" --cpo "$cpo" \
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
