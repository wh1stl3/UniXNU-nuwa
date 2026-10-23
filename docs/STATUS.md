# STATUS

> 按用户要求准备HOB缓存交接单变量候选，离线源码范围/主机边界及顺序测试通过；完整CI和新包验收待完成。本轮无设备动作。

以2273bdec的hob-stage-audit为基线，0019在全部建表分配之后、MAIR/TTBR安装之前一次性调用HOB范围失效。先确认EL1/2、SCTLR.M/C均0、可信arena和原有HOB检查，再覆盖完整cache行执行DSB/IVAC/DSB/ISB；不清空Heap，不clean旧HOB，不改板值/属性。原0018坏条目检查源码逐字节保留，MMU移除新增钩子后与基线完全相同。51输入11补丁15后哈希通过；精确新增C的8192对齐/拒绝/调用顺序/字节不变/一次性钩子主机ASan/UBSan通过。详见operations/2026-10-24-hob-cache-handoff.md。

首嫌仍是缓存交接遗漏，未确认根因或修复；尚无新包SHA或实机效果。最近真实设备为reports/hob-stage-audit-trial/2026-10-24/postcondition.json，UTC2026-10-23T18:20:52.568611（北京时间02:20:52），nuwa/kalama、Android完成1、三分区不变。本轮无实时查询/模式切换。

下一步完整CI、实际SEC回调/维护指令、41行内存表及严格包复验；就绪后通知录像，新鲜确认和恢复门齐备前不启动。Heap/board/bringup/_verified保持不变，未执行XNU/iOS。
