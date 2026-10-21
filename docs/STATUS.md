# STATUS

> 当前唯一真相。每完成一个里程碑**全文重写**，不留过程；过程在 `WORKLOG.md`。

- 更新时间：2026-10-22 03:00
- 阶段：**S0 仓库就位 / 对齐官方移植骨架**（尚未编译内核，尚未生成镜像，尚未碰设备）
- 分支与提交：见 `git log --oneline`

## 需要你点头的一件事（不阻塞）

**D-003：内核页大小走 4 KiB，还是坚持 16K？** 官方 UniXNU 栈自带的是「4 KiB XNU 补丁」，sheng（4K）和 fuxi（沿用 sheng 预链接）都是 4K。本仓默认按 **4K** 推进——补丁集、预链接、defconfig、QEMU fixture 全围绕 4K，选 16K 就要自维护一套补丁并与官方文档脱钩。你说 16K 的话我改 D-004 并重排计划，但不要在 bring-up 中途换页大小。

## 目标

以 UniXNU 为底座改造，使 nuwa（小米 13 Pro / SM8550 / 12 GB）运行 iOS 16。

## 结构：官方是三仓，本仓只占一个

| 仓库 | 作用 | 现状 |
| --- | --- | --- |
| `UniXNU` | 基座：构建驱动、UEFI 启动管理器、DarwinBoot、通用驱动、4K 补丁 | 旧仓有副本，**需确认是否官方最新** |
| `UniXNU-nuwa` | 设备仓：board.toml、defconfig、驱动、kit、package | **本仓**，骨架已有 |
| `uefi-nuwa` | Mu-Silicium 固件移植：DSC/FDF、预检、厂商输入 | **缺** |

## 已确定

- **D-002**：内存窗口由 ADT 的 `darwinboot-memory-size` 决定，**上限 8 GiB**；`[payload] dram_size` 与 `[payload.adt] owned_memory_size` 是板级键，二者不等价。bring-up 先要 512 MiB–1 GiB，不要一次要到顶。
- **D-001 内核侧事实仍有效**：XNU physmap 只有单窗口（`arm_vm_init.c:378,1961`），`pa < gPhysBase` 会 panic。
- 同 SoC 已有移植可对照：**fuxi**（小米 13）自述「基于 UniXNU-sheng 的板级分支，沿用 iPad7,1 iPadOS 17.7.11 镜像与 sheng 预链接」，**vermeer**（K70）有源码构建基线，**sheng** 是功能最全的官方样本。→ 第一版 `board.toml` 照 sheng/fuxi 的结构抄，只换数值。
- 官方文档摘录见 `docs/inherited/unixnu-official-2026-10-22.md`（board.toml 全字段、ADT 契约、七阶段判据、QEMU fixture 命令）。

## 下一步（按序）

1. **补齐三仓**：确认/更新 `UniXNU` 基座（官方 master），建立 `-D ../UniXNU-nuwa` 的调用关系；`uefi-nuwa` 先只做空壳 + 决策记录，等阶段 1 再填。
2. **抄骨架**：拉 `UniXNU-sheng` 与 `UniXNU-fuxi` 作只读参照，产出本仓第一版 `board.toml`（`[board]`/`[ipsw]`/`[userdata]`/`[kernel]`/`[payload]` 全段，未知值写 TODO，不要编数值）。
3. **先跑 QEMU fixture**：`scripts/qemu-entry/make-dt.py` + `package/Scripts/qemu-run.py`，目标是阶段 2「菜单出现」与阶段 4「`DARWINBOOT:` 打印」。**不碰设备、不出 nuwa 镜像，但能证明基座在本机可用。**
4. 之后才谈 UEFI 移植（阶段 1）与 ADT 生成器（`scripts/make-nuwa-adt.py`）。

## 已知坑

- `darwinboot-memory-size` 有 **8 GiB 硬上限**，nuwa 的 9 GiB 主 bank 用不满。
- `dram_size` ≠ `owned_memory_size`，sheng 是 2 GiB vs 4.75 GiB；照抄一个漏抄另一个会很难查。
- sheng 的 ABL **需要启动镜像里有 `/reserved-memory/splash_region` 节点，否则关屏**；nuwa 的 ABL 是否同样需要，属阶段 1 验证项。
- `/chosen` 缺 `unique-chip-id`/`chip-id` 会让 `gethostuuid()` 无限等；`/chosen/memory-map` 缺占位符时 DarwinBoot 返回 `EFI_COMPROMISED_DATA`。
- IPSW 身份必须整组匹配（product/version/build/device_class/chip_id/board_id + sha256），抄 sheng 的 iPad7,1 值不保证对 nuwa 成立。
- 设备侧：`verifiedbootstate=orange` 但 `flash_locked=1`、`vbmeta_device_state=locked`，能否 flash 必须进 bootloader `getvar unlocked` 确认。
- b 槽 `successful:no` 不是可靠兜底；真实兜底是 a 槽重试（剩 6 次）→ TWRP → 强制重启。

## 不要做的事

- 不要修改 `D:\Code\PortingiOS`（只读资料库）或 `D:\Code\PortingiOSWithUniXNU`（已废弃，只读参照）。
- 不要自己发明 `board.toml` 字段名，官方 schema 见 `docs/inherited/unixnu-official-2026-10-22.md` §2。
- 不要把旧仓 `nuwa-mmu16` / P16 那套结论平移过来（页大小不同、代码基座不同）。
