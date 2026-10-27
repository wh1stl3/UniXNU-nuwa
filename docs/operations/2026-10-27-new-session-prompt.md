接手nuwa主线，目标是依赖顺序推进iOS16用户态/桌面。不要新建仓库，不操作enuma，不启动旧会话或第二写入者。项目根D:/Code/PortingiOS/nuwa，设备仓UniXNU-nuwa，固件仓uefi-nuwa；旧资料库D:/Code/PortingiOSLegacy只读。

先读D:/Code/PortingiOS/PATH-MIGRATION.md、两仓AGENTS.md、设备仓docs/STATUS.md、docs/operations/2026-10-27-session-handoff.md，以及docs/DEVELOPMENT-STAGES.md的通用方法和当前S03/S05/S12/S13。按最新实际文件核对，旧交接按需追溯，不把历史状态当当前。官网是开发指南；离线只指不上机，公开资料仍需参考，但遇访问拒绝停止对应访问，不能换通道绕过。

PROBE43已消费，用户媒体已回收且照片稳定超过十秒；postcondition确认Android完成1/A槽/三分区SHA未变。末态A03D=FFFFFFF00519CC10，已到APFS handler内属性处理调用前，尚无519CC48入口/内部返回证明，不能断言死锁或UFS故障。首要疑点是属性处理与ResourceFork vnode查找/读取链。

PROBE44已完成离线资格、未启动/未消费。镜像D:/Code/PortingiOS/nuwa/UniXNU-nuwa/out/trial-boot/xnu-entry-probe-44-chain/boot-xnu-first-entry.img，SHA256 b8e2395576460b8296589ea92a6cfa6b73f34abc4fe04090f0c982d3b6d38030。包报告reports/xnu-first-entry/entry-probe-44.json，资格reports/kernel-entry-probe/2026-10-27-probe44-chain/qualification.json。38串行作业通过，独立内核重编字节一致，整包回读通过。新增68位置覆盖属性/lookup/read三层；239、Restore根和原生锁/错误保留，未证明EL0。详情见2026-10-27-probe43-media-probe44-chain.md。

先只读核对两仓HEAD/status与44摘要，避免重跑已完成的大套回归、覆盖既有输出或重发43。此prompt不触发自动启动。实机前须有当轮拍摄/实体键恢复条件、新鲜nuwa目标/三SHA预检和代码最大疑点/证伪报告；持续临时启动授权不包括flash/erase/改槽、受审内存/基址/IPSW身份或verified=true。遵守AGENTS硬停规则。

媒体按D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE编号/original及derived存放；每轮实机前预检自动建目录，PROBE44/original已建好。1397文件已迁移且SHA一致，旧manifest按根目录media-path-migration-2026-10-27.json追溯，不改原证据。收到新媒体后连续完成归档、实际代码分析、下一包准备/编译/核验再结束；中间问答不打断主线。

脚本/编译/模拟串行，真实Python路径见交接；不操作设备时仍可推进不依赖实机的确定性工作。保留所有现有修改，不reset、不自动push。本次旧会话已获用户明确授权本地收尾提交；新会话提交按当时指令。遇权限拒绝或平台阻断停止对应操作，走正式支持/访问复核，不改安全配置或借新会话绕过。
