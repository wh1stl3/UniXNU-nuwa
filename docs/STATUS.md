# STATUS

> 当前唯一真相；更新：2026-10-23T09:31:37+08:00（Asia/Shanghai）。历史见WORKLOG。

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

## 本次系统卷审查

只读读取恢复后 Android 的 v4 boot/init_boot/vendor_boot 头和 fragment table；Android chosen initrd 为33870292B、模512余468，不满足现有整段BlockIo发布条件。此结果不代表R-011候选的实际initrd，当前不能靠追加FAT或猜偏移完成接线。固定AOSP头与采集摘要、未知项见[审查报告](operations/2026-10-23-system-volume-discovery.md)及reports/system-volume-audit/inputs.json。无新镜像、无新增启动或模式切换。

## 下一步

1. 当前配置查找/BlockIo与Android头字段审查已完成；从已有录像补取SHENGMEM行，继续固定安装ABL对临时v4包的fragment/generic ramdisk/bootconfig拼接路径。候选实际x0/chosen仍TODO，不以Android快照替代。
2. 先验证系统卷发现链路，再接真实Darwin22预链接负载/ADT；本轮未新增FAT或第二次试启动，生成镜像本身无需停，但任何设备动作仍需具体日志和已确认恢复路径。
3. 不把本轮菜单观察写成XNU/完整阶段5通过。实际分配剩余量/失败计数、所有SPSS/协议问题状态、DarwinBoot协议调用及候选x0 DT/initrd均仍未验证。

## 对照基线与固定约定

R-010/CI39829943950：Heap69MiB时实机在DxeMain.c(586)断言；清晰照片末阶段27次失败、25页/100KiB总空闲、最大8页/32KiB、5段。R-011一次单行恢复后达到菜单，支持原资源瓶颈已被越过，但不替代完整泄漏/性能统计。H-006完成；H-001独立按键演练/H-003历史可选连续录像保持独立待办。

基座wh1stl3/UniXNU@76dd641保留nuwa补丁，8796内核CI39793231214成功，源内核20187912B/SHA77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8。五平台导出、零undefined、三archive哈希和65348项donor指针零失败；完整NativePrelink/运行ABI仍未验收，历史payload输入仍CI15 a9e08c69。608B/0x2e0 boot_args已真实编译DarwinBoot EFI，运行未验证。ADT/provider/定时器/watchdog/13回调仍待验收，ARCH_TIMER/BOOT_PROGRESS仍0。

board/feed/bringup-plan/ADT及_verified不变，board仍example=true，普通基座-D入口未完整打通。4KiB、iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3、ipad_identity=true保持；D-002先512MiB–1GiB过阶段5、硬上限8GiB，与UEFI Heap不同。两个旧仓只读；Git/GitHub/workflow持续授权；镜像生成无需硬停，设备缺具体日志/恢复路径及其他AGENTS§3边界仍硬停。Android为原有rooted/custom系统，非完整原厂恢复，A槽标志未改。
