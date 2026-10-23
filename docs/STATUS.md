# STATUS

> 当前唯一真相；更新：2026-10-23T11:20:07+08:00（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**R-011 A已完成：恢复同机原厂209.75MiB DXE Heap后，用户实机观察到UniXNU的Return to firmware / Restart / Power off内置菜单，随后返回BDS的NoBootOS页面。已越过R-010的DxeCore断言位置；这不是XNU启动，当前包没有FAT或XNU负载。**

**09:14:28命令确认nuwa/kalama Android boot_completed=1，postcondition三个分区SHA与试前相同，用户亦确认已回Android。** 无flash/erase/改槽或额外候选试验。当前继续离线审查系统卷发现与ABL initrd链路，不直接猜ramdisk位置或把Android DT当Apple ADT。

[本轮报告](operations/2026-10-23-factory-heap-build-trial.md)，证据reports/factory-heap/39835052901/。本轮画面证据目前为用户明确文字描述，未收到照片/录像；不捏造完整日志、零分配失败或SPSS问题均已解决。

## 已完成的R-011

| 项目 | 结果 |
| --- | --- |
| 固件源码 | codex/nuwa-factory-heap@1ccf760d667b9eec6dd3491c90cc04ebb7c58340，父2ab6827d；只改Heap一行，其余源码保持 |
| Heap来源 | 同机xbl_config抽取表SHA2adc494b；BAB00000/0D1C0000=209.75MiB，末端C7CC0000，非其他板数值 |
| CI39835052901 | 设备2199fa5，6m51s成功，666项下载/输入/实际固件静态检查通过 |
| 实际SEC | Heap唯一记录为获批值；新旧41条72B描述符除Heap地址/长度外字节完全相同 |
| FD / 核心 | FD3145728B SHAaca853390666e48dfd3901bdfca2a9deab0d7978a02152c4ad497564f0b8b4d6；DXE核心8fccb5c9保留分配诊断 |
| shim / PIL | shim112B/8a3b5476、relative offset0保持，原PILDxe89e030af及空AUTO配置dbc9ee6e保持 |
| 唯一v4临时包 | 3153920B SHA8e85215011248b3e9462cace9a92133d4d58f33957ea2534fcb487a401e283c0，仅shim+FD，无FAT/XNU/新DTB/ramdisk |
| 实机观察 | 用户明确先见三项UniXNU内置菜单，后见Failed to Find an Operating System；非完整runtime计数日志 |
| 恢复 | 等待脚本检测fastboot，复位后仅临时加载原Android boot ef558db2；完成1、三分区SHA不变；具体回fastboot方式未捕获，未臆测自动/按键 |

## 当前系统发现结论

同源UniXNU Config.c内置配置只有exit/reset/shutdown三项，无配置时搜索SimpleFileSystem卷与\EFI\BOOT\BOOTAA64.EFI；默认退出返回固件。固件BootManager.c:210在UnableToBoot显示BG_NO_BOOT_OS（NoBootOS.bmp文字与用户报告匹配）。因此本次“菜单→找不到系统”符合无系统负载的当前包，不能把最终图标误判为XNU panic或未进入UniXNU。

真实系统入口仍需可发现的卷、\EFI\UniXNU\unixnu.toml、符合Darwin22的预链接内核及目标ADT。当前NuwaBootMemoryDxe只发布/chosen的整个initrd范围为只读512B BlockIo，并要求总长整扇区；GKI v4的vendor_boot/init_boot拼接及实际候选范围尚未验证，不能把FAT随意追加便称系统卷可用。

## 本次离线进展

用户暂不在设备旁，中午可配合；SHENGMEM未取得，本轮没有ADB/fastboot、切换模式或启动设备。安装版ABL固定哈希反汇编已找到前置段→generic段→bootconfig辅助路径，14处指令核对通过；这不是候选运行跟踪，实际x0/chosen/分支仍TODO。

只读Android头审查已确认其initrd33870292B模512余468；不能据此把追加FAT直接当整段磁盘，也不能从Android快照填候选地址。已评估同SoC sheng发布器：它也要求整段整扇区，未提供nuwa v4拆分方案，不复制其DRAM/GCD策略。

本机WSL已生成独立64MiB FAT32配置探针，SHA bc0b3eae88e0dd8a528b3469d0fa9c3fa21c99097af842cab42c28cfa5068ff2；mtools逐字节读回及fsck.fat -n退出0。只有标记菜单和exit动作，无XNU/ADT。**尚未接入固件或完整启动包，不能直接实机启动，也未验证UEFI挂载。** 产物只在out，不提交二进制。

[离线报告与候选路径](operations/2026-10-23-offline-initrd-and-volume-probe.md)，reports/system-volume-audit/含固定指令、同SoC依赖/许可和工具命令。[前轮输入审查](operations/2026-10-23-system-volume-discovery.md)保留。

## 文件发现链路离线核验

固定源码8项连接检查通过，实际R-011 FD确认Fat/DiskIo/Partition/English及发布器均存在，正常固件入口已有先ConnectAll再查配置的代码；未发现漏装FAT模块，不等于实机绑定/挂载成功。修正审计描述符ResourceAttribute为32位、MemoryType偏移60，全部41行实际SEC类型与源码一致；旧新表原始字节回归仍只差获批Heap字段。Android快照区间落在Kernel保留描述符，候选实际映射/保留仍未验证。见[链路报告](operations/2026-10-23-volume-discovery-chain.md)。本轮无设备命令或固件变更。

## Darwin22入口离线核验

固定DarwinBoot纯函数在本机WSL执行，20个ADT解析正反例符合预期；当前77742999源内核通过其ParseKernel（10个非零映射段，跨度21037056B）。这是主机解析/静态检查，不是EFI/QEMU或内核启动。官方原文缓存与源码确认sidecar槽位逐输入匹配，不能无条件添加RAMDisk/PackedRAMDisk/TrustCache三个槽。

当前实际符号表复查为零未解析外部符号、五个平台观测导出存在；13个boot-progress回调未编入，与关闭开关一致，不是当前链接失败。ArmCpu/ArmDTPlatform源码SHA与本次CI匹配。完整预链接及当前内核DWARF ABI尚未验收。

从已有Android FDT快照取得8个CPU reg（0、0x100…0x700）、GIC显式总线映射、0x40000 redistributor stride、timer声明19.2MHz和PSCI smc。只是报告输入，不生成nuwa ADT、不改板值或内存窗口；CPU编号映射及运行行为仍待验证。见[入口契约报告](operations/2026-10-23-darwin22-entry-input-contracts.md)和reports/darwin22-input-contracts/。

## 下一步

1. 中午用户在场后，通知录像并刷新身份、恢复输入/日志门，再考虑现有已验收包的定向日志复测；优先捕获SHENGMEM的DT、initrd范围及发布状态。当前没有自动/定时启动，未准备新完整试启动包。
2. 离线运输方案优先沿用chosen initrd但要求明确边界/保留策略；FV内嵌小探针是备选，尚未实现。由运行映射决定，不能猜前缀、向上取整越界或盲搜FAT字符串。
3. 离线继续审查CPU affinity与XNU编号映射、GIC/PSCI输入转换规则；确认后才形成目标ADT候选，未知项保留TODO。NativePrelink运行ABI、回调/硬件watchdog另行验收。
4. 探针菜单只能验收卷与配置发现；真正进入XNU前还需匹配的负载/ADT、实际连续内存分配和EL1交接。不能由解析检查推导今日启动时间。生成组件无需硬停，设备动作仍按AGENTS§3检查。

## 对照基线与固定约定

R-010/CI39829943950：Heap69MiB时实机在DxeMain.c(586)断言；清晰照片末阶段27次失败、25页/100KiB总空闲、最大8页/32KiB、5段。R-011一次单行恢复后达到菜单，支持原资源瓶颈已被越过，但不替代完整泄漏/性能统计。H-006完成；H-001独立按键演练/H-003历史可选连续录像保持独立待办。

基座wh1stl3/UniXNU@76dd641保留nuwa补丁，8796内核CI39793231214成功，源内核20187912B/SHA77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8。五平台导出、零undefined、三archive哈希和65348项donor指针零失败；完整NativePrelink/运行ABI仍未验收，历史payload输入仍CI15 a9e08c69。608B/0x2e0 boot_args已真实编译DarwinBoot EFI，运行未验证。ADT/provider/定时器/watchdog/13回调仍待验收，ARCH_TIMER/BOOT_PROGRESS仍0。

board/feed/bringup-plan/ADT及_verified不变，board仍example=true，普通基座-D入口未完整打通。4KiB、iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3、ipad_identity=true保持；D-002先512MiB–1GiB过阶段5、硬上限8GiB，与UEFI Heap不同。两个旧仓只读；Git/GitHub/workflow持续授权；镜像生成无需硬停，设备缺具体日志/恢复路径及其他AGENTS§3边界仍硬停。Android为原有rooted/custom系统，非完整原厂恢复，A槽标志未改。
