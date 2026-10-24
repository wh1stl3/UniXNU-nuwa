# STATUS

更新：2026-10-25 00:20（北京时间），分支 `main`。**实机已证到开启 MMU 之前；离线标记已推进到 SCTLR 写入之后与 arm_init 入口，v5 修正了复核发现的缺陷。未打包、未启动。** iOS 尚未启动。

## 当前候选（v5，取代 v4）

**`8515068dcd6bd699a4301109b76b80022fb07120e6167b65b6169d52aeffcb6a`**（58,339,328 B，24 补丁），在 `1aeebf13` 早期安全预链接上追加：2 头部 + 5 钩子 + BCM2837 专写 NOP + 16 早期向量。`loadable=false`/`runtime_qualified=false` 未改。

- blue(256) 入口、yellow(352) 页表生成后、magenta(448) 开 MMU 前、red(544)+ESR/ELR/FAR 早期异常：与 v3/v4 相同。
- **cyan(736)**：钩在 `msr sctlr_el1` 之后的 `isb`。**先回放 isb，再画带**——出现即说明 SCTLR 变更已同步、其后取指在该状态下完成。
- **white(832)**：钩在 `_arm_init` 首指令，该段在 KVA 上取指——出现即说明 TTBR1 取指可用、控制权进了 C 入口。
- MMU 后 framebuffer 原本不可译，故 magenta 钩子（pre-MMU）在 V=P L1 **slot 2 为空时**装 1 GiB 恒等设备块（`0x6000008000040d`），并把屏幕几何快照进探针页；**槽被占用则不装、不存快照、不画**（v4 此处有缺陷，已修）。

## 本轮修正（独立复核后）

| 项 | 原状 | 现状 |
| --- | --- | --- |
| 占槽分支 | 跳过时仍会保存几何并绘制 | `x15=0`，快照与绘制一起关闭，并有常驻用例 |
| cyan 语义 | 先画带后回放 isb，语义过强 | 先 isb 后画带，语义收窄为「已同步」 |
| walker | 把 L1 block 记为 `block:false` | 按 `desc&3` 判 block/page，记录 `type`/`level` |
| 打包绑定 | 检查数只要 ≥16，删掉关键检查仍能过 | 按钩子集合要求**具体检查名**必须存在 |
| Unicorn 归因 | 「拒绝 MSR/无 MMU 模型」 | 翻译可用；但本构建在 T0SZ=26 时从 L2 起走且 ≥1 GiB VA 不可译，XNU 恰好是 T0SZ=26+L1 根、内核在 0x8c37c7378 |

## 离线证据（`reports/kernel-entry-probe/2026-10-24-v5/`）

`software.json` **33 项通过**（含占槽场景与 isb 顺序的静态断言）；`mapping.json` 装映射后 FB 恒等可译、未装时不可译；`loader.json` 5 用例通过；`unicorn-mmu-support.json` 记录两个宿主上的 A–H 矩阵：T0SZ=25+L1 根可取指、T0SZ=26+L2 根可取指、XNU 真实 TCR 用 L1 根失败，且 T0SZ=26 下 `0x40000000` 与 `0x8c37c7378` 均不可译——机制定位到"起始层 + 高位 VA"，不是"没有翻译"。

## 明确的界限

- **「真正穿过 MMU 切换」的测试本轮做不到**：本构建在 T0SZ=26 下从 L2 起走且丢弃 ≥1 GiB 的 VA 位，无法表达内核地址；改夹具重挂根表也救不了。两个 post-MMU 钩子仍是「带真实页表与真实快照直接进入」的合成执行，只证明钩子逻辑、映射安装与寄存器契约。
- 复核给出的 Unicorn 正例已复跑并解释（见 A–H 矩阵）；`scripts/probe-unicorn-mmu.py` 与 `probe-unicorn-start-level.py` 均可复现。
- 1 GiB 设备块覆盖 `0x80000000-0xBFFFFFFF`；已知内核 V=P 窗口、boot_args、栈、VBAR、探针页都不在该区间，但 arm_init→arm_vm_init 之间的全部访存未穷尽。
- ParseKernel 夹具串行复跑也出现过 rc=139，根因未查（此前「并行内存压力」的推断已撤回）。
- 未验证：arm_init 返回、arm_vm_init、kext start、iOS。

## 当前状态：v5 已打包，preflight 通过，等待录像后单次启动

- 镜像 **`af5862be01126c5cf67e13b3fb36a9a5e8be3d6f028271f49ebc088d03876031`**，70,266,880 B，菜单标识 `XNU ENTRY PROBE 02 - BLUE YELLOW MAGENTA CYAN WHITE`；报告 `reports/xnu-first-entry/entry-probe-02.json`，`--validate` 已从出货 FAT 读回 kernel `8515068d` 与 ADT `ed7235cb` 通过。
- preflight（2026-10-24T16:36:45Z）：唯一 nuwa/kalama、Android 完成 1、槽_a，boot_a `ef558db2`、vendor_boot_a `5ad2a9dc`、init_boot_a `19e95d95` 与基线一致；证据 `reports/xnu-entry-probe-trial/2026-10-25-01/preflight.json`。
- 用户 2026-10-25 00:35 答复「跑V5 可以录像」为**本包**授权；`ab3c092b` 的许可已作废。启动前仍需即时通知，结束后必须恢复 Android 并核三 SHA。

## 下一步

1. 单次 `fastboot boot`（180 秒观察，全程录像），随后 `recover` + postcondition 三 SHA。
2. 判读：有 cyan 无 white → 查 `ret` 到 arm_init 的 KVA 切换；两者皆无 → 查 MMU 开启本身；有 white → 转 pmap/arm_vm_init。
3. 若实机连"异常向量都没抓到"，再评估 QEMU system mode（注意同源 QEMU 对 T0SZ=26 的处理需先验证）。

最近实机事实仍是 2026-10-24T12:53:19Z（北京时间20:53:19）nuwa/kalama、Android 完成 1、槽_a、三 SHA 与试前一致；本轮未刷新设备状态。

细节见 [v5 修正记录](operations/2026-10-25-probe-v5-corrections.md)；v4 记录仅作历史（[已标注取代](operations/2026-10-24-post-mmu-markers.md)）。PR100 Linux 构建支线独立在 `codex/pr100-linux-8796`（`b8872cb`），未合入。
