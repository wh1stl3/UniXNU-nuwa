# HOB缓存交接单变量候选

基线2273bdec实测before-mmu56条及函数内末次create84条有效，返回后off718坏头。依照用户要求，以固定6176a82/Mu cfb93724的hob-stage-audit为基线，只追加0019：页表/HOB分配全部完成后、MAIR/TTBR安装之前调用一次HOB缓存交接。原ArmConfigureMmu ABI及默认无回调路径保留；SEC MemoryPeim显式登记私有一次性回调，其他实例NULL，回调调用前清空、失败沿原错误路径返回。没有GUID/HOB新增，没有修改Heap、板值或缓存属性。

NuwaHobCacheHandoff确认EL1/EL2、适当级别SCTLR.M/C均0和已初始化可信arena；不符合则记录并CpuDeadLoop。调用原始有界HOB检查，取得最新成功终点（覆盖建表过程新增的HOB），按ArmDataCacheLineLength将[可信base,lastEnd+8)向上覆盖完整缓存行；要求base对齐、无溢出、范围完全在已拥有arena内。cache line限制16..4096且为2的幂，异常拒绝。依据上轮FF0使用长度和64B行的例子，维护跨度为1000；这是条件计算示例，不写死板地址或未来长度。

只执行DSB→InvalidateDataCacheRange→DSB→ISB，后续不再HOB写入/分配/打印，返回原MMU安装流程。固定ArmCacheMaintenanceLib的InvalidateDataCacheRange为按行IVAC加结尾DSB，没有边界clean；因此使用完整对齐行，不调用Clean/WriteBack/全缓存或全Heap操作。具体源文件/ArmLib实现哈希纳入profile。CacheMaintenance/ArmLib仅加入候选PrePiHobLib INF依赖，没有新库构造函数。原0018扫描和坏条目保护块源码逐字节保留；移除新增私有回调声明/钩子后，MMU源文本与基线完全相同（semantic-scope.json）。新增检查/日志会改变代码布局和时序，这是修复候选，不是严格同二进制A/B或根因确认。

51输入、11补丁、15后哈希整链通过。精确新增范围函数、HOB保护、交接函数和一次性钩子在主机ASan/UBSan测试：8192种末端对齐、FF0→1000、超范围/溢出/非2幂/部分行越界、错误EL/M/C/未初始化/坏HOB时零维护、显式DSB/IVAC/DSB/ISB调用顺序、HOB全内存字节不变、默认无回调/一次性消费/失败不安装均通过。主机用记录适配器代替真实寄存器和cache操作，不能证明目标缓存效果。旧包冒充及空录像门另测。

公开机制依据及原始实测见2026-10-24-hob-stage-audit-trial.md：Linux v6.12 head.S与ARM64维护者说明支持非缓存写入后失效旧缓存的方向；没有直接复制Linux代码。同SoC顺序参照仍为uefi-sheng@329b473d（same-soc-order.json），不搬其地址或扩展本次改动。

完整CI、实际回调位置/IVAC/屏障/保护和41行内存表、严格容器复验待验。需要完整验收后通知用户确认新包录像，再刷新恢复门；本轮仅离线，无设备动作，不声明故障已修复。
