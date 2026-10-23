# PrePi HOB 查询诊断

最新2b203afa实测最后Mmu enter；用户要求继续直至XNU。下一步先界定GetFirstGuidHob与前一日志返回。

实际SEC（FD ea0277e8）的GetFirstGuidHob/GetNextHob和SerialPortWrite反汇编已保存reports/hob-query/audit.json，源码Mu cfb93724、BSD-2-Clause-Patent。GetHobList读TPIDR，遍历读取HobType/HobLength；没有零步长和边界保护。FrameBuffer日志在写字后仍调用缓存维护，因此最后可见日志不证明其调用已返回。尚无运行PC或坏HOB证据。

0013-prepi-hob-query-trace.patch只改PrePiHobLib/Hob.c，GetFirstGuidHob入口、list、查询返回及GetNextHob逐项/比较日志；每次查询最多128条row，达到上限只停日志、不改遍历。新增header length读取可能影响异常位置，日志影响时序。不会伪造HOB、跳过cache或把缺失GUID改为成功。

独立hob-query profile保留0011/0012，新增第40项原始输入和第9项post-patch输入；完整补丁链内存检查通过。诊断块删除后遍历与返回表达式一致。既有5项MMU离线测试通过。

同SoC参照仍为reports/sec-handoff/same-soc-order.json固定uefi-sheng@329b473d；其SEC同样在PlatformPeim和EntryArg HOB后执行构造，只支持顺序参照，不说明nuwa运行HOB有效；本次未移植其他板内存值。

CI/实际产物/全表/打包尚待。下一次实测须通知录像并刷新恢复门，当前Android恢复已确认。

第一版CI39961551151成功但未打包或实测。39个有资源HOB的描述符加系统内存分配HOB，以及ArmMmuLib AllocatePages页表分配、平台/Extract HOB，可能超出64条日志；将上限改为128再构建。128仍是日志上限，不是运行链有效性限制；达到上限不改变遍历。

## 构建及包就绪

CI39962464061/4d4571b成功，实际SEC九条HOB及前序MMU/CTOR/HANDOFF通过；41行2952B全表与R-011一致。包47b5c4b171d7a0635bb494a8d0e70e9f5159b269aff3b68a66b2fd3868c0de50，3153920B；FD fb28d9ee。完整下载inventory核验和严格整头/载荷/填充重建通过。下载首次EOF后重试成功；未用不完整下载打包。证据reports/hob-query/39962464061/。
