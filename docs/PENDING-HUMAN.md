# PENDING-HUMAN

> 只差用户本人按键/在场的待办。**不阻塞主线**：记一条，继续下一项。
> 只有「会改变设备内容且必须用户在场」的动作才升级为 `NEED-HUMAN.md` 并停机。

| 编号 | 待办 | 为什么必须本人 | 提报时间 | 状态 |
| --- | --- | --- | --- | --- |
| H-001 | C3 长按电源键强制重启恢复演练 | 需要实体按键 + 人在设备旁观察 | 2026-10-22 00:44（继承自旧仓） | open |
| H-002 | 进 bootloader 用 `fastboot getvar unlocked` 核实能否 flash（`verifiedbootstate=orange` 与 `flash_locked=1` 矛盾） | 2026-10-22已读fastboot unlocked=yes；普通reboot回fastboot后，原厂boot临时加载回Android且boot_completed=1。证据reports/trial-boot-preflight/，未实际flash验收 | 2026-10-22 02:55 | completed（19:06） |

| H-003 | 同包试启动的连续录像：包含首个NUWA-ENTRY或启动横幅至最后panic | 用户已提供清晰PIL末屏照片；首屏和时序需人在设备旁录像，当前归属仍未确定 | 2026-10-23 00:50 | open（末屏照片已取得；不阻塞静态分析） |

| H-004 | R-009断言停机后按电源+音量下回fastboot，以便本轮恢复Android | 当前nuwa无ADB/fastboot通道，主机无法发恢复命令；只差实体键，不继续试验 | 2026-10-23 01:24 | completed（用户确认已回fastboot；01:25:30原Android备份临时恢复后完成1，见R-009 recovery-after-keys/postcondition） |

| H-005 | R-010录完画面后按电源+音量下回fastboot，以便原Android恢复 | 候选临时命令已结束，采样无nuwa fastboot；主机等待恢复通道，实体按键需本人 | 2026-10-23 02:28 | completed（用户确认已回fastboot，原boot临时恢复；02:30:04实际nuwa Android完成1，postcondition三分区SHA未变） |

| H-006 | R-011保留画面后回fastboot以恢复Android | 曾请求按键；恢复脚本随后检测到fastboot并接管，具体回返方式未记录 | 2026-10-23 09:11 | completed（用户确认Android，09:14:28命令确认完成1且三分区摘要不变；不再需按键） |

| H-007 | 中午在设备旁时配合定向录像，补取SHENGMEM的DT/initrd/发布状态 | 用户当前不在旁，现有录像未提供该行；本轮只完成离线准备，无自动试启动；如复测须先通知并刷新日志/恢复门 | 2026-10-23T09:56:34+08:00 | completed（中午已录像/提供照片；停于SEC，SHENGMEM未到达，不称目标日志取得） |

| H-008 | 中午SEC停点后按键回fastboot，以便只恢复原Android | 用户已回复“已回 fastboot” | 2026-10-23 12:17 | completed（12:18:42 Android完成1，三分区SHA不变） |

| H-009 | 晚上SEC handoff诊断连续录像，拍摄ENTRY/HANDOFF/DXE并标注相对时间 | 用户要求留晚上一起实测；先完成离线构建检查，启动前通知且刷新日志/恢复门；本轮不操作手机 | 2026-10-23T15:02:06+08:00 | completed（18:30:39实际Android完成1，用户更正照片f3cf9558已取得；视频文件未交付，不称完整连续录像取得） |

- 2026-10-23T21:21:52.765772+08:00 · **已完成**：MMU分支包2b203afa实测后用户回fastboot，21:22:57恢复Android完成1，三分区哈希一致。证据reports/mmu-branches-trial/2026-10-23-evening/。

- 2026-10-23T21:47:07.549927+08:00 · HOB查询包47b5c4b1完成120秒USB观察；等待用户保存录像/最后画面并按键回fastboot。恢复程序接手中，离线分析继续。

- HOB查询试验更新：用户已提供HOB到DXE原图；报告菜单无OS后回充电界面。恢复脚本180秒等待超时，后续ADB未识别；待正常Android或fastboot恢复及三分区核验。录像SHENGMEM段待补取，离线分析继续。

- SHENGMEM补取已完成：收到initrd拒绝与UniXNU/FAT原图，见initrd-observation.json；Android恢复状态仍待确认。

- HOB试验恢复已完成：postcondition.json确认Android完成1及三分区哈希不变；此前恢复待办关闭。下一轮新包需通知录像。

- dd1ef825本轮待恢复闭环：recovery.json等待超时；录像末尾Android标志不是完成1。需确认真实nuwa Android ADB及三分区postcondition，必要时实体键回fastboot后接管。录像已收到并归档摘要/关键帧；离线卷发现分析继续。

- 2026-10-24T00:15:19.951531+08:00 · dd1ef825恢复待办完成：postcondition.json确认本轮nuwa/kalama、Android完成1及三分区SHA与preflight一致。新包录像待产物就绪后确认，离线构建继续。

- 2026-10-24T00:27:22.419670+08:00 · a22e9a44本轮120秒观察已结束；已通知保留录像/末屏并按电源＋音量下回fastboot，恢复工具接管等待。需要本轮NUWA-VOLUME日志、Android完成1及三分区核验，不阻塞离线工作。

- 2026-10-24T00:39:15.327331+08:00 · a22e9a44本轮恢复/照片待办完成：用户六张原图取得；recovery-after-keys及postcondition确认Android完成1、三分区SHA一致。后续新包需另确认录像。

- 2026-10-24T00:56:02.341592+08:00 · 87b14624本轮已取得发布Success和探针菜单原图；恢复程序等待Android/fastboot，已通知保留录像后按键回fastboot。本轮完成1/三分区postcondition待补，离线主线继续。

- 2026-10-24T00:57:15.571203+08:00 · 87b14624本轮恢复待办完成：recovery.json实际Android完成1，postcondition三分区SHA一致；不再需按键。

2026-10-24T01:41:52.750228+08:00 · **暂停（用户要求）**：a2dc8195启动输入包仅离线就绪，用户答复“先停下 落实文档”。当前不等待按键、不执行启动；需用户明确恢复主线并重新确认录像后再测。无本轮设备动作；最近恢复闭环仍是87b14624。

2026-10-24T01:44:39.161097+08:00 · a2dc8195暂停已由用户明确续接解除，本轮录像确认已取得并通知后单次启动。待ReadyToBoot画面及观察结束后的Android恢复；以本轮postcondition关闭，不复用旧记录。

2026-10-24T01:54:51.259229+08:00 · **a2dc8195本轮已闭环**：已取得HOB invalid原图，recovery/postcondition实际确认Android完成1和三分区SHA一致，无需再按键。新诊断模块未执行；后续包需新一轮录像，不复用本轮许可。

2026-10-24T02:14:14.358409+08:00 · HOB阶段新包2273bdec已离线验收，待通知并确认本轮连续录像≥120秒及按键回fastboot条件，确认前不启动。本轮无设备动作；上轮Android恢复闭环已完成。
