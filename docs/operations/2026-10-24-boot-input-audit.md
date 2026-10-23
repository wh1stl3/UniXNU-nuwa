# UEFI 启动输入快照诊断

独立 boot-input-audit profile 固定固件 6176a822e66b846620b5bcd2739a0666814ee663，在已实测的内嵌配置卷探针上增加 NuwaBootAuditDxe。正常固件 DSC/FDF 不改；0017 只修改此候选的模块选择。

ReadyToBoot 一次性回调读取 CurrentEL、MPIDR_EL1、CNTFRQ_EL0 及 GetMemoryMap，打印所有合并后的 ConventionalMemory 范围、最大连续范围和最大 WB 范围，停留10秒方便录像。仅申请并释放快照缓冲区，不分配或预留 XNU 窗口，不调用 ExitBootServices，不修改 MMIO/板值。快照包含自身缓冲区分配；不能把最大范围当成后续分配成功或所有权证据。

精确共享 C 汇总函数通过宿主 UBSan 测试：无序/扩展描述符、相邻同属性合并、间隙/属性分隔、重叠/零页/溢出/格式/数量拒绝。静态完整链验证为46输入、9补丁、12后哈希。完整CI/实际模块检查尚待，实机未执行。内嵌4MiB FAT仍只包含已实测的配置探针，没有XNU或ADT。

下一步：完整CI检查实际PE/DEPEX/标记及SEC表不变，严格打包复验；具体新包录像确认、nuwa身份和恢复门齐备后才允许临时启动。采集原图后再讨论窗口及Apple ADT，不使用Android总DRAM代替可分配范围。
