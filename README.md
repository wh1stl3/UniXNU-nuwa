# UniXNU-nuwa

以 **UniXNU** 为底座，改造使 **nuwa（小米 13 Pro / SM8550 / 12 GB）** 运行 **iOS 16**。

## 当前入口（2026-10-24）

全部已审查上游源码更新已合并到基座e553e46，21模块固定；新固件CI40014018074、Darwin22/iOS16源内核CI40015845083通过，实际二进制/平台归档已复核。GPU VM软件夹具通过用户态QEMU，硬件激活和实机兼容性仍单独验收。新FD/内核未在手机启动；既有26ef8efd缓存候选已实测跨过MMU到配置菜单并恢复Android。

续接先读[STATUS](docs/STATUS.md)、[主线交接](docs/operations/2026-10-23-mainline-handoff.md)和[全量更新记录](docs/operations/2026-10-24-upstream-integration.md)。实际ADT/OS窗口/大负载运输与新内核预链接仍待完成，不重复已结束的设备试验。

## 为什么单开一个仓库

旧仓 `D:\Code\PortingiOS` 走的是自建 P16/16K 链路，已转为**只读资料库**（上游源码副本、实测记录、旧报告都在里面）。
本仓库只做「复用 UniXNU + 移植到 nuwa」这一条线，路线、目录、文档纪律都与旧仓分离，避免两套叙事混在一处。

## 先读什么

1. `AGENTS.md` —— 只读边界、版本管理、文档五件套、硬停边界。**动手前必读**。
2. `docs/STATUS.md` —— 现在做到哪、下一步、已知坑。
3. `docs/DECISIONS.md` —— 已定决策：D-002内存窗口、4KiB、iPhone donor与8796路线，带证据。
4. `docs/inherited/unixnu-official-2026-10-22.md` —— 官方移植指南摘录、board schema与bring-up契约；旧handoff-route仅作历史参照。

## 仓库与构建

[UniXNU基座fork](https://github.com/wh1stl3/UniXNU)承载Actions，本仓是独立设备输入；固件已迁入独立[uefi-nuwa仓](https://github.com/wh1stl3/uefi-nuwa)，设备仓固定引用固件提交并管理诊断补丁。正式构建从基座用`-D ../UniXNU-nuwa`接入，当前board保持example=true，尚不能作为完整设备构建配置。

首轮云端源内核入口见`docs/operations/2026-10-22-source-kernel-ci.md`。它复用固定75bc基座配方，编译8796源码，不运行donor预链接或镜像打包。构建状态只以`docs/STATUS.md`及原始CI日志为准；源编译与QEMU结果均不能当成实机通过。

## 目录

```
docs/            STATUS / WORKLOG / DECISIONS / NEED-REVIEW / PENDING-HUMAN
docs/inherited/  上一轮探针证据（P0 报告、iomem、partitions、meminfo、nuwa-observed）
docs/operations/ 长篇操作记录
scripts/         构建与验证脚本
reports/         产出的报告
```

## 边界

- 不改 `D:\Code\PortingiOS`，不改 `D:\Code\PortingiOSWithUniXNU`。
- 上游源码不复制进本仓库，按路径引用。
- 模拟器 / QEMU 结果不得写成实机通过。
