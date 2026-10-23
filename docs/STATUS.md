# STATUS

> HOB缓存交接单变量候选已完成离线验证、完整构建和新包验收。新包26ef8efd尚未实测；待通知用户确认本轮录像，再刷新设备与恢复门。

CI40005057158成功，构建源bdcf4a2f02f86dca5b7ad88e24377912f3612b0e，固定固件6176a82/Mu cfb93724加0019。包SHA256 26ef8efdc034f726df23f7bb2998d9e980e52e706e914ba9a415ca088dba2051，3153920B；FD0e90473e/3MiB。实际SEC DSB→InvalidateDataCacheRange→DSB→ISB顺序及范围函数指向DC IVAC通过；原CreateHob两次/查询一次检查与CpuDeadLoop分支存在。41行2952B内存表与基线一致，严格整包逐字节重建通过，缺preflight新包在设备子进程前拒绝（调用0）。

行为变量仅为：最后建表分配后、MAIR/TTBR前一次性按完整cache行失效已拥有的HOB使用范围。要求EL1/2且SCTLR.M/C均0，否则停住。原HOB扫描/坏条目保护源码保留，MMU去新增钩子后文本等价；Heap/板值/属性不变。51输入11补丁15后哈希及精确C主机ASan/UBSan的8192对齐/拒绝/屏障序列/HOB字节不变/一次性钩子通过；主机不执行真实cache。详见operations/2026-10-24-hob-cache-handoff.md。

首嫌缓存交接遗漏，但根因与修复效果未闭环，不声明已修好。本轮无设备查询/命令；最近真实状态仍reports/hob-stage-audit-trial/2026-10-24/postcondition.json，UTC2026-10-23T18:20:52.568611（北京时间02:20:52），nuwa/kalama、Android完成1、三分区SHA不变。

下一步取得26ef8efd本轮录像可用答复后复验包与preflight、即时通知后单次临时启动，录像≥120秒，关注HOB-CACHE状态/跨度、after-mmu是否有效及末屏；最后原Android恢复完成1和三分区核验。没有新鲜录像就不启动。board/bringup内存值及_verified未改，未执行XNU/iOS。
