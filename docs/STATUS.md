# STATUS

更新：2026-10-26。本轮完成PROBE28激活读取补充审计，并按最新要求转为下一阶段离线分析/公开资料研究；此后不扩展实现。所有设备操作继续暂停，未运行adb/fastboot、未生成新鲜预检、未启动设备、未构建新候选或重封包。

新增：11场景/12对激活路径快照比较通过，覆盖通用/SIMD寄存器、SP/NZCV/FP控制、线程标识与相关原生内存；内存中x8/x9泄漏负对照被拒绝。默认11项输出与原报告逐字节一致。原PROBE28包报告及23份绑定报告原字节保留；原24项检查和1092比较没有机械重跑。补充证据reports/kernel-entry-probe/2026-10-26-v36-active-audit/audit-manifest-final.json，详见[激活审计](operations/2026-10-26-read-active-transparency-and-waits.md)。它是有API替身的Unicorn/静态检查，未执行真实MAC/APFS/解压或实机。

当前最早未验证点仍为PROBE27的250亮/251暗，264黄/265绿及A033 FFFFFFF005F48EF8只证类型4表项已有。PROBE28尚无实机读数。首要调查文件系统读取内部，次要MAC处理；静态已定位数据锁/UBC/验证/UPL/fetch以及有条件转换等待，但没有锁owner、wait_event、APFS实际v_op或IRQ读数，不能指定唯一根因。

新增参数盲点：真实250调用ioflg=8，len依赖运行时PAGE_SHIFT_CONST；普通夹具为4KiB/flags0。磁盘shift初值0不是运行时值。下一最小离线项是核对固定DarwinBoot的memSize→arm_init→shift→header len契约；目前仅列计划，未扩展参数测试或改内核。之后仍按最早未返回边界再选择内部点，不能跳到dyld或用户态。详见[下一阶段与公开来源](operations/2026-10-26-next-stage-public-research.md)。

联网已核实Apple xnu-8796.141.3/1b191cb固定版本；未找到直接匹配nuwa停点的公开修复。官网nuwa记录较旧，sheng示例为iPadOS17，与本机iOS16/8796不可混用。可迁移机制、同SoC来源及访问限制均已记录，没有采用上游新实现。

权威包reports/xnu-first-entry/entry-probe-28.json；镜像7a04626e631196be116d270fa94e59b957ab537ecc1353501ff8f7b54fec7e0f（204484608B），内核54179a8775ee4d723bb0493a66679932f986d39231e9ef371d856afb07b3ea07（58462208B），ADT458232d6270643a88b465814535eead13eb88771c869e3cf6edfbe1741aa12f0。原JSON LF/Git blob绑定、内核独立重建、新旧包回读有效；首包a8cb为历史，不使用。APFS d180c38d…、192MiB、-v rd=md0、FD/shim、板内存/TCR、身份与_verified保持，loadable/runtime_qualified=false。

R-014仍open。本轮明确纯离线暂停设备；旧交接中的设备命令不是本轮执行许可。实际当前设备状态未刷新，最后确认仍为v35/postcondition于2026-10-26T00:19:12.450574+08:00的Android1/A槽/三SHA闭环，不能作为新预检。恢复用户态239守卫保持；固定restore介质有RunAtLoad恢复服务，完整iOS启动与守卫释放仍需单独审阅。

基线079488f，本轮提交见本文件所属Git提交。未push、新CI、原始媒体上传或其他项目改动；历史28项未跟踪保留。唯一续接入口：[10月26日主线交接](operations/2026-10-26-mainline-handoff.md)。
