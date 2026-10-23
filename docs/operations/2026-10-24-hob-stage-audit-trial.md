# 2273bdec实测：首次坏链在MMU函数末段后可见

## 本轮执行与恢复

用户确认本轮录像，preflight实际确认nuwa/kalama、Android完成1、slot_a及三分区，已即时通知后单次临时boot2273bdec。fastboot ACK0及120秒USB观察完成。阶段事实来自原始照片after-mmu-screen.jpg，SHA256 3b4b9b3efe41288cae06678320cddd860aa1de26d3262b2df4102106a0fe135d，不是USB推断。未flash/erase/改槽位。

recovery实际送回原Android，postcondition.at=2026-10-23T18:20:52.568611+00:00确认nuwa/kalama、完成1、三分区SHA与本轮preflight一致，恢复闭环。无需再按键。证据reports/hob-stage-audit-trial/2026-10-24/。

## 这次实际定位了什么

- hob-constructor检查成功。
- before-mmu检查成功，count56、endBAB00AA8。
- ArmConfigureMmu内最后一次create-after仍成功，context20030（type2、len30）、count84、endBAB00FE8。
- 函数返回的after-mmu检查失败，status context0（函数返回Success），reason2，off718、type0、len0。
- PHIT endBAB00FE8、bottomBAB00FF0、topC7CA4000；原始qword在718为0、720为A7600000、728为1000、730为4。

新增28条、end增加0x540，恰等于28×0x30，符合页表分配新增内存分配HOB的上下文。此前完整扫描仍可遍历这些条目；首次可见异常已收窄为最后一次CreateHob检查之后、ArmConfigureMmu返回的检查之前，涉及表填充收尾、MAIR/TTBR及MMU/cache切换。这里没有证明某条具体写指令、当前EL/SCTLR状态或物理页表内容，不能把after-mmu直接当成硬件根因。

## 优先级明确的工作判断

**首嫌是SEC的缓存/地址转换交接缺陷，最可能是HOB在非缓存访问下重建后，启用MMU/D-cache读回旧缓存行。这个方向应优先于继续怀疑HOB创建算法或尚未运行的DXE模块。** 这是高优先级工程判断，尚未达到已确认根因。

依据：创建期间完整头链有效，切换后立即读坏；故障历次地址/出现与否变化；上轮成功/失败SEC代码相同（仅时间串差）；本轮尚未到PlatformPeim/库构造/DXE。固定Sec.c:169关闭数据缓存，178-179只失效Stack和FD，没有覆盖HOB Heap；固定ArmMmuLib在建表后切MAIR/TTBR，再条件启用D-cache/MMU。实际新包ArmDisableDataCache/ArmEnableDataCache反汇编都仅改控制位并执行屏障，没有DC维护指令，排除了“函数名虽然Disable但内部已自动清空所有缓存”的解释。报告cache-transition-audit.json及其源码锚点。

公开资料直接支持这一机制：Linux ARM64维护者Catalin Marinas解释，MMU/缓存关闭时写入的数据，在之后启用时仍可能被旧缓存条目遮蔽。[维护者原文](https://lists.infradead.org/pipermail/linux-arm/2020-August/000605.html)。Linux v6.12启动代码在保存boot参数及非缓存建表后采用屏障与PoC失效处理。[固定版本head.S](https://github.com/torvalds/linux/blob/v6.12/arch/arm64/kernel/head.S)。这些资料支持机制，不证明nuwa此处一定走了该路径。

第二嫌是TTBR/TCR/MAIR或HOB VA→PA属性/映射不一致，可能与缓存问题耦合；若HOB维护后仍读错，优先实际走表并核对物理地址/属性。第三层再查页表分配与写入覆盖、异步DMA/其他执行者。当前日志不能彻底排除这些，但先随机换Heap、修改HOB长度或归因后续DXE缺乏证据。

## 下一轮的具体证伪方案

准备单变量缓存交接候选：先记录实际EL及适当级别SCTLR/TTBR/TCR/MAIR，确认缓存/MMU状态和HOB所有权；在最后一次建表完成、缓存重新启用之前，对已拥有且按缓存行覆盖的HOB范围审查失效与屏障顺序，再比较前后头链与原始字节。保持Heap/板内存/HOB扫描和失败保护不变。只有该变量改变且可重复消除故障，才提高根因置信度；若失败则转向映射/页表校验。

不把Clean、Invalidate混为一谈：[Arm说明](https://community.arm.com/forums/f/architectures-and-processors-forum/3731/clean-and-invalidate-cache-memory/10061)指出clean会写回脏行，invalidate消除缓存命中。对可能保存旧内容的行盲目clean可能覆盖刚重建的数据；部分行边界及当前缓存状态必须先核对。此次只记录方案，尚未实施新的cache维护、生成修复包或进行第二次启动。新包仍需完整离线验收和新一轮录像门。

## 后续状态（不改写上述基线实测）

后续已按0019实现HOB范围缓存交接候选26ef8efd，完成离线验收和一次临时启动；用户报告进入UniXNU菜单，Android恢复完成1/三分区SHA不变。详见[候选说明](2026-10-24-hob-cache-handoff.md)及[实测记录](2026-10-24-hob-cache-handoff-trial.md)。实际候选守卫读取EL/SCTLR，未增加TTBR/TCR/MAIR运行转储，不得将上文计划写成寄存器均已采集。缓存阶段原图及重复性待补，未确认根因。
