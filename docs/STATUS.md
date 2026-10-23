# STATUS

> 当前唯一真相：卷探针ae9a445a停于零长度HOB循环，已恢复Android；正在构建HOB完整性诊断。

原图显示多行ptr=BAB00718 type=0 len=0至row127；GET_NEXT_HOB按长度推进，零长度使指针不动。尚未到启动卷发现，无XNU证据。创建错误、覆盖、缓存可见性或链边界原因仍未区分。证据reports/volume-envelope-trial/2026-10-23-evening/。

用户回fastboot后原boot临时恢复，postcondition确认nuwa/kalama Android完成1、A槽及三分区哈希不变。

0014候选补丁在异常长度处打印并CpuDeadLoop，查询入口打印GUID及PHIT end/bottom/top；不跳过条目或伪造查询结果。hob-integrity独立profile的41输入/6补丁/9后哈希静态通过。新增诊断待CI和完整包核验，实机前通知并刷新门。

固件接收驱动仍来自uefi-nuwa@150b5ec。64MiB卷探针及完整C主机解析已通过离线检查；ABL运输尚未实机验证。板值与_verified不变，等待人工操作不阻塞离线工作。
