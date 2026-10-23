# HOB缓存交接单变量候选

基线2273bdec实测before-mmu56条及函数内末次create84条有效，返回后off718坏头。依照用户要求，以固定6176a82/Mu cfb93724的hob-stage-audit为基线，只追加0019：页表/HOB分配全部完成后、MAIR/TTBR安装之前调用一次HOB缓存交接。原ArmConfigureMmu ABI及默认无回调路径保留；SEC MemoryPeim显式登记私有一次性回调，其他实例NULL，回调调用前清空、失败沿原错误路径返回。没有GUID/HOB新增，没有修改Heap、板值或缓存属性。

NuwaHobCacheHandoff确认EL1/EL2、适当级别SCTLR.M/C均0和已初始化可信arena；不符合则记录并CpuDeadLoop。调用原始有界HOB检查，取得最新成功终点（覆盖建表过程新增的HOB），按ArmDataCacheLineLength将[可信base,lastEnd+8)向上覆盖完整缓存行；要求base对齐、无溢出、范围完全在已拥有arena内。cache line限制16..4096且为2的幂，异常拒绝。依据上轮FF0使用长度和64B行的例子，维护跨度为1000；这是条件计算示例，不写死板地址或未来长度。

只执行DSB→InvalidateDataCacheRange→DSB→ISB，后续不再HOB写入/分配/打印，返回原MMU安装流程。固定ArmCacheMaintenanceLib的InvalidateDataCacheRange为按行IVAC加结尾DSB，没有边界clean；因此使用完整对齐行，不调用Clean/WriteBack/全缓存或全Heap操作。具体源文件/ArmLib实现哈希纳入profile。CacheMaintenance/ArmLib仅加入候选PrePiHobLib INF依赖，没有新库构造函数。原0018扫描和坏条目保护块源码逐字节保留；移除新增私有回调声明/钩子后，MMU源文本与基线完全相同（semantic-scope.json）。新增检查/日志会改变代码布局和时序，这是修复候选，不是严格同二进制A/B或根因确认。

51输入、11补丁、15后哈希整链通过。精确新增范围函数、HOB保护、交接函数和一次性钩子在主机ASan/UBSan测试：8192种末端对齐、FF0→1000、超范围/溢出/非2幂/部分行越界、错误EL/M/C/未初始化/坏HOB时零维护、显式DSB/IVAC/DSB/ISB调用顺序、HOB全内存字节不变、默认无回调/一次性消费/失败不安装均通过。主机用记录适配器代替真实寄存器和cache操作，不能证明目标缓存效果。旧包冒充及空录像门另测。

公开机制依据及原始实测见2026-10-24-hob-stage-audit-trial.md：Linux v6.12 head.S与ARM64维护者说明支持非缓存写入后失效旧缓存的方向；没有直接复制Linux代码。同SoC顺序参照仍为uefi-sheng@329b473d（same-soc-order.json），不搬其地址或扩展本次改动。

完整CI40005057158、实际IVAC/屏障/保护和41行内存表、严格容器复验已通过；回调插入位置由完整固定源码链验证。以上为离线验收阶段。后续已完成本轮临时实测及Android恢复，见下方更新和实测记录；根因尚未闭环。

## 完整固件与新包验收

CI40005057158/source bdcf4a2成功。下载实际SEC中NuwaHobCacheHandoff的显式调用序列为DSB→InvalidateDataCacheRange→DSB→ISB；范围函数将行操作指针传给CacheRangeOperation，实际地址解析为ArmInvalidateDataCacheEntryByMVA，内含DC IVAC。实际DSB SY/ISB与失败CpuDeadLoop通过。原CreateHob前后两次/查询入口一次checkpoint及失败分支仍存在；41行2952B SEC表7694de6c相同。证据cache-code-audit.json、sec-call-audit.json、memory-map-identical.json。

新包26ef8efdc034f726df23f7bb2998d9e980e52e706e914ba9a415ca088dba2051/3153920B；FD0e90473e1526d29cfda8f0c285f3b3e7db4ee0862e81b3f138dac604860ba225/3MiB，严格容器逐字节重建通过。实际包缺preflight在任何设备子进程前拒绝，调用0；报告reports/hob-cache-handoff/40005057158/。该离线验收之后已取得本轮新鲜录像确认并实测，不能再将候选标作从未启动。若拒绝M/C状态，则优先核查实际入口，不能删守卫强行继续。

## 实测状态更新（2026-10-24）

候选26ef8efd已单次临时启动并完成至少120秒USB观察，用户直接报告“进入了unixnu菜单”。恢复和postcondition确认Android完成1、槽_a与三分区SHA不变。原始缓存阶段画面尚未收到，EL/SCTLR/维护范围、after-mmu链完整性及重复性未验证。菜单观察增强缓存交接假设，但不能排除布局/时序因素，也不代表XNU或iOS执行。详细证据见[实测记录](2026-10-24-hob-cache-handoff-trial.md)；当前交接以[主线交接](2026-10-23-mainline-handoff.md)为准。
