# STATUS

> 当前唯一真相；更新：2026-10-23T18:59:02+08:00（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**晚上2d833461诊断包已完成一次实机临时启动。更正照片明确显示入口HOB创建返回非空data=BAB013B8、list=BAB00000，最后为before-library-constructors；未观察到构造返回、解压、DXE或SHENGMEM。** 现已将范围收窄至库构造调用/相关日志路径，尚未定位具体函数或运行PC，不排除输出通道失效。

**18:30:39电脑已确认nuwa/kalama回Android、sys.boot_completed=1；后置三分区SHA与试前相同。** 本轮恢复脚本只检测到Android，没有发送原boot；回返方式未独立记录。无flash/erase/改槽，不再启动第二包。用户先误发旧图后已更正，旧图不作为本次阶段证据。[晚间报告](operations/2026-10-23-sec-handoff-evening-trial.md)，reports/sec-handoff-trial/2026-10-23-evening/。

XNU源内核已编译，尚未实机进入XNU；上午R-011曾到UniXNU菜单，中午未稳定复现。晚间新图只证明上述SEC边界，不能混为本次菜单成功。

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

严格新scope已接入trial/preflight，纯文件校验通过：重查固定recipe、实际产物、包metadata和整个原头/内容。SEC-HANDOFF-OFFLINE及ready_to_execute=false表示包不替代运行前门。USB观察默认120秒（范围120—600），每条附ACK后相对时间；USB枚举不是具体过程日志。下午完成纯文件/语法检查；晚上已按fresh门试一次，具体结果以上方晚间报告为准。

## 下一步

1. 四构造源码审查及共享库日志候选已准备，39项输入/调用返回静态检查通过；FrameBuffer SerialPortInitialize只有return SUCCESS，无重置显示代码。先构建constructor-trace并核验实际8条marker、旧门和全部41行表；本轮无设备操作。见[构造诊断](operations/2026-10-23-constructor-trace.md)。
2. 新构建/产物检查通过后再安排单构造定位实测，具体照片日志/恢复门仍需刷新；不重复旧包、不跳过构造。共享库日志也影响其他消费者，需记录新DXE核心实际哈希，不沿用旧值。
3. SHENGMEM、真实initrd范围和载荷卷挂载尚未取得；保持FAT探针→当前内核prelink/ADT→EL1入口→原生根卷顺序，不猜偏移或改板值。
4. Android完成1及三分区未变已确认。H-009拍摄配合完成（新照片已取得、完整视频未交付）；历史独立按键演练不混称完成。

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
