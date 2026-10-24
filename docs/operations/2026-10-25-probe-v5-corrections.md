# 入口探针 v5：复核发现的修正

2026-10-25 00:20，`main`。承接 `09d0bb8`（v4）。独立复核（Codex）对 v4 提出 4 项实质问题，本轮逐条修复并重出候选 **v5**。全离线，无设备动作。

## 复核指出的问题与处理

| # | 问题 | 判定 | 处理 |
| --- | --- | --- | --- |
| 1 | 占槽失败分支仍会绘制：`MAP_FB` 跳过时 `x15` 仍是既有描述符（非零），`SNAP_VIDEO` 据此继续保存几何，post-MMU 钩子于是在别人的映射上写屏 | **成立，真缺陷** | 跳过分支显式 `mov x15, #0`，快照与绘制同时关闭 |
| 2 | cyan 语义过强：v4 先画带、后回放 `isb`，画带时 SCTLR 变更尚未同步 | **成立** | 改为先 `.inst original_mmu_on_word`（isb）再画带 |
| 3 | walker 把 L1 block 记为 `block:false` | **成立** | 改按 `desc & 3 == 1` 判 block，并记录 `type`/`level` |
| 4 | 「Unicorn 拒绝 MSR / 无 MMU 模型」的说法不成立 | **成立，我原来的归因错了两次** | 见下节 A–H 矩阵：MSR 能执行、翻译也可用；真正的限制是 T0SZ=26 时从 L2 起走且 ≥1 GiB VA 不可译 |
| 5 | 打包绑定放宽：检查数只要求 ≥16，删掉 cyan/white 检查仍能过 | **成立** | 改为按钩子集合要求**具体检查名**必须存在 |
| 6 | 「ParseKernel rc=139 是并行导致内存压力」 | **不成立（我的推断无据）** | 文档改为「根因未验证」 |

## 关于 Unicorn：先把事实钉住

三组实测（`scripts/probe-unicorn-mmu.py`、`scripts/audit-unicorn-mmu-support.py`）：

1. 教科书式 4 KiB 粒度三级页表（VA `0x500000` → PA `0x41000000`，非恒等），`SCTLR_EL1.M=1`、`PSTATE=EL1h`，**取指失败**（`UC_ERR_EXCEPTION`）。Windows 构建与 WSL pip 2.1.4 两个构建都失败。
2. 真实冷启动路径：`msr sctlr_el1` **执行成功**（SCTLR 读到 `0x3454593d`，PC 前进到 MSR+4），随后第一条被翻译的取指失败。
3. 同一实例把 MMU 关掉（`M=0`）后，对同一地址的 NOP 取指立刻成功；`M=1` 时对**已映射 RAM 内的恒等地址**取指也失败。

结论（第二次更正）：**翻译本身可用**。`scripts/probe-unicorn-start-level.py` 的 A–H 矩阵（页表内容完全相同，只变 TCR 与根表布局）：



- A：T0SZ=25 + L1 根 → 成功；B：T0SZ=26 + L1 根 → 失败；

- C：T0SZ=26 + L2 根 → 成功；D：T0SZ=25 + L2 根 → 失败（对照，说明不是"随便换个布局就能过"）；

- E：XNU 真实 TCR `0x22a51a251a` + L1 根 → 失败；F：同 TCR + L2 根 → 成功；

- G/H：T0SZ=26 + L2 根下，`0x8c37c7378` 与 `0x40000000` **仍失败**。



也就是说：本构建在 T0SZ=26 时**从 L2 起走**，并且**≥1 GiB 的 VA 无法翻译**。XNU 用的正是 T0SZ=26 + L1 根布局，内核又位于 `0x8c37c7378`，所以真实冷启动路径必然在第一条被翻译的取指处失败；**改夹具重新挂根表也救不了**（高位 VA 丢失），要穿越只能换执行引擎或实机。



这一条是复核者用可执行反例（TCR `0x280993519`，我复跑通过）推翻了我先前"不实现取指翻译"的结论后查清的；原结论已作废，机制见上。



复核随后给出可执行反例（TCR `0x280993519`，非恒等 VA→PA 取指成功），我复跑一致；据此把 A–H 矩阵补齐并定位到"起始层 + 高位 VA"这一层，见上。

**因此本轮无法交付「真正穿过 MMU 切换」的测试**：这不是取舍，是当前工具做不到。两个后 MMU 钩子仍是「带真实页表与真实快照直接进入」。要真正穿越，需要另一条执行通道（QEMU system mode 跑真实内核，或实机）。这一条已明确列为阻塞，而不是用合成测试替代后声称完成。

## v5 候选与证据

候选 **`8515068dcd6bd699a4301109b76b80022fb07120e6167b65b6169d52aeffcb6a`**，58,339,328 B，24 补丁（与 v4 同构，只有汇编语义与占槽分支变化）。`loadable=false` / `runtime_qualified=false` 未改，板值/认证/AMFI/`_verified` 未动。

- `software.json`：**33 项通过**（v4 为 29）。新增 4 项：
  - `Cyan hook replays the original isb before anything is drawn`（静态：钩子首字必须是 `0xd5033fdf`）；
  - 预置 L1 slot 2 为哨兵描述符后：`Pre-occupied L1 slot 2 is left untouched`、`Pre-occupied slot yields no geometry snapshot`、`Pre-occupied slot draws nothing and does not fault`。
  占槽场景的复现方式是：在 tables 钩子处用 `x25`（页表物理地址）先写入哨兵，再跑完整路径——正是复核给出的最小证伪路径，现在成为常驻用例。
- `mapping.json`：装映射后 `0xB8000000` 恒等可译（`type` 字段已修正）；未装时不可译。
- `loader.json`：5 用例通过。
- `unicorn-mmu-support.json`：上节三组实测的原始输出与判定，`refused_everywhere=true`。

## 仍未验证

- 实机上 cyan/white 是否出现——这才是 MMU/arm_init 的证据；软件侧只证明钩子逻辑、映射安装、寄存器契约。
- arm_init 返回、arm_vm_init、kext start、iOS。
- 那条 1 GiB 设备块覆盖 `0x80000000-0xBFFFFFFF`；已知内核 V=P 窗口、boot_args、栈、VBAR、探针页都不在该区间，但 arm_init→arm_vm_init 期间的**全部**访存未穷尽，不能宣布无其他访问。
- ParseKernel 夹具在串行复跑中也出现过 rc=139（复核发现），根因未查。

## 复现（串行执行，勿与 Unicorn 模型并行）

```sh
python -B scripts/build-kernel-entry-probe.py --work out/kernel-entry-probe-05 \
  --output reports/kernel-entry-probe/2026-10-24-v5/build.json
python -B scripts/test-kernel-entry-probe.py --build reports/kernel-entry-probe/2026-10-24-v5/build.json \
  --output reports/kernel-entry-probe/2026-10-24-v5/software.json
python -B scripts/audit-entry-probe-post-mmu-mapping.py --build reports/kernel-entry-probe/2026-10-24-v5/build.json \
  --output reports/kernel-entry-probe/2026-10-24-v5/mapping.json
python -B scripts/audit-entry-probe-loader.py --build reports/kernel-entry-probe/2026-10-24-v5/build.json \
  --work out/loader-audit-v5 --output reports/kernel-entry-probe/2026-10-24-v5/loader.json
python -B scripts/audit-unicorn-mmu-support.py reports/kernel-entry-probe/2026-10-24-v5/unicorn-mmu-support.json
```

## 下一步

1. 若要真正穿越 MMU：评估 QEMU system mode（`qemu-system-aarch64` + 真实内核 + ADT）作为第二条执行通道；这比继续在 Unicorn 上找开关更有把握。
2. 打包与实机试验仍按原门：`build_xnu_boot_package.py --entry-probe` 指向 v5 报告，包校验、新鲜 preflight、即时通知、用户对本包的录像与恢复确认，`ab3c092b` 的许可不可复用。
3. 结果判读（不变）：有 cyan 无 white → 查 `ret` 到 arm_init 的 KVA 切换；两者皆无 → 查 MMU 开启本身；有 white → 转 pmap/arm_vm_init。
