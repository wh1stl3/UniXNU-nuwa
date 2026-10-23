# 主线交接：dd1ef825实测后（2026-10-23）

先读AGENTS、STATUS、DECISIONS。设备仓文档前基线c69f538；固件仓codex/nuwa-sec-handoff-trace@150b5ec。用户目标持续推进至XNU，人工恢复不阻塞离线工作。每次硬停必须同步本文、STATUS和NEED-REVIEW/PENDING-HUMAN。

## 实际进度

CI39973030321/source4139464构建成功，本地实际新标记、全41行内存表及完整容器检查通过。HOB-INTEGRITY-OFFLINE scope接入并通过原5项MMU门测试。临时包dd1ef82517d256a44b05b5d72e132fe4a37078e2e12cf82f40302b408886034e/70266880B，仍含64MiB配置探针，不含XNU/ADT。

录像和两张用户原图确认：相同HOB首址BAB00000被不同GUID查询；本次BAB00718是type3 len0x30并推进到BAB00748，Lzma成功，随后进入DXE/UniXNU。不同运行间前包同地址零长度异常未复现，未证实0014修复任何根因。query至少两处，不代表只调用两次。用户未见invalid，审查图片也未见；未逐帧证明全程缺失。

视频35秒为内置菜单/no boot entry found，未见目标探针标题；45秒USB发现回退；71.6秒Android标志。原视频D:/Code/VIdeos-nuwa/dd1ef825.mp4（73.598秒）摘要在reports/hob-integrity-trial/2026-10-23-evening/video-source.json，关键帧及原图已归档同目录。详细解释见2026-10-23-hob-integrity-trial.md。

## 设备状态与待人工

本轮recovery.json等待180秒超时；尚无本轮Android完成1/三分区postcondition。视频Android标志不替代ADB核验。前轮ae9a445a的恢复已完成，但不得当本轮恢复。没有flash/erase/改槽。

## 续接命令及工作

- 继续逐帧读取视频30至32秒NuwaBootMemoryDxe/RamManagerDxe窗口，找NUWA-VOLUME chosen/result/block device或SHENGMEM拒绝信息。已装av/pillow在本聊天work/video-deps，提帧脚本work/read_hob_video.py、extract_volume_window.py；可重建，非仓库依赖。保持原视频只读。
- 查询/恢复：将D:/Code/PortingiOS/common/tools/platform-tools临时加入PATH，以已识别nuwa为目标；需要恢复时运行 `python -B scripts/trial-v4-firmware.py recover --evidence reports/hob-integrity-trial/2026-10-23-evening/recovery-after-keys.json --package reports/hob-integrity/39973030321/package.json`，只用尚不存在的新证据路径。
- Android可用后运行 `python -B scripts/record-nuwa-trial-state.py --output reports/hob-integrity-trial/2026-10-23-evening/postcondition.json --before reports/hob-integrity-trial/2026-10-23-evening/preflight.json`。
- 按卷日志区分ABL运输/映射范围/CRC/BlockIo/配置发现，不直接修改板级内存或把initrd整段取整。探针成功后再做真实XNU预链接和ADT；现有源内核不能当可启动预链接。
- 每次新设备启动前重新确认用户录像、真实nuwa身份、包复验及恢复门，立即通知后启动。只差人工恢复时继续离线，不复试旧包。

两只读旧资料库边界、board/bringup地址容量身份及_verified审阅边界继续有效。固件源码在uefi-nuwa，设备仓固定引用、配置、补丁、证据。当前无要求更改未知板值的操作，不虚构新审批；设备恢复未确认限制下一次启动。
