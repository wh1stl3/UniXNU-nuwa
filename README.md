# UniXNU-nuwa

以 **UniXNU** 为底座，改造使 **nuwa（小米 13 Pro / SM8550 / 12 GB）** 运行 **iOS 16**。

## 当前进度（2026-10-25）

**nuwa实机已进入XNU的`kernel_bootstrap`入口。iOS尚未启动。** PROBE16镜像`6f0907b2`、内核`167bd013`在ADT缺少pram时跳过可选旧panic日志导入，保留原控制台初始化；用户文字与原图确认pmap绿色块下的kernel_bootstrap橙色块出现。仅证明入口，不证明完成、调度器、驱动、root或用户态。

本轮恢复于北京时间16:44:29：Android完成1、A槽，三个启动分区SHA与试前相同，无flash/erase/改槽。原始音视频、截图只保留本地，仓库提交脱敏文字/哈希/命令证据。

源DT panic区补丁已适配8796，函数体编译和边界测试通过；整核源码重建未完成。现有诊断内核仅支持缺pram路径，不能作为通用DT panic缓冲实现。下一步验证kernel_bootstrap内部和VM启动内存初始化，不把模型指令预算耗尽写成卡死。

先读[STATUS](docs/STATUS.md)、[v23实现/实测](docs/operations/2026-10-25-v23-dt-panic-console.md)和[官网QR/迁移复核](docs/operations/2026-10-25-official-porting-update.md)。官方二维码日志是UEFI/EBS前功能，nuwa尚未接入；Format2/共享SM8550迁移另行评审，保留iOS16 ABI及nuwa板值。

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
