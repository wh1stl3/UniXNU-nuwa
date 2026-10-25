# nuwa下一阶段依赖与公开资料核对

核查2026-10-26；本轮转为分析后不再扩展实现。所有设备操作暂停，包括adb/fastboot查询与状态变化、临时启动、刷写。未读取其他设备项目，未联系第三方，未上传私有源码/日志/媒体。公开检索仅使用公开函数、项目和版本名。PROBE28/7a04626e…及原证据不变，仍未实机。

## 当前判断

最早未验证点仍是实际header读取：PROBE27观察250调用而未见251后继，类型4表项已存在；PROBE28外层MAC/VNOP/分派配对尚无实测。首要调查文件系统读取内部，次要独立MAC读取处理；没有依据把具体锁、解压器、永久卡死或IRQ故障定为已证根因。本轮补齐激活模型透明性，未修复或复现实机故障。

最低成本的下一离线项是核对真实header参数契约。原生w6=8，长度依赖运行时PAGE_SHIFT_CONST；现夹具4KiB/flags0只能证明那些模型输入下的透明性。先串起固定loader的boot_args.memSize、arm_init赋值和编译期ARM_PGSHIFT，记录每步指令/输入，未知处保留TODO。验收是得到可复核值或明确证明只能由运行时读数确定；之后若获准改测试，只补真实参数与有理由的负对照，不改板内存/TCR，不重做全套已过检查。当前没有实施这一参数扩展。

## 已联网核对的一手来源

直接匹配指同一XNU版本的机制和本地指令对应，不代表实机根因已证。公开资料未发现可直接套到nuwa当前250停点的修复issue/commit。

| 来源/版本 | 关键证据、适用等级 | 最小核对及实机需求 |
| --- | --- | --- |
| [Apple发布提交](https://github.com/apple-oss-distributions/xnu/commit/1b191cb58250d0705d8a51287127505aa4bc0789) | 对应xnu-8796.141.3，直接版本匹配 | 本地三个文件CRLF归一后逐字节等于此提交blob；不按网页行号推断二进制偏移 |
| [vfs_vnops.c](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/bsd/vfs/vfs_vnops.c) | MAC通过后才走普通或swap读取，保留真实错误和残余量；直接匹配 | 已有调用/返回配对；需本次实际stage、返回、resid，不以旧聚合errno代替 |
| [mac_vfs.c](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/security/mac_vfs.c) | read检查是独立策略检查；直接匹配 | 本地指令有策略列表busy和两个间接调用；需线程/阶段或回调目标实测，不能用exec检查已过代替read已过 |
| [decmpfs.c](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/bsd/kern/decmpfs.c) | 已注册只免去空表项注册等待，仍有数据锁、缓存、验证、UPL和回调；转换等待有错误/状态前提；直接匹配 | 按已有静态地图选择真实进入路径；需272/273及后续实际目标，不能直接把msleep当根因 |
| [vnode_pager.c](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/bsd/vm/vnode_pager.c) | 特定PAGEIN路径保留EAGAIN重启与EPERM语义以处理压缩/保护；条件可迁移 | 先证明进入该分页路径再核对UPL abort/restart；当前未观察此路径，不建议改返回值 |
| [apfs-fuse固定Decmpfs实现](https://github.com/sgan81/apfs-fuse/blob/66b86bd525e8cb90f9012543be89b1f092b75cf3/ApfsLib/Decmpfs.cpp) | type4资源分叉/Zlib数据格式控制，GPL-2.0-or-later；仅主机层参考 | 本项目相同工具已审计文件，无需重复挂载；主机解码成功不覆盖XNU锁、UBC或驱动 |
| [维护者ARM兼容issue #25](https://github.com/sgan81/apfs-fuse/issues/25) | 2018年Raspbian工具编译问题，维护者改用可移植库；不是当前内核读等待修复 | 当前主机工具已能读type4，不适用为nuwa补丁；不替换内核实现 |
| [fscmp维护者说明](https://github.com/Siguza/fscmp) | MIT、macOS-only、依赖不稳定私有框架；可迁移工具思路 | 不能在现有Windows/WSL或XNU中直接替代；本轮不安装、不转换根镜像 |

为避免网页截断误读，GitHub长文件HTML未显示目标函数时读取同tag官方raw文件。网页提取行号与本地原文件不同，引用使用本地固定行号与原始指令。公开源码内容未整份复制进设备仓。

### 同SoC与日志来源的适用边界

[sheng当前README](https://github.com/UniXNU/UniXNU-sheng)选择iPadOS17.7.11-21H461；[SM8550共用仓](https://github.com/UniXNU/UniXNU-sm8550-common)区分通用硬件资源与设备内存/固件/电源策略。它们是后续平台整合来源索引，不是当前iOS16/8796读停点的直接修复。历史已固定主仓16e592abee8a550dec8154ed1f38b5ebc4f16213、共用仓23b2049fcd9e30356161def84231334fb55ecca9，见10月25日official-porting-update及review.json；本轮不迁移或拉取上游。

[固定DT panic补丁](https://github.com/UniXNU/UniXNU/blob/16e592abee8a550dec8154ed1f38b5ebc4f16213/patches/xnu/native-dt-panic-region.patch)用于诊断区选择/边界检查，不能解释已到exec读取的当前停点。[AdvancedLogDxe固定INF](https://github.com/UniXNU/UniXNU/blob/16e592abee8a550dec8154ed1f38b5ebc4f16213/package/UniXNUPkg/Driver/AdvancedLogDxe/AdvancedLogDxe.inf)提供固件日志QR思路，不能当XNU接管后的日志通道。

[sheng日志例程](https://unixnu.com/devices/sheng-unattended-test)依赖该板持久UFS区域、writer/reader、Linux恢复输入及自动返回；只可迁移“日志先行、读写/恢复闭环”的方法，不能照搬其userdata尾区、boot格式、定时返回或PMIC/板值。[ShengUfs](https://github.com/UniXNU/ShengUfs)是后续真实存储来源；当前根为md0，未证明现停点是原生UFS读问题。

[官网nuwa页](https://unixnu.com/devices/nuwa)仍引用较早IODTNVRAM/用户态未证记录，落后于本地PROBE27/28；本地最新交接仍是当前依据。未因此退回旧卡点，也未据其他设备宣称nuwa已启动用户态。

### 访问限制

本地只读git remote/HEAD查询D:/Code/PortingiOS/common/sources/UniXNU-sheng被dubious ownership保护拒绝：目录owner为CodexSandboxOnline，当前为Administrator。未改safe.directory或重试绕过；改用已授权历史评估记录和公开README。

联网工具无法访问UniXNU仓的API提交端点、commits/main历史、共用仓固定tree URL及sheng-ufs指南直链；记录为不可访问，不据动态README虚构当前提交。固定Apple源码、固定主仓补丁/INF、公开README和维护者issue可读，已继续研究。上述限制不阻塞当前分析，但阻塞把新上游代码纳入可采用输入。本轮未采用该代码，不申请扩大权限。

## 从当前停点到后续启动的依赖与验收

| 顺序 | 依赖与已知状态 | 可独立离线工作 | 需要的运行时验收 |
| --- | --- | --- | --- |
| 0 · 真实参数 | 250前参数已解码；PAGE_SHIFT运行时来源未闭合 | 核对固定loader→memSize→arm_init→shift→len，补具体参数契约计划 | 若静态不能定值，需本轮实际参数；磁盘初值0不代替运行时 |
| 1 · 读取分界 | 27仅250亮/251暗；28未启动 | 保留已验证28及本轮补充模型，不再无依据加点 | 同一次header尝试的268/269、270/271、272/273和异常布局；仍须日志/恢复门，本轮不执行 |
| 2 · 选中内部路径 | 尚不知MAC或文件系统哪个未返 | 只针对观测选中路径固定一组最小调用/返回、输入与否定条件 | MAC需区分策略busy与回调；文件系统需实际APFS目标，再分锁/缓存/验证/UPL/fetch；无此证据不认定具体锁/IRQ |
| 3 · header/Mach-O/dyld | 252后继等未观察；主机文件和解释器路径已审计 | 复用既有文件SHA、LC_LOAD_DYLINKER=/usr/lib/dyld、ABI/权限/依赖资料；分析真实返回类型/残余量传播 | 251实际返回及resid，252/253激活、256/257 load_machfile、258..263 dyld路径；成功须来自当前尝试 |
| 4 · 任务切换/签名 | A02F未见；原生签名/任务切换守卫保留 | 审核真实输入和信任来源，区别errno、Mach loader结果；不放宽权限/认证 | 原生切换、签名、异常/错误日志；先保留239释放守卫，不能把模型零值当签名成功 |
| 5 · 用户态释放 | 当前是restore APFS，不是完整iOS系统根；RunAtLoad恢复服务已知 | 先审计launchd作业、服务路径、依赖和设备写入风险，形成独立最小评审项 | 现有guard阻止未审阅restore用户态；不得自动去守卫或启动恢复服务 |
| 6 · 完整iOS16路径 | 完整系统根、服务/驱动组合及UI均未验证 | 固定同一身份/ABI的完整输入，逐项盘点存储、显示、输入、电源等真实组件与来源/许可 | 用户态入口、服务运行、持续驱动/恢复闭环各自证据；首次exec或restore launchd不等于iOS启动完成 |

第5项依据reports/kernel-entry-probe/2026-10-25-v32b/restore-policy.json：固定APFS含com.apple.restored_external.plist，RunAtLoad=true，程序/usr/local/bin/restored_external。该报告是只读主机审计、没有执行用户态；不能据此预测已发生刷写。第3项标签按scripts/exec_path_sites.py逐项映射，不混用跨尝试保留的errno。

## 最小下一阶段计划（规划，不自动实施）

1. 先完成一个离线参数契约核对项：固定输入、确认w6=8与PAGE_SHIFT初始化链；验收为可复核的值/条件及明确TODO。没有新镜像目标。
2. 设备暂停保持。以后获得当轮条件并重新核对授权时，才考虑现有28的一次观测；必须先满足R-014和新鲜预检，本轮不生成preflight、不运行adb/fastboot。
3. 用最早未返回边界决定唯一下一内部调查，不同时改MAC、APFS、解压和调度；改动必须有首要假设、反例与最小验收。252、dyld、签名和用户态都排在真实header读取之后。
4. 即使读取打通，也保留恢复用户态释放边界，另做restore服务/完整系统根的输入与内容更改审阅。当前不批准此释放，不创建新候选、不升级OS、不迁移Format2/SoC、不推送。

未宣称有价值的离线工作全部耗尽；已经明确了下一个能独立核对的参数契约。当前不能离线回答真实等待线程、锁owner、当前APFS回调目标、IRQ完成或是否能进用户态，这些需要受控运行时证据。
