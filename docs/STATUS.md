# STATUS

> USB内存ramdisk诊断包8177783e已构建并严格复验：v3与v4离线对照仅头部两字节不同。7新测试/10历史门控及16项真实ABL门字节QEMU夹具通过，待本包新鲜录像确认后实测，无需OTG。

全部已审查上游更新已合并并完成默认配置构建验证。e553e46/21模块已推送；固件CI40014018074和Darwin22/iOS16源内核CI40015845083成功。本轮复用固定FD生成新v3运输容器，不重复编译同一固件；无手机或USB介质操作，新固件和内核尚未实测。

源：wh1stl3/UniXNU@e553e467ebfe7642e9f483d3977a57066c6d1aef，真实双亲merge上游1a01c2af，54冲突落实，合并树精确为完整上游+3个nuwa工作流。设备接入提交5abdde1，内核前置依赖修复6070627。全部21模块初始化并固定；两旧资料库只读。固件默认upstream-merged，内核merged与NativePrelink工具入口已切新源。[完整落实记录](operations/2026-10-24-upstream-integration.md)。

固件：CI40014018074/source5abdde1，FD SHA256 2d606985ad768dcfaab66c2b28073c0a4c2820126b42b23286623fdc450e848f/3145728B，697项产物静态检查通过。SEC SHA7192fd3f与已实测26ef8efd逐字节一致，Heap/内存表/HOB保护及DSB→IVAC→DSB→ISB保留；CreateHob两次/查询一次检查和停机分支复核通过。

内核：首轮40014023191漏前置zzw授权补丁，最终链接失败；已补完整真实实现。第二轮40015845083/source6070627成功，64项有序补丁、平台归档/复链通过；独立下载复核内核bf14e5305a9f764c6852c2d3a69e81edc9c6199bc870c7b08160d55610616dea/20188216B，Darwin22.6.0、iOS16.0、零未定义符号、ArmCpu/ArmDTPlatform五个目标导出及实际归档哈希一致。不是合格预链接OS负载。

测试：新版DarwinBoot解析24项、packed C/Python稀疏格式与逻辑1TiB边界/13拒绝、SMMU页表/stream夹具、授权助手9项、预链接常量池4项通过。GPU VM真实实现保留目标DSB，AArch64交叉链接及用户态QEMU软件夹具通过；这不是nuwa GPU/cache/SMMU或XNU ABI实机证明。代码全量纳入不等于开启全部硬件功能；原source-only编译开关保留，CS-hash/owner-root/GPU等可选分支尚未全功能编译或运行验收。reports/upstream-integration/2026-10-24/integration-result.json记完整边界。

最近实机仍26ef8efd：原图确认维护后after-mmu ok/count84、ReadyToBoot和配置菜单，支持缓存交接遗漏为早期HOB首因；唯一性/重复性待验。末尾无OS/充电符合配置探针timeout60/action=exit。原Android恢复证据北京时间02:55:45（postcondition UTC2026-10-23T18:55:45.904383），nuwa/kalama、槽_a、完成1及三分区SHA一致；不冒充本轮新查询。[实测记录](operations/2026-10-24-hob-cache-handoff-trial.md)。

新分析eb66542cc9b6c34f369c07229900408ab67288152f561be63fa6061efce9ffca/58335232B，65348绑定读回、30段donor/native代码不变、24解析通过。历史AMFI地址是已slide结果，已逆解定位真实_mac_policy_register，局部策略结构80B偏移对应。[预链接记录](operations/2026-10-24-merged-native-prelink.md)。

本轮以成功CI相同64项补丁在内存重建六文件，12项检查确认安全加载先于mac_late与最终lockdown，可选入口在构造/成功start之后。DATA_CONST初始RWNX、最后RNX，单靠Mach-O只读标志判故障的风险排序已修正。实际bf14 dSYM的mac_policy_ops为335槽/2680B，原AMFI直线注册块23次指针写入均落在native槽位且目标位于原AMFI RX；槽位匹配不证明参数结构/C++ABI。[阶段与槽位记录](operations/2026-10-24-amfi-phase-and-slots.md)。

USB运输当前首因倾向v4 ABL选择已安装init_boot，临时ramdisk未交接。新增固定ABL版本来源+0x28→context+0x458与选择门证据；36原始门字节在AArch64用户QEMU16例通过，不是完整ABL执行。新v3包8177783e1364caed71e0db82f4c91db720f9586f8bc0d05ca044e133be4ad898/70266880B，v4匹配对照91e86ce4，两者仅offset20/40不同，4096之后全部相同。相同FD/64MiB封装CRC/配置探针，无XNU/ADT，保留原cmdline和全部板值。包报告reports/usb-ramdisk/40014018074/package-v3.json；匹配v4仅离线，不安排自动启动。[USB诊断记录](operations/2026-10-24-usb-ramdisk-v3.md)。

下一步取得本包新鲜录像/按键恢复条件，刷新唯一nuwa/kalama、Android完成1及三分区基线并即时通知后，才单次临时启动。必须看到独立封装result=1/64MiB块发布Success；内嵌配置菜单fallback不算运输成功。失败先核版本/拼接或v3解析兼容，不改Heap/分区。用户现已具备OTG线并授权判断路线；先试已就绪USB v3，减少host角色/供电/枚举新变量，OTG作为备选。没有本轮设备状态查询，恢复仍以上述历史证据为准。

离线主线继续donor构造/start间接路径/once-guard/关键回调参数、真实ADT和OS窗口资格；initializer仍为空，loadable=false。9GiB为快照而非已分配窗口，64MiB配置封装成功也不等于真实58MiB预链接文件/内核执行通过。Heap/HOB保护/ST FTS路线、board内存/身份/_verified未改，无flash/erase/改槽位。最近菜单后充电仍由探针action=exit/无OS负载解释。[交接](operations/2026-10-23-mainline-handoff.md)。
