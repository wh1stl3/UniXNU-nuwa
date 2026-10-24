# STATUS

> **6b3e5bfd 单次实机文件校验通过**（2026-10-24 18:09:48）：照片 PASS exact length, EOF and SHA256 / exit Success，恢复 Android 完成1、槽_a、三分区SHA不变。**本轮无新设备动作**；内核仍未执行。

## 本轮（2026-10-24 晚，全离线）：ADT 生成器落地 + board 受审字段获批

设备仓此前缺 `make-nuwa-adt.py`，`[payload.adt] tool` 一直是 TODO，OS 入口 blocker 3（真实 nuwa ADT 未提供）无从推进。本轮补齐并拿到批准：

- `scripts/make-nuwa-adt.py` —— 按基座契约生成 `kernel.macho.adt`，补上旧路线实现缺的 `--gpu-addon`/`--text-fixup`/`--persistent-data`（`payload.py:149-170` 会传）。
- `scripts/check-nuwa-adt.py` —— 独立有界解码，不复用生成器编码器。board 配置 21 节点/31 检查、带 sidecar 21 节点/34 检查，**0 失败**。
- `scripts/audit-nuwa-adt-inputs.py` —— 生成器常量对回实机 FDT，14 项对照 **10 项精确相等、0 项不符**。
- `scripts/test-nuwa-adt.py` —— 正负例 **10 用例全部符合预期**：真生成器产物必须过；缺 `/options`、双 ramdisk 占位符、窗口越界三类违约树必须被拒。
- `scripts/check-nuwa-adt-board.py` —— 按 `payload.py:149-170` 从 board.toml 重放参数组装（基座因 `example = true` 跑不起来，`config.py:103`）。

证据 `reports/adt-nuwa/2026-10-24/{min,board,board-with-sidecars,inputs,test}.json`，输入 `out/live-nuwa-dt/android-dt-after-r011/android-live.dtb`（4815 节点）。记录：[ADT](operations/2026-10-24-nuwa-adt.md)。

**R-012 已批准 A**：用户 18:40 批准，只写两个受审字段 `[payload] dram_size = "0x240000000"`、`[payload.adt] owned_memory_size = "0x40000000"`。`example = true`、其余 TODO、所有 `_verified` 未动。

板级值全部有实机依据：timebase 19200000、GIC `0x17100000/0x10000`+`0x17180000/0x200000`、stride `0x40000`、psci smc、8 核 Affinity1 `0x0..0x700`、ufshc `0x1d84000/0x3000`、DRAM base `0x8c0000000`。`/memory` 9 条合并成 8 段，最大段跨度 `0x240000000`，与 D-001 的 9216 MiB 独立吻合。

三处判断留档：① 根 `compatible` 采用实机值（`ArmDTPlatform::configure()` 不匹配该属性，`ArmDTPlatform.cpp:123-142`）；② iomem 的 System RAM 比 FDT 描述只少最后一个 4 KiB 页（`0x1000`），此前"少 55 MiB"的印象是取整错误；③ 修正旧实现强制 `--unique-chip-id`/`--chip-id` 成对的契约不兼容 —— 基座独立传参，board 的 `chip_id` 仍是 TODO，成对校验会让 payload exit 2。

## 本轮（2026-10-24 深夜，全离线）：早期安全初始化器通路打通

blocker 1 的"not configured"部分已解，qualification 仍缺。关键发现：

- **AMFI 没有 kmod_start。** 228 个 kext 的 start 全是跳转桩（读 `__DATA/__common` 全局槽），AMFI/IONetworkingFamily/AppleARMPlatform 的槽静态为 **0**，corecrypto 的槽是真实函数 —— 空槽即"无 start"。
- **三个 `__mod_init_func` 只做 `OSMetaClass` 静态注册**，与策略注册无关。
- **初始化由 `[kernel.prelink] early_security_init` 驱动**：`emit_prelink.py:138-156` 要求 native 导出 `_native_prelink_security_init_version == 1`；bf14e530 **有且为 1**（`0xfffffff007021760`）。
- **配置后 emit 全部前置检查通过**，记录 `0xfffffff004703c54`（= 原 VA `0x5703c54` + slide）。根因是 `scripts/emit-current-prelink-analysis.py:18,43` 硬编码空映射，这张表从未配置过。
- 新候选 `1aeebf13` 与 `eb66542c` 同长度，408983 字节差异**全在 `__PRELINK_INFO`**，三个可执行段**零差异**。

证据 `reports/native-prelink-merged/{amfi-callgraph,early-security-init,earlysec-diff}.json`。记录：[早期安全初始化器](operations/2026-10-24-early-security-init.md)。

**方法论教训（已写入脚本注释）**：全段一次性 `capstone.disasm` 会在首个无法解码字节处静默停止，本轮首轮扫描因此得出"注册函数无人调用"的错误结论；改为 `array` 按位模式逐字检查后才正确。`scripts/audit-amfi-callgraph.py` 现在对每个区段报告覆盖方式。

## OS 入口四个 blocker（仍未解）

`reports/os-entry-next-step/continuation.json`：① 早期安全初始化器 —— "未配置"已解，"调用 ABI / 返回语义 / 构造与 start 间接路径"仍未资格化；② donor/native 完整 C++ 与结构 ABI；③ 真实 ADT 与运行时分配窗口（生成器与板值已就位，**窗口能否被固件满足仍未验证**）；④ 大负载装载（读取已通过，装载未做）。

分析内核 `eb66542c` 与带初始化的 `1aeebf13` 均 **`loadable=false`**、`runtime_qualified=false`，不作实机 OS 包。**文件 SHA PASS 不等于执行许可。**

## 下一步

1. 核对 `0x5703c54` 的调用约定与返回语义（结合 23 项 ops 槽位与 `mac_policy_register` 导入），补完 blocker 1。
2. 再评估是否把 `early_security_init` 接入 `emit-current-prelink-analysis.py`（当前硬编码空映射属有意保留）。
3. 其余 board TODO：`[ipsw]` url/chip_id/board_id/sha256、`[payload]` volume/size_mib/kernel_args、`[kernel]` defconfig/archives/prelink、`[firmware]`、`[bootimg.image]`。

任何新包仍需离线验收、新鲜录像与恢复门、启动前即时通知，结束恢复 Android 完成 1 并核对三分区。原 Heap/HOB 保护、认证策略与所有 `_verified` 保持原状。[交接](operations/2026-10-23-mainline-handoff.md)。
