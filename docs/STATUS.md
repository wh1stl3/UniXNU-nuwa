# STATUS

> 当前唯一真相。每完成一个里程碑**全文重写**，不留过程；过程在 `WORKLOG.md`。

- 更新时间：2026-10-22 02:55
- 阶段：**S0 仓库就位 / 输入准备**（尚未编译任何内核，尚未生成任何镜像，尚未碰设备）
- 分支与提交：见 `git log --oneline`

## 目标

以 UniXNU 为底座改造，使 nuwa（小米 13 Pro / SM8550 / 12 GB）运行 iOS 16。

## 已确定

- 骨架用 UniXNU（native + `OWNER_*` 挂载），iOS16 人格层仍用 sweet；两者补丁**不重叠**，见 `D:\Code\PortingiOS\docs\handoff-unixnu-route-2026-10-22.md`。
- 补丁可移植性实测：49 个 UniXNU 补丁中 **38 个可直接 `git apply`**，11 个需 rebase。
- 物理内存窗口：**D-001**，`gPhysBase = 0x8c0000000` / `memSize = 9216 MiB`（单窗口是内核硬约束）。

## 下一步（按序，第一项就是 gate）

1. **验证 D-001 §5 的装载前提**：boot image header 的 offset 是否支持把 kernel/ramdisk 放到 `≥0x8c0000000`，以及 ABL 是否限制 payload 装载窗口。结论写进 `DECISIONS.md`（通过 → D-001 生效；不通过 → D-002 退 A′ 768 MiB）。
2. 归档输入清单：UniXNU 骨架、`UniXNU-sheng` 板级（同 SM8550）、`xnu-ios16-full`、`ios-sweet` 补丁集，路径与 commit 写进 `docs/inherited/INPUTS.md`。
3. 11 个失败补丁逐个 rebase 可行性评估（只评估，不落代码）。
4. 跑通「UniXNU 树 + iOS16 补丁」的**编译**（只到编译通过，不出镜像）。

## 已知坑

- 上游 sheng 是 **4K** 内核（`sheng_defconfig` 有 `CS_HASH_CACHE`），若沿用 16K 需逐处核 DMA/SMMU 对齐假设。
- `UniXNU-sheng` 的 `board.toml` 写 `dram_size = "0x80000000"`（2 GiB），**直接照抄会丢掉 9 GiB 主 bank**。
- 设备侧：`verifiedbootstate=orange` 但 `flash_locked=1`、`vbmeta_device_state=locked`，二者矛盾 —— 能否 `fastboot flash` 必须进 bootloader 用 `getvar unlocked` 确认，不要在 adb 侧推断。
- b 槽 `successful:no`，**不是可靠兜底**；真实兜底是 a 槽重试（剩 6 次）→ TWRP → 强制重启。

## 不要做的事

- 不要修改 `D:\Code\PortingiOS`（只读资料库）或 `D:\Code\PortingiOSWithUniXNU`（只读参照）。
- 不要在 D-001 §5 验证完成前动 `bringup-plan.json` 的内存字段、不要出镜像、不要碰设备。
