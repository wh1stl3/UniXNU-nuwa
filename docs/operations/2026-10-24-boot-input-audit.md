# UEFI 启动输入快照诊断

独立 boot-input-audit profile 固定固件 6176a822e66b846620b5bcd2739a0666814ee663，在已实测的内嵌配置卷探针上增加 NuwaBootAuditDxe。正常固件 DSC/FDF 不改；0017 只修改此候选的模块选择。

ReadyToBoot 一次性回调读取 CurrentEL、MPIDR_EL1、CNTFRQ_EL0 及 GetMemoryMap，打印所有合并后的 ConventionalMemory 范围、最大连续范围和最大 WB 范围，停留10秒方便录像。仅申请并释放快照缓冲区，不分配或预留 XNU 窗口，不调用 ExitBootServices，不修改 MMIO/板值。快照包含自身缓冲区分配；不能把最大范围当成后续分配成功或所有权证据。

精确共享 C 汇总函数通过宿主 UBSan 测试：无序/扩展描述符、相邻同属性合并、间隙/属性分隔、重叠/零页/溢出/格式/数量拒绝。静态完整链验证为46输入、9补丁、12后哈希。完整CI39995937843及实际模块检查已通过，实机未执行。内嵌4MiB FAT仍只包含已实测的配置探针，没有XNU或ADT。

完整CI、实际PE/DEPEX/标记、SEC表及严格打包复验已完成。用户要求暂停；恢复主线后仍须具体新包录像确认、nuwa身份和恢复门齐备才允许临时启动。采集原图后再讨论窗口及Apple ADT，不使用Android总DRAM代替可分配范围。

## 完整产物验收与暂停

CI39995937843成功，构建源84c88f8，实际固件源6176a82。新包a2dc8195b4368da37276a4618dca90fd556f1d5de72fd58faff0b600936ba65b/3153920B，FD bfb02a6334f201778467ecc1f1a9042396dc1a3dcd2014c8c4118b88664f106b/3MiB。实际PE/DEPEX/字符串、精确内嵌FAT资源、容器逐字节重建均通过；41行2952B SEC内存表SHA7694de6c一致。缺preflight的实际新包在任何设备子进程前拒绝，调用0；旧包冒充新profile/空录像两项回归通过。报告reports/boot-input-audit/39995937843/。

用户回复“先停下 落实文档”，不是录像许可。本轮没有设备动作；完成文档提交后停止主线。当前无新包实机快照，最近Android状态仍来自embedded-probe-trial/2026-10-24/postcondition.json，北京时间00:56:45，并非现在重新查询。恢复主线及该轮新鲜录像均须得到用户确认。续接命令和恢复步骤见主线交接。
