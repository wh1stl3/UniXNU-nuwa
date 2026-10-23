# 有界 HOB 阶段检查候选

## 问题和目标

a2dc8195在SEC Mmu构造查询中发现BAB00118/type4/len0。它与旧成功87b14624的实际SEC只有构建时间字符串4字节不同，尚无首次写坏阶段证据。新独立hob-stage-audit profile保留所有原始失败保护，在固定固件6176a822e66b846620b5bcd2739a0666814ee663及Mu cfb93724a06ff86ff5ba971413368a7809ee42a5上追加0018，只改候选PrePiHobLib/Hob.c、MemoryInitPei.c和Sec.c。正常固件源及旧profile不改；无新板值/内存映射/缓存策略。

## 检查与日志

HobConstructor及PrePeiSetHobList后，以InitializeMemory已经选出的arena基址和长度启用检查。其他PrePi消费者未调用Init，检查为无操作。每次先验证GetHobList等于可信基址、PHIT类型/长度/物理上下界、end/bottom/top关系，再扫描头链；不会盲信损坏PHIT的end去读。长度/地址溢出、对齐、每次推进、终点typeFFFF/len8均检查；最大1MiB头链跨度、4096条，超出拒绝，不输出部分成功。不分配内存。

检查点：hob-constructor；create-before/create-after（context高16位type、低16位len）；resource-filled/allocation-filled（context为当前既有内存描述符地址）；before-mmu/after-mmu；memory-peim-return；before-platform/after-platform；entry-arg-filled；before-constructors/after-constructors；guid-query。资源/追加循环有效时不刷屏，里程碑有效输出ok；失败输出bad、last-good、PHIT，最多4个处于声明终点以内的原始8字节字，然后CpuDeadLoop。reason1格式/跨度、2坏长度、3跨终点、4不一致结束、5条数上限、6可信PHIT关系失败。

所有阶段扫描只读HOB，写入的是诊断自身静态状态。last-good保存检查时刻的阶段/context/end/count和头部FNV32；hash只是辅助，不是全HOB或无碰撞证明，也不检查GUID payload的语义。日志和额外读取可能改变时序/缓存状态；若新包不复现，不代表问题修复。观测点只能缩小异常首次可见区间，不自动等于写坏指令或根因。未改变缓存维护、TTBR、MMIO、Heap或HOB内容；原0014保护保留。

## 离线证据

47输入、10补丁、14后哈希整链静态校验通过。tests/test_hob_stage_audit.py从精确patch提取实际新增检查器和运行包装，在WSL clang ASan/UBSan及mmap保护页下执行：有效链、336种截断、+0x118零长、短/奇数/巨大长度、越终点、提前结束、终点损坏、4096条上限、坏end/list/bottom、arena溢出、失败不更新last-good均通过。报告reports/hob-stage-audit/host-tests.json。主机适配仅供诊断自身内存边界验证，不是硬件驱动模拟或实机运行。旧FD伪装新profile、空录像两项门测试通过。

同SoC参照沿用已核验UniXNU/uefi-sheng@329b473df1e53a3bfa64b2b39b79670c4c02279b，Sec.c SHA960823c3/BSD-2-Clause-Patent及PrePi依赖；其PlatformPeim→EntryArg HOB→constructors顺序与nuwa一致，仅为顺序参照，不提供坏HOB修复依据，不引入其板地址。证据reports/sec-handoff/same-soc-order.json。

完整固件CI40000310916、实际SEC标记/阶段代码/失败路径、41行内存表及容器复验已通过。新包不含XNU/ADT；只做离线诊断及构建，实际试验前另通知用户并确认该轮录像/恢复门。

主机验证补充：最初PIE+ASan二进制偶发exit139；verbose输出止于ASan信号处理器安装、尚未到Init done，未产生检查器报告。改为仅主机测试的-fno-pie/-no-pie，保留同一候选C、保护页及ASan/UBSan，单测和同一二进制连续20次均exit0。该变更不影响固件编译，不声称已解决WSL/ASan初始化根因；证据host-startup-review.json。

## 新包离线验收

CI40000310916/source a6e9a4c成功，profile固定6176a82+0018。实际SEC CreateHob有2次checkpoint调用、GetFirstGuidHob有1次，checkpoint错误路径含CpuDeadLoop；直接调用未出现allocator/cache维护或间接分支（不代表完整传递调用图）。所有stage标记通过，41行2952B内存表7694de6c与基线相同。

包2273bdecab25410dc290df84b031871f1f18d8dd2dbe57eea89dffd741813d61/3153920B，FD74ad39a67305944849b09935b80e457ac46e3016fa74e3ea22a93a9636d34051/3MiB；严格重建逐字节一致，缺preflight实际包在任何设备子进程前拒绝。证据reports/hob-stage-audit/40000310916/。新包尚未实测，需要通知用户并取得本轮录像确认后刷新preflight/通知/临时启动/恢复闭环；不从离线验证宣称HOB根因已定位。
