> 历史入口已更新（2026-10-28）：当前状态与续接请读`2026-10-28-session-handoff.md`及`2026-10-28-new-session-prompt.md`。PROBE44/45均已消费并恢复，下面的未启动、待恢复及启动命令仅供历史追溯，禁止直接执行。PROBE46是否可部署以最新STATUS、实际qualification和消费记录为准。

## 最新：PROBE45已单次临时启动，待媒体与恢复后验（2026-10-27T23:28:53.8339879+08:00）

用户确认正在录像且实体键恢复已准备好。新鲜预检确认nuwa/kalama、Android完成1、A槽、三分区SHA与44后验一致。fastboot Sending/Booting OKAY（4.566秒/0.112秒），仅证明传输接受，不证明内核执行。

45已消费，禁止重发。镜像SHA e6a9494cb05992142032ddc80e42e9ca247f249ad373d7fefc398f382605902d。证据：reports/xnu-entry-probe-trial/2026-10-27-probe45-cluster/{preflight,launch,consumed}.json。当前等待菜单电源Enter后的录像、稳定照片及Android恢复后验，不能沿用启动前Android状态。媒体目录：D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE45/original/。本轮覆盖UBC/UPL/IO读取及既有解码、Mach-O/dyld、exec续接；239保留。无flash/erase/改槽、提交或推送。

下方45未启动/未消费描述为历史快照，已由本记录取代。

# 当前主线交接（原文件名保留）

## 最新续接：PROBE44已消费并恢复，PROBE45整包完成

44 postcondition确认Android1/A槽/三SHA不变；末态A03D=FFFFFFF00519C49C，已到APFS read内cluster_read调用前，未证明callee入口或具体死锁。用户声明今后末态照片均稳定后拍摄，不再逐轮询问稳定性/秒数，未知秒数保留未知。

45未启动/未消费，镜像out/trial-boot/xnu-entry-probe-45-cluster/boot-xnu-first-entry.img，SHA e6a9494cb05992142032ddc80e42e9ca247f249ad373d7fefc398f382605902d。38作业、独立重编、整包回读已通过；最终资格reports/kernel-entry-probe/2026-10-27-probe45-cluster/qualification.json。沿用239及Restore根，无EL0证明。原件目录Media-nuwa/PROBE45/original已创建，启动前仍需新鲜预检与当轮拍摄/恢复条件。本轮新改动未提交。优先读2026-10-27-probe44-media-probe45-cluster.md与STATUS顶部；下方44未消费、待媒体/恢复或默认不启动等是旧会话快照，不得按它重发44。

## 当前更新：PROBE44已单次临时启动，待媒体及Android恢复（2026-10-27T22:09:00.4304633+08:00）

用户本轮明确批准44直接启动，并确认连续拍摄与实体键恢复条件均已准备好。新鲜预检确认nuwa/kalama、Android完成1、A槽及三分区SHA与43后验一致；fastboot Sending/Booting OKAY，传输4.562秒、Booting 0.112秒。这是传输接受证据，未证明内核或目标读取链执行。

44已消费，禁止重发；当前等待媒体及Android恢复后验，不能把启动前Android1或43后验写成44恢复完成。原件投放目录D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE44/original/已由预检确认。证据reports/xnu-entry-probe-trial/2026-10-27-probe44-chain/{preflight,launch,consumed}.json。镜像SHA b8e2395576460b8296589ea92a6cfa6b73f34abc4fe04090f0c982d3b6d38030；239保留，无flash/erase/改槽，本轮未提交/推送。

下方“44未启动/未消费”和“默认只读不启动”均是此前封存快照，已被本轮用户指令及消费记录更新；不得按旧prompt重发44。收到媒体后继续归档、分析与下一包离线交付。

本长篇记录保留全过程；新会话先读[2026-10-27精简交接](2026-10-27-session-handoff.md)及[续接prompt](2026-10-27-new-session-prompt.md)。用户已授权本次本地收尾提交，旧“未提交”段落是当时快照，不自动沿用为当前禁止；无push/设备动作授权扩展。

## 最新：43恢复完成，44整包离线资格完成（2026-10-27 21:48 +08）

43的postcondition已确认Android1/A槽/三SHA不变；用户确认照片稳定超过十秒。末态A03D=FFFFFFF00519CC10，已在handler内到达属性处理调用前；首要范围为519CC48及其ResourceFork vnode lookup/read，尚无该子函数入口证据，不能断言锁死或UFS故障。代码/媒体依据见2026-10-27-probe43-media-probe44-chain.md与reports/kernel-entry-probe/2026-10-27-probe43-analysis。

44内核out/kernel-entry-probe-44-chain/kernel-entry-probe.macho，SHA49b913fc15e1517c51acc57af919c76d32187a1258a3a9fbb7f4890ebe2c74f1。新增68位置/96B状态；完整38作业通过，含2768透明性、2025调用流程（含818新增）及67绑定，另29 x18扰动、9向量连续路径、6媒体目录检查通过。独立内核重编逐字节一致、整包回读通过。镜像out/trial-boot/xnu-entry-probe-44-chain/boot-xnu-first-entry.img，204484608字节，SHA b8e2395576460b8296589ea92a6cfa6b73f34abc4fe04090f0c982d3b6d38030。包报告reports/xnu-first-entry/entry-probe-44.json，资格reports/kernel-entry-probe/2026-10-27-probe44-chain/qualification.json。44未启动/未消费，239不解除，无EL0/桌面声明。WSL编码日志异常保留。

媒体已按轮迁移1397文件并比较SHA一致；历史路径由Media-nuwa/media-path-migration-2026-10-27.json解析，下一轮目录Media-nuwa/PROBE44/original已建好。record-nuwa-trial-state.py现会在XNU包预检设备查询前创建媒体目录并记录位置；新鲜预检和当轮拍摄/恢复条件仍须满足。本轮未启动/未提交。只读包回读续接：在D:/Code/PortingiOS/nuwa/UniXNU-nuwa中用真实Python执行`-B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-44.json`；不要重跑已完成的收尾脚本覆盖证据。以下为历史状态。

## 最新：PROBE43已单次临时启动，待媒体及恢复（2026-10-27T20:54:31.4467599+08:00）

用户本轮明确批准启动并确认随时拍摄和实体键恢复。新鲜预检确认nuwa/kalama、Android1、A槽、三分区SHA与42后验一致；fastboot Sending/Booting OKAY，传输4.564秒、Booting 0.112秒。只证明命令接受，不证明菜单、内核或handler执行。43已消费，禁止重发。当前等待菜单电源Enter后的连续视频、稳定照片及Android恢复后验，不能沿用预检Android状态。

镜像SHA256 ca73e9562f6236cddcba12c8cc2f62980804c419cb31ac05531c8f8007d8d585；证据reports/xnu-entry-probe-trial/2026-10-27-probe43-handler/{preflight,launch,consumed}.json。观测handler入口、内部调用/返回及wrapper续接，以区分原生处理未完成和观测遗漏；239保留。本轮无flash/erase/改槽或提交。下方43未启动/本轮不上机等表述为先前离线阶段快照。

## 最新：42恢复及媒体闭环，43离线整包完成（2026-10-27 20:49 +08）

42的postcondition已确认Android1/A槽/三SHA不变；媒体415源帧及用户五阶段截图在Media-nuwa/derived/PROBE42/review-01，原件保留。稳定末态A03D=FFFFFFF00746E1A4、A03E=FFFFFFF00519CB28，旧panic文字未见；不把调用前当入口或死锁。代码审阅及首要假设见2026-10-27-probe42-media-probe43-handler.md、reports/kernel-entry-probe/2026-10-27-probe42-analysis。

43候选内核out/kernel-entry-probe-43-handler/kernel-entry-probe.macho，SHA e5df5bef0779347edc5d94becd1611f8c3ffe7d5595795f345872dc02fe74a8b；新增19个handler位置、32B配对状态、无新增网格。38项串行作业全部通过：2496透明性、1207调用流程（含192新增）、67绑定；另29项x18扰动和9项连续路径通过。独立内核重编逐字节一致，整包回读通过，42旧内核/镜像及原媒体摘要未变。

新镜像out/trial-boot/xnu-entry-probe-43-handler/boot-xnu-first-entry.img，204484608字节，SHA256 ca73e9562f6236cddcba12c8cc2f62980804c419cb31ac05531c8f8007d8d585。包报告reports/xnu-first-entry/entry-probe-43.json，资格reports/kernel-entry-probe/2026-10-27-probe43-handler/qualification.json。43未启动/未消费；当前Android恢复依据仍是42 postcondition。239不解除，无本轮启动/提交，WSL编码日志缺陷保留。启动前核对当轮观测/恢复和新鲜预检；不要执行下方历史已消费候选命令。可只读回读当前包：在D:/Code/PortingiOS/nuwa/UniXNU-nuwa中用真实Python执行`-B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-43.json`。以下为历史状态。

## 最新：PROBE42已单次临时启动，待媒体与恢复（2026-10-27T20:05:46.332150+08:00）

新鲜预检nuwa/kalama、Android1、A槽及三SHA与41后验一致；用户确认连续拍摄和实体键恢复条件。fastboot Sending/Booting OKAY，仅证明传输接受，不能证明菜单/内核或修复通过。42已消费，禁止重发。当前等待菜单电源Enter后的连续视频、稳定照片及Android恢复后验；不能沿用启动前Android状态。本轮无flash/erase/改槽或提交。证据reports/xnu-entry-probe-trial/2026-10-27-probe42-x18/{preflight,launch,consumed}.json。

观测目标：原HEX渲染panic是否消失、资源读取/解压/exec是否推进；若同类异常复现则重审x18假设。239保持。以下未启动/未消费/仅离线表述为历史阶段记录。

## 2026-10-27 PROBE42离线续接

19:51 +08收尾：PROBE42已完成38项串行资格、29行x18扰动、9连续路径、独立内核字节复现和整包回读。镜像out/trial-boot/xnu-entry-probe-42-x18/boot-xnu-first-entry.img，SHA256 edae54d85c90d35458cfc97b412f92af5852afad35ba4633ada891c48a276a9b，204484608字节。资格reports/kernel-entry-probe/2026-10-27-probe42-x18/qualification.json。内核较41仅HEX helper内19字节变化；42未消费，本轮无设备访问/提交。239未解除，轻量记录架构尚待实施。下段核验中状态为本轮过程记录。

最新事实覆盖下方历史快照：41 r5媒体已落位，18:46:38 +08的postcondition确认Android1/A槽/三SHA不变。A034为FFFFFFF0084DA0F4，首要嫌疑为增量HEX跨异常返回持有x18缓存指针。新内核out/kernel-entry-probe-42-x18/kernel-entry-probe.macho已编译；29行x18扰动和旧候选负对照通过，完整串行核验正在进行，不可提前部署。新报告reports/kernel-entry-probe/2026-10-27-probe42-x18；详情2026-10-27-probe42-x18.md。本轮不上机，不提交。239仍保留，因为包内仍是Restore根，正常根/Data的provider及挂载尚未接入；不把删除停点当成正常用户态进展。

2026-10-27T18:43:05.203664+08:00

2026-10-27T18:43:05.203664+08:00 · 用户恢复实机且当轮确认连续拍摄/实体键恢复已就绪。PROBE41 r5单次临时启动已获fastboot Sending/Booting OKAY，包SHA256 6d2d0023437ab0aa630372aeb57ff4925a6ef5e9db18a5131cf2ffab1e6cb748；ACK只证明命令接受，不证明菜单/内核/handler已执行。候选已消费，禁止重发。新鲜预检Android1、nuwa/kalama、A槽，三SHA与PROBE40一致。当前等待用户菜单电源Enter、连续录像/稳定照片和回Android；启动后设备状态尚未取得后验，不沿用启动前Android1冒充恢复。证据reports/xnu-entry-probe-trial/2026-10-27-v49-r5/{preflight,launch,consumed}.json。媒体目录D:/Code/PortingiOS/nuwa/Media-nuwa；恢复后补postcondition与三SHA。未flash/erase/改槽、未提交。

PROBE41已调整为实际ResourceFork分派版r5，现已消费，待媒体/恢复后验。镜像out/trial-boot/xnu-entry-probe-41-dispatch-r5/boot-xnu-first-entry.img，204484608字节，SHA256 6d2d0023437ab0aa630372aeb57ff4925a6ef5e9db18a5131cf2ffab1e6cb748；内核89fdd0a831500ff2f28d2245824c47a0d1ad5e7d1719c42f7ede3b7e9237eaad，ADTfbc8ee7eabb52c2d1c0e4bca2dd581af6b107f0c2672fba33b8f455fa1e5e155。38项串行作业全部通过，2420透明性、1015专项（含新增38项分派检查）、9连续路径/重置、独立内核逐字节复现与镜像回读通过。新增A03D=FFFFFFF00746E1A4/A03E=原生实际x8目标，A03D=FFFFFFF00746E1A8/A03E=配对返回原始x0；调用前不是handler入口，A03D不是停止PC。仍使用原矩形，旧22点及后续主线继续；Restore根、239门、板值/内存/IPSW身份、verified边界不变。旧r4内核/ADT/整包摘要核对不变，旧资格保留且不套给r5。本轮没有设备操作、提交、推送或CI。详情docs/operations/2026-10-27-probe41-dispatch-r5.md，资格reports/kernel-entry-probe/2026-10-27-v49-r5/qualification.json，包报告reports/xnu-first-entry/entry-probe-41-r5.json。

当前默认候选以r5为准。下列既有离线里程碑中的“41未变/无内核变更”描述其当时状态；OS/Data准备成果继续保留，不表示已接入本轮镜像。当前41实测已按本轮用户安排恢复；启动前状态由本轮preflight确认，启动后恢复仍待核验。

最新Data候选已生成，见2026-10-27-linux-apfs-data-candidate.md及reports/desktop-readiness/2026-10-27-data-linux-r1/qualification.json。采用固定fajita Linux builder+固定apfsprogs源归档，依赖在仓外Toolchain-nuwa，无git clone/init。160个20H392源目录，逻辑1 GiB、无文件偏好、APFS/role none，包106608B SHA256 1e00210d8fb17f13736efe8d6ca9f6b72eb424c223fa1bf03168b808bf2f7598，卷UUID 3FA04580-6AA3-5949-A64F-B5F03A271995；两次构建/独立FS读回/C++完整逻辑摘要通过。仅宿主候选，未接入41。当前实际内核未见RamBlock符号、恢复root RAMDisk与新Data不得混同；待固定正确iOS16 provider ABI/archive/link/init及完整root发布/挂载。旧快照和公开配置pin字节不同，Git元数据因dubious ownership停止，不作safe.directory或手读.git绕过，正式访问复核尚需解决。41/239/板值/设备暂停不变，未提交。

最新OS原始输入准备见2026-10-27-raw-os-input.md及reports/desktop-readiness/2026-10-27-raw-os-r1/qualification.json：5635081728字节raw SHA256 6e87bfcaa8eca952e00b719f333d1f1060715a63566112267ad8730e1ed98906，3638块回读、5文件只读视图对照、源DMG前后摘要/卸载闭环。System卷UUID DADD93F8-DBBF-4B17-A1DF-0F11E64172F7单独取得，候选契约out/desktop-raw-os-20261027-r2/raw-window-contract.json；未写board/ADT。15上游+14本地检查通过，Clock skew原日志保留；首次Windows/POSIX父证据路径差异失败日志保留，hash要求不变。只补齐宿主原始输入，非完整根/Data或启动包；目标容量、发布/匹配、Data种子/保护/初始化及原生运行仍未验收。41/239不变，设备暂停，未提交。历史“OS解码摘要未知”由本轮新证据取代，不重写旧报告。

最新根/Data/服务推进见2026-10-27-root-data-service-contract.md及reports/desktop-readiness/2026-10-27-contract-r1/qualification-r2.json：根原始窗口总预览8380219392字节，目标容量/OS解码SHA未定；532作业、1668 Mach名、63路径，containermanagerd条件参数不展开，9个跨组件程序找到/ARM64-all，4个其它缺项待条件审查。out/desktop-root-contract-20261027-r2/assembly-contract.json和os-var-source.tar为本轮交付，198项初始来源包回读通过；排除staged_system_apps，非APFS种子。r1归档触及预算而不完整，禁止使用，原失败报告/日志保留。15+9+9项测试通过，源摘要不变/挂载退出，未用设备/未改41或239/未提交。r2资格仅纠正计数元数据及绑定，初版保留。下一项为Data APFS元数据/初始化与原生服务解释、OS解码/完整挂载契约；不要将host tar当payload Data输入。

最新S05/S06推进：新增desktop_cache.py、desktop_namespace.py、audit-desktop-cache.py、test-desktop-cache.py；最终r3完成42子缓存+symbols UUID/映射引用、2710镜像索引，四个磁盘入口静态库路径1103节点/17649边，必需缺失0，弱依赖缺失6边/4路径，14项测试通过。三个组件前后摘要一致且卸载；r1/r2结果保留，r3修正lazy依赖覆盖和dyld磁盘/cache同名入口选择。reports/desktop-readiness/2026-10-27-cache-r1/qualification.json绑定最终源码和证据，详见2026-10-27-desktop-cache-closure.md。虚拟OS/cryptex/cache映射未部署，非完整符号/认证/运行闭包。下一离线项为根组装契约和Data/服务范围；41、239门和设备暂停保持，无提交。

最新规则复审：新增audit-resource-progress.py、test-resource-progress.py、test-native-resource-uio.py；固定原生UIO双分配与VFS参数/初始化模型已核对。六项CFG检查、三组UIO含错误分支、一项VFS Unicorn模拟通过；真实分配器/APFS和live v_op未知。不能把IOMallocData返回当作UIO分配完成，不能把磁盘descriptor offset=0当作live index。详见2026-10-27-mainline-reassessment.md及reports/mainline-reassessment/2026-10-27-r1/qualification.json，包含失败原记录、疑点排序、阶段缺口和仅追溯的已执行命令。41仍未消费，包新读SHA未变，无设备操作/内核变更/提交；后续可离线推进命名空间/cache闭包，保留239门与平台独立验收缺口。

用户明确本轮“离线”只指不使用实机，仍须在线参考公开资料；本轮没有设备访问/启动。阶段持续实机授权暂不执行，待用户恢复设备工作后按当轮观测/恢复及新鲜预检继续。最后设备证据仍是PROBE40的12:00:43 +08 Android1、nuwa/kalama、A槽及三分区SHA一致；不是本轮新查询。

原生当前卡点仍是PROBE40细条带535资源块表读取调用可见、536续接未辨出。第二次分配非零及向量准备已观察，不能确定资源helper入口或死锁。详见docs/operations/2026-10-27-probe41-resource-bottleneck.md。原始媒体、首次screen和补充证据保留。

历史PROBE41资源版r4为未启动、未消费的合格诊断包（当前默认候选已由r5替代）：38作业、2412透明性、977专项、9连续路径/重置、独立内核逐字节复现及包回读。包out/trial-boot/xnu-entry-probe-41-resource/boot-xnu-first-entry.img，204484608字节，SHA256 8d242a2dd953146af5c3c8ae59c6805cba6599aa7283188180667bfca5c2ec2a，本轮重新核对未变。内核8757bc0c38449099e3d10b8fcd69ec0cbd830c263f99c77bce2ff191848e4418；ADT82b5219204cd30f79d520e1710c5b63d105e19f4337f16ef87cdc1603da00a57。资格reports/kernel-entry-probe/2026-10-27-v49-r4/qualification.json，包报告reports/xnu-first-entry/entry-probe-41.json。旧28—40已消费启动命令只追溯，不重发。

新增桌面输入准备：4个脚本、6项测试；恢复RAMDisk实际缺少SpringBoard/backboardd和shared cache，无主launch配置。三份完整20H392的OS/SystemOS/AppOS组件已重新只读挂载、流式核对manifest摘要和前后不变，均卸载。OS含SpringBoard/backboardd及532项主launch配置，SystemOS有44个shared-cache文件。记录的是输入、头和配置，尚未完成cache引用/依赖闭包、根组装、认证或GUI运行。非部署输入计划及资格reports/desktop-readiness/2026-10-27-qualification-r1；组合证据reports/desktop-readiness/2026-10-27-combined-r1/qualification.json。

已在线固定领先设备来源：sheng 08cde20edc32（SM8550/iPadOS17）、ishtar 9ee8ee510ebb（SM8550/iOS18，详细日志到锁屏、按键与USB；README滞后）、ios-sweet 45263bee51df（iOS16桌面）。实际审阅显示ABI构建、显示电源补丁、OS/cryptex根脚本；版本/文件SHA/许可和nuwa差异见reports/desktop-readiness/2026-10-27-reference-r1/manifest.json。维护者设备记录不是nuwa通过；没有导入板值、固定地址或上游实现。

当前判断、已完成证据及下一项离线代码工作见docs/operations/2026-10-27-desktop-offline-progress.md：OS/cryptex虚拟命名空间；shared-cache引用与路径闭包；可写Data/服务内容；iOS16 IOSurface/MobileFramebuffer/HID接口资格。完整原材料已有，恢复根不能代表桌面根。

距离首次用户态仍需原生读取/解压、exec认证和映射、实际EL0；桌面还需完整根、服务与图形/输入。239未审用户任务释放门保持，UFS未验收，当前根是RAMDisk/md0。未改受审内存/IPSW身份、未置*_verified=true。HEAD855daaf，无本轮提交/推送/CI；原迁移修改与历史证据保留，新路径/Legacy只读/串行脚本/单写入者规则持续有效。

本轮已执行的离线命令及新输出见2026-10-27-desktop-offline-progress.md；历史输出均已存在，不重跑覆盖。后续只读包回读可执行build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-41.json；本轮不运行设备续接命令。

2026-10-27T14:10:38.5350403+08:00 · 官网顺序复核：驱动依赖、root/Data、先CPU呈现再GPU、分层日志和OS ABI契约已对照；后续按docs/operations/2026-10-27-official-adaptation-sequence.md推进。仅查阅/文档维护，设备暂停，PROBE41与受审输入未变。

2026-10-27T14:14:30.9449713+08:00 · 用户已确认将UniXNU官网内容作为后续开发指南。执行规则已写入设备仓AGENTS.md第0节，固件仓同步引用；按官网依赖/启动阶段/ABI与日志完成条件推进，保留既有用户指令、硬停和证据边界。决策D-071。当前仍仅离线、不操作设备，PROBE41未变。

2026-10-27T14:25:45.9616435+08:00 · 用户要求各阶段具体方法/步骤落为规则：docs/DEVELOPMENT-STAGES.md已定义S00—S13及通用执行方法，两仓AGENTS强制引用，决策D-072。后续按前提、实施、离线/必要实测及完成/失败条件推进；当前阶段状态和证据不变。设备继续暂停，未改PROBE41，未提交。
