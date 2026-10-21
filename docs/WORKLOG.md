# WORKLOG

> 只追加不修改。一行一个里程碑：`时间 · 结论 · 提交号 · 证据路径`

- 2026-10-22 02:55 · S0 仓库就位：git 初始化、`AGENTS.md`（只读边界 / 版本管理 / 五档文档机制 / 硬停四类）、`docs/` 骨架、上一轮探针证据拷入 `docs/inherited/`（P0 报告 + iomem/partitions/meminfo/nuwa-observed）· commit e417c76（bootstrap）· `AGENTS.md`, `docs/`
- 2026-10-22 02:55 · D-001 内存窗口结案：physmap 单窗口是代码硬约束（`arm_vm_init.c:378,1961`），排除 C；低 4 GiB 最大连续块仅 768 MiB，原 A 提案不成立；首选 B（`0x8c0000000`/9216 MiB），PA 位宽 40 位够用（`proc_reg.h:972-974`）· commit e417c76（bootstrap）· `docs/DECISIONS.md`, `docs/inherited/nuwa-observed.json`
