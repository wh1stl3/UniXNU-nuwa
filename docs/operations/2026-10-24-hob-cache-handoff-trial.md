# 26ef8efd 缓存交接候选实测

用户本轮确认“可以，现在准备录像”后，preflight记录nuwa/kalama、Android完成1、槽_a及三分区SHA。已即时通知录像，再单次临时启动；launch.json记录ACK=0及至少120秒USB观察。USB不能代替屏幕日志。

用户直接文字报告“进入了unixnu菜单”（user-observation.json）。这是越过此前早期HOB停机点的用户观察证据；尚无本轮原图，未读取HOB-CACHE的EL/SCTLR/范围、after-mmu链状态，不据此宣布缓存根因或修复正式闭环。此包只有配置探针，不包含XNU/ADT；菜单后找不到操作系统不等于本轮早期HOB失败。

恢复已完成：recovery.json实际临时加载原boot后识别Android完成1；postcondition.json再次确认nuwa/kalama、槽_a、完成1及三分区SHA与本轮preflight一致。postcondition.at=2026-10-23T18:55:45.904383+00:00。无需再按键；本轮不重复启动。Heap、内存表、原坏条目保护未改；没有flash/erase/改槽位。

证据目录：reports/hob-cache-handoff-trial/2026-10-24/。构建CI40005057158，来源bdcf4a2f02f86dca5b7ad88e24377912f3612b0e，整包26ef8efdc034f726df23f7bb2998d9e980e52e706e914ba9a415ca088dba2051。

文档落实：设备仓当前决策D-025及主线交接已同步；固件仓文档提交b569e4a（前序899ede3）已推送，仅文档，不改变本轮固件固定6176a82。本轮原始记录提交747d8fc，后续归档不得覆盖。当前只待画面，无新的录像/启动请求。
