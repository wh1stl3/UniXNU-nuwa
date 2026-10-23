# STATUS

> 2026-10-24：缓存交接候选26ef8efd已完成一次临时实测，用户报告进入UniXNU菜单。Android恢复完成1，三个启动分区SHA与启动前一致。缓存阶段原图尚未收到，根因及修复重复性未确认。

本轮构建CI40005057158成功，源码bdcf4a2f02f86dca5b7ad88e24377912f3612b0e；固定固件6176a822e66b846620b5bcd2739a0666814ee663、Mu cfb93724，追加0019。镜像SHA256 26ef8efdc034f726df23f7bb2998d9e980e52e706e914ba9a415ca088dba2051，3153920B；FD0e90473e/3MiB。固件仓当前b569e4a仅补文档，不改变本轮构建固定提交。实测归档747d8fcc7368778a4af6ff49bf3d845e5154cf2e已推送。

候选只在最后建表分配后、MAIR/TTBR前对已拥有HOB使用范围按完整cache行失效，要求EL1/2、SCTLR.M/C关闭及完整链有效；Heap、板值、属性和原坏条目保护保留。51输入/11补丁/15后哈希、主机ASan/UBSan边界测试、实际DSB/IVAC/DSB/ISB指令、原保护分支、41行内存表与严格容器重建均静态检查通过。主机不执行目标cache操作。详见[候选说明](operations/2026-10-24-hob-cache-handoff.md)。

启动前preflight确认nuwa/kalama、Android完成1、槽_a及三分区基线；已通知录像后单次boot，120秒USB观察结束。用户文字“进入了unixnu菜单”是阶段推进观察；EL/SCTLR/维护范围和after-mmu仍待画面，不用ACK或菜单推导具体寄存器。postcondition.at=2026-10-23T18:55:45.904383+00:00（北京时间02:55:45），确认本轮Android完成1/三分区SHA不变，当前无需按键。[本轮实测](operations/2026-10-24-hob-cache-handoff-trial.md)；证据reports/hob-cache-handoff-trial/2026-10-24/。

下一步接收并归档缓存阶段/菜单原始画面，核对维护是否执行及链状态；缓存交接遗漏仍为首要假设，代码布局/时序混杂未排除。不要重复本轮启动，不复用录像许可或旧preflight；新的设备试验另过日志与恢复门。[主线交接](operations/2026-10-23-mainline-handoff.md)、[当前人工待办](PENDING-HUMAN.md)、决策D-025已同步。

本包仅配置探针，无XNU/ADT/ramdisk；尚未执行XNU/iOS。当前native分析预链接5a128fb2仍loadable=false，真实ADT、OS内存窗口、大负载运输与完整ABI尚待验收。board/bringup内存与_verified未改，本轮未flash/erase/改槽位；两个旧资料库只读。
