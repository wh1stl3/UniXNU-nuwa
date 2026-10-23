# STATUS

> a2dc8195已单次实测，在SEC Mmu构造的HOB长度检查停住，未到新诊断模块。原Android已恢复，完成1及三分区SHA不变；根因仍待定位。

CI39995937843/固件6176a82/包a2dc8195/3153920B，本轮新鲜录像、包复验、身份/恢复门及启动前通知已完成。用户原图最后`invalid ptr=BAB00118 type=4 len=0 target=4`，0014检查对此调用CpuDeadLoop。120秒USB观察完成，不能当成ReadyToBoot阶段证据。EL/MPIDR/CNTFRQ/连续内存范围均未取得，不移除检查或跳过异常条目。

reports/boot-input-audit-trial/2026-10-24/postcondition.json于2026-10-23T17:48:19.683937+00:00实际确认nuwa/kalama、Android完成1、slot_a、三分区SHA与本轮preflight一致；本轮恢复闭环，无flash/erase/改槽。

实际SEC对比旧成功包87b14624：所有指令/数据/内存表一致，全SEC仅构建时间字符串4字节变化；掩蔽8字节时间后完全相等。新DXE模块尚未运行，不能把HOB异常直接归因其逻辑；创建、覆盖、缓存可见性等尚未区分。证据sec-differential.json及operations/2026-10-24-boot-input-audit-trial.md。

下一步离线准备创建/填充、MMU前后、构造前后有边界的HOB检查，定位首次异常阶段；保留失败保护，不同时改缓存/Heap。新包需完整构建复验及新的录像门，当前不重复启动。

87b14624的4MiB配置卷发现实机通过。当前77742999内核分析预链接5a128fb2静态绑定/主机解析通过，但早期安全initializer/完整ABI/目标ADT/窗口/大负载运输仍缺，loadable=false。board/bringup内存值与_verified未改，未执行XNU。
