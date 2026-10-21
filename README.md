# UniXNU-nuwa

以 **UniXNU** 为底座，改造使 **nuwa（小米 13 Pro / SM8550 / 12 GB）** 运行 **iOS 16**。

## 为什么单开一个仓库

旧仓 `D:\Code\PortingiOS` 走的是自建 P16/16K 链路，已转为**只读资料库**（上游源码副本、实测记录、旧报告都在里面）。
本仓库只做「复用 UniXNU + 移植到 nuwa」这一条线，路线、目录、文档纪律都与旧仓分离，避免两套叙事混在一处。

## 先读什么

1. `AGENTS.md` —— 只读边界、版本管理、文档五件套、硬停四类。**动手前必读**。
2. `docs/STATUS.md` —— 现在做到哪、下一步、已知坑。
3. `docs/DECISIONS.md` —— 已定技术决策（`D-001` 内存窗口），带代码证据。
4. `docs/handoff-route.md` —— 路线交接（三段式架构、4K/16K 岔路、补丁可移植性）。

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
