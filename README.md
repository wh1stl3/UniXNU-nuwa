# UniXNU-nuwa

以 **UniXNU** 为底座，改造使 **nuwa（小米 13 Pro / SM8550 / 12 GB）** 运行 **iOS 16**。

## 当前进度（2026-10-25）

**PROBE19实机已越过MAC/Image4并进入BSD，当前停于pthread内核函数表未注册panic。root发现/挂载与iOS用户态尚未进入。** 镜像`f1febc06`、内核`f3c33194`，MAC后继89和BSD入口6点亮，A02A=0、A02B=6、A02C=1。硬件IRQ递送/驱动资格仍未验证。

最近恢复记录为2026-10-25北京时间20:03:58：Android完成1、A槽，三个启动分区SHA与试前相同，无flash/erase/改槽，无待人工恢复任务。原始音视频、截图只保留本地，仓库提交脱敏文字/哈希/命令证据。

本轮生成绑定实际FD/shim/kernel/基础ADT的非Apple诊断启动测量和主机CSPRNG nonce，集成AMNM/CHMH兼容路径，保留认证失败；不声称Apple IM4M/TSS链或硬件防重放。25项完整Image4检查、740差分、29绑定及镜像回读通过。固定donor有遗漏的iOS16 pthread组件，已完成31组件闭合/真实注册的11项离线审计；下一步接入正常OSKext生命周期，不能以假表跳过检查。

先读[STATUS](docs/STATUS.md)、[当前交接](docs/operations/2026-10-25-mainline-handoff.md)、[v27实现/实测](docs/operations/2026-10-25-v27-image4-to-bsd.md)和[官网QR/迁移复核](docs/operations/2026-10-25-official-porting-update.md)。官方二维码日志是UEFI/EBS前功能，nuwa尚未接入；Format2/共享SM8550迁移另行评审，保留iOS16 ABI及nuwa板值。

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
