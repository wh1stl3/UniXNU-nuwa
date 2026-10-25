# UniXNU-nuwa

以 **UniXNU** 为底座，改造使 **nuwa（小米 13 Pro / SM8550 / 12 GB）** 运行 **iOS 16**。

## 当前进度（2026-10-25）

**nuwa实机已进入XNU的`pmap_bootstrap`入口。iOS尚未启动。** entry-probe-15的镜像`36969f94`、内核`a8b8fc90`修复了页表切换后诊断代码与framebuffer失去映射的问题，用户照片和视频记录到pmap入口标记。不能据此宣称pmap完成、kernel_bootstrap或用户态通过。

本轮恢复于北京时间16:12:44：Android完成1、A槽，boot/vendor_boot/init_boot三SHA与试前相同，无flash/erase/改槽。原始音视频只留本地；仓库提交文字读数、哈希和脱敏命令报告。

下一模型停点是`PE_create_console`读取BCM固定旧panic日志区`0x3c0fc000`，未捕获实机唯一ELR/FAR。新查到上游已有`native-dt-panic-region.patch`，优先评估它与8796/iOS16的兼容性，不跳过整个console。

先读[当前状态](docs/STATUS.md)、[v22实现与实测](docs/operations/2026-10-25-v22-pmap-transition.md)及[最新官网复核：QR/Format2/DT panic区](docs/operations/2026-10-25-official-porting-update.md)。官网QR日志覆盖UEFI阶段，nuwa尚未接入；Format2/共享SM8550支持仍为待迁移项目，不能套用sheng的iPadOS17板值。

旧记录中把固件画面残留解释为XNU安全锁停止/返回固件的判断已被后续复核收窄；以当前STATUS和最新证据为准。分析内核`loadable=false`/`runtime_qualified=false`保留，未把一次阶段到达等同整核资格化。

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
