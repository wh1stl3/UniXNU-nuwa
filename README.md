# UniXNU-nuwa

以 **UniXNU** 为底座，改造使 **nuwa（小米 13 Pro / SM8550 / 12 GB）** 运行 **iOS 16**。

## 当前入口（2026-10-24）

**单次实机文件校验通过**：固件内 `NuwaFileAuditDxe` 在 ReadyToBoot 只读 58335232 字节 `READTEST.BIN` 并验证完整 SHA-256，照片确认 `PASS exact length, EOF and SHA256 / exit Success`，30 秒后返回固件；随后恢复到 Android `boot_completed=1`、槽_a、三分区 SHA 与试前一致（北京时间 18:09:48）。产物 `6b3e5bfd…`/70266880 B，CI 40080439083 / dbbdc02，[诊断记录](docs/operations/2026-10-24-fv-file-audit.md)。**这是数据读取与 SHA 通过，不是内核执行。**

同日设备仓 ADT 生成器落地：`scripts/make-nuwa-adt.py` 按基座契约产出 `kernel.macho.adt`，板级常量逐项对回实机 FDT，结构审计 0 失败；[ADT 记录](docs/operations/2026-10-24-nuwa-adt.md)。`[payload] dram_size` 与 `[payload.adt] owned_memory_size` 属受审字段，等 [NEED-REVIEW](docs/NEED-REVIEW.md) R-012 批准，因此 board 仍 `example = true`。

分析内核 `eb66542c`（58335232 B）仍 **`loadable=false`**：早期安全初始化器调用 ABI、donor/native C++ 与结构 ABI、真实 ADT 与运行时分配窗口、大负载装载四项未资格化。文件 SHA PASS 不构成执行许可。

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

[UniXNU基座fork](https://github.com/wh1stl3/UniXNU)承载Actions，本仓是独立设备输入；固件已迁入独立[uefi-nuwa仓](https://github.com/wh1stl3/uefi-nuwa)，设备仓固定引用固件提交并管理诊断补丁。正式构建从基座用`-D ../UniXNU-nuwa`接入。ADT 工具已就位（`[payload.adt] tool`），但 `dram_size`/`owned_memory_size` 未获批，payload 步骤仍不可运行；加上其它 TODO，board 保持 `example = true`，尚不能作为完整设备构建配置。

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
