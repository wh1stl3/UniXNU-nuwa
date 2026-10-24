# arm_init 之后的路径分析（离线，2026-10-25 00:56）

`main` 分支，承接 `2ab3d6c`（实机青/白）。本轮**只做离线分析**：不打包、不启动、未碰设备。
目标：把实机"进入 `arm_init` 之后又回到固件"这件事，在软件模型里定位到可执行、可验证的具体点。

## 方法

用带 AArch64 高异常级状态（`SCR_EL3=0x431`、`HCR_EL2=0x80000000`，见 D-034 第三次更正）的真实候选 `8515068d`，从入口连续执行，观察越过 `arm_init` 之后停在哪、为什么停。

## 发现 1：UBSan 陷阱是模型保真度缺口，不是实机结论

模型连续执行 375,270 条指令后，停在：

```
___ubsan_handle_sub_overflow_minimal + 0x0     brk #0x1206
调用者：_wfe_timeout_configure + 0xe0
```

查代码链：

- `osfmk/arm64/machine_routines.c:2298`：`ticks_per_sec = gPEClockFrequencyInfo.timebase_frequency_hz;`
- `pexpert/arm/pe_identify_machine.c:60`：`if (pe_arm_get_soc_base_phys() == 0) return;`
- 时基的默认值 `24000000` 在该 return **之后**才赋值（同文件 line 68），所以提前返回会把整个结构留在 BSS 零值；
- `pexpert/arm/pe_identify_machine.c:185-196`：`pe_arm_get_soc_base_phys()` 通过 `SecureDTFindEntry("name","arm-io")` 取 `ranges` 的第二个 64 位字。

陷阱时刻实测 `gPEClockFrequencyInfo` **全零**。而根因是：**我的测试夹具从来没有设置 `boot_args->deviceTreeP/deviceTreeLength`**，模型里没有设备树 → `SecureDTFindEntry` 必然失败 → soc base 0 → 提前返回 → 时基 0 → `flsll(0)-1` 下溢 → UBSan `brk`。

实机不是这样：DarwinBoot `DarwinBoot.c:630-631` 明确写入 `Args->DeviceTree` 与 `Args->DeviceTreeLength`，并且我们随包附带的 `kernel.macho.adt`（`ed7235cb`，13,120 B）里 `arm-io` 节点与 `timebase-frequency`（TIMEBASE=19200000）都在。

**结论：这条陷阱是模型缺 ADT 造成的，不能当作实机根因。** 同时它暴露一个必须补的保真度项——任何"越过 arm_init"的分析都要先把 ADT 交给内核。

## 发现 2：把真 ADT 喂进去之后，下一个断点更具体

把随包的 `kernel.macho.adt` 加载到模型的空闲物理地址，并设置 `deviceTreeP/deviceTreeLength` 后：

- UBSan 陷阱**消失**（时基被正确读到）；
- 继续执行 319 条指令后，停在

```
0xfffffff0073bb19c    _current_percpu_base + 0xc
当前指令：ldr x0, [x0, #0xe0]
现场：TPIDR_EL1 = 0x0
```

`_current_percpu_base+0x08` 是一个 `bl`，返回的是 per-CPU 基址（来自 `TPIDR_EL1`）；而 `start.s` 明确 `msr TPIDR_EL1, xzr` 清空它，真正的 per-CPU 数据要等更后的 `cpu_bootstrap` 才建立。于是这里解引用 `0xe0` 触发异常。

**这条既可能实机成立、也可能是模型路径差异**：不能只凭模型宣布实机根因。但它给出了一个**一次实机观测就能判定**的目标——如果硬件上也走到这里，FAR 会是 `0xe0` 附近。

## 因此 v6 的验收目标从"盲目打点"变成三条可判定命题

1. **恒等 VBAR + 页内向量**（magenta 钩子里把 `VBAR_EL1` 改成探针页的恒等物理地址，页内放 16 个自己的向量）：让 MMU 之后的异常自报 ESR/ELR/FAR。若实机 FAR=`0xe0` 且 ELR=`_current_percpu_base+0xc`，发现 2 在实机成立。
2. **`_current_percpu_base` 入口一条带**：区分"走到这里"与"没走到"。
3. **`_arm_vm_init` / `_pmap_bootstrap` / `_kernel_bootstrap` 入口各一条带**：若这些出现，说明 per-CPU 问题被跨过，前线推进到 pmap/kext。

风险与已知限制：

- `arm_vm_init` 会重建 pmap，**我们那条 1 GiB 设备恒等映射可能被替换**，pmap 之后的标记要么画在重建前，要么先重建写屏通路；
- 探针页需要同时容纳 5 个绘制桩、向量表（16×128 = 2 KiB）与快照区，可能要放到 2 页（这会让构建脚本的"单页"约束需要显式放宽并重记）；
- 每加一个钩子都要有"钩子位置指令字"的静态断言 + 一段连续执行的动态断言，否则不进包。

## 复现（本次用到的三条测量）

```sh
# 1) 不给 ADT：停在 __ubsan_handle_sub_overflow_minimal（375,270 条）
# 2) 给 ADT：停在 _current_percpu_base+0xc（374,951 条），TPIDR_EL1=0
# 3) 时基假设检验：在 wfe_timeout_configure 入口写入 24MHz，UBSan 陷阱消失
```

数据与判定见 `reports/kernel-entry-probe/2026-10-25-post-arm-init/analysis.json`。
本轮未打包、未启动、未改任何内核参数或页表；板值、认证、`_verified` 未动。
