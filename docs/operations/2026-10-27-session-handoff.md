# nuwa 会话封存交接 — PROBE44未消费

本文件是2026-10-27会话结束时的精简入口，当前状态优先于旧交接中的过程快照。用户本次明确要求落地所有文档并提交；本次允许本地检查点提交，不包含push或设备启动。不是历史验证重跑，也不授权把verified置真。

## 工作区与版本

- 项目根：`D:/Code/PortingiOS/nuwa`。
- 设备仓：`D:/Code/PortingiOS/nuwa/UniXNU-nuwa`，本次检查点之前HEAD为`855daaff4cb99fdeec43dac6ec5045c1d591f52c`。本文件随设备仓本地检查点提交，实际提交号以`git log -1 --format=fuller`为准。
- 固件仓：`D:/Code/PortingiOS/nuwa/uefi-nuwa`，资料收尾提交`2affc24864bf520bf6c830f704415dd655accf8e`，分支`codex/nuwa-sec-handoff-trace`；没有改变已验收镜像的固定固件输入。
- 迁移索引：`D:/Code/PortingiOS/PATH-MIGRATION.md`。
- 旧资料库：`D:/Code/PortingiOSLegacy`，只读；不操作enuma，不创建新仓库，不启动旧会话或第二写入者。
- 原媒体：`D:/Code/PortingiOS/nuwa/Media-nuwa`，本地留存，不纳入Git或上传。

## 先读这些

1. 两仓AGENTS.md、设备仓docs/STATUS.md、本交接。
2. docs/DEVELOPMENT-STAGES.md通用方法及当前S03/S05/S12/S13；官网为开发指南，但示例身份/内存/verified值不是nuwa事实。
3. docs/operations/2026-10-27-probe43-media-probe44-chain.md：最新实测、最大疑点、44范围、证伪结果。
4. docs/operations/2026-10-27-probe42-x18.md：上一轮渲染修复及离线扰动边界。
5. 需要OS/Data背景时读2026-10-27-mainline-reassessment.md、root-data-service-contract.md、desktop-cache-closure.md、linux-apfs-data-candidate.md；不把目录种子或静态库闭包当作用户态通过。

## 当前实测事实

- PROBE43已单次临时启动、已消费，禁止重发。用户已提供媒体并恢复Android。
- `reports/xnu-entry-probe-trial/2026-10-27-probe43-handler/postcondition.json`确认nuwa/kalama、Android完成1、A槽，boot_a/vendor_boot_a/init_boot_a摘要与43预检一致。这是最后已记录后验，不是未来启动的新鲜预检。
- 用户确认照片前稳定超过十秒；原照片及视频末帧可见A03D=`FFFFFFF00519CC10`。43处理函数观测已从wrapper分派推进到APFS handler内部的属性处理调用前。
- 原生下一条目标是`FFFFFFF00519CC48`；尚无其入口及内部返回的实测证明。最后记录不是停止PC，稳定显示不证明CPU停止或死锁。
- 原生`519CBD4`条件辅助路径已被跳过或完成，不能继续把它当当前停止位置。最大疑点是属性处理与ResourceFork vnode查找/取数链未完成可观察返回；锁、缓存读取、属性重试及观测干扰仍待区分。
- 当前`rd=md0`为RAMDisk根；`_cluster_read`存在于实际读取函数内，不等于本轮访问UFS，不以此验收或指认UFS。

## PROBE44：离线完成，未启动/未消费

| 产物 | 当前值 |
| --- | --- |
| boot镜像 | `out/trial-boot/xnu-entry-probe-44-chain/boot-xnu-first-entry.img` |
| 大小 | 204484608字节 |
| boot SHA256 | `b8e2395576460b8296589ea92a6cfa6b73f34abc4fe04090f0c982d3b6d38030` |
| 内核 | `out/kernel-entry-probe-44-chain/kernel-entry-probe.macho` |
| 内核SHA256 | `49b913fc15e1517c51acc57af919c76d32187a1258a3a9fbb7f4890ebe2c74f1` |
| ADT | `out/exec-probe44-chain/launch/kernel.macho.adt` |
| ADT SHA256 | `260e212658598fa21732d7d14f7e75fcf5974e5f8918ca70df12148991d861c7` |
| 包报告 | `reports/xnu-first-entry/entry-probe-44.json` |
| 最终资格 | `reports/kernel-entry-probe/2026-10-27-probe44-chain/qualification.json` |

68个新增位置/96B状态覆盖属性处理519CC48、ResourceFork vnode lookup519D350、文件read519C2A4的入口/返回及31个重要调用。父子调用验证read线程、配对位、帧及saved LR。沿用A03D/E两行、不加网格；原生锁/错误/IO、239门及Restore根保留，顺利返回后继续既有解压/exec路径。当前工作增加定位能力，未证明原生卡点已修复。

38项串行作业全部通过：2768透明性、2025调用流程（含818新增）、67绑定；另29项x18扰动、9项向量准备连续路径、6项媒体目录检查通过。独立内核重编逐字节一致、整包回读通过。Unicorn/夹具不是完整APFS执行、物理中断或实机资格。既有WSL/GBK stderr读取异常保留，不能称日志完全正常。

原生读取/解压/exec及EL0还未闭环，正常OS/Data provider和挂载尚未接入。Restore镜像不能据此释放239，不能跳过错误、锁或认证，不能把添加观测点写成用户态进度。

## 媒体规则与历史证据

原件按`Media-nuwa/PROBE编号/original/`存放，派生材料按同轮`derived/review-编号/`；修订轮如PROBE41-r5保持独立。1397文件移动前后SHA一致；`Media-nuwa/media-path-migration-2026-10-27.json`提供旧→新路径。历史manifest保留原文，不能改写原件、旧转录或重算历史摘要伪装原验证。

下一轮投放目录`D:/Code/PortingiOS/nuwa/Media-nuwa/PROBE44/original/`已建好。`record-nuwa-trial-state.py`在XNU包预检设备查询前通过`trial_media.py`创建轮目录并记录位置；同名原件不覆盖。每轮保留菜单触发前开始的短视频和稳定态清晰照片，源PTS与抽样帧区分，没拍到不等于没执行。

本地外部文档的逐字节快照在`reports/session-closeout/2026-10-27/`：路径迁移索引、媒体README和媒体迁移JSON；不包含原始图片/视频。构建镜像、out/临时脚本仍只在本机；Git提交不能替代本机产物备份。

## 执行方式与硬停

- 真实Python：`C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe`，使用`-B`。
- 每条命令显式cwd为设备仓；工具串行：脚本、编译、模拟测试不并跑。ffmpeg在PATH；adb/fastboot使用`D:/platform-tools-latest-windows/platform-tools`，仅修改当前进程PATH。
- 会话里的中间问答/状态询问不取消主线任务。收到媒体后直接归档、实际代码分析、准备/编译/核验下一包再结束；不能只交分析等待“继续”。
- 每次实机前充分分析实际代码，报告最大疑点、支持/反对证据及证伪范围；临时启动已有持续授权，但当轮拍摄/实体键恢复和新鲜目标预检仍必须满足，不沿用43的旧现场确认。
- 硬停：修改受审内存/基址/IPSW身份；缺失实际观测或恢复条件却要启动；任何`*_verified=true`。flash/erase/改槽需要具体授权及依据。
- 239边界保留；已消费候选不重发。等待人工恢复时继续无设备依赖的离线工作。
- 不自动push。用户本次提交授权仅用于本次会话收尾；未来提交按当时指令。

## 新会话先做什么

先核对两仓`git status`、当前HEAD与44产物摘要，读取资格及本交接。没有新改动/失败时不重跑整套38作业，也不要重跑会拒绝既有输出的收尾脚本。

只读回读包可执行：

```powershell
Set-Location -LiteralPath 'D:/Code/PortingiOS/nuwa/UniXNU-nuwa'
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B scripts/build_xnu_boot_package.py --validate --output reports/xnu-first-entry/entry-probe-44.json
```

若安排44实测，先确认当轮现场条件，再用现有record-nuwa-trial-state.py生成全新43后验对比预检，随后trial-v4-firmware.py仅发送44一次，消费标记/状态同步，再回收媒体及Android三SHA后验。此段是条件式续接，不是本交接自动启动授权。新会话默认先做只读核对。

若收到44媒体：优先看属性入口、lookup/read调用及返回、cluster_read前后、519D2AC/519CC14/wrapper续接，再按原生错误和解压/exec轨迹更新归因，继续完成下一候选的离线交付。

## 未完成验证与访问复核

路径迁移包含既有文档、脚本和配置修改。本次检查点保留全部这些修改，旧测试不自动验收迁移后的所有入口。44依赖链已按当前路径通过，不等于历史固件/CI/所有迁移脚本均已复验；需要时按任务串行补验，不改Legacy或重算旧摘要。

公开资料搜索曾返回403，停止对应访问，没有换通道绕过；本轮没有完成新的在线资料核验。若继续无法访问，走正式服务/访问复核；不把旧网页缓存当最新验证。旧资料库Git安全拒绝不得通过safe.directory或安全配置绕过。

含空目录清理的组合命令曾被自动审批拒绝，只返回blocked by policy，无具体原因。该命令未执行，旧空derived目录保留；不重试清理、不改安全配置。此前平台风险拦截不是可在新会话忽略的授权；出现新的阻断时停止对应操作并记录，按正式支持/访问复核处理。

本次Git检查点会保留有绑定关系的源文件/报告原字节，通过精确路径.gitattributes避免换行转换；不重写历史报告来适配Git。语法检查仅覆盖待提交Python文件，不替代迁移全量验收或新的实机结果。
