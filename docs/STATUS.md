# STATUS

> 当前唯一真相：卷探针ae9a445a停于零长度HOB循环，已恢复Android；正在构建HOB完整性诊断。

原图显示多行ptr=BAB00718 type=0 len=0至row127；GET_NEXT_HOB按长度推进，零长度使指针不动。尚未到启动卷发现，无XNU证据。创建错误、覆盖、缓存可见性或链边界原因仍未区分。证据reports/volume-envelope-trial/2026-10-23-evening/。

用户回fastboot后原boot临时恢复，postcondition确认nuwa/kalama Android完成1、A槽及三分区哈希不变。

0014候选补丁在异常长度处打印并CpuDeadLoop，查询入口打印GUID及PHIT end/bottom/top；不跳过条目或伪造查询结果。hob-integrity独立profile的41输入/6补丁/9后哈希静态通过。新增诊断待CI和完整包核验，实机前通知并刷新门。

固件接收驱动仍来自uefi-nuwa@150b5ec。64MiB卷探针及完整C主机解析已通过离线检查；ABL运输尚未实机验证。板值与_verified不变，等待人工操作不阻塞离线工作。

CI39973030321已成功；新产物尚待下载、实际新标记核验及独立打包scope接入。当前续接入口见operations/2026-10-23-mainline-handoff.md。用户要求每次硬停落档已纳入AGENTS。


## HOB完整性包本地验收更新

CI39973030321已下载并通过实际SEC新标记及全固件检查。新包dd1ef82517d256a44b05b5d72e132fe4a37078e2e12cf82f40302b408886034e，70266880B；FD8e37ba79。41行2952B内存表相同，完整容器逐字节复验通过。独立HOB-INTEGRITY-OFFLINE scope已接入打包、preflight和trial；旧volume-envelope包仍按旧scope复验。原5项MMU门测试通过。

用户本轮确认通知后录像，preflight确认真实nuwa/kalama Android完成1及A槽/三分区摘要。包待立即通知并临时启动；屏幕和恢复未发生，不宣称实机通过。证据reports/hob-integrity/39973030321/与reports/hob-integrity-trial/2026-10-23-evening/。旧交接中的“尚未本地核验/未接入scope”被本节取代。继续关注query GUID/PHIT及invalid行，不跳过损坏条目。
