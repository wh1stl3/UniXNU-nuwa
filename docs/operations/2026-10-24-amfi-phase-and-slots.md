# AMFI 初始化阶段和回调槽位核查

时间：2026-10-24 15:16 +08:00。本轮只读离线审计，无手机、USB介质或固件行为修改。

## 结论修正

此前把 donor `__DATA_CONST` 的 Mach-O `initprot=1` 视作初始化写入的主要风险，依据不充分。Apple XNU 8796.141.3 的平台路径先将 coalesced `__PLK_DATA_CONST` 映射为 RWNX，之后才在 `arm_vm_prot_finalize` 收紧为 RNX；不能直接把文件中的保护标志等同于初始化时的实际页表权限。

本次按成功内核 CI40015845083/build.json 的真实64项补丁顺序和哈希，在内存中重建六个相关源码文件。原始源从固定 git 对象1b191cb读取，不修改旧资料库。12项源码顺序检查通过：`mac_policy_initmach` 先加载安全组件，再置 `mac_late=1`；启动线程之后才调用 `machine_lockdown`，其调用平台保护终结函数。NativePrelink可选入口在正常构造和成功的kmod start之后，仍拒绝mac_late阶段。split kext的映射保护交由平台路径处理。

证据：[init-phase-final.json](../../reports/native-prelink-merged/init-phase-final.json)、[审计脚本](../../scripts/audit-prelink-init-phase.py)。它是固定补丁重建后的源码时序证据，不是完整预处理/CFG证明，也不是运行时页表读回；未把“可写期风险下调”升级为实机通过。

## 原始注册块与实际新内核槽位

对实际bf14内核dSYM的`mac_policy_ops`提取335个成员，大小2680B（0xa78），每项间距8B。原donor表起点0xfffffff006cb6e28，直到下一策略配置0xfffffff006cb78a0的间距正好也是0xa78；这支持几何对应，但间距本身不能单独证明donor结构类型。

原AMFI指令区间[0xfffffff005703e4c,0xfffffff005703f5c)为直线常量写入块。逐条解码ADRP/ADD/STR/STP，没有跳过控制流或替换实际代码；23项指针写入均对应新内核实际DWARF槽位，所有目标都在原AMFI可执行段内。该表的原始335项均为零，注册块负责填入回调。对应名称包括`mpo_vnode_check_signature`、`mpo_file_check_library_validation`、`mpo_vnode_check_exec`，未将表格对应当作这些回调已经执行。

证据：[amfi-ops-slots.json](../../reports/native-prelink-merged/amfi-ops-slots.json)、[审计脚本](../../scripts/audit-amfi-ops-slots.py)。报告保留实际dSYM、donor、新内核和原始指令块SHA。类型名/槽位来自native，不能反向证明donor每个回调的意图、参数结构或C++ABI；完整ABI与构造/start间接路径仍待审。

## 当前故障排序

1. **最近“菜单后无OS/充电”的直接原因仍是配置探针没有可启动OS负载且执行退出动作，置信高。** 原图的菜单标题、配置路径和timeout/action对应；本轮没有新实机证据推翻它。不能把尚未执行过的AMFI归因为这次充电。
2. **对于下一阶段真正的内核候选，donor初始化完整路径及回调/对象ABI比单纯DATA_CONST文件保护标志更值得优先追查。** 注册函数、局部策略结构及23项槽位已经有较强静态依据；未证明构造/start已经调用注册或必须补调用，不能先加入口再观察。
3. **DATA_CONST时序仍保留为运行时核查项，但下调优先级。** 源码顺序有直接反证，最小证伪是在合格负载执行时采集调用前的实际映射/阶段；当前不修改页面权限、不移除保护。

最小离线下一步：追踪三个原构造函数和kmod start的全局间接槽，确定是否通向注册及once-guard，然后逐项核对关键回调参数。初始化映射仍为空，eb66542c仍loadable=false，不作实机OS包。

## 无OTG条件与构建状态

用户本轮确认暂时没有OTG转接线/U盘。大文件读取探针及介质镜像尚未构建，OTG不能作为已具备的实测路径；不要求先购买硬件，不自动写内部UFS/分区，不把已验证4MiB配置卷当成约58MiB负载运输证明。继续离线准备不依赖介质的读取核心，并审查现有临时启动链的负载交接；实际来源和内存边界明确后才接入固件。

本轮没有固件/内核行为变化，因此不重复构建相同二进制。已成功的固件2d606985和内核bf14e530、分析eb66542c保持；Heap/HOB保护、板值、身份和_verified不改。没有新包可实测，也不复用旧录像许可。

## 公开原始资料

- [Apple arm_vm_init.c，8796.141.3](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/osfmk/arm64/arm_vm_init.c)：初始coalesced映射及最终保护。
- [Apple OSKext.cpp，同版本](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/libkern/c%2B%2B/OSKext.cpp)：正常构造、start和split kext保护路径；本地补丁后顺序另由报告固定。
- [Apple startup.c，同版本](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/osfmk/kern/startup.c)与[mac_base.c](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/security/mac_base.c)：MAC早期加载与后续lockdown顺序。

复现：bundled Python -B scripts/audit-prelink-init-phase.py --output reports/<新文件>.json；audit-amfi-ops-slots.py同参数。输出须为新路径，拒绝覆盖历史报告。后者需WSL Ubuntu-22.04 llvm-dwarfdump及现有只读Capstone工具环境。
