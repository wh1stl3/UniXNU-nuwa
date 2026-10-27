# STATUS — nuwa（2026-10-28）

本轮收尾获用户明确授权本地提交，不推送、不自动启动下一候选。最新交接：[2026-10-28-session-handoff](operations/2026-10-28-session-handoff.md)；新会话提示：[2026-10-28-new-session-prompt](operations/2026-10-28-new-session-prompt.md)。旧27日及以前交接只用于追溯，已消费启动命令失效。

## 实测与设备状态

PROBE45已单次临时启动、已消费，禁止重发。媒体已归档，Android完成1、nuwa/kalama、A槽及boot_a/vendor_boot_a/init_boot_a三SHA与45预检一致。后验：`reports/xnu-entry-probe-trial/2026-10-27-probe45-cluster/postcondition.json`。这是当次恢复，不是未来启动的新鲜预检。

稳定末态A03D=`FFFFFFF00743CC74`，A03E=0，对应缓存辅助函数RET前。尚不能证明RET完成、整个ResourceFork读取完成或确定死锁。首要排查返回边界观测干扰/遗漏及调用方消费量、预读和收尾；不把44的旧调用前卡点继续当45事实。实际代码、反证、字段含义及证伪范围见[45媒体与46准备](operations/2026-10-28-probe45-media-probe46-progress.md)。

原媒体：`D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE45/original/`；7阶段截图、227源帧/PTS和manifest在同轮`derived/review-01/`。原件未改字节，未上传或提交；未宣称全帧逐字符OCR。按用户约定末态默认稳定，秒数未知。

## PROBE46整包离线合格，未启动／未消费

资格完成时间：2026-10-28T00:54:02.611557+08:00。

| 产物 | 路径或摘要 |
| --- | --- |
| boot镜像 | `out/trial-boot/xnu-entry-probe-46-progress/boot-xnu-first-entry.img` |
| 大小 | 204484608字节 |
| boot SHA256 | `5f05da60910590111089d196dda0160dee2ecccb8cd3112fd6adf977d72c7cbf` |
| 内核SHA256 | `ee2c130fd0e184e4d262f4b0eec86e65c370c3d323413570c761aabe91eca70f` |
| ADT SHA256 | `e5a5cf89e2420db031edaa82c90e74577c6d141938faaed564a763435b7b6cad` |
| 包报告 | `reports/xnu-first-entry/entry-probe-46.json` |
| 最终资格 | `reports/kernel-entry-probe/2026-10-27-probe46-progress/qualification.json` |

38串行作业全部通过：3084指令透明性、2988调用流程（含963专项）、67绑定；另29 x18扰动和9向量连续路径通过。独立内核重编字节一致、整包回读通过。离线夹具不等于真实VM、IO、IRQ或实机通过。

46恢复缓存辅助函数的原生字节，移除内部6钩子；79个cluster位置/128B状态覆盖请求量、残余、预读及收尾。沿用两行、不加网格。`7438C3C`处A03E高32位requested、低32位residual，不是errno。后续ResourceFork、解压、Mach-O/dyld、exec的12对路径已在实际镜像核对；正常续接不中断，原生错误及239保留。扩大范围不代表已修复本次卡点。

## 下一步与未完成项

- 新会话先只读核对HEAD/status及46资格/实际摘要；本次收尾不自动启动46。准备媒体目录`D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE46/original/`已创建。
- 安排46实测时按当轮拍摄/恢复共同确认、新鲜目标/三SHA预检执行一次临时boot。用户明确正在录像可视为同时确认实体键恢复，不机械重复问；存在相反证据仍硬停。45后验仅用于before比较。
- 原生读取、解压、exec、EL0和桌面尚未闭环；OS/Data未接入当前启动路径，Restore用户任务不能放开239。RAMDisk路径不验收UFS；timer/IPI/DMA与完整驱动资格仍分别待验。
- 路径迁移全量入口未重新验收，46只覆盖其实际绑定链。公开最新资料访问403及既有安全拒绝按正式支持/访问复核处理，不改安全配置、不通过新会话绕过。
- 45绑定原始源码快照：`reports/session-closeout/2026-10-28/probe45-source-archive.json`。旧45验证不作用于当前46源码；原镜像、媒体和历史证据保持。
- 两仓既有修改保留；本轮新会话提交权限不能从本次收尾授权自动延伸。out镜像和媒体不在Git内，跨机器接手需另外保留本机文件。

原先累积STATUS快照保存在`reports/session-closeout/2026-10-28/status-before-closeout.md`；不要从快照执行旧启动命令。
