# PENDING-HUMAN

> 只差用户本人按键/在场的待办。**不阻塞主线**：记一条，继续下一项。
> 只有「会改变设备内容且必须用户在场」的动作才升级为 `NEED-HUMAN.md` 并停机。

| 编号 | 待办 | 为什么必须本人 | 提报时间 | 状态 |
| --- | --- | --- | --- | --- |
| H-001 | C3 长按电源键强制重启恢复演练 | 需要实体按键 + 人在设备旁观察 | 2026-10-22 00:44（继承自旧仓） | open |
| H-002 | 进 bootloader 用 `fastboot getvar unlocked` 核实能否 flash（`verifiedbootstate=orange` 与 `flash_locked=1` 矛盾） | **已预授权，可自行执行**：属恢复类只读操作，不写设备；执行后必须 `fastboot reboot` 送回 Android 并确认 `sys.boot_completed=1`。此处仅登记 | 2026-10-22 02:55 | 可执行 |
