# WORKLOG

> 只追加不修改。一行一个里程碑：`时间 · 结论 · 提交号 · 证据路径`

- 2026-10-22 02:55 · S0 仓库就位：git 初始化、`AGENTS.md`（只读边界 / 版本管理 / 五档文档机制 / 硬停四类）、`docs/` 骨架、上一轮探针证据拷入 `docs/inherited/`（P0 报告 + iomem/partitions/meminfo/nuwa-observed）· commit e417c76（bootstrap）· `AGENTS.md`, `docs/`
- 2026-10-22 02:55 · D-001 内存窗口结案：physmap 单窗口是代码硬约束（`arm_vm_init.c:378,1961`），排除 C；低 4 GiB 最大连续块仅 768 MiB，原 A 提案不成立；首选 B（`0x8c0000000`/9216 MiB），PA 位宽 40 位够用（`proc_reg.h:972-974`）· commit e417c76（bootstrap）· `docs/DECISIONS.md`, `docs/inherited/nuwa-observed.json`
- 2026-10-22 03:00 · 接入 UniXNU 官方移植指南（porting/devices 共 5 页 + sheng/fuxi/vermeer 设备页）：确认三仓结构（基座 `UniXNU` + 设备仓 + `uefi-<device>`）、官方栈为 4 KiB XNU、同 SoC 的 fuxi/vermeer 可作对照 · 摘要见 `docs/inherited/unixnu-official-2026-10-22.md`
- 2026-10-22 03:00 · **D-002 推翻 D-001 §5**：内存窗口真实控制点是 ADT `darwinboot-memory-size`，硬上限 8 GiB（不是 9216 MiB）；板级键为 `[payload] dram_size` 与 `[payload.adt] owned_memory_size`（sheng 2 GiB vs 4.75 GiB，不等价）。D-001 的 A/B/C 三选项全部作废 · `docs/DECISIONS.md`
- 2026-10-22 03:00 · D-003（proposed）：内核页大小走 4 KiB 官方主线，16K 不进本仓，等用户点头，不阻塞离线工作 · `docs/DECISIONS.md`, `docs/STATUS.md`
- 2026-10-22 03:02 · 用户拍定 4 KiB（D-003 → accepted），并明确目标身份是 **iOS 而非 iPadOS** → D-004：查基座 `docs/zh/guide/skip-setup.md` 确认 `ipad_identity` 写的是 4 个 `/chosen` 安全属性（`certificate-production-status=0` 等，供 `mobileactivationd` 原生激活），**与平台身份无关，必须保持 true**；真正决定 iOS/iPadOS 的是 `[ipsw]`、ADT `/product`、`[kernel.prelink]`、disable-jobs。donor 沿用旧仓 iPhone10,3/d22ap/iOS 16.7.16/20H392 · `docs/DECISIONS.md`
- 2026-10-22 03:02 · D-005（proposed）：基座 `feeds.toml` 钉 `xnu-10063.141.1`（17.x），iOS 16 是 8796，49 个补丁按 10063 写 → 先做 `git apply --check` 批量试算再选路，判定前不动 xnu 版本 · `docs/DECISIONS.md`, `docs/STATUS.md`
