# PENDING-HUMAN

> 只差用户本人按键/在场的待办。**不阻塞主线**：记一条，继续下一项。
> 只有「会改变设备内容且必须用户在场」的动作才升级为 `NEED-HUMAN.md` 并停机。

## 当前状态（2026-10-25）

PROBE26已仅一次临时boot ACK，等待菜单电源Enter后完整画面，含白色字段与右侧全部新增行。本轮Android恢复后验待完成，不重复启动；人工等待继续离线工作。

续接见[当前交接](operations/2026-10-25-mainline-handoff.md)。以下保留历史快照，旧open项不构成当前主线启动条件或新设备动作授权。

## 历史记录（原2026-10-24待办）

- 全量上游合并：离线合并/构建已授权，目前不需要用户按键或录像；新FD尚未实测，若后续需要启动须另确认当轮日志及恢复条件。

- 26ef8efd：五张缓存/ReadyToBoot/菜单/后备原图已取得，画面待办完成。无需再次按键，Android及三分区恢复已闭环。
- 当前不等待新启动许可；本轮录像确认已用于一次启动，后续试验重新确认。
- 下方为历史记录：历史open项不自动授权重启；H-003早期首屏录像仍缺，不能用本轮菜单文字替代。

| 编号 | 待办 | 为什么必须本人 | 提报时间 | 状态 |
| --- | --- | --- | --- | --- |
| H-001 | C3 长按电源键强制重启恢复演练 | 需要实体按键 + 人在设备旁观察 | 2026-10-22 00:44（继承自旧仓） | completed（R-010恢复路径已演练，见reports/dxe-allocation/39829943950/recovery.json；不重复要求演练） |
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

2026-10-24T02:26:06.995875+08:00 · **2273bdec本轮完成**：after-mmu坏链原图取得，recovery/postcondition确认Android完成1及三分区SHA不变，无需再按键。新的缓存交接候选尚未生成；后续新包另需录像。

2026-10-24T02:48:52.565741+08:00 · HOB缓存交接新包26ef8efd已离线验收，待通知并确认本轮录像≥120秒和必要时按键回fastboot条件。当前不启动，无本轮设备动作；上轮恢复已闭环。

2026-10-24T02:53:09.563575+08:00 · 26ef8efd本轮用户已确认录像，preflight确认nuwa/kalama、Android完成1及三分区基线；即时通知后已单次fastboot boot，ACK=0。正在120秒观察，等待屏幕证据及本轮恢复闭环；ACK不证明HOB修复。

2026-10-24T02:55:21.975969+08:00 · 26ef8efd已完成120秒观察，用户报告进入UniXNU菜单；请保存本轮菜单/缓存日志录像或原图，必要时按键回fastboot，恢复程序等待接管。Android完成1/三分区核验待补，不再启动新包。

2026-10-24T02:56:24.080562+08:00 · **26ef8efd恢复已闭环**：recovery/postcondition确认nuwa/kalama、Android完成1、槽_a及三分区SHA与preflight一致，无需再按键。仅待本轮缓存阶段/菜单原图或录像，未确认根因；不自动再启动。

2026-10-24T03:08:47.513216+08:00 · **26ef8efd画面待办完成**：五张原图归档，after-mmu ok/count84、ReadyToBoot和菜单已核对；用户报告末尾充电。无需补本轮录像或再次按键，重复性留作未来独立试验。

2026-10-24T15:04:24.918562+08:00 · 为后续独立大文件运输诊断询问OTG转接线/U盘可用性，尚不写介质/启动；继续离线构建，不因等答复停止。旧录像许可不复用。

2026-10-24T15:16:00+08:00 · OTG询问已答复：用户暂时没有转接线/U盘，该问项关闭，不等待用户购买/按键/录像。继续离线资格审计和运输方案准备；探针及新包尚未构建，无本轮设备动作。

2026-10-24 USB路线 · v3包8177783e已离线构建/逐字节验收，待确认本轮连续录像至少120秒及必要时按电源＋音量下回fastboot条件；确认前不启动，启动前即时通知。无需OTG/U盘；完整准备见operations/2026-10-24-usb-ramdisk-v3.md。v4匹配对照仅离线，不安排第二轮自动启动。

2026-10-24 USB候选准备期间 · 用户新增“现在有OTG线了”，授权自行选择稳健/快速路线；已记录可用线缆，不再沿用暂无OTG状态。当前仍先测就绪v3候选，OTG介质/host验证作备选，不需用户先操作OTG；本包录像条件仍待新确认。

2026-10-24 v3-01正在观察 · 用户本轮已答“可以，现在准备录像”；preflight唯一nuwa/kalama、Android完成1/A槽及三分区旧基线一致，已即时通知后单次启动8177783e，fastboot ACK=0。正在120秒观察，待chosen/封装/发布原图或录像及本轮恢复闭环；ACK不证明v3接受或运输成功。证据reports/usb-ramdisk-trial/2026-10-24-v3-01/，具体时间见launch.json。

2026-10-24 v3-01观察结束 · 已完成120秒；用户文字“菜单显示 booting volume config loaded”已记observation.json，原图/录像尚未提交。已通知保存录像，必要时按电源＋音量下回fastboot；recovery程序正在等nuwa恢复，Android完成1及三分区postcondition待补。人工恢复待办不阻断离线工作，不安排第二轮启动。

2026-10-24T15:41:49+08:00 · **v3-01本轮全部待办关闭**：两张原图已归档，独立64MiB封装/块Success/FAT挂载实机证据取得；recovery/postcondition确认nuwa/kalama、Android完成1/A槽及三分区SHA与试前一致。不再需要按键/补录像，不自动安排OTG或第二候选。下次新包另过本轮录像门。

2026-10-24 文件SHA候选 · 新包18ebd838完成离线构建/全包验收及完整UEFI QEMU文件SHA/返回验证；待本包新鲜连续录像≥120秒和必要时电源＋音量下恢复条件确认。确认前不启动，启动前即时通知，仅原USB线无需OTG。期望NUWA FILE SHA PROBE及NUWA-FILE-SHA actual SHA/PASS，旧菜单不作成功。最近手机恢复仍15:41:49，本轮无新设备动作。

文件SHA第01轮正在执行：本轮用户已确认录像，preflight刷新nuwa/kalama、Android完成1/A槽及三SHA与上轮恢复一致；即时通知后单次18ebd838临时启动ACK=0，正在120秒观察。证据reports/file-read-audit-trial/2026-10-24-01/，待本轮实际SHA/PASS或失败画面及恢复闭环，不复用旧结果，不启动第二候选。

文件SHA第01轮菜单阶段：120秒USB观察结束；用户文字报告新Read 58MB条目，并询问是否选中。已说明如仍在菜单可用Enter一次，菜单任何键会取消倒计时；缺输入设备时先保存当前画面，不猜nuwa实体电源键映射。当前等待该轮实际SHA/FAIL画面或用户完成操作，尚未启动恢复程序，避免打断该轮应用；启动后Android完成1/三SHA闭环仍待补，不安排第二次fastboot boot。

2026-10-24T16:14:06+08:00 · **文件SHA第01轮待办关闭**：原图明确returned Access Denied，已纠正需要Enter的判断，不再要求键盘；recovery/postcondition实际确认nuwa/kalama/Android完成1/A槽及三分区SHA不变。无本轮文件SHA成功证据，不重复启动同包；继续离线认证入口诊断，当前无需按键/录像。

2026-10-24 FV文件候选 · 最终6b3e5bfd已完成第二轮CI40080439083及独立710项产物/全包验收；原Heap/HOB/SEC和认证策略保持。待本包连续录像≥120秒及必要时电源＋音量下回fastboot确认，确认前不启动，启动前即时通知。校验由固件ReadyToBoot自动执行，不用Enter/键盘/OTG；重点留NUWA-FV-FILE实际SHA/PASS或失败阶段。本轮离线无设备动作，最近恢复仍16:14:06。

2026-10-24 18:09：6b3e5bfd本轮录像在场条件已确认、三张原图已收、用户回fastboot并完成自动原厂恢复；Android1及三SHA不变。本轮无需继续按Enter或按键，完整视频文件未交付。新包另确认录像条件，当前继续离线资格检查。
2026-10-24 内核入口探针01：用户已确认本包ab3c092b可连续录像≥180秒并必要时按键恢复；新鲜preflight唯一nuwa/kalama、Android1/A槽/三SHA基线通过。已即时通知，准备单次临时启动；待本轮色带/异常原图录像及恢复闭环，不复用旧试验结果。
2026-10-24 20:5x 入口探针01：用户已报告绿蓝黄品红四色，内核内执行阶段证据取得；180秒观察完成，原图录像待交付。恢复程序已运行；若仍停屏，保存录像后电源＋音量下回fastboot；若Android已回无需按键。待Android1及三SHA postcondition；人工恢复不阻断离线分析，不启动第二候选。
2026-10-24 20:53:19 · 入口探针01恢复待办已关闭：原图5716899a确认四色；recovery/postcondition确认nuwa/kalama、Android1/A槽、三分区SHA不变。无需再按键；完整录像文件可后续补交，不阻断离线推进。不自动再次启动。

- [x] 2026-10-25：entry-probe-14录像就绪、菜单电源键触发与恢复已完成；15:07:42北京时间Android完成1，三分区SHA不变。用户明确后续取消固定180秒等待。

- [x] 2026-10-25：entry-probe-15用户录像/菜单电源键触发/恢复已完成；16:12:44北京时间Android完成1、三SHA不变。本轮无待恢复任务，原始音视频仅本地。

- 2026-10-25 PROBE16：用户已报告并拍到kernel_bootstrap橙色块；候选只临时启动一次，恢复脚本正在等待nuwa fastboot/Android完成1，尚未获得本轮postcondition，不启动新候选。保存照片后电源+音量下即可；人工恢复等待不阻断离线分析。

- [x] PROBE16恢复等待已关闭：2026-10-25 16:44:29北京时间，Android1/A槽，三SHA与preflight一致，无新待录像/按键任务。先前等待条目保留为过程记录。

- [x] 2026-10-25 PROBE19（20:03:58后验已关闭，以下保留先前等待过程）：本包用户录像/恢复条件已确认，19:56:34新鲜Android1/A槽/三SHA通过；19:57单次临时boot ACK。照片5bad2ca9已本地保留，BSD入口ID6/A02B=6点亮，pthread kernel extension not loaded panic，root未进入。第一次原厂恢复监测180秒未见Android完成，待用户电源+音量下回fastboot后临时加载固定原厂boot；人工恢复等待不阻断离线分析，不启动第二候选。证据reports/xnu-entry-probe-trial/2026-10-25-v27/。

- [x] PROBE19恢复闭环：2026-10-25 20:03:58北京时间，用户已回Android；命令确认Android完成1/A槽/boot_a、vendor_boot_a、init_boot_a三SHA与preflight完全一致。第一次recovery超时保留，成功重试确认已在Android，无第二试验包。当前无待恢复任务；下一包另核对当轮录像/恢复条件。

- [x] PROBE20：用户确认录像/恢复就绪，单次临时boot并取得照片36983517，实机进入IOFindBSDRoot。用户回fastboot后临时原厂boot恢复，2026-10-25 20:45:31 +08确认Android1/A槽/三SHA与本轮preflight一致。当前无待恢复任务，不重复启动20；证据reports/xnu-entry-probe-trial/2026-10-25-v28/。

- [x] PROBE21：照片b412ba53已确认root介质匹配等待；第一次恢复监测超时保留，用户回fastboot后固定原厂boot临时加载一次。21:12:18 Android完成1，2026-10-25 21:13:15 +08后验A槽/三SHA与本轮preflight一致，恢复关闭。用户最新要求暂不排查重启并继续新临时启动；PROBE22离线准备中，不复用旧包作为新进度。

- [x] PROBE22：原图fc1c4ade确认真实md0路径及原生挂载返回0、212绿，预定终点停止。21:30:22观察Android1，2026-10-25 21:30:50 +08后验A槽/三SHA与本轮preflight一致，恢复关闭。用户要求减少阶段停止并连续推进下一候选；不重复启动22。

- [x] PROBE23：原图624b4cda确认bsd_init返回、首进程准备及首次exec前217/218；21:50:19 Android1，2026-10-25 21:50:51 +08后验A槽/三SHA与preflight一致，恢复关闭。用户确认已回Android，无待按键任务；后续按“都连续推进”执行，不重复启动23。
