# UniXNU-nuwa

Xiaomi 13 Pro（nuwa，SM8550）的 UniXNU 设备仓。目标：iOS 16.7.16 / 20H392，donor 身份 iPhone10,3（D22AP）。

**当前阶段**：官方 `porting/steps` 第 2–3 步之间——仓库已转成 format 2（`schema_version = 2`），OS profile 与硬件输入仍在收集；`board.os_profile` 保持 `REQUIRED_OS_PROFILE`，解析失败属预期。

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

`board.os_profile` 仍是占位值、`[ipsw] url/chip_id/board_id/sha256` 未填之前，上述命令会在解析阶段停止；待办见 `porting.toml` 的 `configuration` 与 `packaging` 区域。

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
