# S05/S06：完整根窗口、Data来源与服务契约

2026-10-27，继续按依赖顺序离线推进，不使用设备。依据AGENTS第0/6/8节及DEVELOPMENT-STAGES的S05/S06方法。未改板值、启动参数、内核、镜像、认证或239门；PROBE41仍未消费。不提交/推送，不操作其它机型或第二写入者。

## 本轮交付

- `out/desktop-root-contract-20261027-r2/assembly-contract.json`：机器可读的根/Data/所选服务契约，明确`deployable=false`，不含设备操作命令。
- 同目录`os-var-source.tar`：固定OS中`/private/var`的初始来源材料，161个目录、36个文件、1个链接，文件内容589907字节；实际归档回读的名称、mode、uid/gid、文件摘要和链接目标一致。SHA256 `100ab22088446f9cb224fff6e4721bbd343f71b8f8e3993a5198607cd4a99c83`。
- 新增9个脚本/模块：根几何/服务契约、Data来源导出、通用Mach-O检查及其命令/测试入口。15项根/服务检查、9项来源包检查、9项服务格式检查通过，共33项；项目脚本始终串行。
- 最终报告`reports/desktop-readiness/2026-10-27-contract-r1/{audit-r2,data-source-r2,service-layers-r2}.json`，统一绑定`qualification-r2.json`。原失败和中间结果保留，不能套用给新源码。初版qualification将Mach服务数量误写为逐属性Count数组；r2仅修正计数字段及文档绑定，原文件保留，不改变测试和来源结果。

## 根窗口契约：必须区分DMG字节与原始磁盘字节

官网当前路径保留原始磁盘内容，通过SHNGROOT窗口发布，不是把上一轮虚拟文件树直接复制成可启动根。虚拟命名空间仍是静态依赖模型；尚未实现挂载/组装策略。OS为带LZFSE块的UDIF，SystemOS/AppOS没有koly尾，按原始磁盘字节核对。

| 项目 | 当前实际值 |
| --- | --- |
| OS下载文件 | 4730814044字节 |
| OS解码磁盘几何 | 5635081728字节；3638个块连续覆盖，其中3266个LZFSE、369个raw、3个ignore |
| SystemOS原始窗口 | 2743074816字节；SHA256 `9cd738f3b0169055549df84ad6d8d13e50a2da39af618ce0522ca4e06df86849` |
| 拟定OS窗口起点 | 1048576字节 |
| 拟定SystemOS窗口起点 | 5637144576字节，按1 MiB对齐 |
| 两窗口总预览长度 | 8380219392字节，含头和对齐；不含Data、日志及存储保留 |
| 目标分区容量/适配结果 | 均未知，保持null；未引用其它机型GPT或把历史值当本轮预检 |

已经检查UDIF尾、plist/mish表、压缩块存储范围及逻辑覆盖；**没有解码OS数据块，OS原始磁盘摘要仍未知**。DMG的固定摘要不能填充原始窗口摘要。没有生成SHNGROOT镜像或写入设备；root UUID、nuwa发布/匹配路径及Data/log容量仍须具体验证。AppOS有独立10485760字节原始输入，当前两窗口预览不暗示它可省略，App服务路径需独立挂载/供应契约。

## 服务、身份与路径

重新读取同一实际主配置`/System/Library/xpc/launchd.plist`，保持原始文件SHA；532项作业、1668个Mach服务名、36个重复声明服务名、63条路径声明。没有把提供端口的声明当成消费者依赖，未生成服务启动拓扑；重复声明可能涉及会话/条件，不能自动删重。本配置未发现显式KeepAlive.OtherJobEnabled关系。

选取10项桌面/基础服务作详细记录：SpringBoard、backboardd、runningboardd、cfprefsd、containermanagerd、trustd、lsd、logd、notifyd、securityd。其OS程序路径均存在。实际声明的用户/组可在OS静态passwd/group中找到；SpringBoard/backboardd的mobile为UID/GID 501。省略UserName/GroupName的项仍记为launchd默认未显式声明，不伪造配置。静态身份表不代替运行中的目录服务查询，报告不保存密码列。

**containermanagerd不能按普通字符串数组直接展开。** 参数下标1/4/6为`#IfFeatureFlagEnabled: containermanagerd/user_system_split`的Then/Else结构，分别涉及runmode、bundle-container-mode和system-container-mode。已保留原结构和规范化作业摘要；没有手选分支或改配置。全主配置有10处此类功能开关条件，已读取可找到的3份域默认plist；containermanagerd默认文件没有`user_system_split`项，不能由此断言运行时为false。原生解释器、其它默认/覆盖来源及消费者仍未核验。

OS单层有13个程序路径未找到，其中9个实际在SystemOS/AppOS中，已只读解析并核对程序摘要：8个通用Mach-O、1个thin，均有ARM64-all输入；没有以ARM64e切片替代。本轮这9项直接load-command库路径均在既有缓存索引中，但未作新增服务的递归符号/执行闭包。仍在OS清单中未找到的4项为sntpd、dietappleh13camerad、dietapplecamerad、factory.NFQRCoded；必须按硬件/配置条件查适用性，不造空程序或批量放行。另未在所查主配置发现com.apple.amfid标签，这不等于全系统没有相应认证机制。

## Data来源包的明确边界

16个候选路径中13个存在、3个不存在（containers、mobile/Containers、keybags）；存在项保存OS给出的基本元数据，不存在项的目标UID/GID/mode保持未知，没有沿父目录猜填。它们只是OS占位/初始内容，不是已验收的完整Data种子。

来源包明确排除`private/var/staged_system_apps`：该目录含大量预装应用资源，不能把它不加区分地当小型可写目录种子。原内容仍在固定OS中；后续必须确定预装应用的供应/迁移策略，排除不代表不需要。来源包没有创建特殊节点；链接只存目标，不跟随到宿主。198项都查询了宿主reader提供的xattr，记录名称/长度/摘要，不在tar中恢复xattr。

**该tar不是APFS镜像，也不能作为payload的Data ramdisk输入。** 仍缺APFS对象flags/ACL/保护类、卷UUID、硬链接语义、运行时目录/数据库初始化，以及RamBlock/ADT稀疏或稠密接口、易失/持久策略与容量。没有生成任意空目录来冒充这些前提。暂不实施持久化回调或设备写入。

## 失败保留与续验

1. 初次根/服务audit因ProgramArguments含非字符串被本机解析器拒绝；`audit.json`、`console.txt`保留，挂载已退出、三输入前后摘要一致。改为保留结构化参数且标未解释，15项检查及`audit-r2.json`通过。
2. 首次全var导出达到128 MiB字节预算，停止于预装应用素材；`data-source.json`、`data-console.txt`及`out/desktop-root-contract-20261027-r1/os-var-source.tar`保留。该r1归档**不完整、不可使用**，另有INCOMPLETE.json标记。加入明确的staged_system_apps范围排除后，9项检查及新的r2来源包通过；没有覆盖r1。
3. 首次跨组件程序核验的thin-only解析器报Unsupported Mach-O；`service-layers.json`及日志保留。新增32/64位通用文件范围/对齐/重叠/架构检查，9项测试后`service-layers-r2.json`通过。没有降低架构/签名要求来消除错误；签名和ABI执行仍未验收。

所有成功/失败轮次均保存只读源摘要前后对照与卸载命令。未遇权限拒绝，未修改安全配置。工作路径始终为新nuwa目录；本机指定旧来源目录下未找到udif.py，改为阅读固定公开版本，没有执行旧路径脚本。

最终命令（输出已存在，仅供追溯；重验选新的路径）：

```powershell
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/test-desktop-root-contract.py --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-contract-r1/tests-r3.json
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/audit-desktop-root-contract.py --mount /var/tmp/nuwa-desktop-contract-20261027-r2 --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-contract-r1/audit-r2.json
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/test-desktop-data-source.py --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-contract-r1/data-tests-r3.json
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/prepare-desktop-data-source.py --work /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/desktop-root-contract-20261027-r2 --mount /var/tmp/nuwa-desktop-data-source-20261027-r2 --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-contract-r1/data-source-r2.json
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/test-desktop-service-macho.py --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-contract-r1/service-tests-r2.json
wsl -d Ubuntu-22.04 -- python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/audit-desktop-service-layers.py --work /var/tmp/nuwa-service-layers-20261027-r2 --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/reports/desktop-readiness/2026-10-27-contract-r1/service-layers-r2.json
```

## 接下来的依赖

先落实OS解码/原始窗口摘要、完整挂载及AppOS供应契约，和合格iOS16 Data种子/元数据/保护与初始化路径；再核对服务条件解释、IPC消费者和设备接口。不能以本轮33项宿主检查解除239门、证明exec/EL0或宣称桌面运行。ResourceFork读取边界与平台独立验收仍是当前实机前提；设备继续暂停，PROBE41内核/包不变。

## 固定公开来源

2026-10-27在线查阅：[UniXNU userdata构建](https://unixnu.com/guide/userdata)、[窗口/Data格式](https://unixnu.com/concepts/userdata)、[平台/root/Data顺序](https://unixnu.com/porting/platform)。格式实现参考UniXNU固定提交`0fc0fc1f9ddd0fbd4787738afef38667df5e0a95`的[udif.py](https://github.com/UniXNU/UniXNU/blob/0fc0fc1f9ddd0fbd4787738afef38667df5e0a95/scripts/unixnu/udif.py)，仅阅读，不复制或执行上游实现。这里没有采用其设备参数或运行flash/seed-growth命令。

[Apple launchd说明](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)只用于通用的按需启动/服务注册解释，iOS具体配置与条件来自本轮实际文件。通用Mach-O格式参照cctools固定提交`e0d56624eca2a76c2ace4c21850df9e666de4ca5`的[fat.h](https://github.com/apple-oss-distributions/cctools/blob/e0d56624eca2a76c2ace4c21850df9e666de4ca5/include/mach-o/fat.h)，APSL-2.0；实际架构来自只读文件，不把格式解析当运行资格。
