# UniXNU-nuwa

以 **UniXNU** 为底座，改造使 **nuwa（小米 13 Pro / SM8550 / 12 GB）** 运行 **iOS 16**。

## 当前入口（2026-10-24 19:2x）

**iOS 16 内核已在 nuwa 上实际执行过。** 内核候选 `1aeebf13` 经 `fastboot boot` 临时启动，DarwinBoot 打印 `Exiting boot services`、屏幕出现绿色横条，XNU 自身输出 `AppleARMPlatform: IODTNVRAM from …`、`SecurityLock::LockType: SOFTWARE_LOCK`、`LockCapsuleInterface`、`App Log Flush : 0 ms`，约 235 秒后设备自动重启回 Android。**iOS 未启动** —— 内核在 Apple 启动链安全锁阶段终止（判断置信中高，缺 SEP/硬件信任链）。恢复闭环完成：Android 完成 1、槽_a、三分区 SHA 未变。详见[首次内核进入](docs/operations/2026-10-24-xnu-first-entry.md)。

确切读数：`kernel va 0xfffffff003DC8000 pa 0x8C01C8000`、`window 0x40000000 bytes`（**1 GiB 连续窗口由 UEFI 成功给出**）、`TCR_EL1 0x28003518`（4 KiB granule，与 D-003 一致）、`CurrentEL 1`。

同日离线完成 ADT 生成器落地（`scripts/make-nuwa-adt.py` 等四个脚本，板级常量逐项对回实机 FDT，结构审计与正负例 0 失败）、R-012 批准 A（写入 `dram_size = 0x240000000` 与 `owned_memory_size = 0x40000000`）、以及早期安全初始化器通路打通（`early_security_init` 被 emitter 接受、注册调用 ABI 静态核对通过）。

分析内核的 `loadable` 标志仍为 `false`（人工资格化字段），但**实机已证明它可被加载并跳转**。

续接先读 [STATUS](docs/STATUS.md) 与[主线交接](docs/operations/2026-10-23-mainline-handoff.md)，再看[全量更新记录](docs/operations/2026-10-24-upstream-integration.md)。不重复已结束的设备试验。

## 为什么单开一个仓库

旧仓 `D:\Code\PortingiOS` 走的是自建 P16/16K 链路，已转为**只读资料库**（上游源码副本、实测记录、旧报告都在里面）。
本仓库只做「复用 UniXNU + 移植到 nuwa」这一条线，路线、目录、文档纪律都与旧仓分离，避免两套叙事混在一处。

## 先读什么

1. `AGENTS.md` —— 只读边界、版本管理、文档五件套、硬停边界。**动手前必读**。
2. `docs/STATUS.md` —— 现在做到哪、下一步、已知坑。
3. `docs/DECISIONS.md` —— 已定决策：D-001/D-002内存窗口、4KiB、iPhone donor与8796路线，带证据。
4. `docs/inherited/unixnu-official-2026-10-22.md` —— 官方移植指南摘录、board schema与bring-up契约；旧handoff-route仅作历史参照。
5. `docs/operations/2026-10-24-nuwa-adt.md` —— ADT 生成器契约、板级值溯源、两处证据分歧的判断。

## 仓库与构建

[UniXNU基座fork](https://github.com/wh1stl3/UniXNU)承载Actions，本仓是独立设备输入；固件已迁入独立[uefi-nuwa仓](https://github.com/wh1stl3/uefi-nuwa)，设备仓固定引用固件提交并管理诊断补丁。正式构建从基座用`-D ../UniXNU-nuwa`接入。ADT 工具与 `dram_size`/`owned_memory_size` 已就位，ADT 侧参数可按 `payload.py` 的规则组装并离线复核；但 `[ipsw]`、`[kernel]`、`[firmware]` 等仍有 TODO，board 保持 `example = true`，基座整体构建仍不可运行。

首轮云端源内核入口见`docs/operations/2026-10-22-source-kernel-ci.md`。它复用固定75bc基座配方，编译8796源码，不运行donor预链接或镜像打包。构建状态只以`docs/STATUS.md`及原始CI日志为准；源编译与QEMU结果均不能当成实机通过。

## 目录

```
docs/            STATUS / WORKLOG / DECISIONS / NEED-REVIEW / PENDING-HUMAN
docs/inherited/  上一轮探针证据（P0 报告、iomem、partitions、meminfo、nuwa-observed）
docs/operations/ 长篇操作记录
scripts/         ADT 生成与审计、构建与验证脚本
reports/         产出的报告
```

## 边界

- 不改 `D:\Code\PortingiOS`，不改 `D:\Code\PortingiOSWithUniXNU`。
- 上游源码不复制进本仓库，按路径引用。
- 模拟器 / QEMU 结果不得写成实机通过。
