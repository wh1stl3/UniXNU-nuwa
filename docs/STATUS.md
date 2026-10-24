# STATUS

更新：2026-10-25 00:45（北京时间），分支 `main`。**实机已确认：MMU 成功开启，控制权进入 `_arm_init`（C 入口）。** 内核未继续到 iOS，停点未知。`arm_init` 之后是当前唯一前线。

## 本轮实机结果（entry-probe-02）

单次 `fastboot boot`，六条色带全部出现：绿（EBS）、蓝(256)、黄(352)、品红(448)、**青(736)**、**白(832)**，未见红条。

- **青** = `msr sctlr_el1` + 回放的 `isb` 已完成同步，且该带是**在 MMU 开启状态下经 1 GiB 设备恒等映射**写进 framebuffer 的 → MMU 真的开了、V=P 覆盖执行区、设备写屏可用。
- **白** = 到达 `_arm_init` 首指令（KVA 取指）→ TTBR1 翻译与取指可用、进入 C 入口。
- 内核随后返回/复位回固件菜单（菜单重绘并重新倒计时），**未到 iOS**。

| 项 | 值 |
| --- | --- |
| 镜像 / 内核 / ADT | `af5862be` / `8515068d` / `ed7235cb` |
| 原图 | `out/trial-evidence/entry-probe-02/screen-01.jpg`，SHA256 `7030b14c8e82f1a63525f6d2d51b1632112762021ed8f4bd6791b0231ebeafac` |
| 恢复 | 16:43:19Z Android 完成 1；16:43:30Z 唯一 nuwa/kalama、槽_a，boot/vendor_boot/init_boot 三 SHA 与 preflight **完全相同** |

## 边界（不要越过）

1. 没有红条**不等于**无异常：MMU 后 VBAR 已是内核 KVA 向量，物理早期向量抓不到那个阶段。
2. 停点未知：`arm_vm_init`/pmap 的哪一步、以及是返回还是复位（panic/watchdog），均未验证。
3. 固件菜单在内核返回后会重新倒计时，可能再次拉起同一内核；`fastboot boot` 只发过一次、ACK 一次，但"单次启动"要按"fastboot 动作"与"固件自行重入"分开记。
4. 板值、认证/AMFI、`_verified`、donor/pin 全部未动；本轮没有 flash/erase/改槽。

## 下一步（v6，目标已收敛）

离线分析（[arm_init 之后](operations/2026-10-25-post-arm-init-analysis.md)）给出三条可判定命题：

1. ~~**恒等 VBAR + 页内向量**~~ **已完成（v7）**：magenta 钩子把 `VBAR_EL1` 换成探针页恒等物理地址，页首 16 个向量全指 `probe_exception`；该处理器只读快照（不依赖 x20），画红带(1216) + ESR/ELR/FAR(1280/1312/1344)。待实机判定：若 FAR 落在 `0xe0` 附近、ELR=`_current_percpu_base+0xc`，则"per-CPU 基址为空导致解引用"在实机成立。
2. **`_current_percpu_base` 入口一条带**：判定是否走到该处（模型里 `TPIDR_EL1=0`，`ldr x0,[x0,#0xe0]` 解引用空）。
3. **`_arm_vm_init` / `_pmap_bootstrap` / `_kernel_bootstrap` 入口各一条带**：若出现，前线推进到 pmap/kext。

已知风险：`arm_vm_init` 会重建 pmap，可能替换掉那条 1 GiB 设备恒等映射，pmap 之后的标记要么画在重建前，要么先重建写屏通路；探针页可能要扩到 2 页（届时显式放宽单页约束并重记）。任何新包仍需打包校验、新鲜 preflight、即时通知与本包录像确认。

## 离线测试能力（2026-10-25 00:55 起）

`scripts/test-kernel-entry-probe.py` 已能把**真实候选从入口连续执行穿过 MMU 到 `_arm_init`**：模型需先置入 AArch64 高异常级状态（`SCR_EL3.NS|RW`、`HCR_EL2.RW`）；默认状态保留为负对照。42 项通过，含负对照、占槽场景，以及三项钉死绑定：SCR_EL3/HCR_EL2 读回、页表摘要 `682cb477…`、停止点等于 white 回放地址。此前"引擎不支持、只能合成进入"是测试初始化错误，已作废。

## 当前状态：v7 已试验并闭环；v8 已把色带改成等高等距，待打包

**entry-probe-03（v7 `af6e1b5f`）单次实机已闭环**：2026-10-24T17:16:20Z preflight → 17:22Z 恢复 Android 完成 1 → 17:25:11Z postcondition，三分区 SHA 与试前完全一致；原图 `out/trial-evidence/entry-probe-03/screen-01.jpg`（`dc310fb1…`）。

- 可确认：绿（固件面包屑）+ 蓝/黄/品红/青/白，即 **MMU 已开、进入 `_arm_init`**（与 v5 结论一致）。
- **不能从这张斜拍照片确认**：紫(496)/棕(544)/青绿(592)/橙(640)/红(688)与三行十六进制。所以"是否走到 `_current_percpu_base`、异常是否自报"仍是未知——照片有反光、色带又细，这正是要做等距布局的原因。

**v8（`c3c39839…`，28 补丁）把布局改成等高等距**：所有带高 32 行不变，行距统一 48 行，首行 256：

| 行 | 颜色 | 含义 |
| --- | --- | --- |
| 256 / 304 / 352 | 蓝 / 黄 / 品红 | 入口 / 页表生成 / 开 MMU 前 |
| 400 / 448 | 青 / 白 | SCTLR+isb 之后 / 进入 `_arm_init` |
| 496 / 544 / 592 / 640 | 紫 / 棕 / 青绿 / 橙 | `_current_percpu_base` / `_arm_vm_init` / `_pmap_bootstrap` / `_kernel_bootstrap` |
| 688 | 红 | 异常 |
| 736 / 784 / 832 | ESR / ELR / FAR | 十六进制 |

最上面的绿色粗条**不是我们的代码**：是固件 `DarwinBootPkg/Driver/Entry.S` 的 `DarwinEnter` 面包屑，占帧缓冲顶部 1/16 = 200 行，写在 hash 钉死的固件里，按规矩不动；它占 0–199 行，与我们的 256 行起不重叠。

v8 离线资格：42 项固定测试 + 带 ADT 7 项 + 处理器合成 2 项，全部通过。**尚未打包、未启动。**

## 当前状态：v9 已带 per-CPU 垫片，等距布局 + 主线推进，待打包

v9 候选 **`b5db0f1e5793a2557efa99af735a59ca1c923ed1ae9e461f712a5a79163ac348`**（58,343,424 B，28 补丁），在 v8 等距布局之上多做一件主线事：

**per-CPU 基址垫片**。模型里 `arm_init` 之后第一个真实阻塞是平台专家路径通过 `TPIDR_EL1` 读 per-CPU 基址，而 `start.s` 在开 MMU **之后**才 `msr TPIDR_EL1, xzr`，于是 `_current_percpu_base+0xc` 的 `ldr x0,[x0,#0xe0]` 解引用空。v9 在白带钩子里把 `TPIDR_EL1` 指向探针第二页（整页零）：`cpu_number`（+0xe8）读成 0——启动 CPU 的正确值；XNU 稍后在 `cpu_bootstrap` 会写入真正的 per-CPU 数据。

模型验证（带随包 ADT，8 项）：垫片生效、`TPIDR_EL1` 回读等于零页 VA、执行**越过空解引用**，前进到 `_cpu_number+0x10`；再往后模型撞在 `msr TPIDRRO_EL0, x0`（Unicorn 不实现该写入），所以**模型到此为止**，下一阻塞只能在实机暴露。42 项固定测试 + 处理器合成 2 项也通过。

探针段从一页扩到两页（第 2 页整页零），打包绑定已同步改为 8192。

## 当前状态：entry-probe-04 已闭环——per-CPU 垫片在实机生效，前线推进到 `arm_vm_init` 内

单次 `fastboot boot`（内核 v9 `b5db0f1e`）已闭环：preflight 17:45:50Z → 恢复 17:51:16Z Android 完成 1 → postcondition 17:51:58Z，**三分区 SHA 与试前完全一致**。原图 `out/trial-evidence/entry-probe-04/screen-01.jpg`（`e6dedeb0…`），判读记录 `reports/xnu-entry-probe-trial/2026-10-25-03/screen-evidence.json`。

**观测到的色带（行号与颜色取自 `.S`，非从照片推断）**：绿（固件）→ 蓝 256 → 黄 304 → 品红 352 → 青 400 → 白 448 → **紫 496** → **棕 544（最后一条）**。

**结论**：

- 紫(496)=`_current_percpu_base` 出现 ⇒ **per-CPU 基址垫片在实机生效**，这是模型没能走到的一步；
- 棕(544)=`_arm_vm_init` 出现 ⇒ 执行**进入了 `arm_vm_init`**；
- **未见**青绿(592)=`_pmap_bootstrap`、橙(640)=`_kernel_bootstrap`、红(688)+三行十六进制 ⇒ 停在 `arm_vm_init` 内部、且在调用 `pmap_bootstrap` 之前；没有异常落到我们的向量页。

**未验证**：为什么停在 `arm_vm_init` 里（复位/panic 路径/挂死），以及 `pmap_bootstrap` 之后的一切。红带没出现说明不是"被向量捕获的异常"，更像复位或走进不取异常的路径。

**下一轮**：在 `arm_vm_init` 内部再插 2–3 个点（它开头就是内存映射/DT 解析，`SecureDTGetProperty(memory_map,"TrustCache"/"AuxKC")` 附近），把断点从"函数入口"推进到具体语句；同时保留红带自报。模型侧需先绕过 `msr TPIDRRO_EL0` 才能继续预演。

## 当前状态：v15 已打包待试；但"探针页只读"假设已被证伪，v16 需要换方向

**entry-probe-07（v14）逐帧复核（60fps、230 帧）**：前 3.2 秒手机不在可读位置，从 t=3.25 s 起一帧里所有内容同时出现 ⇒ 这段录像**只有终态**，排不出先后。终态帧（f0224）清晰可读：绿 · 蓝 · 黄 · 品红 · 青 · 灰白(=白带448) —— **没有棕带(544)**，也没有紫(496)。两行 HEX = 两个 `COUNT16` 计数钩子，各显示 `0000000000000001`。

⇒ **v14 停在 `_arm_vm_init` 之前**（v13 至少到 `arm_vm_init+0x54`），且两个计数钩子（`SecureDTLookupEntry`、`pe_arm_get_soc_base_phys`，都在 `PE_init_platform` 里）各只被调用一次 ⇒ 设备树查询路径走了一次，然后内核停在 `PE_init_platform` 与 `arm_vm_init` 之间。

**"探针段被内核映射成只读"的假设被证伪**：v14 的青带、白带都是 MMU 后的钩子，它们能画出来 ⇒ 守卫写进探针页是成功的，那一页可写。v15 把守卫搬到设备窗口因此**不是对症**（虽然也无害）。

**v14 相对 v13 的新东西只剩两样**：守卫写、以及在两个 PE_init_platform 钩子里**画 16 位十六进制**（约 23000 条写指令，且发生在平台初始化过程中）。最可疑的是后者。v16 的方向因此是：**把计数渲染改轻**（只画 1 位十进制/十六进制，约 1400 条指令）或**把这两个 PE_init_platform 钩子先改回普通色带**，用一轮实机判定是哪一样害的。

v15 已打包为 entry-probe-08（镜像 `4526caeb8e508d420e3cb3ae1f1d1bfa474753e978de04c96bfbb10cb01d12d7`，kernel `57c5b1d8`，ADT `ee12e99e`，`--validate` 通过）——但它验证的假设已被证伪，**是否还跑它请你定**。

## 构建支线

`codex/pr100-linux-8796`（`b8872cb`）保持独立、未合入；其平台链接产物 `89a30cfb` 仍是链路资格，不是可启动镜像。

细节与复现命令见 [探针02试验记录](operations/2026-10-25-entry-probe-02-trial.md)；v5 离线资格见 [v5 修正记录](operations/2026-10-25-probe-v5-corrections.md)。
