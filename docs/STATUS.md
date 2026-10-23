# STATUS

> 2273bdec实机已把首次坏链可见区间定位至ArmConfigureMmu末段/返回之间；Android恢复和三分区核验闭环。首要工作判断是HOB缓存/地址转换交接缺陷，尚未确认具体机制。

本轮原图before-mmu有效：56条/endBAB00AA8；MMU函数中最后一次create-after有效：84条/endBAB00FE8/context20030。返回Success后的after-mmu首次读坏：reason2/off718/type0/len0。未到平台HOB、库构造或DXE；未执行XNU。照片/转录/源码及实际缓存控制反汇编在reports/hob-stage-audit-trial/2026-10-24/。

本轮postcondition于2026-10-23T18:20:52.568611+00:00实际确认nuwa/kalama、Android完成1、slot_a、三分区SHA与preflight一致。原Android恢复闭环，无flash/erase/改槽位。

源码及实际指令显示SEC关闭D-cache后只失效Stack/FD，HOB Heap未覆盖；MMU库建表后切MAIR/TTBR并条件重新启用D-cache/MMU。Linux ARM64公开启动实现/维护者说明支持关闭缓存期间写数据、开启后旧cache遮蔽的机制。因此首嫌缓存交接，次嫌VA→PA/属性/页表问题；不是已确认根因，实际EL/SCTLR/TTBR未取得。

下一步离线准备单变量的HOB缓存交接候选：核对实际寄存器路径、HOB所有权和cache-line覆盖及屏障/失效顺序，保持Heap/板值及保护不变；若不奏效，走表核验映射。尚无修复包，不重复启动2273bdec。详见operations/2026-10-24-hob-stage-audit-trial.md。board/bringup内存值及_verified未改；分析预链接5a128fb2仍loadable=false。
