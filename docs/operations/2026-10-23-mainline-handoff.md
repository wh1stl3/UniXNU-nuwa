# 主线交接：卷发布状态诊断（更新2026-10-24）

先读AGENTS、STATUS、DECISIONS。设备仓文档前基线c69f538；固件仓codex/nuwa-sec-handoff-trace@bc38be0（卷状态修正；原实测包仍为150b5ec）。用户目标持续推进至XNU，人工恢复不阻塞离线工作。每次硬停必须同步本文、STATUS和NEED-REVIEW/PENDING-HUMAN。

## 实际进度

CI39973030321/source4139464构建成功，本地实际新标记、全41行内存表及完整容器检查通过。HOB-INTEGRITY-OFFLINE scope接入并通过原5项MMU门测试。临时包dd1ef82517d256a44b05b5d72e132fe4a37078e2e12cf82f40302b408886034e/70266880B，仍含64MiB配置探针，不含XNU/ADT。

录像和两张用户原图确认：相同HOB首址BAB00000被不同GUID查询；本次BAB00718是type3 len0x30并推进到BAB00748，Lzma成功，随后进入DXE/UniXNU。不同运行间前包同地址零长度异常未复现，未证实0014修复任何根因。query至少两处，不代表只调用两次。用户未见invalid，审查图片也未见；未逐帧证明全程缺失。

视频35秒为内置菜单/no boot entry found，未见目标探针标题；45秒USB发现回退；71.6秒Android标志。原视频D:/Code/VIdeos-nuwa/dd1ef825.mp4（73.598秒）摘要在reports/hob-integrity-trial/2026-10-23-evening/video-source.json，关键帧及原图已归档同目录。详细解释见2026-10-23-hob-integrity-trial.md。

## 设备状态与待人工

recovery.json曾等待180秒超时。2026-10-24已只读ADB确认nuwa/kalama、Android完成1/slot_a及本轮三分区与preflight一致；新postcondition.json记录实际查询时间与命令，恢复闭环已补齐。没有flash/erase/改槽。

## 续接命令及工作

- 继续逐帧读取视频30至32秒NuwaBootMemoryDxe/RamManagerDxe窗口，找NUWA-VOLUME chosen/result/block device或SHENGMEM拒绝信息。已装av/pillow在本聊天work/video-deps，提帧脚本work/read_hob_video.py、extract_volume_window.py；可重建，非仓库依赖。保持原视频只读。
- 查询/恢复：将D:/Code/PortingiOS/common/tools/platform-tools临时加入PATH，以已识别nuwa为目标；需要恢复时运行 `python -B scripts/trial-v4-firmware.py recover --evidence reports/hob-integrity-trial/2026-10-23-evening/recovery-after-keys.json --package reports/hob-integrity/39973030321/package.json`，只用尚不存在的新证据路径。
- Android可用后运行 `python -B scripts/record-nuwa-trial-state.py --output reports/hob-integrity-trial/2026-10-23-evening/postcondition.json --before reports/hob-integrity-trial/2026-10-23-evening/preflight.json`。
- 按卷日志区分ABL运输/映射范围/CRC/BlockIo/配置发现，不直接修改板级内存或把initrd整段取整。探针成功后再做真实XNU预链接和ADT；现有源内核不能当可启动预链接。
- 每次新设备启动前重新确认用户录像、真实nuwa身份、包复验及恢复门，立即通知后启动。只差人工恢复时继续离线，不复试旧包。

两只读旧资料库边界、board/bringup地址容量身份及_verified审阅边界继续有效。固件源码在uefi-nuwa，设备仓固定引用、配置、补丁、证据。当前无要求更改未知板值的操作，不虚构新审批；设备恢复未确认限制下一次启动。

## 2026-10-24离线推进

2026-10-24T00:15:19.951531+08:00：复查19至35秒抽帧仍无可读卷结果，不宣称驱动未调度或定位根因。固件bc38be0实现错误传播/分阶段日志，8项主机C测试通过；volume-status独立profile静态41输入/7补丁/10后哈希通过。正常构建无停留，0015诊断profile最终状态停留5秒；完整CI及产物核验待完成。

直接续接：`python -B scripts/check-volume-status.py`；`gh workflow run firmware-candidate.yml --repo wh1stl3/UniXNU-nuwa --ref main -f profile=volume-status`。运行后记录run id，实际FD/EFI/BootShim验收后使用`python -B scripts/volume_probe_package.py <run> --profile volume-status`打包。新scope VOLUME-STATUS-OFFLINE已接入原严格包校验/录像/恢复门；不使用旧scope绕过。新鲜用户录像门尚未确认，当前只做离线构建。细节见2026-10-24-volume-publisher-status.md。

2026-10-24T00:17:00.937798+08:00：CI39985245383/source b8e6e2a构建中；固件bc38be0。旧产物冒充/录像空值2项反向测试及原5项MMU门回归通过。

## 新包就绪（2026-10-24）

2026-10-24T00:23:43.134759+08:00：CI39985245383成功，FD ff218da4；新状态及全部旧诊断二进制标记通过，41行内存全表与dd1ef825逐字节一致。包a22e9a44561c85c52aa5697d0452c38dc8bdd1f5b2c7c7a40e79f5396a27f9f0/70266880B已复验，reports/volume-status/39985245383/package.json。用户已本轮确认录像/恢复按键准备，刷新preflight后通知并启动。观察窗口>=120秒，恢复和postcondition用新目录reports/volume-status-trial/2026-10-24/，上一轮恢复不代替本轮。

2026-10-24T00:27:22.419670+08:00：本轮a22e9a44在新鲜用户录像确认、preflight及通知后临时启动，fastboot boot exit0，00:26:15（UTC+8）完成120秒USB采样；具体屏幕结果尚待。最后无nuwa fastboot，ADB总数1不当作nuwa或完成1。recovery工具已启动，尚无本轮postcondition，不借用上轮恢复；必要时只差人工按键，继续离线但不启动新包。证据reports/volume-status-trial/2026-10-24/。

2026-10-24T00:39:15.327331+08:00：收到六张原图，确认publisher执行且envelope absent，DTB b5db1000/938800B，chosen [b5fb2000,b7fff1d4)/33870292B。原厂boot恢复后本轮postcondition完成1及三分区SHA一致；恢复待办关闭。固定ABL init_boot选择离线数据流已补，其他报错逐项审查见2026-10-24-error-triage-and-initboot.md。下一步独立embedded-probe（固件00a37d9），43输入/8补丁/12后哈希与9项主机测试通过，CI待启动；不复试旧包。

2026-10-24T00:48:14.773032+08:00：CI39988591973/source b4f9075成功，实际新驱动DEPEX/PE和完整RAW资源SHA通过，FD70b266b3；41行2952B内存表与dd1ef825相同。包87b14624e95a4b608435da96c4a7f939893bef7c94186af9d2f157eacef0e496/3153920B（ramdisk0，FV内含4MiB FAT16）逐字节复验通过。新EMBEDDED-PROBE-OFFLINE scope校验和缺录像/预检时设备子进程前拒绝通过；新增旧包冒充/空录像2项回归通过。用户已本轮确认“可以，继续录像测试”，下一动作刷新preflight、通知后临时启动一次。目标为NUWA-FV-PROBE block Success和探针配置菜单；不是XNU。新证据目录reports/embedded-probe-trial/2026-10-24/。
