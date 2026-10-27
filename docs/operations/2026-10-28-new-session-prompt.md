接手nuwa主线，先只读核对，不自动启动设备或创建新仓库。

项目根：D:/Code/PortingiOS/nuwa
设备仓：D:/Code/PortingiOS/nuwa/UniXNU-nuwa
固件仓：D:/Code/PortingiOS/nuwa/uefi-nuwa
迁移索引：D:/Code/PortingiOS/PATH-MIGRATION.md
旧资料库D:/Code/PortingiOSLegacy只读；不操作enuma，不启动旧会话或第二个写入者。

先读两仓AGENTS.md、设备仓docs/STATUS.md、docs/operations/2026-10-28-session-handoff.md、docs/operations/2026-10-28-probe45-media-probe46-progress.md，以及DEVELOPMENT-STAGES.md对应阶段。核对两仓git status/HEAD，以实际最新文件与最终qualification为准；旧27日及以前prompt和启动命令仅供追溯，禁止按旧命令重发已消费镜像。

PROBE45已消费、媒体已归档、Android完成1/A槽/三分区SHA恢复后验已闭环。清晰末态A03D=FFFFFFF00743CC74、A03E=0：已到缓存辅助函数RET前，不能认定RET完成、读取完成或死锁。首要排查返回边界的观测干扰/遗漏及调用方消费量、预读和收尾；不要沿用44的旧卡点推断。45原始源码已独立按旧资格SHA归档，不能用46源码冒充45原验证输入。

下一候选PROBE46，内核SHA ee2c130fd0e184e4d262f4b0eec86e65c370c3d323413570c761aabe91eca70f。先核对reports/kernel-entry-probe/2026-10-27-probe46-progress/qualification.json与reports/xnu-first-entry/entry-probe-46.json，再回读实际boot文件摘要。46削减UBC内部钩子，补请求/残余、预读和收尾，继续既有解码、Mach-O/dyld及exec路径；7438C3C处A03E是requested/residual各32位打包，不能当errno。239和Restore根限制保留，无EL0/桌面完成证明。是否已启动以当轮consumed/launch及STATUS为准，不能仅依本prompt。

本次先完成接手核对并报告，不自动启动46。若随后安排实测，按已授权临时启动范围、新鲜目标/三SHA预检及当轮拍摄/恢复条件执行一次；用户明确“正在录像”时已表示能实体键恢复，不机械重复询问。末态照片默认稳定，不逐轮问等待时长。每次实机前已有目录Media-nuwa/PROBE编号/original与derived，原件不改字节、不上传/提交。收到新媒体后持续归档、实际代码分析、修复静态确定项，完成下一包编译和核验；中间问答不打断。

脚本/编译/模拟串行。真实Python和WSL路径见交接。保留现有修改和历史证据；不reset、不自动提交/推送，不重跑要求全新输出目录的历史脚本。上一会话本地收尾提交授权仅用于上一会话。遇权限拒绝/平台阻断停止对应操作，走正式支持/访问复核，不改安全配置或换通道绕过。硬停及官网开发依赖顺序继续执行。
