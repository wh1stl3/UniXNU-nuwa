# PENDING-HUMAN

> 只差用户本人按键/在场的待办。**不阻塞主线**：记一条，继续下一项。
> 只有「会改变设备内容且必须用户在场」的动作才升级为 `NEED-HUMAN.md` 并停机。

| 编号 | 待办 | 为什么必须本人 | 提报时间 | 状态 |
| --- | --- | --- | --- | --- |
| H-001 | C3 长按电源键强制重启恢复演练 | 需要实体按键 + 人在设备旁观察 | 2026-10-22 00:44（继承自旧仓） | open |
| H-002 | 进 bootloader 用 `fastboot getvar unlocked` 核实能否 flash（`verifiedbootstate=orange` 与 `flash_locked=1` 矛盾） | 2026-10-22已读fastboot unlocked=yes；普通reboot回fastboot后，原厂boot临时加载回Android且boot_completed=1。证据reports/trial-boot-preflight/，未实际flash验收 | 2026-10-22 02:55 | completed（19:06） |

| H-003 | 同包试启动的连续录像：包含首个NUWA-ENTRY或启动横幅至最后panic | 用户已提供清晰PIL末屏照片；首屏和时序需人在设备旁录像，当前归属仍未确定 | 2026-10-23 00:50 | open（末屏照片已取得；不阻塞静态分析） |
