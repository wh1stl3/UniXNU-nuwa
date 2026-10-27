## 最新：PROBE45已单次临时启动，待媒体与恢复后验（2026-10-27T23:28:53.8339879+08:00）

用户确认正在录像且实体键恢复已准备好。新鲜预检确认nuwa/kalama、Android完成1、A槽、三分区SHA与44后验一致。fastboot Sending/Booting OKAY（4.566秒/0.112秒），仅证明传输接受，不证明内核执行。

45已消费，禁止重发。镜像SHA e6a9494cb05992142032ddc80e42e9ca247f249ad373d7fefc398f382605902d。证据：reports/xnu-entry-probe-trial/2026-10-27-probe45-cluster/{preflight,launch,consumed}.json。当前等待菜单电源Enter后的录像、稳定照片及Android恢复后验，不能沿用启动前Android状态。媒体目录：D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE45/original/。本轮覆盖UBC/UPL/IO读取及既有解码、Mach-O/dyld、exec续接；239保留。无flash/erase/改槽、提交或推送。

下方45未启动/未消费描述为历史快照，已由本记录取代。

# STATUS

## 当前更新：44媒体及恢复闭环，45整包资格完成（2026-10-27 23:09 +08）

44 postcondition确认Android1/A槽/三分区SHA不变；用户确认末态稳定，并约定今后默认稳定后拍照、无需逐轮再问。清晰A03D=FFFFFFF00519C49C，实际APFS read已到cluster_read调用前，尚不能证明cluster入口或确定死锁。首要范围转为UBC缓存拷贝、UPL请求和IO完成等待。

45新增64位置/160B状态，覆盖缓存快拷贝、UPL请求、IO分派与等待续接；附带读数实际为原生PAGE_SHIFT_CONST，不是可变page_shift。38项串行作业全部通过：3024透明性、2795调用流程（含770新增）、67绑定；另29 x18扰动、9向量连续路径通过。独立内核重编逐字节一致、整包回读通过。镜像`out/trial-boot/xnu-entry-probe-45-cluster/boot-xnu-first-entry.img`，204484608字节，SHA256 `e6a9494cb05992142032ddc80e42e9ca247f249ad373d7fefc398f382605902d`；资格`reports/kernel-entry-probe/2026-10-27-probe45-cluster/qualification.json`。45未启动/未消费，239保留，原生读取尚未闭环，未证明EL0。详情[44媒体与45缓存链](operations/2026-10-27-probe44-media-probe45-cluster.md)。

下一轮原件目录`D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE45/original/`已创建；启动前仍需新鲜设备预检及当轮拍摄/恢复条件。本轮新改动未提交，无新的实机启动。以下44待媒体/恢复及45核验中描述均为历史。

45同轮验收目标已扩大为缓存读取→ResourceFork完成→type4解码→Mach-O→dyld→exec受控释放边界。静态确认现有镜像包含全部12对exec/dyld路径与后续观察点，正常续接连续执行；239保留，扩大目标不代表前置读取已修复或EL0已通过。范围记录见资格同目录expanded-trial-objectives.json，镜像SHA及既有资格保持原值。

## 当前更新：PROBE44已单次临时启动，待媒体及Android恢复（2026-10-27T22:09:00.4304633+08:00）

用户本轮明确批准44直接启动，并确认连续拍摄与实体键恢复条件均已准备好。新鲜预检确认nuwa/kalama、Android完成1、A槽及三分区SHA与43后验一致；fastboot Sending/Booting OKAY，传输4.562秒、Booting 0.112秒。这是传输接受证据，未证明内核或目标读取链执行。

44已消费，禁止重发；当前等待媒体及Android恢复后验，不能把启动前Android1或43后验写成44恢复完成。原件投放目录D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE44/original/已由预检确认。证据reports/xnu-entry-probe-trial/2026-10-27-probe44-chain/{preflight,launch,consumed}.json。镜像SHA b8e2395576460b8296589ea92a6cfa6b73f34abc4fe04090f0c982d3b6d38030；239保留，无flash/erase/改槽，本轮未提交/推送。

下方“44未启动/未消费”和“默认只读不启动”均是此前封存快照，已被本轮用户指令及消费记录更新；不得按旧prompt重发44。收到媒体后继续归档、分析与下一包离线交付。

会话封存入口：[2026-10-27精简交接](operations/2026-10-27-session-handoff.md)；[新会话prompt](operations/2026-10-27-new-session-prompt.md)。用户现已明确授权本次本地收尾提交，下文各轮“未提交”描述仍是当时快照。本次提交不包含push或新的设备动作。

## 最新：43媒体与恢复闭环，44整包离线资格完成（2026-10-27 21:48 +08）

43 postcondition确认Android1/A槽/三分区SHA不变；照片稳定超过十秒，A03D=FFFFFFF00519CC10，实际handler已到属性处理调用前，尚不能证明519CC48入口或死锁。当前重点为ResourceFork vnode查找、文件/缓存读取及元数据/锁重试；不能直接归因于UFS。

44新增68个位置覆盖3个函数入口/返回及31个重要调用。38项串行作业通过（2768透明性、2025调用流程含818新增、67绑定）；29项x18扰动、9项向量准备连续路径、6项媒体目录检查通过。独立内核重编逐字节一致，整包回读通过。镜像`out/trial-boot/xnu-entry-probe-44-chain/boot-xnu-first-entry.img`，204484608字节，SHA256 `b8e2395576460b8296589ea92a6cfa6b73f34abc4fe04090f0c982d3b6d38030`；资格`reports/kernel-entry-probe/2026-10-27-probe44-chain/qualification.json`。44未启动/未消费，无新增网格，239及原生锁/错误保持，未证明进入EL0。详见[43媒体与44连续链](operations/2026-10-27-probe43-media-probe44-chain.md)。

媒体1397文件已按轮移动且前后SHA一致，旧manifest不改写，路径迁移索引在Media-nuwa根目录。下一轮投放目录`D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE44/original/`已创建，自动建目录已接入XNU包预检。启动前仍需新鲜身份/摘要预检及当轮拍摄/恢复条件。本轮未启动新设备试验、未提交。以下43待媒体/恢复及旧路径描述均为历史快照。

## 最新：PROBE43已单次临时启动，待媒体及恢复（2026-10-27T20:54:31.4467599+08:00）

用户本轮明确批准启动并确认随时拍摄和实体键恢复。新鲜预检确认nuwa/kalama、Android1、A槽、三分区SHA与42后验一致；fastboot Sending/Booting OKAY，传输4.564秒、Booting 0.112秒。只证明命令接受，不证明菜单、内核或handler执行。43已消费，禁止重发。当前等待菜单电源Enter后的连续视频、稳定照片及Android恢复后验，不能沿用预检Android状态。

镜像SHA256 ca73e9562f6236cddcba12c8cc2f62980804c419cb31ac05531c8f8007d8d585；证据reports/xnu-entry-probe-trial/2026-10-27-probe43-handler/{preflight,launch,consumed}.json。观测handler入口、内部调用/返回及wrapper续接，以区分原生处理未完成和观测遗漏；239保留。本轮无flash/erase/改槽或提交。下方43未启动/本轮不上机等表述为先前离线阶段快照。

## 最新：42媒体与恢复完成，43离线整包资格完成（2026-10-27 20:49 +08）

42后验已确认Android1、nuwa/kalama、A槽、三分区SHA与启动前一致。415帧视频及五阶段截图已归档；用户确认照片前已稳定，等待秒数未知。最终A03D=FFFFFFF00746E1A4/A03E=FFFFFFF00519CB28，未见旧panic文字，支持x18修复；只证明分派调用前/实际目标，不证明APFS handler入口或死锁。首要疑点为getxattr处理路径未完成，条件锁/属性读取及观测遗漏待区分。

43新增该handler的19个位置，沿用A03D/E而不加网格。38项串行作业通过（2496项透明性、1207项调用流程含192项新增检查、67项证据绑定），另有29项x18扰动和9项连续路径通过；独立内核重编逐字节一致、整包回读通过。新包`out/trial-boot/xnu-entry-probe-43-handler/boot-xnu-first-entry.img`，204484608字节，SHA256 `ca73e9562f6236cddcba12c8cc2f62980804c419cb31ac05531c8f8007d8d585`，资格`reports/kernel-entry-probe/2026-10-27-probe43-handler/qualification.json`。

43未启动/未消费；本轮不自动上机、不提交。239、Restore根及固件保持；正常OS/Data接入、EL0和桌面仍未验收。构建日志中的既有WSL编码异常保留，不称日志完全正常。下一实测需新鲜预检及当轮拍摄/恢复条件，保留短视频和稳定照片。详情[42媒体与43观测](operations/2026-10-27-probe42-media-probe43-handler.md)。下方42待媒体/恢复、43之前的候选资格均为历史快照，不作为当前操作命令。

## 最新：PROBE42已单次临时启动，待媒体与恢复（2026-10-27T20:05:46.332150+08:00）

新鲜预检nuwa/kalama、Android1、A槽及三SHA与41后验一致；用户确认连续拍摄和实体键恢复条件。fastboot Sending/Booting OKAY，仅证明传输接受，不能证明菜单/内核或修复通过。42已消费，禁止重发。当前等待菜单电源Enter后的连续视频、稳定照片及Android恢复后验；不能沿用启动前Android状态。本轮无flash/erase/改槽或提交。证据reports/xnu-entry-probe-trial/2026-10-27-probe42-x18/{preflight,launch,consumed}.json。

观测目标：原HEX渲染panic是否消失、资源读取/解压/exec是否推进；若同类异常复现则重审x18假设。239保持。以下未启动/未消费/仅离线表述为历史阶段记录。

## 当前更新：PROBE42离线资格完成（2026-10-27 19:51 +08）

新包out/trial-boot/xnu-entry-probe-42-x18/boot-xnu-first-entry.img，204484608字节，SHA256 edae54d85c90d35458cfc97b412f92af5852afad35ba4633ada891c48a276a9b。38项串行作业、29行x18扰动及9项连续路径通过，独立内核重编逐字节一致，整包回读通过；内核仅HEX helper内19字节变化。42未启动/未消费，239保留，正常根/Data接入和诊断记录/显示分离仍未完成。以下“核验中”描述准备阶段，最终资格以reports/kernel-entry-probe/2026-10-27-probe42-x18/qualification.json为准。

PROBE41 r5媒体已收到；postcondition.json于2026-10-27 18:46:38 +08确认Android完成1、A槽及三分区摘要未变。以下18:43的“待媒体/恢复”段落是历史启动快照，不再是当前设备状态。41已消费，不重发。本轮不启动设备。

照片A034校正为FFFFFFF0084DA0F4，落在HEX增量渲染器读取x18缓存指针的指令。实际原生异常返回默认清零x18，旧候选离线扰动复现读0x8失败；新内核改用保存/恢复的x0，29行扰动及旧候选负对照已通过，全套串行资格仍在运行。新包未完成前不可部署。239条件释放门保留：当前仍是Restore根，正常OS/Data provider及挂载接入未完成。详见[PROBE42记录](operations/2026-10-27-probe42-x18.md)。

以下为既有里程碑记录，其“无本轮设备操作”“候选未消费”等表述只描述各自当时状态。

2026-10-27T18:43:05.203664+08:00

2026-10-27T18:43:05.203664+08:00 · 用户恢复实机且当轮确认连续拍摄/实体键恢复已就绪。PROBE41 r5单次临时启动已获fastboot Sending/Booting OKAY，包SHA256 6d2d0023437ab0aa630372aeb57ff4925a6ef5e9db18a5131cf2ffab1e6cb748；ACK只证明命令接受，不证明菜单/内核/handler已执行。候选已消费，禁止重发。新鲜预检Android1、nuwa/kalama、A槽，三SHA与PROBE40一致。当前等待用户菜单电源Enter、连续录像/稳定照片和回Android；启动后设备状态尚未取得后验，不沿用启动前Android1冒充恢复。证据reports/xnu-entry-probe-trial/2026-10-27-v49-r5/{preflight,launch,consumed}.json。媒体目录D:/Code/PortingiOS/nuwa/Media-nuwa；恢复后补postcondition与三SHA。未flash/erase/改槽、未提交。

PROBE41已调整为实际ResourceFork分派版r5，现已消费，待媒体/恢复后验。镜像out/trial-boot/xnu-entry-probe-41-dispatch-r5/boot-xnu-first-entry.img，204484608字节，SHA256 6d2d0023437ab0aa630372aeb57ff4925a6ef5e9db18a5131cf2ffab1e6cb748；内核89fdd0a831500ff2f28d2245824c47a0d1ad5e7d1719c42f7ede3b7e9237eaad，ADTfbc8ee7eabb52c2d1c0e4bca2dd581af6b107f0c2672fba33b8f455fa1e5e155。38项串行作业全部通过，2420透明性、1015专项（含新增38项分派检查）、9连续路径/重置、独立内核逐字节复现与镜像回读通过。新增A03D=FFFFFFF00746E1A4/A03E=原生实际x8目标，A03D=FFFFFFF00746E1A8/A03E=配对返回原始x0；调用前不是handler入口，A03D不是停止PC。仍使用原矩形，旧22点及后续主线继续；Restore根、239门、板值/内存/IPSW身份、verified边界不变。旧r4内核/ADT/整包摘要核对不变，旧资格保留且不套给r5。本轮没有设备操作、提交、推送或CI。详情docs/operations/2026-10-27-probe41-dispatch-r5.md，资格reports/kernel-entry-probe/2026-10-27-v49-r5/qualification.json，包报告reports/xnu-first-entry/entry-probe-41-r5.json。

当前默认候选以r5为准。下列既有离线里程碑中的“41未变/无内核变更”描述其当时状态；OS/Data准备成果继续保留，不表示已接入本轮镜像。当前41实测已按本轮用户安排恢复；启动前状态由本轮preflight确认，启动后恢复仍待核验。

公开设备实现检索已消除“缺Mac就无法制作Data候选”的前提：固定fajita Linux/APFS方法并实际构建1 GiB逻辑卷、160个源OS目录、role=none；Data包106608字节/SHA256 1e00210d8fb17f13736efe8d6ca9f6b72eb424c223fa1bf03168b808bf2f7598。apfsck、目录读回、独立FUSE/APFS读回、两次构建摘要复现及实际旧C++parser/importer完整逻辑摘要通过；8项输入检查、4000差分I/O通过。候选out/linux-data-candidate-20261027-r1/build-a/data-linux.dbr，不代表iOS16原生挂载/保护/迁移通过。下一项是Data provider源码/ABI/链接初始化与root/Data分离：当前41的64693符号中未见RamBlock相关名称，ADT仍是恢复根RAMDisk占位，不能直接加入PackedRAMDisk。旧快照文件与配置公开pin不同；旧库Git所有权保护拒绝后已停止该Git操作，未改safe.directory，未重置源码。详见docs/operations/2026-10-27-linux-apfs-data-candidate.md、reports/desktop-readiness/2026-10-27-data-linux-r1/qualification.json。没有新建Git仓库、设备操作、板值/41/239修改或提交。

OS原始输入已补齐：out/desktop-raw-os-20261027-r2/os.raw.img，5635081728字节，SHA256 6e87bfcaa8eca952e00b719f333d1f1060715a63566112267ad8730e1ed98906；3638块逐块/全文件回读通过，raw只读挂载的4程序+主配置与固定库存一致，DMG前后摘要不变/挂载退出。System卷UUID DADD93F8-DBBF-4B17-A1DF-0F11E64172F7（不是GPT分区GUID）作为候选root-matching输入写入独立raw-window-contract.json，未改板配置。15项上游LZFSE往返及14项本地检查通过，构建Clock skew原警告保留。最终证据reports/desktop-readiness/2026-10-27-raw-os-r1/qualification.json，详见docs/operations/2026-10-27-raw-os-input.md。此前OS解码摘要缺口已补齐；下一项仍为合格Data文件系统元数据/初始化、完整挂载/目标存储与OS ABI、原生服务状态。未生成SHNGROOT/Data/payload/boot新包，未用设备，41/239/板值不变，未提交。

S05/S06根/Data/服务契约已推进：UDIF几何确认OS原始磁盘5635081728字节（DMG为4730814044），两只读窗口预览8380219392字节，容量/OS解码摘要未知，不可部署。532作业/1668 Mach服务名/63路径已清点，containermanagerd的条件参数保持未解释；9个跨cryptex程序均找到且有ARM64-all输入，另外4个OS单层未找到项待按条件判断。已导出198项OS-var初始来源包并回读，明确排除staged_system_apps；不是APFS Data种子。15+9+9项检查通过，所有成功/失败只读挂载均退出，源摘要不变。out/desktop-root-contract-20261027-r2/assembly-contract.json与os-var-source.tar为当前交付，r1归档不完整不可用；最终绑定reports/desktop-readiness/2026-10-27-contract-r1/qualification-r2.json（计数字段纠正，初版保留），详见docs/operations/2026-10-27-root-data-service-contract.md。下一项仍是合格Data元数据/初始化、OS解码与完整挂载/服务解释契约。设备暂停，41/239/板值不变，无提交。

S05/S06此前缓存证据保持：主缓存42子文件与symbols UUID/VM offset闭环，2710镜像路径索引；四个实际磁盘入口的递归静态库路径检查1103节点/17649边，0缺失必需边，6条弱依赖缺失边/4路径，14项回归通过。OS/两个cryptex只读前后SHA256/SHA384一致且均卸载。证据reports/desktop-readiness/2026-10-27-cache-r1/{audit-r3,tests-r3,qualification}.json，方案与限制见docs/operations/2026-10-27-desktop-cache-closure.md。虚拟缓存绑定尚未组装/部署，不代表符号/fixup/认证或用户态运行通过。组装/Data与服务契约已由上述新结果续接，ResourceFork、平台验收及239门仍保留。

按最新S01/S04/S05/S06规则复审并新增固定指令检查：UIO实际双分配（0x8004与16字节/flags4），getxattr描述符静态存在且未禁用；六项CFG测试、三组UIO正常/错误分支和VFS包装Unicorn模拟通过，真实分配器/APFS主体未执行。最高优先级仍是ResourceFork调用链进度，尚不能区分UIO等待与vnode/APFS路径；确定性布局/注册错误优先级降低。阶段依赖与最小证伪路径见docs/operations/2026-10-27-mainline-reassessment.md，新证据reports/mainline-reassessment/2026-10-27-r1/qualification.json。设备保持暂停，41新读SHA未变，无内核/包修改或重编；239门保持。下一独立离线项为OS/cryptex命名空间与cache引用闭包。

用户明确本轮“离线”只指不使用实机，仍须在线参考公开资料；本轮没有设备访问/启动。阶段持续实机授权暂不执行，待用户恢复设备工作后按当轮观测/恢复及新鲜预检继续。最后设备证据仍是PROBE40的12:00:43 +08 Android1、nuwa/kalama、A槽及三分区SHA一致；不是本轮新查询。

原生当前卡点仍是PROBE40细条带535资源块表读取调用可见、536续接未辨出。第二次分配非零及向量准备已观察，不能确定资源helper入口或死锁。详见docs/operations/2026-10-27-probe41-resource-bottleneck.md。原始媒体、首次screen和补充证据保留。

历史PROBE41资源版r4为未启动、未消费的合格诊断包（当前默认候选已由r5替代）：38作业、2412透明性、977专项、9连续路径/重置、独立内核逐字节复现及包回读。包out/trial-boot/xnu-entry-probe-41-resource/boot-xnu-first-entry.img，204484608字节，SHA256 8d242a2dd953146af5c3c8ae59c6805cba6599aa7283188180667bfca5c2ec2a，本轮重新核对未变。内核8757bc0c38449099e3d10b8fcd69ec0cbd830c263f99c77bce2ff191848e4418；ADT82b5219204cd30f79d520e1710c5b63d105e19f4337f16ef87cdc1603da00a57。资格reports/kernel-entry-probe/2026-10-27-v49-r4/qualification.json，包报告reports/xnu-first-entry/entry-probe-41.json。旧28—40已消费启动命令只追溯，不重发。

新增桌面输入准备：4个脚本、6项测试；恢复RAMDisk实际缺少SpringBoard/backboardd和shared cache，无主launch配置。三份完整20H392的OS/SystemOS/AppOS组件已重新只读挂载、流式核对manifest摘要和前后不变，均卸载。OS含SpringBoard/backboardd及532项主launch配置，SystemOS有44个shared-cache文件。记录的是输入、头和配置，尚未完成cache引用/依赖闭包、根组装、认证或GUI运行。非部署输入计划及资格reports/desktop-readiness/2026-10-27-qualification-r1；组合证据reports/desktop-readiness/2026-10-27-combined-r1/qualification.json。

已在线固定领先设备来源：sheng 08cde20edc32（SM8550/iPadOS17）、ishtar 9ee8ee510ebb（SM8550/iOS18，详细日志到锁屏、按键与USB；README滞后）、ios-sweet 45263bee51df（iOS16桌面）。实际审阅显示ABI构建、显示电源补丁、OS/cryptex根脚本；版本/文件SHA/许可和nuwa差异见reports/desktop-readiness/2026-10-27-reference-r1/manifest.json。维护者设备记录不是nuwa通过；没有导入板值、固定地址或上游实现。

当前判断、已完成证据及下一项离线代码工作见docs/operations/2026-10-27-desktop-offline-progress.md：OS/cryptex虚拟命名空间；shared-cache引用与路径闭包；可写Data/服务内容；iOS16 IOSurface/MobileFramebuffer/HID接口资格。完整原材料已有，恢复根不能代表桌面根。

距离首次用户态仍需原生读取/解压、exec认证和映射、实际EL0；桌面还需完整根、服务与图形/输入。239未审用户任务释放门保持，UFS未验收，当前根是RAMDisk/md0。未改受审内存/IPSW身份、未置*_verified=true。HEAD855daaf，无本轮提交/推送/CI；原迁移修改与历史证据保留，新路径/Legacy只读/串行脚本/单写入者规则持续有效。

2026-10-27T14:10:38.5350403+08:00 · 官网顺序复核：驱动依赖、root/Data、先CPU呈现再GPU、分层日志和OS ABI契约已对照；后续按docs/operations/2026-10-27-official-adaptation-sequence.md推进。仅查阅/文档维护，设备暂停，PROBE41与受审输入未变。

2026-10-27T14:14:30.9449713+08:00 · 用户已确认将UniXNU官网内容作为后续开发指南。执行规则已写入设备仓AGENTS.md第0节，固件仓同步引用；按官网依赖/启动阶段/ABI与日志完成条件推进，保留既有用户指令、硬停和证据边界。决策D-071。当前仍仅离线、不操作设备，PROBE41未变。

2026-10-27T14:25:45.9616435+08:00 · 用户要求各阶段具体方法/步骤落为规则：docs/DEVELOPMENT-STAGES.md已定义S00—S13及通用执行方法，两仓AGENTS强制引用，决策D-072。后续按前提、实施、离线/必要实测及完成/失败条件推进；当前阶段状态和证据不变。设备继续暂停，未改PROBE41，未提交。
