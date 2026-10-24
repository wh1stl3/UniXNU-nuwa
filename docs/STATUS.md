# STATUS

> **6b3e5bfd 单次实机文件校验通过**（2026-10-24 18:09:48）：照片 PASS exact length, EOF and SHA256 / exit Success，恢复 Android 完成1、槽_a、三分区SHA不变。**本轮无新设备动作**；内核仍未执行。

## 本轮（2026-10-24 晚，离线）：ADT 生成器落地

设备仓此前缺 `make-nuwa-adt.py`，`[payload.adt] tool` 一直是 TODO，OS 入口 blocker 3（真实 nuwa ADT 未提供）无从推进。本轮补齐：

- `scripts/make-nuwa-adt.py` —— 按基座契约生成 `kernel.macho.adt`，补上旧路线实现缺的 `--gpu-addon`/`--text-fixup`/`--persistent-data` 三个参数（`payload.py:149-170` 会传）。
- `scripts/check-nuwa-adt.py` —— 独立有界解码，不复用生成器编码器。最小树 12 节点/20 检查、完整树 21 节点/35 检查，**0 失败**。
- `scripts/audit-nuwa-adt-inputs.py` —— 生成器常量对回实机 FDT，14 项对照 **10 项精确相等、0 项不符**。
- `scripts/test-nuwa-adt.py` —— 正负例 8 个用例全部符合预期：真生成器产物必须过，缺 `/options`、双 ramdisk 占位符、窗口越界三类违约树必须被拒。

证据 `reports/adt-nuwa/2026-10-24/{min,full,inputs,test}.json`，输入 `out/live-nuwa-dt/android-dt-after-r011/android-live.dtb`（4815 节点）。记录：[ADT](operations/2026-10-24-nuwa-adt.md)。

板级值全部有实机依据：timebase 19200000、GIC `0x17100000/0x10000`+`0x17180000/0x200000`、stride `0x40000`、psci smc、8 核 Affinity1 `0x0..0x700`、ufshc `0x1d84000/0x3000`、DRAM base `0x8c0000000`。`/memory` 9 条合并成 8 段，最大段跨度 `0x240000000`，与 D-001 的 9216 MiB 独立吻合。

两处证据分歧已判断并留档：根 `compatible` 采用实机值（`ArmDTPlatform::configure()` 不匹配该属性，`ArmDTPlatform.cpp:123-142`）；iomem 的 System RAM 比 FDT 描述**只少最后一个 4 KiB 页**（`0x1000`），此前"少 55 MiB"的印象是取整表述错误。

## 卡点：board 仍不能组装 payload

`[payload] dram_size`（`payload.py:149` 直接读取）与 `[payload.adt] owned_memory_size` 属 AGENTS §3.1 受审字段，**未写入**，已提 `docs/NEED-REVIEW.md` **R-012** 三选一待批。因此 payload 步骤仍不可运行，board 保持 `example = true`。

## OS 入口四个 blocker（未解）

`reports/os-entry-next-step/continuation.json`：① 早期安全初始化器身份与调用 ABI（AMFI 注册入口已静态定位、23 项槽位与 12 项时序通过，构造/kmod start 间接路径与 C++ ABI 仍缺）；② donor/native 完整 C++ 与结构 ABI；③ 真实 ADT 与运行时分配窗口（本轮只解掉"生成器缺失"，窗口仍待 R-012 与 UEFI 证据）；④ 大负载装载（读取已通过，装载未做）。

分析内核 `eb66542c`（58335232 B）仍 `loadable=false`、`runtime_qualified=false`，不作实机 OS 包。**文件 SHA PASS 不等于执行许可。**

## 下一步

R-012 获批后写入两个受审字段，再离线复核 payload 组装；同时推进原生内核加载链、ADT 与连续内存分配资格审查。任何新包仍需离线验收、新鲜录像与恢复门、启动前即时通知，结束恢复 Android 完成 1 并核对三分区。原 Heap/HOB 保护、认证策略、板值与所有 `_verified` 保持原状。[交接](operations/2026-10-23-mainline-handoff.md)。
