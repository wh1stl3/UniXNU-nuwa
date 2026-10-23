# 主线交接：零长度HOB诊断与启动卷接入（2026-10-23晚）

当前基线设备仓main@4139464，固件仓codex/nuwa-sec-handoff-trace@150b5ec。当前无新增硬停；用户明确要求持续离线推进，实际设备动作仍须日志与恢复门。先读AGENTS、STATUS、DECISIONS。本文件替换早先过期的MMU入口交接。

## 当前实机与恢复

最近临时包ae9a445a119fd98f386f79a177b2cdef73f086a57d1e398edde75c7049f57132，70266880B，含64MiB配置探针，未含XNU/ADT。原图显示ptr=BAB00718 type=0 len=0重复至row127，随后log-limit。原GET_NEXT_HOB按HobLength推进，零长度导致原地循环；未定位零条目来源，不宣称是载荷或缓存根因。

用户已回fastboot；recovery-after-keys.json记录原厂boot临时加载并Android完成1；postcondition.json确认真实nuwa/kalama、A槽、boot_a/vendor_boot_a/init_boot_a三分区SHA与本次preflight一致。证据reports/volume-envelope-trial/2026-10-23-evening/。不把此记录视为后续启动前的新鲜检查。

## 已完成

- 0012 MMU分支、0013 HOB查询日志接入profile/CI，前轮47b5c4b1曾进入DXE及UniXNU，原图可见SHENGMEM拒绝整initrd扇区长度，四条FAT挂载来源未确定。
- uefi-nuwa@150b5ec接收64字节版本化长度/CRC封装；FDT和initrd限于既有Kernel保留映射，不改板地址。7项C主机测试及真实64MiB FAT配合模拟非对齐前缀解析通过。CRC仅检测传输损坏。
- CI39966008923成功，volume-envelope实际FD 3c653d1e；41行2952B内存表与R011一致。完整容器逐字节复验通过，但该次实机卡在前述零HOB，未到卷发现。
- 0014新增非法长度日志及CpuDeadLoop，查询打印GUID与PHIT end/bottom/top；它是停在损坏现场的诊断，不跳过HOB或伪造返回。
- hob-integrity profile的41输入/6补丁/9后哈希通过。CI39973030321已查询确认success，源4139464。该次产物尚未下载/本地核验/打包/实测。

## 接续工作与命令

1. 下载新固件：`gh run download 39973030321 -R wh1stl3/UniXNU-nuwa --dir out/firmware-ci/39973030321`。
2. 用scripts/ci/inspect-firmware-candidate.py检查实际FD（publisher NuwaBootMemoryDxe，sec/no-auto/allocation全部启用，allocation-profile hob-integrity），额外核验实际SEC包含NUWA-HOB-CHECK新标记；目前检查器尚未强制新标记，应补齐。
3. 扩展scripts/volume_probe_package.py以明确支持hob-integrity的源/profile/scope；当前脚本限定volume-envelope，不可把新产物冒充旧profile。保留旧包可复验性。补齐对应preflight/trial严格scope。
4. 核验0014实际控制流、完整内存表、整镜像头/载荷/零填充。生成新包后更新STATUS/交接及提交，再通知用户录像、刷新真实nuwa身份与恢复门后试验。
5. 重点取得完整查询入口GUID/PHIT及invalid日志和发生前阶段；若链损坏早于查询，追踪构造器前后的创建与覆盖。不要仅跳过零长度条目继续MMU。
6. 卷探针菜单验证后才接真实内核预链接和ADT。现有源内核77742999不等于可直接启动的预链接内核；ADT/owned-memory未知板值仍受审阅边界约束。

## 权限与停点纪律

D:/Code/PortingiOS和PortingiOSWithUniXNU只读；固件源码在uefi-nuwa，设备仓存固定引用、补丁和证据。board/bringup内存地址容量及身份、*_verified不得默改。无flash/erase/改槽。

用户要求：每次硬停先落档STATUS、本文、NEED-REVIEW/PENDING-HUMAN，说明原因、设备状态、证据、待办和续接命令；人工恢复等待期间继续离线工作。每次设备试验先确认可拍摄日志与可恢复路径，通知后才启动。
