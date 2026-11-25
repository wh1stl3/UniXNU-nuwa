# nuwa UFS 信息汇总（2026-11-25）

**记录整理，self-checked；未运行设备命令，未刷写。**
本文只汇总既有 UFS 事实并标注出处与验证等级，不新增硬件行为、不授权任何写操作。
所有「已验证」仅指本记录对本地文件的重算；设备侧数值仍是 2026-11-07 只读采集或主控转述。

| 来源 | 内容 | 本记录的处理 |
| --- | --- | --- |
| `.cache/device-evidence/20261107-recovery/gpt-sd{a,b,e,f}.bin` | 4096 B LBA 设备前 32 KiB（主 GPT） | 重算 header/entry CRC32，全部匹配 |
| `.cache/device-evidence/20261107-recovery/{blk-sizes,blockdev}.txt` | 六 LUN 的 `size`/块大小/`ro` | 原文数值照录 |
| `.cache/device-evidence/20261107-recovery/live.dts`（SHA256 `1a329e36397fbc64b98b745e6a1f6794d18d3ff2a0c3f25202a68d2459c66101`） | 设备运行时的 ufshc 节点 | 与 OSS 交叉核对 |
| `MiCode/kernel_devicetree` branch `fuxi-t-oss` @ `5647c799a064dfec73332a4fe2ef7aa3fb2f4887` | `qcom/kalama.dtsi`、`qcom/xiaomi-sm8550-common.dtsi` | 逐行读取 |
| `MiCode/Xiaomi_Kernel_OpenSource` branch `fuxi-t-oss` @ `7fad87dc178d09489b74a714e4a525d56f546855` | `drivers/scsi/ufs/ufs-qcom.c`、`drivers/scsi/ufs/ufshcd.c` | 逐行读取 |
| `docs/device-evidence-2026-11-07.md` | LUN 与分区表 | 数值核对，见 §1.3 一处笔误 |
| `docs/nuwa-data-write-design-20261125.md`（branch `display/20h392-dsp-diag` @ `87264f3`） | 当前 iOS provider | 原文引用；该文不在本分支 |

## 1. GPT（2026-11-07 主表快照）

### 1.1 采集与校验

每个 `gpt-*.bin` 为 32768 B，即 4096 B LBA 设备的 LBA0..LBA7：LBA1 起为 GPT 头
（偏移 4096），entry array 在偏移 8192（sda/sdb/sdf 32 槽×128 B，sde 96 槽）。
本记录重新解析并逐项核对：

| 文件 | 头部 CRC32（存/算） | 条目 CRC32（存/算） | 当前头 LBA | 备用头 LBA | 可用范围 | 槽位/已用 |
| --- | --- | --- | --- | --- | --- | --- |
| `gpt-sda.bin` | `41835d9b` / 同 | `4edcb8b5` / 同 | 1 | 61850623 | 6..61850618 | 32 / 32 |
| `gpt-sdb.bin` | `349daa90` / 同 | `262cf78a` / 同 | 1 | 5119 | 6..5114 | 32 / 5 |
| `gpt-sde.bin` | `c36256a9` / 同 | `e0e2605f` / 同 | 1 | 588799 | 6..588792 | 96 / 76 |
| `gpt-sdf.bin` | `faeca65b` / 同 | `a90b03cf` / 同 | 1 | 8191 | 6..8186 | 32 / 6 |

`sdc`、`sdd` 的 GPT 未采（只有 `blk-sizes`/`blockdev` 的容量读数），本文件不推断其分区表。

### 1.2 分区（LBA 为 4096 B 单位）

| 分区 | LUN | first_lba | last_lba | LBAs | 字节（LBA×4096，算术值） |
| --- | --- | --- | --- | --- | --- |
| userdata | sda32 | 3110976 | 61850618 | 58739643 | 240597577728（约 224 GiB） |
| super | sda31 | 751680 | 3110975 | 2359296 | 9663676416（9 GiB） |
| boot_a | sde14 | 149126 | 198277 | 49152 | 201326592（192 MiB） |
| recovery_a | sde27 | 249990 | 275589 | 25600 | 104857600（100 MiB） |
| vendor_boot_a | sde24 | 217670 | 242245 | 24576 | 100663296（96 MiB） |

`vendor_boot_a` 是同一份 `gpt-sde.bin` 的读数，因启动载荷落在这里一并列出。
`userdata` 的 `last_lba` 等于 sda 的最后一个可用 LBA（61850618）：这是 GPT 观察，
不构成「userdata 归本移植所有」或「可写」的结论。

### 1.3 与旧记录的差异

`docs/device-evidence-2026-11-07.md:60` 的 super 行写作 `2361296` LBA / `9671868416` B，
与同一行的 LBA 边界（751680..3110975）不符。正确值是 `2359296` LBA / `9663676416` B，
即本表数值；旧文为笔误，LBA 边界本身无误。该处只在本文更正，不回改历史文档。

### 1.4 边界

- **这是 2026-11-07 的主 GPT 快照。** 备用 GPT 未采（文件只覆盖 LBA0..7，`altLBA`
  见 §1.1 但内容不在本地），此后是否有分区表变更未知。
- 写授权前必须 live 重读主、备两份表并比对，不能以本快照代替当轮读数。
- 单位陷阱仍在：GPT 用 4096 B LBA，`/sys/block/*/size` 与 `blockdev --getsz` 用
  512 B 扇区（误差因子 8）。

## 2. LUN 与块设备（2026-11-07 只读采集）

原文 `blk-sizes.txt` / `blockdev.txt`（`size` 为 512 B 扇区计数，`lbs`/`ss` 为逻辑块大小）：

| LUN | `size`（512 B 扇区） | 逻辑/物理块 | `ro` | 折合 4096 B LBA | 字节 |
| --- | --- | --- | --- | --- | --- |
| sda | 494804992 | 4096 / 4096 | 0 | 61850624 | 253340155904（236 GiB） |
| sdb | 40960 | 4096 / 4096 | 0 | 5120 | 20971520（20 MiB） |
| sdc | 40960 | 4096 / 4096 | 0 | 5120 | 20971520（20 MiB） |
| sdd | 65536 | 4096 / 4096 | 0 | 8192 | 33554432（32 MiB） |
| sde | 4710400 | 4096 / 4096 | 0 | 588800 | 2411724800（2.25 GiB） |
| sdf | 65536 | 4096 / 4096 | 0 | 8192 | 33554432（32 MiB） |

- 六个 LUN 全部 `ro=0`：内核未声明只读，**不等于**已授权写入。
- `sda size × 512` 与 `gpt-sda.bin` 的 61850624×4096 相等，两种单位自洽。
- 2026-11-07 的采集环境是 TWRP 3.7.1_12（root adb，`_a` 槽，Android 5.15.195 内核）；
  `ro=0` 是该环境下的属性，iOS 启动后的状态未测。

## 3. 平台配置（小米 OSS + 本机 live DTB）

### 3.1 IOMMU 与 DMA 声明

| 项 | 值 | 出处 |
| --- | --- | --- |
| `iommus` | `<&apps_smmu 0x60 0x0>`（流 ID `0x60`，两参数单元） | `kalama.dtsi:2321`；live.dts:8998 为 `<0x3e 0x60 0x00>` |
| `qcom,iommu-dma` | `"fastmap"` | `kalama.dtsi:2322`；live.dts:8999 |
| `dma-coherent` | 存在 | `kalama.dtsi:2323`；live.dts:9000 |
| SMMU provider | `qcom,qsmmu-v500`，窗口 `0x15000000 + 0x100000`、`0x151fe000 + 0x40` | live.dts:15245–15259 |

`dma-coherent` 与 `fastmap` 只是 Android 侧声明，不证明 XNU 的映射/一致性，
也不构成接管该 SMMU 上下文的授权。

### 3.2 寄存器窗口（三对）

| 名 | 基址 | 长度 |
| --- | --- | --- |
| `ufs_mem` | `0x1d84000` | `0x3000` |
| `ufs_ice` | `0x1d88000` | `0x8000` |
| `ufs_ice_hwkm` | `0x1d90000` | `0x9000` |

出处：`kalama.dtsi:2212–2215`、live.dts:8978–8979；`iomem.txt:11` 记录
`01d88000-01d8ffff : 1d84000.ufshc ufs_ice`（32 KiB，与 `0x8000` 一致）。

### 3.3 resets：分两层，别混用

- SoC 节点 `ufshc@1d84000`（`kalama.dtsi:2210–2339`）**没有** `resets` 属性。
- 小米板级 `qcom/xiaomi-sm8550-common.dtsi:98–119` 在 `&ufshc_mem` 上追加
  `reset-gpios = <&tlmm 210 GPIO_ACTIVE_LOW>`、`resets = <&gcc GCC_UFS_PHY_BCR>`、
  `reset-names = "rst"`。nuwa 与 fuxi 共用这份 common dtsi。
- nuwa 实机 DTB 同样带这三项（live.dts:9014–9016，`resets = <0x37 0x18>`）。

因此「无 `resets`」只在 SoC 节点层成立；成品板有 GCC 复位与 GPIO 复位。
`out/nuwa-ufs-input-audit-20261110.md` 的表已按 GCC `[0x37,0x18]`/GPIO 210 记录。

### 3.4 `ufs_qcom_force_mem_config`

`ufs-qcom.c:719–747`，在 `ufs_qcom_hce_enable_notify` 的 `PRE_CHANGE` 调用（:757）：

| 时钟 | MEM 标志 |
| --- | --- |
| `core_clk_ice`、`core_clk_ice_hw_ctl` | `CLKFLAG_RETAIN_MEM` |
| 其余 gcc 时钟 | `CLKFLAG_NORETAIN_MEM` |
| 全部（含上一行） | `CLKFLAG_NORETAIN_PERIPH` + `CLKFLAG_PERIPH_OFF_CLEAR` |
| `ref_clk`（rpmh） | 跳过 |

含义：ICE 关闭时保留其 RAM（含密钥配置），host controller 的非 ICE RAM 掉电。
**这不能当作 ICE 上下文在控制器 reset 后仍有效的证明**——它只描述时钟门控行为。

### 3.5 abort/clear 只以 DB=0 为判据

`ufshcd.c:1091–1140` 的 `ufshcd_wait_for_doorbell_clr()`：轮询
`UTP_TASK_REQ_DOOR_BELL` 与 `UTP_TRANSFER_REQ_DOOR_BELL` 是否同时为 0，
超时后再补一次检查即返回。函数内**没有** DMA 排空、unmap、cache 维护或
迟到完成排除。结论：`DB=0` 是软件可见的提交队列空，不是介质/DMA 完成的独立证据；
这与 `docs/nuwa-ufs-queue-five-run-20261114.md` 对 `UTRLDBR=0` 仅瞬时的判断一致。

## 4. iOS provider 现状（branch `display/20h392-dsp-diag` @ `87264f3`）

> 这一节描述 r8 候选，代码与设计只在 `display/20h392-dsp-diag`；本分支
> （`display/20h392-abi`）没有 `package/nuwa-data-write/`。此处按分支+提交引用，
> 不代表已合入。

### 4.1 队列与提交

| 项 | 值 | 出处 |
| --- | --- | --- |
| 传输列表 | UTRLBA/UTRLBAU `0x50/0x54`，UTRLDBR `0x58`，UTRLCLR `0x5c`，UTRLRSR `0x60` bit0 | `nuwa-data-write-design-20261125.md:339` |
| 任务列表 | UTMRLBA/UTMRLBAU `0x70/0x74`，UTMRLDBR `0x78`，UTMRLCLR `0x7c`，UTMRRSR `0x80` bit0 | 同上 |
| 槽位 | 单槽（slot 0），DB bit 0，每次提交写一次 | 同上 `:341` |
| 接管 | 只在接管时确认两 DB 空、屏蔽 IE、停两列表、换 UTRL BA/U、重启 UTRL；不改 UTMR BA/U、不重启 UTMR、不用 CLR | `retained/PreservedNop.h:68–128` |
| DMA | 连续 147456 B：UTRD 0、UCD 4096、response 4608、PRDT 5120、data 16384 | `CombinedRead.h:39–70,92–153` |

常用简写「UTRL 0x50/0x60、UTMR 0x70/0x80」指「基址 + RSR」；
DB 在 `0x58`/`0x78`，单槽用 bit0。

### 4.2 Data 写后端

- 单块 4096 B WRITE(10)：opcode `0x2a`，FUA bit `0x08`，transfer length 1，
  UTRD 方向 host→device，UPIU LUN 0、write flag `0x20`、expected length 4096，
  单 PRD 指向 retained bounce（长度编码 4095）。
- 复用 `Gate.h`（源自 ShengUfs `f020bd69` `RootCommands.h`）的窗口判定与 FUA CDB；
  不接上游多槽写路径。
- **写门关闭**：生产面仍是 `Provider<CandidatePort, false>`，未启用编译 opt-in；
  `native_ufs_store_write/sync` 只走软件门禁并返回 0，`RetainedWritePort` 实际发写
  路径未链接。`sync` 是完成屏障，不发 `SYNCHRONIZE CACHE`。
- 任何失败（含归属明确的 CHECK CONDITION）终止本会话并锁存隔离；timeout 保持
  orphan，不重放。冷启动资格与 FUA 硬件资格当前均为 false，**无真介质 FUA 持久性证明**。

### 4.3 历史读数

- `PU DATA st=4`（r30，`docs/nuwa-userspace-20261119-observation.md:53`）：Data 卷已
  挂载且可写，`kb=ooo`；同轮 keybagd 在 `t=72109 ms` 请求普通重启。这是 r30 的历史
  读数，不是当前候选的状态。
- r34 页面 `DATA st=4` 同义；本轮（2026-11-25）未重新读取。

## 5. 未知项

1. **UFS 设备描述符**：LUN 数量/配置、`bUFSFeaturesSupport`（FUA、cache）、
   `bLUWriteProtect`、cache 大小与 flush 行为——无 READ DEVICE DESCRIPTOR 采集。
2. **live GPT**：当前主/备表与 2026-11-07 快照是否一致、槽位与分区表是否变过。
3. **bsg/透传通道**：是否存在可用 `/dev/bsg/*`（或等价）节点、能否在不接管队列的
   前提下发查询命令。
4. **FUA 断电持久性**：真实介质上 FUA 写后立即断电是否持久；当前只有 mock 与
   设计论证。
5. **控制器 reset 后的 retained domain**：SID `0x60` 的 SMR/CBAR/SCTLR、UTM/UTR
   归属、link 有效性在 reset 后是否仍成立——均未证。
6. **ICE/CRYPTODMA 与厂商 UTRL 配置寄存器**：板上地址、位义、reset 持久性 unknown，
   候选不读写。
7. **介质状态**：坏块/寿命/写保护锁存（`bLUWriteProtect` 与 fuse 层）未采。

## 6. 已知 / 未知 / 写授权前必须补

| # | 已知（可引用） | 未知（不得假设） | 写授权前必须补 |
| --- | --- | --- | --- |
| 1 | sda 61850624×4096，主 GPT 头/条目 CRC 通过 | live 主表是否仍如此 | live 重读主、备两份 GPT 并比对 |
| 2 | userdata `3110976..61850618` = 240597577728 B | 目标窗口内是否有他方数据 | 窗口内容抽查 + 用户确认数据可弃 |
| 3 | super `751680..3110975` = 9663676416 B | — | 与备份/回滚件一致性核对 |
| 4 | boot_a `149126..198277` 192 MiB | 槽内当前镜像是否为本轮件 | 回读槽内镜像并核哈希 |
| 5 | recovery_a `249990..275589` 100 MiB | 槽内内容 | 回读或不使用该槽 |
| 6 | vendor_boot_a `217670..242245` 96 MiB | 槽内当前镜像（r9/r34 记录未回读） | 回读并核哈希 |
| 7 | 六 LUN 容量/4096 B 块/`ro=0`（TWRP 环境） | iOS 启动后的 `ro` 与可见性 | 启动后重新读 sysfs/blockdev |
| 8 | userdata 末 LBA = sda 最后可用 LBA | 是否希望扩到分区边界 | 明确目标范围，不擅自扩展 |
| 9 | `iommus = <&apps_smmu 0x60 0x0>` | 该域当前归属与空闲上下文 | SMMU 域归属证据（DMA/IOMMU 改动需 deep review） |
| 10 | `dma-coherent` + `qcom,iommu-dma="fastmap"`（Android 声明） | XNU 侧一致性与映射契约 | 明确一致性契约后再谈映射 |
| 11 | ICE `0x1d88000+0x8000`、HWKM `0x1d90000+0x9000` | CRYPTODMA/厂商 UTRL 配置寄存器地址位义 | 不读写未知窗口；需要时另取证据 |
| 12 | SoC 节点无 `resets`；板级有 GCC `GCC_UFS_PHY_BCR` + GPIO 210 | reset 后各寄存器/域/链路状态 | reset 后状态复核 |
| 13 | `force_mem_config` 仅 ICE clock `RETAIN_MEM` | ICE 上下文 reset 后是否有效 | 该结论不能替代证据 |
| 14 | abort/clear 只看 DB=0，无 DMA 排空 | 总线/SMMU 在途 DMA 何时真正结束 | 独立的 DMA 终止证据 |
| 15 | provider 单槽、DB bit0、寄存器偏移见 §4.1 | UTMR 是否曾被固件使用 | 不假设 UTMR 可用 |
| 16 | 4096 B 单块 FUA 后端存在、生产写门关闭 | 真实介质 FUA 持久性 | 断电试验设计 + 授权 |
| 17 | 历史 `PU DATA st=4`（r30/r34） | 当前候选下 Data 状态 | 新一轮上机读数 |

**结论**：GPT/LUN 几何与平台声明这一层已经够用；缺的是 (a) live 双表重读、
(b) 设备描述符（FUA/cache/WP）、(c) reset 后 DMA/SMMU 终止与 retained 域有效性。
在这三项补齐前，`docs/context-brief.md` 的「写操作须当轮授权」是唯一放行条件，
本文不构成任何写入许可。

## 复跑（独立 verifier 可重做）

GPT 校验无需设备，可用任意脚本读取本地文件重算（本记录用 node 逐字节解析）：

```sh
# 期望：EFI PART 位于偏移 4096，header CRC 与 entry array CRC 均自洽
# sda 41835d9b/4edcb8b5, sdb 349daa90/262cf78a,
# sde c36256a9/e0e2605f, sdf faeca65b/a90b03cf
```

OSS 侧复跑：按文首来源表里的 commit 取 `qcom/kalama.dtsi:2210–2339`、
`qcom/xiaomi-sm8550-common.dtsi:98–119`、`drivers/scsi/ufs/ufs-qcom.c:719–747`、
`drivers/scsi/ufs/ufshcd.c:1091–1140`，核对本文引用的每个值。
