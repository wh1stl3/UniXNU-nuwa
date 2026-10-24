> **已被 v5 取代（2026-10-25 00:20）。** 独立复核发现三处真缺陷：占槽失败分支仍会绘制、cyan 在回放 isb 之前画带、以及"Unicorn 拒绝 MSR/无 MMU 模型"的归因错误。修正与 v5 候选 `8515068d` 见 [v5 修正记录](2026-10-25-probe-v5-corrections.md)。本文保留为 v4 的历史记录，不作当前依据。

# 入口探针02：MMU 开启后与 arm_init 的独立可观测标记

2026-10-24，北京时间23:50 起。`main` 分支，前序 `8f46cf0`（PR100 支线 `b8872cb` 未合入，保持独立）。全离线：无手机、USB、固件动作。

## 为什么先做这一步

`ab3c092b` 已实机确认绿/蓝/黄/品红四条色带，最远插桩点是**开启 MMU 的 MSR 之前**。品红之后到 arm_init、到 iOS 之间是黑箱，而"MMU 是否真的开启成功"是当前唯一必须回答的分叉点：若开启，下一批问题在 pmap/arm_vm_init；若没开启，问题仍在启动汇编尾部。所以本轮把标记推进到 SCTLR 写入之后与 arm_init 入口。

## 先量后改的三个事实

1. **`msr sctlr_el1, x0` 位于 `_start_first_cpu+0x318`**（编码 `0xd5181000`），紧随其后 `+0x31c` 是 `isb`（`0xd5033fdf`）。品红钩子在 `+0x308`，是构建 SCTLR 值的 `movk`，确实在 MSR 之前。`+0x318`/`+0x31c` 由编码定位并校验，不靠硬编码偏移。
2. **MMU 后 framebuffer 未映射**。用 `scripts/audit-entry-probe-post-mmu-mapping.py` 走真实 bootstrap 页表（v3 候选，未改动页表时）：`0xB8000000` 与 `0xB8001000` 均 `mapped=False`，而 PC 恒等地址、`_arm_init` KVA、探针页 KVA、boot_args KVA 均已映射。也就是说"MMU 后直接照旧写屏幕"会取指/访存异常，且那时 VBAR 已切到内核虚拟向量，红色异常栏也未必出现。
3. **`arm_init` 入口处 x0 是 boot_args 的 KVA**（`start.s` 在 `ret` 前 `add x0, x20, x22; sub x0, x0, x23`），x20 仍是 PA（KASAN 关闭时不被改写）。两条指针在 MMU 后的可用性都取决于 boot_args 落在哪个物理区间，不能想当然。

## 设计

- **magenta 钩子（pre-MMU，`+0x308`）多做两件事**：
  - 在 V=P 的 L1 表 slot 2（覆盖 `0x80000000-0xBFFFFFFF`）**若且仅若为空**，安装一条 1 GiB 恒等块：`0x6000008000040d` = valid block + AF + AttrIndx 3（MAIR_DISABLE，Device-nGnRnE）+ PXN|UXN，物理基址 `0x80000000`。槽被占用就什么都不改（不覆盖既有映射）。
  - 从 boot_args 校验并快照 `framebuffer base` 与 `line stride` 到探针页内的 `probe_scratch`（`.quad 0,0` 初始值）。
- **两个新钩子只读探针页**，不再依赖 boot_args 的物理地址，因此与 boot_args 落在哪个区间无关；无快照就不画。
  - `probe_mmu_on`（cyan，y=736）：钩在 MSR 之后的 `isb`。它执行时 MMU 已开，且 `.inst` 回放的就是那条 `isb`。
  - `probe_arm_init`（white，y=832）：钩在 `_arm_init` 第一条指令。这一段在 KVA 上取指，因此白色同时证明 **TTBR1 映射与取指可用**。
- 位置无关：整段探针只靠 PC 相对跳转与 `adr`，所以 pre-MMU 在物理地址执行、post-MMU 在恒等/KVA 执行都指向同一页。

## 结果（`reports/kernel-entry-probe/2026-10-24-v4/`）

候选 `db4aa1723c8c5c4f253452e6e74b44f9a1e421fecf9c68d80d7f0e04c1fa2b11`，58,339,328 B；24 处补丁（2 头部 + 5 钩子 + BCM NOP + 16 早期向量，v3 为 22）；`loadable=false` / `runtime_qualified=false` 未改。

- `software.json`：**29 项全通过**。含原有 14 项（基线在 BCM 专写处失败、单 NOP 对照到达 MSR 前、活动寄存器一致、BCD 表比对、四条色带像素、缺 framebuffer 路径、异常三寄存器字形解码）。
  - 表比对改为"屏蔽 slot 2 后一致"，并单独断言：最小修正内核 `slot2=0x0`，探针内核 `slot2=0x6000008000040d`。
  - 两个新钩子用**真实表 + 真实快照**直接进入（`probe_mmu_on_replay` / `probe_arm_init_replay` 处停下），断言：到达回放点、无非法访存、cyan/white 像素正确、x0-x8/x18-x30 不变、早前色带不被破坏。
  - 无 framebuffer 时快照保持 `(0,0)`，钩子到达但不画。
- `mapping.json`：在**装过映射之后**再走一次页表，`0xB8000000`/`0xB8001000` 变为 `mapped=True` 恒等；这是对"映射确实进了 L1 表"的独立确认，不只是读回自己的常量。TTBR0=`0x8c355e000`。
- `loader.json`：固定 `DarwinBoot.c` 的 `ParseKernel` 源体在 ASan/UBSan 下 5 用例通过（原版/候选接受，重叠段、命令越界、文件越界拒绝）。

## 必须写清的边界

- Unicorn **拒绝执行** `msr sctlr_el1`（无 MMU 模型，`UC_ERR_EXCEPTION`），所以"开启 MMU 的那一步"没有软件执行证据。两个 post-MMU 钩子是**带着真实页表与真实快照直接进入**的合成执行，不是穿过 MMU 开关的执行。
- 因此 cyan/white 只证明**钩子逻辑、映射安装、寄存器契约**；真机上它们是否出现，才是 MMU/arm_init 的证据。仍未验证：arm_init 返回、arm_vm_init、kext start、iOS。
- 那条 1 GiB 设备块是**诊断用**，会覆盖 `0x80000000-0xBFFFFFFF` 的地址空间（不含内核自身的 V=P 区间）。若该 slot 在别的机器/固件上非空，代码不改映射也不画带，启动路径不受影响。
- 未打包、未生成可启动镜像、未碰板值/`_verified`/认证/AMFI。上一次实机事实仍是北京时间 20:53:19 Android 完成 1/A 槽/三 SHA。

操作备注：`loader` 夹具与 Unicorn 模型**并行**跑过一次崩溃（rc=139，无输出），串行重跑 3 次均 5 用例通过。判断是 WSL 内存压力下的偶发，不是候选差异；后续验证串行执行。

## 复现

```sh
python -B scripts/build-kernel-entry-probe.py --work out/kernel-entry-probe-04 \
  --output reports/kernel-entry-probe/2026-10-24-v4/build.json
python -B scripts/test-kernel-entry-probe.py --build reports/kernel-entry-probe/2026-10-24-v4/build.json \
  --output reports/kernel-entry-probe/2026-10-24-v4/software.json
python -B scripts/audit-entry-probe-post-mmu-mapping.py --build reports/kernel-entry-probe/2026-10-24-v4/build.json \
  --output reports/kernel-entry-probe/2026-10-24-v4/mapping.json
python -B scripts/audit-entry-probe-loader.py --build reports/kernel-entry-probe/2026-10-24-v4/build.json \
  --work out/loader-audit-v4 --output reports/kernel-entry-probe/2026-10-24-v4/loader.json
```

## 下一步

打包属于下一道门：需要 `build_xnu_boot_package.py --entry-probe` 用本报告生成镜像，再做严格包校验；启动前仍需新鲜 preflight（唯一 nuwa/kalama、Android 完成 1、三分区 SHA、可恢复路径）、即时通知与用户对本包的录像确认。`ab3c092b` 的录像许可不可复用。

`scripts/kernel_entry_probe_inputs.py` 的打包绑定已从"硬编码 22 补丁/16 检查"改为按钩子集合推导补丁形状、检查数下限，v3 与 v4 两套证据都能通过验证，篡改证据摘要仍被拒绝。
