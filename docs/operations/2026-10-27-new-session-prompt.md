> 历史入口已更新（2026-10-28）：当前状态与续接请读`2026-10-28-session-handoff.md`及`2026-10-28-new-session-prompt.md`。PROBE44/45均已消费并恢复，下面的未启动、待恢复及启动命令仅供历史追溯，禁止直接执行。PROBE46是否可部署以最新STATUS、实际qualification和消费记录为准。

## 最新：PROBE45已单次临时启动，待媒体与恢复后验（2026-10-27T23:28:53.8339879+08:00）

用户确认正在录像且实体键恢复已准备好。新鲜预检确认nuwa/kalama、Android完成1、A槽、三分区SHA与44后验一致。fastboot Sending/Booting OKAY（4.566秒/0.112秒），仅证明传输接受，不证明内核执行。

45已消费，禁止重发。镜像SHA e6a9494cb05992142032ddc80e42e9ca247f249ad373d7fefc398f382605902d。证据：reports/xnu-entry-probe-trial/2026-10-27-probe45-cluster/{preflight,launch,consumed}.json。当前等待菜单电源Enter后的录像、稳定照片及Android恢复后验，不能沿用启动前Android状态。媒体目录：D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE45/original/。本轮覆盖UBC/UPL/IO读取及既有解码、Mach-O/dyld、exec续接；239保留。无flash/erase/改槽、提交或推送。

下方45未启动/未消费描述为历史快照，已由本记录取代。

## 最新续接：PROBE44已消费并恢复，PROBE45整包完成

44 postcondition确认Android1/A槽/三SHA不变；末态A03D=FFFFFFF00519C49C，已到APFS read内cluster_read调用前，未证明callee入口或具体死锁。用户声明今后末态照片均稳定后拍摄，不再逐轮询问稳定性/秒数，未知秒数保留未知。

45未启动/未消费，镜像out/trial-boot/xnu-entry-probe-45-cluster/boot-xnu-first-entry.img，SHA e6a9494cb05992142032ddc80e42e9ca247f249ad373d7fefc398f382605902d。38作业、独立重编、整包回读已通过；最终资格reports/kernel-entry-probe/2026-10-27-probe45-cluster/qualification.json。沿用239及Restore根，无EL0证明。原件目录Media-nuwa/PROBE45/original已创建，启动前仍需新鲜预检与当轮拍摄/恢复条件。本轮新改动未提交。优先读2026-10-27-probe44-media-probe45-cluster.md与STATUS顶部；下方44未消费、待媒体/恢复或默认不启动等是旧会话快照，不得按它重发44。


## 当前更新：PROBE44已单次临时启动，待媒体及Android恢复（2026-10-27T22:09:00.4304633+08:00）

用户本轮明确批准44直接启动，并确认连续拍摄与实体键恢复条件均已准备好。新鲜预检确认nuwa/kalama、Android完成1、A槽及三分区SHA与43后验一致；fastboot Sending/Booting OKAY，传输4.562秒、Booting 0.112秒。这是传输接受证据，未证明内核或目标读取链执行。

44已消费，禁止重发；当前等待媒体及Android恢复后验，不能把启动前Android1或43后验写成44恢复完成。原件投放目录D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE44/original/已由预检确认。证据reports/xnu-entry-probe-trial/2026-10-27-probe44-chain/{preflight,launch,consumed}.json。镜像SHA b8e2395576460b8296589ea92a6cfa6b73f34abc4fe04090f0c982d3b6d38030；239保留，无flash/erase/改槽，本轮未提交/推送。

下方“44未启动/未消费”和“默认只读不启动”均是此前封存快照，已被本轮用户指令及消费记录更新；不得按旧prompt重发44。收到媒体后继续归档、分析与下一包离线交付。
接手nuwa主线，目标是依赖顺序推进iOS16用户态/桌面。不要新建仓库，不操作enuma，不启动旧会话或第二写入者。项目根D:/Code/PortingiOS/nuwa，设备仓UniXNU-nuwa，固件仓uefi-nuwa；旧资料库D:/Code/PortingiOSLegacy只读。

先读D:/Code/PortingiOS/PATH-MIGRATION.md、两仓AGENTS.md、设备仓docs/STATUS.md、docs/operations/2026-10-27-session-handoff.md，以及docs/DEVELOPMENT-STAGES.md的通用方法和当前S03/S05/S12/S13。按最新实际文件核对，旧交接按需追溯，不把历史状态当当前。官网是开发指南；离线只指不上机，公开资料仍需参考，但遇访问拒绝停止对应访问，不能换通道绕过。

PROBE43已消费，用户媒体已回收且照片稳定超过十秒；postcondition确认Android完成1/A槽/三分区SHA未变。末态A03D=FFFFFFF00519CC10，已到APFS handler内属性处理调用前，尚无519CC48入口/内部返回证明，不能断言死锁或UFS故障。首要疑点是属性处理与ResourceFork vnode查找/读取链。

PROBE44已完成离线资格、未启动/未消费。镜像D:/Code/PortingiOS/nuwa/UniXNU-nuwa/out/trial-boot/xnu-entry-probe-44-chain/boot-xnu-first-entry.img，SHA256 b8e2395576460b8296589ea92a6cfa6b73f34abc4fe04090f0c982d3b6d38030。包报告reports/xnu-first-entry/entry-probe-44.json，资格reports/kernel-entry-probe/2026-10-27-probe44-chain/qualification.json。38串行作业通过，独立内核重编字节一致，整包回读通过。新增68位置覆盖属性/lookup/read三层；239、Restore根和原生锁/错误保留，未证明EL0。详情见2026-10-27-probe43-media-probe44-chain.md。

先只读核对两仓HEAD/status与44摘要，避免重跑已完成的大套回归、覆盖既有输出或重发43。此prompt不触发自动启动。实机前须有当轮拍摄/实体键恢复条件、新鲜nuwa目标/三SHA预检和代码最大疑点/证伪报告；持续临时启动授权不包括flash/erase/改槽、受审内存/基址/IPSW身份或verified=true。遵守AGENTS硬停规则。

媒体按D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE编号/original及derived存放；每轮实机前预检自动建目录，PROBE44/original已建好。1397文件已迁移且SHA一致，旧manifest按根目录media-path-migration-2026-10-27.json追溯，不改原证据。收到新媒体后连续完成归档、实际代码分析、下一包准备/编译/核验再结束；中间问答不打断主线。

脚本/编译/模拟串行，真实Python路径见交接；不操作设备时仍可推进不依赖实机的确定性工作。保留所有现有修改，不reset、不自动push。本次旧会话已获用户明确授权本地收尾提交；新会话提交按当时指令。遇权限拒绝或平台阻断停止对应操作，走正式支持/访问复核，不改安全配置或借新会话绕过。
