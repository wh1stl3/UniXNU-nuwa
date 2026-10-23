# a2dc8195 启动输入试验：SEC HOB异常

## 执行与恢复

用户明确恢复主线并确认该包录像，启动前已即时通知。preflight实际查询时间2026-10-23T17:43:37.527711+00:00，nuwa/kalama、Android完成1、slot_a，三分区SHA已保存。单次fastboot boot接受，120秒USB观察完成；这只证明命令接受/USB观察，阶段结论来自本轮用户原图。无flash/erase/改槽位。

原图hob-invalid-screen.jpg SHA256 07867a1046f2694e83317ca380bf65d1b7d1835e274a66aa887a215b6439021f，用户说明“直接停在了hob check invalid ptr”。本轮recovery确认Android完成1；postcondition 2026-10-23T17:48:19.683937+00:00 实际再次确认nuwa/kalama、slot_a、三分区SHA与preflight相同，恢复闭环。无需再按键。证据目录reports/boot-input-audit-trial/2026-10-24/。

## 原图支持的结论

SEC已完成InitializeMemory、PlatformPeim及EntryArg HOB，Debug/Extract构造返回Success，Mmu构造开始GetFirstGuidHob。列表BAB00000，前可见记录为+0 type1 len38、+38 type7 len50、+88/+b8/+e8 type3 len30（均十六进制）。最后是`[NUWA-HOB-CHECK] invalid ptr=BAB00118 type=4 len=0 target=4`。

0014-hob-invalid-entry-diagnostic.patch在GetNextHob发现长度小于EFI_HOB_GENERIC_HEADER或不按8字节对齐时记录并CpuDeadLoop。因而这是保护性停点的直接证据：不能移除检查或把坏长度补成猜测值后继续。画面不是异常PC采样，不能证明检测日志后的具体PC，也不能定位最初写坏/可见性变化发生时间。未到after-library-constructors、DXE或NuwaBootAuditDxe，尚无ReadyToBoot、EL/MPIDR/CNTFRQ或连续内存范围；新诊断模块实机未验收。

## 实际二进制差分

scripts/audit-boot-input-sec.py固定旧成功FV探针CI39988591973/FD70b266b3与本轮CI39995937843/FDbfb02a63，解析实际SEC TE并比较所有字节。两者均69288B，`.text`40960B SHA022ad200一致，`.data`及`.pdata`一致。全SEC只有4字节变化，全部在同一8字节`__TIME__`字符串：16:36:44→17:25:24（SOURCE_DATE_EPOCH分别1792773404/1792776324）；将该8字节置零后整个SEC逐字节相等。41行2952B内存表也一致。报告sec-differential.json。

这排除了“新包SEC指令或该内存描述表改了”的解释；不能排除完整FD/FV布局、加载环境、缓存可见性、其他执行者或运行时写入。新DXE驱动此时还没运行，不能仅凭加入新驱动就归因其内存快照代码。已实测87b14624成功也不代表早期HOB链稳定。历史同地址BAB00718坏长/有效长的运行差异见2026-10-23-hob-integrity-trial.md；不得据此单独确认缓存根因。

## 后续离线定位

优先准备带边界检查的只读HOB阶段诊断：在创建/填充之后、ArmConfigureMmu前后、PlatformPeim/各构造前后检查相同头链，报告首次异常阶段、PHIT范围、坏头及邻近有限原始字节；保留失败保护。不要同时改缓存策略或移动Heap，否则难以比较。需先审查扫描边界/上限和实际生成代码，再完整构建、包复验；新包设备测试另需恢复闭环与新一轮录像确认。

另一可选是重复原87b14624以测重现性，但不能定位首次异常；本轮不自动增加设备启动。当前没有生成或启动后续包，没有修改board/bringup内存值/_verified，HOB根因未解决。
