# MMU构造内部离线核验与分支日志候选

2026-10-23T20:34:35+08:00。本轮仅离线研究，不操作设备、不生成新镜像。最近实测仍为19:46:21 Android完成1及三分区不变。

## 实际二进制

scripts/audit-mmu-constructor.py核对FD a47d8289、SEC20b77681和link-map。ArmReplaceLiveTranslationEntry首选链接地址A7109800，size字段A71098F0，实际长度240B，helper SHA f615b9f458887ed15c7d62ccfdd82a2dbf6894d5e6f09dee54033a8ff299561d。首选地址不是采集的运行PC或新板值。

ArmDataCacheLineLength指令从寄存器值提取bits19:16，再计算4左移字段，合法返回值为4至131072的2次幂，不能直接归因为零步长死循环。寄存器读取本身是否成功仍未验证。

CacheRangeOperation向下对齐，调用行操作，累加步长，末尾DSB；行操作ArmCleanDataCacheEntryByMVA是dc cvac。正常有限地址/长度和非零步长下不是无限循环；这不排除权限陷阱、cache维护异常或barrier问题，没有运行CTR_EL0/CurrentEL/故障寄存器证据。

GetFirstGuidHob会遍历HOB并比较GUID，非法长度或终结链可能影响遍历。入口HOB及Extract调用返回不能证明此刻整链正确，尚不能排除查询路径。

构造找到HOB时读取函数指针；没找到时仅清理helper缓存，**不会调用helper执行页表替换**。因此helper里的SCTLR/TLBI指令不是本轮已执行故障点的证据。实际Mmu enter仍只说明入口日志已打印。

audit.json保存实际函数反汇编、helper字段、固定Mu四文件SHA和行号。来源microsoft/mu_basecore@cfb93724a06ff86ff5ba971413368a7809ee42a5，BSD-2-Clause-Patent。同SoC顺序评估仍见reports/sec-handoff/same-soc-order.json，不借其他板值。

## 下一轮候选

0012-mmu-constructor-branches.patch在0011之后，仅加五条日志：after-guid-query hob、before/after-hob-function-read、before-cache helper/bytes、after-cache。原Mmu enter已位于查询前。没有新增硬件寄存器读取、HOB遍历或指针解引用，不跳过缓存同步、不更换函数指针/返回状态。

内存严格上下文应用通过，删除五条日志后逐字节还原父源码；branch-proposal.json固定前后SHA。**尚未接入CI、编译、打包或实机执行**，不能将530f56b4旧包称为包含这些日志。下一步接入独立profile及post-patch pin，再构建/检查实际TE和全部内存表。

after-guid-query区分查询是否返回；HOB分支前后区分字段读取边界；cache前后区分调用是否返回。若有before-cache而无after-cache，仍需区分寄存器读取、dc、DSB和输出，不直接修改缓存策略。用户在场及日志/恢复门必须于新试验前刷新。

## 发布状态

前一实测提交3f49c80的Git对象API发布两次401，读ref/auth可用；未认定凭据已修复或远程更新。本轮保留全部本地工作，发布结果单独确认。未改board/feed/bringup-plan/验证标志。
