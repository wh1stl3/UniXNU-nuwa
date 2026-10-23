# STATUS

> 上游合并进行中：用户已授权合并所有更新，真实合并e553e46已推送；21模块固定，63项内核补丁和51输入/11补丁固件链静态检查通过，完整CI待验。

2026-10-24：26ef8efd五张原图已取得；缓存维护标记后after-mmu ok/count84，随后ReadyToBoot和唯一配置菜单，本轮阶段实机通过。原Android恢复完成1，三个启动分区SHA不变。缓存交接遗漏为明确首要原因判断，稳定性及唯一根因仍待验。

CI40005057158/source bdcf4a2f02f86dca5b7ad88e24377912f3612b0e；固件固定6176a822e66b846620b5bcd2739a0666814ee663/Mu cfb93724加0019。包26ef8efdc034f726df23f7bb2998d9e980e52e706e914ba9a415ca088dba2051/3153920B；固件仓e7a2284（前序6770fb9）仅文档/规则，不改变构建来源。51输入/11补丁/15后哈希、主机边界测试、实际维护指令及原保护分支、41行内存表和严格容器重建静态检查通过。

证据reports/hob-cache-handoff-trial/2026-10-24/screen-observation.json及五张原图。第1图HOB-CACHE下面是after-mmu成功；SCTLR全值/hash低清不强行转录。第3图ReadyToBoot EL1，map6144B、128描述符、17常规合并范围，最大/writeback base0x8C0000000、bytes0x240000000（9GiB），明确只快照未分配窗口。第4图配置菜单，第5图Not Found/USB后备；用户另报告最终充电。探针timeout60/action=exit且无OS负载，充分解释无OS后备；没有本轮HOB再次失败证据。[详细实测与原因排序](operations/2026-10-24-hob-cache-handoff-trial.md)。

首要工程判断为HOB非缓存写入后的旧缓存可见性问题：基线切换前有效/切换后坏，本候选保留Heap和保护，加范围IVAC后成功，公开ARM64维护者机制说明相符。代码布局/时序混杂与映射因素仍未完全排除；后续同包重复及完整日志用于证伪，当前不自动启动。判断规则已写AGENTS第8节。

恢复postcondition.at=2026-10-23T18:55:45.904383+00:00（北京时间02:55:45）确认nuwa/kalama、槽_a、Android完成1、三分区SHA一致；这是本轮恢复证据，不将旧充电画面当实时状态。当前无需按键或补本轮画面。

新增离线进展：固定DarwinBoot分配选择函数在主机ASan/UBSan下12项通过，当前分析内核同余偏移0x1c8000，照片大区子集能产生完整64位候选；不代表实际UEFI分配。4MiB配置卷装不下58,335,232B分析预链接，且它仍未具备启动资格。[离线分配与运输缺口](operations/2026-10-24-loader-window-offline.md)，reports/loader-window-host/results.json及reports/os-entry-next-step/continuation.json。

下一步保持Heap/保护，准备独立大文件读取/长度/SHA诊断，再落实真实ADT和实际窗口分配；未来设备动作另过新鲜录像/包/恢复门。当前native分析预链接5a128fb2仍loadable=false，ABI/ADT/OS窗口/大负载运输未验；本包无XNU/ADT，未执行iOS。board/bringup内存/_verified未改，无flash/erase/改槽位。两个旧资料库只读。[当前交接](operations/2026-10-23-mainline-handoff.md)。

上游最新驱动审查已完成：主仓1a01c2af与12模块/同SoC更新已固定对照；GPU/Metal/显示/HID有实质改动，ArmCpu/ArmDTPlatform/Prelink工具实现未变。Darwin22补丁对最新DarwinBoot严格内存apply通过但未构建。主仓已分叉，不整体升级；优先独立评估DarwinBoot+RamBlock，nuwa ST FTS不套Novatek。[审查记录](operations/2026-10-24-upstream-driver-review.md)。当前固定源码和实机候选保持，无设备动作。

当前“合并所有更新”授权已替代此前只审查不采用的决定。设备固件新增upstream-merged、内核merged接新源；保留已实测旧包与原profile作证据。详见[合并落实](operations/2026-10-24-upstream-integration.md)。无新手机动作，完整CI待结果。
