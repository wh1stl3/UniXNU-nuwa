# nuwa 新会话交接（2026-10-28）

## 最终离线交付（2026-10-28T00:54:02.611557+08:00）

PROBE46 boot为`out/trial-boot/xnu-entry-probe-46-progress/boot-xnu-first-entry.img`，204484608字节，SHA256 `5f05da60910590111089d196dda0160dee2ecccb8cd3112fd6adf977d72c7cbf`；内核SHA `ee2c130fd0e184e4d262f4b0eec86e65c370c3d323413570c761aabe91eca70f`。38项串行作业、3084透明性、2988调用流程（包含963专项）、67绑定全部通过；另29 x18和9向量连续路径通过，独立内核字节复现与整包回读通过。本轮execution.json的38条stderr均为空；历史WSL/GBK异常仍留在旧报告，不写成当前失败。

实际镜像已核对后续6段目标、12对exec/dyld调用与续接及239条件边界，见同目录expanded-trial-objectives.json。46未启动/未消费，当前45已恢复Android；不存在新增实机或EL0完成结论。45原镜像、媒体、原资格和绑定源码均保留，快照清单见reports/session-closeout/2026-10-28/probe45-source-archive.json。PROBE46媒体目录已按实际包创建。


以本文件、docs/STATUS.md和最新资格报告为当前入口。2026-10-27及以前交接中的44/45启动、未消费、待媒体/恢复描述均为历史，不得直接执行旧续接命令。本轮用户明确要求所有文档、本地提交和新会话prompt；这次提交不包含push或下一轮设备启动。

## 工作区及规则

- 项目根`D:/Code/PortingiOS/nuwa`；设备仓`D:/Code/PortingiOS/nuwa/UniXNU-nuwa`；固件仓`D:/Code/PortingiOS/nuwa/uefi-nuwa`。
- 迁移索引`D:/Code/PortingiOS/PATH-MIGRATION.md`；Legacy只读，不操作enuma、不建仓、不启动旧会话或第二个写入者。
- 先读两仓AGENTS.md、STATUS、本交接，以及DEVELOPMENT-STAGES.md通用方法和S03/S05/S06/S12/S13。必要时补S04依赖。
- 用户的离线指不用实机，仍参考公开原始资料；已固定本地原始资料可继续使用，但不得把旧来源称为最新联网验证。已有公开访问403缺口和Legacy Git安全拒绝不通过换通道或safe.directory绕过；出现新阻断，停止对应操作，按正式支持/访问复核处理。
- 脚本、编译和模拟串行。文件阅读及文档维护可在测试进程运行时进行。不要为了“继续”重跑完整已合格回归。
- 原始媒体只留本地，不提交/上传；历史原件、报告及绑定摘要不改写。原路径用迁移索引追溯。

## 最新实测：PROBE45已消费并恢复

45实际镜像SHA `e6a9494cb05992142032ddc80e42e9ca247f249ad373d7fefc398f382605902d`，内核SHA `2935ab6e53067a5daa4156510e158f3eebe765c50592abbd4b617375c2f05247`。禁止重发45及此前已消费候选。

`reports/xnu-entry-probe-trial/2026-10-27-probe45-cluster/{preflight,launch,consumed,postcondition}.json`构成45启动及恢复链。postcondition确认nuwa/kalama、Android完成1、A槽和三分区摘要不变。新会话不能把此后验当未来启动的新鲜预检。

45原视频/照片在`D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE45/original/`。同轮`derived/review-01/`保留7个用户阶段、227源帧、源PTS及manifest，未宣称全部帧逐字符OCR。末态默认稳定，未给秒数就记未知，不再追问。

清晰末态A03D=`FFFFFFF00743CC74`，A03E=0：缓存辅助函数RET前已到达，不等于RET完成、缓存数据读完或死锁。首要排查返回边界的观测干扰/遗漏，其次是缓存消费量、预读与收尾进度；不能继续仅根据44的调用前画面认定UPL/IO阻塞。实际代码及反证见`2026-10-28-probe45-media-probe46-progress.md`。

## 下一候选：PROBE46

内核`out/kernel-entry-probe-46-progress/kernel-entry-probe.macho`，SHA `ee2c130fd0e184e4d262f4b0eec86e65c370c3d323413570c761aabe91eca70f`。包报告`reports/xnu-first-entry/entry-probe-46.json`，最终资格`reports/kernel-entry-probe/2026-10-27-probe46-progress/qualification.json`。最终boot摘要、时间及完成结果见STATUS与资格；只有最终资格存在且匹配实际文件才可部署，不以本段路径代替资格。

46移除缓存辅助函数内部6个观察钩子并核验原生函数字节；cluster观察改为79位置/128B状态，补请求量、残余、预读与锁/等待/收尾。7438C3C处A03E高32位requested、低32位residual，不是errno；其它特殊字段见操作记录。延续已有ResourceFork→type4解码→Mach-O/dyld→exec控制流，保持原生错误与239受控释放门，未证明EL0/桌面。

新旧源码不能混用：`reports/session-closeout/2026-10-28/probe45-source-archive.json`及同目录probe45-bound-sources保存45资格绑定的原始源码，SHA必须对应原45报告。46代码不是45的原验证输入；45历史检查不重跑、不重算冒充当前通过。

## 后续如何操作

默认先只读核对两仓HEAD/status、46最终资格及镜像摘要。当前设备已恢复Android，本次收尾不自动上机。若用户安排46实测：先报告最大疑点和证伪范围（已有操作记录可直接复核），确认当轮拍摄/恢复条件及新鲜目标/三SHA预检，再单次临时启动。用户已明确“都在录像了，肯定能恢复”，同一轮明确正在录像可作为拍摄与实体键恢复的共同确认，不机械重复询问；若有相反证据或实际条件缺失仍硬停。

新鲜预检的before使用45 postcondition，package使用entry-probe-46.json，输出全新`reports/xnu-entry-probe-trial/<执行日期>-probe46-progress/preflight.json`。预检自动创建`D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE46/original/`及derived。启动只走现有trial-v4-firmware.py launch，一次fastboot boot；不flash/erase/改槽。ACK只证明传输，菜单电源Enter后才有内核过程录像。消费记录与STATUS/交接必须同步，已消费不重发。

收到46媒体后：先补恢复后验，原件单独归档；核对调用方7438C38/7438C3C的返回与消费量，结合预读、UPL/IO、收尾及后续解码/exec做实际代码分析。能静态确定的问题先修，随后直接完成下一候选编译核验，除非真实硬停；中间问答不取消任务。不要只增加探针或把每轮最后位置当独立故障。

硬停仍是受审内存/基址/IPSW/板值变化、缺乏实际观测或恢复条件、任何*_verified=true；flash/erase/改槽另需具体目标和恢复依据。当前Restore根不允许释放239。OS/Data接入、真实用户态、平台timer/IPI/DMA独立资格仍未完成，不能宣称桌面可用。

## 工具与续接限制

真实Python：`C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe`，加`-B`；Windows python别名不是本项目运行时。ffmpeg在PATH，adb/fastboot目录`D:/platform-tools-latest-windows/platform-tools`只加入当前进程PATH。WSL Ubuntu-22.04使用既有clang/ld.lld。

每条执行命令明确cwd为设备仓。所有历史finalize/prepare脚本通常要求输出目录不存在，不能原地重跑覆盖；修复或新证据要另建对应输出。固件当前为固定FD/shim输入，没有因文档HEAD变化重编；固件仓本次若无变更无需空提交。

旧大范围迁移没有全量复验；46只验其绑定依赖链。旧WSL/GBK日志异常按原报告保留；当前日志按本轮实际结果描述。仍缺的公开最新资料/访问复核、OS/Data、完整用户态与各驱动实机资格见操作记录和STATUS。Git不含out镜像或原媒体，换机器须另行备份本机产物。

## 收尾校验提示

Git暂存源码/证据逐字节审计通过；初次文档助手因默认GBK读取UTF-8中文失败，已仅修正out助手的显式编码并完成，原失败及初次暂存清单保留，最终清单/字节审计另存final版本。没有改镜像或重写运行检查来消除该宿主文档错误。

`git diff --cached --check`仍报告`scripts/resource_cluster_sites.py:97`一处行尾空格。它是非执行格式提示，保留当前已绑定源码字节；没有屏蔽该检查、改写已有摘要或把格式检查称为通过。后续真正修改该源码时可清理并按新候选重新绑定。38项回归、专项、独立重编及整包回读通过与此格式提示分别记录。

最终提交号和两仓清洁状态记录在项目根`D:/Code/PortingiOS/nuwa/SESSION-CLOSEOUT-2026-10-28.json`（提交后生成，不入本次Git）。前一日receipt是历史快照，不覆盖。