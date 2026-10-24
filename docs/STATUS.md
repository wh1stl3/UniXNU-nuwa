# STATUS

> 已用合并后bf14新内核生成eb66542c分析预链接并完成65348绑定读回/24项解析；AMFI入口已追到真实策略注册调用，但初始化可写期与完整ABI未闭环，loadable=false。

用户要求的全部已审查上游源码更新已合并并完成默认配置构建验证。基座e553e46/21模块已推送；固件CI40014018074和Darwin22/iOS16源内核CI40015845083均成功。本轮无手机操作，新固件和内核尚未实测。

源：wh1stl3/UniXNU@e553e467ebfe7642e9f483d3977a57066c6d1aef，真实双亲merge上游1a01c2af，54冲突落实，合并树精确为完整上游+3个nuwa工作流。设备接入提交5abdde1，内核前置依赖修复6070627。全部21模块初始化并固定；两旧资料库只读。固件默认upstream-merged，内核merged与NativePrelink工具入口已切新源。[完整落实记录](operations/2026-10-24-upstream-integration.md)。

固件：CI40014018074/source5abdde1，FD SHA256 2d606985ad768dcfaab66c2b28073c0a4c2820126b42b23286623fdc450e848f/3145728B，697项产物静态检查通过。SEC SHA7192fd3f与已实测26ef8efd逐字节一致，Heap/内存表/HOB保护及DSB→IVAC→DSB→ISB保留；CreateHob两次/查询一次检查和停机分支复核通过。

内核：首轮40014023191漏前置zzw授权补丁，最终链接失败；已补完整真实实现。第二轮40015845083/source6070627成功，64项有序补丁、平台归档/复链通过；独立下载复核内核bf14e5305a9f764c6852c2d3a69e81edc9c6199bc870c7b08160d55610616dea/20188216B，Darwin22.6.0、iOS16.0、零未定义符号、ArmCpu/ArmDTPlatform五个目标导出及实际归档哈希一致。不是合格预链接OS负载。

测试：新版DarwinBoot解析24项、packed C/Python稀疏格式与逻辑1TiB边界/13拒绝、SMMU页表/stream夹具、授权助手9项、预链接常量池4项通过。GPU VM真实实现保留目标DSB，AArch64交叉链接及用户态QEMU软件夹具通过；这不是nuwa GPU/cache/SMMU或XNU ABI实机证明。代码全量纳入不等于开启全部硬件功能；原source-only编译开关保留，CS-hash/owner-root/GPU等可选分支尚未全功能编译或运行验收。reports/upstream-integration/2026-10-24/integration-result.json记完整边界。

最近实机仍26ef8efd：原图确认维护后after-mmu ok/count84、ReadyToBoot和配置菜单，支持缓存交接遗漏为早期HOB首因；唯一性/重复性待验。末尾无OS/充电符合配置探针timeout60/action=exit。原Android恢复证据北京时间02:55:45（postcondition UTC2026-10-23T18:55:45.904383），nuwa/kalama、槽_a、完成1及三分区SHA一致；不冒充本轮新查询。[实测记录](operations/2026-10-24-hob-cache-handoff-trial.md)。

新分析eb66542cc9b6c34f369c07229900408ab67288152f561be63fa6061efce9ffca/58335232B已生成，非旧产物改标签；30段donor和native代码保持。历史AMFI地址是已slide结果，已逆解到原始候选并定位_mac_policy_register，dSYM局部策略结构80B/偏移一致；DATA_CONST写入/调用阶段仍待核查，不采用初始化映射。[本轮记录](operations/2026-10-24-merged-native-prelink.md)。

下一步追踪初始化可写期和完整ABI，准备独立大文件读取SHA探针、真实nuwa ADT及实际OS窗口分配；旧5a128fb2/7774分析输入仅历史、loadable=false。9GiB为UEFI快照，不是已分配窗口。当前不需按键/录像；任何新实机启动另确认当轮日志/恢复并即时通知。Heap/保护/ST FTS路线、board内存/身份/_verified均未改，无flash/erase/改槽位。[交接](operations/2026-10-23-mainline-handoff.md)。
