# STATUS

更新：2026-10-24 23:55（北京时间），分支 `main`。**实机已证到开启 MMU 之前；本轮把内核内标记推进到 SCTLR 写入之后与 arm_init 入口，离线资格完成，未打包、未启动。** iOS 尚未启动。

## 本轮做了什么

候选 `db4aa1723c8c5c4f253452e6e74b44f9a1e421fecf9c68d80d7f0e04c1fa2b11`（58,339,328 B），在 `1aeebf13` 早期安全预链接上追加 24 处补丁：2 头部 + 5 钩子 + BCM 2837 专写 NOP + 16 早期向量。`loadable=false`/`runtime_qualified=false` 未改。

- 新增 **cyan（y=736）**：钩在 `msr sctlr_el1, x0` 之后的 `isb`。出现即说明 SCTLR 写入执行、其后取指已翻译（V=P 恒等）。
- 新增 **white（y=832）**：钩在 `_arm_init` 第一条指令。该段在 KVA 上取指，出现即说明 TTBR1 映射与取指可用、控制权已进入 C 入口。
- 原有 blue(256)/yellow(352)/magenta(448)、red(544)+ESR/ELR/FAR(608/640/672) 保持。

## 关键发现（决定实现方式）

1. MMU 后 **framebuffer 未映射**：软件页表 walk 显示 `0xB8000000` 不可译，而 PC 恒等地址、`_arm_init` KVA、探针页 KVA 均已映射。所以不能"照旧往屏幕写"。
2. 因此 magenta 钩子（pre-MMU）在 V=P L1 **slot 2 为空时**装一条 1 GiB 恒等设备块（`0x6000008000040d`，AttrIndx 3 = Device-nGnRnE，PXN|UXN），并把 framebuffer 基址与行跨度快照进探针页；两个 post-MMU 钩子只读探针页，**不依赖 boot_args 物理地址**，无快照就不画。
3. `arm_init` 入口 x0 是 boot_args 的 KVA、x20 是 PA（`KASAN` 关闭）；这也是选"快照进探针页"而不是继续用 x20 的原因。

## 离线证据

`reports/kernel-entry-probe/2026-10-24-v4/`：`software.json` **29 项全通过**（含两个新钩子在真实页表+真实快照下直接进入：到达回放点、无非法访存、像素正确、x0-x8/x18-x30 不变；表比对改为屏蔽 slot 2 后一致并单独断言两个内核的 slot2 值；无 framebuffer 时快照为 0 且不画）；`mapping.json` 显示装完映射后 `0xB8000000` 变为恒等可译（独立复核，不是读回常量）；`loader.json` 固定 `ParseKernel` 源体 5 用例通过。

## 明确的界限

Unicorn 拒绝执行 `msr sctlr_el1`，所以**开启 MMU 这一步没有软件执行证据**；两个新钩子是带真实页表直接进入的合成执行。cyan/white 在真机是否出现才是 MMU/arm_init 的证据。未验证：arm_init 返回、arm_vm_init、kext start、iOS。那条 1 GiB 设备块是诊断用，slot 被占用时不改映射也不画。

## 下一步

1. 打包（`build_xnu_boot_package.py --entry-probe` 指向本报告）+ 严格包校验，属离线可做。
2. 启动前必须：新鲜 preflight（唯一 nuwa/kalama、Android 完成 1、boot/vendor_boot/init_boot 三 SHA、可恢复路径）、即时通知、用户对本包的录像确认。`ab3c092b` 的许可不可复用。
3. 目标画面：若出现 cyan 而不出现 white，首个嫌疑落在 `ret` 到 arm_init 的 KVA 切换或 C 入口前；若两个都无，重点转向 MMU 开启本身的硬件/属性问题；若出现 white，下一阶段转 pmap/arm_vm_init。

最近实机事实仍是 2026-10-24T12:53:19Z（北京时间20:53:19）nuwa/kalama、Android 完成 1、槽_a、三 SHA 与试前一致；本轮未刷新设备状态、未操作手机。

细节与复现命令见 [MMU后标记操作记录](operations/2026-10-24-post-mmu-markers.md)；PR100 Linux 构建支线保持在 `codex/pr100-linux-8796`（`b8872cb`），未合入本线。
