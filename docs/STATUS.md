# STATUS

> 当前唯一真相。每完成一个里程碑**全文重写**，不留过程；过程在 `WORKLOG.md`。

- 更新时间：2026-10-22 03:00
- 阶段：**S0 仓库就位 / 对齐官方移植骨架**（尚未编译内核，尚未生成镜像，尚未碰设备）
- 分支与提交：见 `git log --oneline`

## 需要你点头的一件事（不阻塞）

**D-005：「4K + iOS 16」的版本落差怎么办？** 基座 `feeds.toml` 钉死 `xnu-10063.141.1`（17.x），sheng 配 iPadOS 17.7.11 正好；但 **iOS 16 是 xnu-8796**，49 个补丁按 10063 写的。宿主建议先做一次 `git apply --check` 批量试算（旧仓对 sweet 补丁干过，38/49 可过），按失败面决定是「rebase 到 8796 直达 iOS 16」还是「先用 iOS 17.x iPhone 打通再降」。详见 `DECISIONS.md` D-005。**在此之前不动 `feeds.toml` 的 xnu 版本。**

## 目标

以 UniXNU 为底座改造，使 nuwa（小米 13 Pro / SM8550 / 12 GB）运行 iOS 16。

## 结构：官方是三仓，本仓只占一个

| 仓库 | 作用 | 现状 |
| --- | --- | --- |
| `UniXNU` | 基座：构建驱动、UEFI 启动管理器、DarwinBoot、通用驱动、4K 补丁 | 旧仓有副本，**需确认是否官方最新** |
| `UniXNU-nuwa` | 设备仓：board.toml、defconfig、驱动、kit、package | **本仓**，骨架已有 |
| `uefi-nuwa` | Mu-Silicium 固件移植：DSC/FDF、预检、厂商输入 | **缺** |

## 已确定

- **D-003 页大小 = 4 KiB**（用户 03:02 拍定）。16K 不进本仓，旧仓 `nuwa-mmu16` 的结论不平移。
- **D-004 平台身份 = iOS（iPhone donor），不是 iPadOS**。donor 沿用旧仓已定：`iPhone10,3 / d22ap / iOS 16.7.16 / 20H392`，内核参考源码 `8796.141.3`。
  **注意 `ipad_identity = true` 必须保持**——它写的是四个 `/chosen` 安全属性（`certificate-production-status=0` 等，给 `mobileactivationd` 走原生激活），与「跑不跑 iPadOS」无关。
- **D-002**：内存窗口由 ADT 的 `darwinboot-memory-size` 决定，**上限 8 GiB**；`[payload] dram_size` 与 `[payload.adt] owned_memory_size` 不等价。bring-up 先要 512 MiB–1 GiB。
- **D-001 内核侧事实仍有效**：XNU physmap 只有单窗口（`arm_vm_init.c:378,1961`），`pa < gPhysBase` 会 panic。
- 同 SoC 可对照：**fuxi**（小米 13）、**vermeer**（K70）、**sheng**（官方最全）。**但只抄结构，不抄 `[kernel.prelink]` 数值**——那些绑在 iPadOS 17.7.11 的 kernelcache 上。
- 官方文档摘录见 `docs/inherited/unixnu-official-2026-10-22.md`。

## 下一步（按序）

1. **D-005 的试算（最便宜、最先做）**：对 `xnu-8796` 树跑 49 个补丁的 `git apply --check`，把失败清单与失败类型（头文件/文档 vs pmap/SMMU/ABI）写成 `docs/operations/2026-10-22-patch-portability-8796.md`。结论决定走哪条版本路。
2. **补齐三仓**：确认/更新 `UniXNU` 基座（官方 master），建立 `-D ../UniXNU-nuwa` 调用；`uefi-nuwa` 先空壳 + 决策记录。
3. **抄骨架**：拉 `UniXNU-sheng`、`UniXNU-fuxi` 作只读参照，产出第一版 `board.toml`。`[ipsw]` 按 **iPhone donor（iOS 16.7.16 / 20H392 / d22ap）** 填，`[kernel.prelink]` 留 TODO 等 donor kernelcache 到手再算，**不许抄 sheng 的数**。
4. **先跑 QEMU fixture**：`scripts/qemu-entry/make-dt.py` + `package/Scripts/qemu-run.py`，目标阶段 2「菜单出现」与阶段 4「`DARWINBOOT:` 打印」。不碰设备、不出 nuwa 镜像。
5. 之后才谈 UEFI 移植（阶段 1）与 ADT 生成器 `scripts/make-nuwa-adt.py`。

## 已知坑

- **`[kernel.prelink]` 的 4 个值（`kernelcache_sha256` / `slide` / `early_security_init` / `roots`）与 donor kernelcache 强绑定**，sheng 那套是 iPadOS 17.7.11 的，抄来必炸。
- 基座 `feeds.toml` 钉 `xnu-10063.141.1`，与 iOS 16 的 8796 差一个大版本；改版本前先做 D-005 的试算。
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
