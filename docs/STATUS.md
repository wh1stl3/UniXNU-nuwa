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

## 下一步

1. **C 内打点**：把钩子推进到 `arm_vm_init` / `pmap_bootstrap` / `kernel_bootstrap` 首指令，沿用"探针页 + 快照"，把停点收敛到具体函数。
2. **MMU 后异常自报**：magenta 钩子里把 `VBAR_EL1` 换成探针页恒等地址并放自己的向量，画 ESR/ELR/FAR——"MMU 后能写屏"已有实机证据，风险已降。
3. 串口/QEMU 作为后备，且先验证同源 QEMU 对 T0SZ=26 的处理。

## 构建支线

`codex/pr100-linux-8796`（`b8872cb`）保持独立、未合入；其平台链接产物 `89a30cfb` 仍是链路资格，不是可启动镜像。

细节与复现命令见 [探针02试验记录](operations/2026-10-25-entry-probe-02-trial.md)；v5 离线资格见 [v5 修正记录](operations/2026-10-25-probe-v5-corrections.md)。
