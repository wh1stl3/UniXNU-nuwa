# UniXNU-nuwa

Xiaomi 13 Pro（nuwa，SM8550）的 UniXNU 设备仓。目标：iOS 16.7.16 / 20H392，donor 身份 iPhone10,3（D22AP）。

**最新进展（2026-11-07）**：官方 bring-up **阶段 1（UEFI）已通过、阶段 2（UniXNU 菜单）菜单已出现**。四次 `fastboot boot`（不写分区）：header v1 未交接；header v4 后固件跑起来；清空 `uefipil.cfg` 的 `[AUTO]` 消除 PIL panic；DXE Heap 改为 `0xBAB00000+0x0D1C0000`（`uefi-nuwa` `d7c97a7`）后 `DxeMain.c(581)` 断言消失，UniXNU 内置配置菜单出现（倒计时 10 s，默认 `Return to firmware`）。Tools → Advanced Logger 以 24 个 OneSend 二维码导出日志，主机已解码（179 行）：RamManager 映射了高 9 GiB，UniXNURamDisk 发布了 initrd 块设备。所有区域仍为 `planned`。详见 `docs/step5-firmware.md` 的 "First hardware runs" 与 "Run 4"。**下一步**：官方阶段 3（负载）——先弄清 ABL 附带约 32 MiB ramdisk 与 payload FAT 卷的位置关系（`unixnu bootimg` 的 `vendor_boot` 处理），再构建 payload；每次上机前须用户当轮授权并检查 A 槽重试计数。

**此前阶段**：官方 `porting/steps` **第 5 步（准备硬件描述与固件）的固件配置已能构建，并由独立 Verifier 复跑（PASS）**。第 4 步已完成并留证：`defconfig` → `fetch` → `status --json` → `tree` 对本地 iOS 16.7.16-20H392 profile 解析通过，`unixnu.lock` 已提交。OS profile 在本地基座 `UniXNU` 的 `693f5d9cae8a408dd18b39f3f9fdc4228c934241`（xnu 8796.141.3 / `1b191cb58250d0705d8a51287127505aa4bc0789`）；本仓记录基线 `279c990a0c7a238aa0a5818493c6cd6a46528749`。第 5 步 `uefi-nuwa` 的 `nuwaPkg` DSC/FDF 集成（UniXNU、UniXNUDxe、UniXNURamDiskDxe、DarwinBoot、AdvancedLogDxe）构建退出码 0，产出 `SILICIUM_UEFI.fd` 3145728 字节（= `0x300000`，与 `nuwa.toml` 的 `uefi_fd.size` 一致），构建步骤见 `docs/step5-firmware.md`。**Advanced Logger 已接线**（`uefi-nuwa` `e494c01b`：DXE_CORE 用 DxeCore 版 `AdvancedLoggerLib` 安装 `gAdvancedLoggerProtocolGuid`，驱动用 Dxe/Runtime 实例，构建通过），但**仍未上机**。ADT 身份已定：`chip_id = 4acab8db` 已写入 `board.toml`；`unique-chip-id` 种子只存在于基座检出里被 git 忽略的 `unixnu.local.toml`（每次构建沿用同一值，需用户自行备份）；`root_match_volume_uuid` 已注释掉，待 userdata 镜像构建后、阶段 6 前补。仍缺：运行时验证（Tools→Advanced Logger 页与 dispatch）、内存所有权证据（`0xbe000000-0xd4c00000` 的现行所有者、`0xafffff000-0xb00000000` 尾部）。启动链常规审查已出结论——**APPROVE WITH CONDITIONS**（仅针对首次 `fastboot boot`；未升级 Deep Reviewer，因无候选满足 `ai-orchestration` §2.3）。静态对账另有两条约束：`MemoryMapLib` 未描述 6 个 live `no-map` 保留区；不要调小 `owned_memory_size`（低于约 925 MiB 窗口会落到 ADT `dram-base` 之外）。**下一步**：首次 `fastboot boot` 的放行条件还剩 RamPartition 协议生产者确认、SEC HOB 写入确认与用户当轮明确授权（**尚未放行**）；上机验证 Tools→Advanced Logger 与运行时 dispatch，内存门禁取证，root UUID 补齐后再进入第 6 步驱动选型。

## 三仓关系

| 仓 | 作用 | 位置 |
| --- | --- | --- |
| `UniXNU-nuwa`（本仓） | 板级连接、组件选择、镜像与分区策略、记录 | 本目录 |
| `UniXNU-sm8550-common` | SM8550 共享资源、DTSI、SoC 配置与补丁 | `../UniXNU-sm8550-common`（上游 `UniXNU/` 检出，HEAD = `a9f45dc6…`，与 `feeds.toml` 同一 commit） |
| `uefi-nuwa` | Mu-Silicium 固件（nuwaPkg、`Resources/Configs/nuwa.toml`） | `../uefi-nuwa` |
| `UniXNU`（基座） | 解析器、package、DarwinBoot、组件 | `../../UniXNU` |

## 前置条件

- 基座检出：`D:/Code/PortingiOS/UniXNU`（`[package] unixnu` 指向它）。
- Python 3.11+、git、`dtc`、`mtools`；内核与 payload 在 Linux/WSL 构建（`scripts/linux/setup-toolchain.py`）。
- 网络：`unixnu fetch` 需要拉取 feeds 与 Apple 源码参考。

## 构建

在基座检出目录执行：

```sh
./unixnu defconfig nuwa_defconfig -D ../nuwa/UniXNU-nuwa
./unixnu fetch -D ../nuwa/UniXNU-nuwa
./unixnu status --json -D ../nuwa/UniXNU-nuwa
./unixnu tree -D ../nuwa/UniXNU-nuwa
```

或使用设备打包脚本（所有取值来自 `board.toml`）：

```sh
scripts/package.sh --check --os ios-16.7.16-20H392
scripts/package.sh --os ios-16.7.16-20H392 --uefi ../uefi-nuwa
```

第 4 步的 `defconfig` / `fetch` / `status --json` / `tree` 已对 `board.os_profile = ios-16.7.16-20H392` 解析通过，不再停在解析阶段；镜像组装属第 7 步。仍缺：donor `KernelCache` 成员在 `[ipsw.sha256]` 的哈希、`[userdata]` 几何与 `[bootimg]` 实测值——待办见 `porting.toml` 的 `configuration`、`packaging` 区域。

## 记录

`porting.toml` 是唯一权威记录（14 个区域，完成等级 `planned` → `device-verified`）。改动代码后同步对应区域的 findings/evidence，并运行：

```sh
python3 scripts/porting-record.py check --device .
```

## 文档

- 移植流程：<https://unixnu.com/zh/porting/steps>
- 设备仓规范：<https://unixnu.com/zh/porting/device-repository>
- 迁移指南：<https://unixnu.com/zh/porting/migration>
- 组件目录：<https://unixnu.com/zh/reference/components>
- 启动验证：<https://unixnu.com/zh/porting/bring-up>

## 约定

治理规则见 `../../docs/governance-2026-11-06.md`（12 条）。Apple 派生产物（`kernel.macho`、`boot.img`、IPSW 组件）只留本地 `out/`，不上传 GitHub；ECID 等设备种子只经命令行或 Git 忽略的 `unixnu.local.toml` 传入。
