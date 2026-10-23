# STATUS

> 当前唯一真相；更新：2026-10-23T17:03:32+08:00（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**晚上实测候选已离线准备完成：CI39915967862成功，四条新HANDOFF日志进入实际SEC，41条内存描述符2952B与R-011逐字节相同。唯一v4包3153920B、SHA2d833461，尚未实机启动。本轮没有ADB/fastboot命令。** 用户要求留晚上一起实测。

**XNU源内核已经编译成功，尚未实机进入XNU。** 上午R-011同包曾由用户观察到UniXNU三项菜单，随后NoBootOS；中午同包照片最后可见platform-hobs status=Success，未取得本次DXE/SHENGMEM/菜单证据。最后可见行不等于实际PC，输出失效或执行阻塞仍未区分，不能称稳定进入UniXNU。

最近一次恢复为中午12:18:42：实际nuwa/kalama Android boot_completed=1、后置三分区SHA与试前相同，无flash/erase/改槽；这不替代晚上新鲜前置条件。[中午报告](operations/2026-10-23-initrd-retest-sec-stop.md)。

## 新诊断固件与包

| 项目 | 核验事实 |
| --- | --- |
| 固件源码 | wh1stl3/uefi-nuwa，codex/nuwa-sec-handoff-trace@ddd794fc07e9bc64057222a9bffa4d79c8553af8，父1ccf760；仅Sec.c四处日志，保留调用顺序 |
| CI | 39915967862，设备脚本abe4be9，15:09:28—15:15:19成功；666个下载清单文件大小/SHA通过 |
| FD | 3145728B，SHAfcf2f829fb4748034014f8913b967a928cdbafe16836b9992eee5a13d838ac24 |
| 实际SEC | SHA fad4af6b4c2b8422f4951f71b2ea9f9b00b5813485e9820db668f2f35e5840aa，四条HANDOFF及原ENTRY日志存在 |
| 内存表 | 全部41条72B描述符共2952B与R-011完全一致；获批同机Heap BAB00000/0D1C0000保持 |
| 核心/PIL | DXE核心8fccb5c9保留分配诊断，原PILDxe89e030af、空AUTO dbc9ee6e保持，四模块/PCD/DEPEX检查通过 |
| BootShim | 112B，SHA8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462，relative offset0保持 |
| 唯一v4包 | out/trial-boot/sec-handoff-39915967862/boot-sec-handoff-v4.img，3153920B，SHA2d8334613a415c24574f93c0bcb30ba50d32175ff062d8ec2cc149651bcde846 |
| 容器范围 | 原Android头仅改kernel_size；整个头＋shim＋FD＋零填充重建一致。无FAT/ADT/XNU、新DTB或ramdisk；恢复boot原件ef558db2复查通过 |

[构建与晚间计划](operations/2026-10-23-sec-handoff-build-ready.md)，reports/sec-handoff/39915967862/保存真实run、完整workflow日志、inputs/result/inventory、实际产物检查、内存表对比及package。二进制只留out。

## 停点分析与工具准备

实际SEC TE/link-map核对显示platform-hobs之后存在入口参数HOB和库构造调用。固定Mu@cfb93724的PrePiHobLib通过TPIDR取得列表，提取器构造涉及AllocatePool、GUID HOB，其他构造涉及缓存操作；不能以两行源码或DXE Heap容量排除这些路径。同SoC uefi-sheng@329b473d也采用PlatformPeim→入口HOB→库构造顺序，未取得重排依据。

只补before/after-entry-arg-hob及before/after-library-constructors，记录list/data而不额外解引用，不绕过错误。[分析与来源](operations/2026-10-23-sec-handoff-diagnostic.md)，reports/sec-handoff/保留固定提交、SHA、许可、适用性及35项输入检查。

严格新scope已接入trial/preflight，纯文件校验通过：重查固定recipe、实际产物、包metadata和整个原头/内容。SEC-HANDOFF-OFFLINE及ready_to_execute=false表示包不替代运行前门。USB观察默认120秒（范围120—600），每条附ACK后相对时间；USB枚举不是具体过程日志。本轮只做纯文件/语法/CLI帮助检查，未启动新包或查询设备。

## 下一步（晚上）

1. 用户在场后通知录像，使用reports/sec-handoff/39915967862/package.json刷新目标nuwa/kalama、Android完成1、三分区SHA、原boot及实际恢复证据，生成独立fresh preflight；不得复用中午记录冒充当晚门。
2. 门通过后只临时启动2d833461候选；录像覆盖至少120秒完整阶段，标注相对时间，读取四条HANDOFF最后可见项及list/data。具体失败先记录再恢复，不为凑时长延迟恢复；缺失日志仍不能自动判为精确阻塞点。
3. 若到DXE/UniXNU，取得SHENGMEM的x0/initrd范围及发布状态；无系统负载时NoBootOS符合当前包。若未到则按边界证据定位，不盲猜initrd或改内存表。
4. 结束后仅恢复已校验原Android boot，确认sys.boot_completed=1和三分区SHA不变；视频/照片及过程写入独立reports目录。H-009为晚上拍摄待办。

设备前缺具体过程日志或恢复依据则按AGENTS§3写审阅并硬停；镜像生成本身无需硬停。本轮不需要改板值、身份、内存参数或_verified。

## 后续系统卷／启动载荷预研

已固定四层交付关系：FAT启动载荷→Darwin22预链接内核/Apple ADT→只读OS/SystemOS根卷→可写Data及用户态。既定iPhone donor的7项组件在本机，两个trust模块本轮重算SHA并解出v2/2760与61条，静态长度/类型/排序检查通过；未输出bundle、ADT或系统镜像。大DMG只复核长度/UDIF尾签名，raw大小/根卷UUID尚缺，不能直接拼压缩DMG当块盘。

实际77742999内核没有NativeUfs/NativeRamBlock对应命名符号或_sheng_pmgr_run，仍需原生根卷后端适配。隔壁预链接报告使用89d8ff86输入，不能称当前内核预链接已完成。固定75bc13dd的packed输入上限256MiB、逻辑上限2GiB；1TiB文档与iPad17硬编码工具不套用到当前版本。优先小FAT探针→内核入口→原生只读根卷，晚间诊断包不变；改写userdata的恢复证据不能由临时boot恢复推导。

[预研报告](operations/2026-10-23-ios16-system-payload-research.md)，reports/ios16-payload-research/含来源/许可/组件/符号/就绪矩阵；官网本轮7页404，引用10月22日已保存HTML并记录SHA，不称实时官网核验。下一步仍按上方晚间试验推进，后续只读prelink计划、ADT和根卷准备分别实施。

## 系统卷和内核入口的未完成项

NuwaBootMemoryDxe只把/chosen整个initrd作为只读512B BlockIo，长度必须整扇区；实际FD具有Fat/DiskIo/Partition/English及预连接代码，不等于实机挂载成功。Android快照initrd33870292B模512余468，不能移作候选地址或把追加FAT当整段磁盘；ABL vendor/generic/bootconfig拼接的候选范围仍待证。离线64MiB FAT探针bc0b3eae仅通过WSL读回/fsck，未接入完整包。[卷审查](operations/2026-10-23-volume-discovery-chain.md)。

固定DarwinBoot纯解析函数在WSL主机20例通过，当前77742999源内核ParseKernel接受（10个非零映射段，跨度21037056B）；零未解析外部符号、五个平台观测导出，ArmCpu/ArmDTPlatform来源SHA匹配。13个boot-progress回调未编入，与关闭开关一致，不是当前链接错误。主机解析不是EFI/QEMU/XNU执行。

缓存nuwa FDT已提取CPU affinity 0、0x100…0x700、GIC显式映射/0x40000 stride、timer声明19.2MHz、PSCI smc；仅输入来源，未生成目标ADT。CPU编号映射、中断/定时器/PSCI、完整NativePrelink运行ABI、连续分配及EL1交接均未验收。[入口契约](operations/2026-10-23-darwin22-entry-input-contracts.md)。

## 基线与固定约定

R-010/CI39829943950在Heap69MiB时实机分配失败及DxeMain断言；R-011/CI39835052901恢复获批同机工厂Heap，唯一包8e852150一次到达菜单，中午未稳定复现。两次观察分别保留，不抹去上午结果，不把静态检查写成实机通过。

基座wh1stl3/UniXNU@76dd641保留nuwa补丁；源内核CI39793231214成功，20187912B/SHA77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8。当前固件仍固定上游75bc13dd；608B/0x2e0 Darwin22 boot_args补丁已编译，运行未验证；历史payload输入仍CI15 a9e08c69，不混称当前预链接完成。

board/feed/bringup-plan/ADT及_verified保持，board仍example=true，普通基座-D入口未完整打通。4KiB、iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3、ipad_identity=true保持；D-002先512MiB—1GiB过阶段5、硬上限8GiB，与UEFI Heap不同。两旧仓只读。Android为原有rooted/custom系统，非完整原厂恢复，A槽标志未改。
