# AGENTS.md — UniXNU-nuwa

长期规则见共享治理文档：`D:/Code/PortingiOS/docs/governance-2026-11-06.md`（12 条，v2 对齐官方 format 2）。本文件只写 nuwa 专属约定。

## 目标
小米 13 Pro（nuwa / SM8550）通过 UniXNU 运行 iOS 16（donor: iPhone10,3 / 16.7.16 / 20H392，xnu-8796 线）。

## 基线
- 基座：`D:/Code/PortingiOS/UniXNU`（上游 main `e2fdae4` + 本地 `af9d099`（submodule pin：ArmCpu=93a5030、XnuPrelink=f1d80d3）与 `693f5d9cae8a408dd18b39f3f9fdc4228c934241`（iOS 16.7.16-20H392 profile））。
- **已是官方 format 2 骨架**：`schema_version = 2`、`feeds.toml`（钉 `UniXNU-sm8550-common@a9f45dc6…`）、`dts/nuwa.dts`、`configs/nuwa_defconfig`、`patches/xnu/series`、`porting.toml`、`scripts/package.sh`、`.github/workflows/*`。
- 进度：官方第 4 步已完成——`defconfig` → `fetch` → `status --json` → `tree` 对 `board.os_profile = ios-16.7.16-20H392` 解析通过，`unixnu.lock` 已提交（设备仓基线 `279c990a0c7a238aa0a5818493c6cd6a46528749`）；第 5 步（硬件描述与固件）的固件配置已能构建（self-check，未独立复跑），`SILICIUM_UEFI.fd` 3145728 字节 = `0x300000`；Advanced Logger 已接线（`uefi-nuwa` `e494c01b`，self-checked 构建通过），未上机。
- 未完成：第 5 步 Advanced Logger 已接线（`uefi-nuwa` `e494c01b`，self-checked 构建通过），但运行时未验证（Tools→Advanced Logger 页与 dispatch）、内存所有权证据与启动链交接的独立审查（Astra High 通道不可用）仍缺；`[ipsw.sha256]` 缺 donor `KernelCache` 成员哈希（url/chip_id/board_id 与 DeviceTree、StaticTrustCache 哈希由 profile 提供）；`[payload.adt]` 的 `chip_id`、`root_match_volume_uuid` 仍是 `REQUIRED_*`；`[userdata]`、`[bootimg]` 缺实测值。
- 历史 8796 补丁（41+64）与 ADT 脚本仍在旧仓/备份，未迁入 format 2；`scripts/` 下是历史审计工具，可直接复用，但不再充当 ADT 生成器。

## 目录约定（官方布局）
- 板级文件：`board.toml`、`porting.toml`、`feeds.toml`、`configs/`、`dts/`、`patches/xnu/series`、`package/`、`scripts/package.sh`、`proprietary-files.txt`、`local.toml.example`。
- `drivers/`、`kits/` 不是设备仓目录——驱动与库来自组件仓，共享资源来自 SM8550 仓；设备 `package/` 在构建树内成为 `kits/nuwa`。
- 本机覆盖写 Git 忽略的 `local.toml`；设备输入写 `unixnu.local.toml`（基座检出处）。

## 硬边界
- flash/erase/改槽等设备写入动作：须用户当轮明确授权。
- 唯一 ECID（`--unique-chip-id`）等设备种子只经命令行或 Git 忽略的配置传入，不入库（治理 §6）。
- 含 Apple 组件的产物（`kernel.macho`、`boot.img` 等）只留本地 out/，不上传 GitHub（治理 §7）。
- 不照抄 sheng 板值（MMIO/IRQ/面板/电源/chip_id 均须 nuwa 证据）；组件一律用规范 ID。

## 记录纪律
`porting.toml` 是唯一权威记录：改代码同步对应区域的 findings/evidence，并跑 `python3 scripts/porting-record.py check --device .`。

## 关联文档
- AI 分工与调度：`../../docs/ai-orchestration-2026-11-06.md`。
- 路线背景：`../../docs/nuwa-ios17-sheng-migration-2026-11-06.md`。
