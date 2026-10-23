# STATUS

> HOB缓存交接单变量候选已完成离线验证、完整构建和新包验收。26ef8efd本轮用户已确认录像，preflight通过并已通知后单次临时启动，120秒观察已结束，用户文字报告已进入UniXNU菜单；原Android已恢复完成1，三个启动分区SHA一致；缓存阶段原图待补。

CI40005057158成功，构建源bdcf4a2f02f86dca5b7ad88e24377912f3612b0e，固定固件6176a82/Mu cfb93724加0019。包SHA256 26ef8efdc034f726df23f7bb2998d9e980e52e706e914ba9a415ca088dba2051，3153920B；FD0e90473e/3MiB。实际SEC DSB→InvalidateDataCacheRange→DSB→ISB顺序及范围函数指向DC IVAC通过；原CreateHob两次/查询一次检查与CpuDeadLoop分支存在。41行2952B内存表与基线一致，严格整包逐字节重建通过，缺preflight新包在设备子进程前拒绝（调用0）。

行为变量仅为：最后建表分配后、MAIR/TTBR前一次性按完整cache行失效已拥有的HOB使用范围。要求EL1/2且SCTLR.M/C均0，否则停住。原HOB扫描/坏条目保护源码保留，MMU去新增钩子后文本等价；Heap/板值/属性不变。51输入11补丁15后哈希及精确C主机ASan/UBSan的8192对齐/拒绝/屏障序列/HOB字节不变/一次性钩子通过；主机不执行真实cache。详见operations/2026-10-24-hob-cache-handoff.md。

首嫌缓存交接遗漏，但根因与修复效果未闭环，不声明已修好。本轮preflight见reports/hob-cache-handoff-trial/2026-10-24/preflight.json，启动前nuwa/kalama、Android完成1、槽_a与三分区基线已取得；launch.json记录临时启动ACK=0。用户报告“进入了unixnu菜单”，见user-observation.json；这支持越过此前早期停机点，但HOB-CACHE寄存器/范围及after-mmu仍待画面核对。recovery.json及postcondition.json已确认本轮Android完成1/三分区SHA一致，恢复闭环。

下一步收取本轮HOB-CACHE/after-mmu/菜单原图或录像，核对缓存维护真实状态及链完整性。当前无需人工按键，不自动重复启动；后续设备试验须新鲜日志/恢复门。Heap、坏条目保护、board/bringup内存及_verified均不改，未执行XNU/iOS。
