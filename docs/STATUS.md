# STATUS

> dd1ef825实测进入UniXNU内置菜单，目标卷和XNU尚未确认。2026-10-24已补齐Android恢复和三分区核验；正在构建卷发布状态诊断。

最新只读ADB确认nuwa/kalama、Android boot_completed=1、slot_a，三个启动分区SHA与上轮preflight一致；证据reports/hob-integrity-trial/2026-10-23-evening/postcondition.json。原恢复等待超时保留为历史，不再作为当前设备状态。

固件固定bc38be0：发布器错误传播/分阶段日志、可选5秒诊断停留，8项C主机测试通过。新volume-status profile的41输入/7补丁/10后哈希静态检查通过；CI39985245383/source b8e6e2a已启动，实际产物核验待完成，无新设备试验。未改板值、映射及_verified。

录像抽帧未取得可读NUWA-VOLUME结果，不能从缺失确定根因。下一步构建并验收新profile；新包启动须重新确认录像、日志/恢复门并通知用户。详见operations/2026-10-24-volume-publisher-status.md和operations/2026-10-23-mainline-handoff.md。

新scope的包校验、录像确认和恢复门已接入；2项旧产物冒充/空录像拒绝测试及5项MMU门回归通过，未执行设备命令。
