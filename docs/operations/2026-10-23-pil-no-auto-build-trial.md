# R-009 A：保留PIL并取消自动ABL链

用户在具体R-009 A请求后回复“批准”。范围涵盖源码、独立EFI/FD/shim编译和产物检查、受限v4临时对照及Android完成1收尾；不扩展board/内存、flash/erase/槽位或_verified。

## 最终结论

**本轮已完成并按用户要求停止。** CI39820752081真实构建及665项下载产物检查通过，空AUTO实际嵌入、原PILDxe保留；唯一一次新包实机试启动已进入候选DXE，后续页面分配失败、架构协议缺失并停在DxeMain.c(581)。BDS/UniXNU加载器/XNU尚未运行。用户按键返回fastboot后，临时加载已验证Android备份，2026-10-23 01:25:30+08确认实际nuwa boot_completed=1；boot/vendor_boot/init_boot三个分区hash与试前一致。未进一步修复或试启动。

## 构建前静态门

`scripts/audit-pil-auto.py`从R-007实际FD在RAM解包PILDxe，PE SHA89e030af07847bdc596f0c213bdce0ac430be66e572db55b434d7ec66ad9afcb，恰与先前安装UEFI的该驱动一致。保存原指令字节/地址与字符串交叉引用至reports/pil-no-auto/parser-disassembly.json，不输出PE/固件文件。下述地址均为PE首选地址，不是实机PC：

- 初始化列表函数0x41b4按AUTO选择0x4398回调；枚举完成后AUTO走0x4364的x19=0并在0x437c返回成功。不存在“列表必须至少一项”的AUTO后置检查；特殊检查是另一个16进制长度0x16的节名，不能套到AUTO。
- 通用配置解析初始化0x11378将注释字符设置为`#`；0x11764按节名枚举回调，枚举耗尽在0x117dc返回0。完整迭代/行处理路径保留0x11400–0x11844。
- 自动项计数首选地址0x18718在PE数据/零填充映像初始为0；AUTO回调只有实际条目才会累加（0x4414–0x4424）。入口0x1600的CBZ在计数0时跳0x1650安装协议，绕过加载循环及0x163c panic消息/调用。

结论为**静态检查通过**，前提是配置RAW可读取、解析成功且普通初始化内存状态正常；未模拟执行，更未把它写成实机验收。此门足以继续获批构建，最终行为以新FD试启动取证为准。

复现命令：

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -X utf8 -B scripts/audit-pil-auto.py --range 0x1588:0x1708 --range 0x41b4:0x446c --range 0x11298:0x113d8 --range 0x11400:0x11844
```

## 已固定源码与CI接线

独立固件分支`codex/nuwa-no-auto-abl@2ab6827d77dfe15010534b52e1abb76a26464a7d`，父910ee079，仅两条路径：RAW.inc改该输入路径，新增nuwa本地uefipil.cfg。候选配置SHA dbc9ee6e4c7728b32245453322f348c32d6a5eef0107f8c07662918bc3c23fdd；对原配置只改AUTO ABL行为，不改GUID/RETAIL/镜像定义/内存数值。保留原配置既有行尾空白，未借机格式化。固件提交信息符合既有格式，逐blob/tree/commit等同发布报告source-publish.json；稳定/SEC/相对偏移旧分支未改。

新增firmware-pil-no-auto-profile.json，继承SEC profile并固定该新提交、R-008已批准的相对头0以及两个新源码输入。`check-pil-no-auto-profile.py`核对33项本机来源hash、完整profile差异与board固定值，通过；两个旧资料库只读，未初始化/改写其中任何源码。

固件workflow增加独立pil-no-auto选项。CI构建校验头时区分relative text_offset和FD destination，不再把新头0误判为必须等于FD_BASE；旧profile默认行为保留。下载检查器新增严格新FD门：实际PILDxe PE SHA不变、原GUID仍存在、实际RAW SHA为dbc9ee6e且AUTO条目为空、正确头0、SEC标记与四个真实EFI继续核对。旧R-007产物回归检查通过；没有为了通过而删除旧profile保护。

当前编译/下载产物与实机结果待后续记录，不能用profile或源码静态检查替代。

## 后续验收顺序

固定本设备提交启动CI → 取实际终态/日志/产物 → 严格检查新RAW/PILDxe/SEC/四EFI/FD/shim → v4原头受限打包（仅kernel_size，raw shim+FD，无新DTB/ramdisk/FAT/XNU）→ 重新识别nuwa并核对Android/恢复源 → D-016隔离bootloader临时试启动 → 记录画面/采样并恢复Android=1，核对三个Android分区hash。任何失败以实际首错推进，不自动切换R-009 B。

## CI已启动与本地打包门

CI39819452729于2026-10-23 01:04:23+08由固定设备6af9701启动，选择pil-no-auto；run-initial.json保存本次实际状态，编译尚未以成功验收。本地prepare-pil-no-auto-boot.py固定新profile并要求实际RAW/原PIL/正确shim；试启动工具只接受R-009对应source/hash/配置范围。两个负路径验证旧39809636575在检查器及打包器被拒绝，且没有输出新包，见reject-old-profile.json。尚未操作设备，读前置时实际nuwa/kalama Android=1，三个分区hash和恢复源SHA已记录。

## 用户收尾边界

用户追加“做完这笔实机验证就停下 写好文档”。本轮仅完成当前R-009验证、恢复/确认Android完成1并保存证据与文档；其后不展开新镜像或下一轮修复，新增问题只列下一轮起点。见stop-after-trial.json。

## 首轮CI的实际失败与最小前置修复

39819452729在01:10:37+08结束：Install build tools退出124，未执行Build步骤，无固件包。失败日志最后下载是cpp-13-aarch64-linux-gnu 10.8MB，仍为http://azure.archive.ubuntu.com；前面的mono包也逐个慢速下载。没有源码编译首错，不能归因PIL或空AUTO。旧workflow只替换ubuntu.sources，现扩大到/etc/apt下depth<=2的sources.list、*.list、*.sources，逐一记录有效源并检查Azure主机名已清除；保持签名仓库、包版本选择、超时和固件输入不变。是否完全解决以重试实际日志为准。

## 重试CI及新产物实际核验

39820752081固定device424513d、firmware2ab6827d、pil-no-auto；2026-10-23 01:13:31–01:19:28+08成功，总5m57s。工具安装01:13:35–01:14:22为47秒，实际下载已走archive.ubuntu.com；完整原日志仅留ignored out/pil-no-auto-39820752081-success.log，选取命令/下载地址保存ci-selected.log。并非忽略旧失败或延长超时。

artifact名nuwa-firmware-39820752081，服务端记录13366686B/digest sha256:8220aef727b04abc3fb11bab838d2e310f0bc28bb31afd816922101fbb10ec8b。gh解包下载，未另保存ZIP做全ZIP摘要核验；665项文件清单/大小/SHA与实际FV/PE/TE/DEPEX/配置/头检查通过。不能把服务端digest标成已独立验证的本地ZIP摘要。

| 实际产物 | 结果 |
| --- | --- |
| 四EFI | UniXNU/UniXNUDxe/DarwinBoot/NuwaBootMemoryDxe存在，实际FV与独立EFI对应，依赖/HOB检查通过 |
| FD | 3145728B，SHA5ad08040a420608119d1d4cc72b2f54150d1fd33e111460fef711153aa2a3a45 |
| 内嵌配置 | 6930B，SHAdbc9ee6e4c7728b32245453322f348c32d6a5eef0107f8c07662918bc3c23fdd，AUTO活动条目空 |
| PILDxe | 原PE SHA89e030af07847bdc596f0c213bdce0ac430be66e572db55b434d7ec66ad9afcb保持，未移除或改二进制跳过panic |
| shim | 112B/SHA8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462，与R-008修正版相同；相对offset0、_Payload112、复制3145728B |
| 临时v4包 | 3153920B，SHAb60f96c0b69e8be6a36b3c74f919fb6a3c88eac7d0c8d3f785c26272cc3e864e；原头只更新kernel_size，无新增DTB/ramdisk/FAT/XNU |

输入/检查/包报告见reports/pil-no-auto/39820752081/{run-final,artifact-metadata,artifact-inspection,package}.json。

## 本轮唯一一次实机与照片归属

launch.json于01:21:19+08开始，重新核对实际nuwa/kalama、Android=1及product/unlocked/slot，按D-016重进bootloader隔离状态。Sending OKAY0.075s、Booting OKAY0.117s；随后15次nuwa fastboot采样均false，USB快照未出现其fastboot端点。ACK仍只表示命令接受，不单独作为阶段证明。

用户回复“停在报错了”，照片原字节保存user-screen.jpg，SHA及人工转录见screen-observation.json。可读结果包括：

```text
SPSS Failed to load metadata
AllocatePoolPages: failed to allocate 233 pages
...（多组不同页数的分配失败）...
Security Arch Protocol not present!!
Bds Arch Protocol not present!!
Variable Arch Protocol not present!!
Variable Write Arch Protocol not present!!
Capsule Arch Protocol not present!!
Real Time Clock Arch Protocol not present!!
Driver 29B950CF-586D-49EA-9D71-F88645CCDAF6 was discovered but not loaded!!
Driver 1B64AF87-8415-4B57-9B16-680D70913B9F was discovered but not loaded!!
ASSERT_EFI_ERROR (Status = Not Found)
ASSERT [DxeCore] DxeMain.c(581)
```

上述两个GUID分别是候选UniXNUDxe与DarwinBoot，实际新FD内存在，先前安装原厂UEFI的98PE清单没有这两个GUID。它们与用户当前时点照片共同支持**候选DXE实际执行已观察到**，改善了上一轮单凭原厂共用驱动名无法归属的问题。但二者明确为discovered/not loaded，不等于加载器运行。最终画面已到PIL之后的后续驱动分派，不再以上轮AUTO ABL panic为终点；SPSS仍有加载失败，不能说全部PIL硬件路径成功。

实际阻塞：页面分配失败和架构协议缺失导致DXE断言。**根因未确定**：当前没有运行时UEFI最终map、分配器空闲量/最大连续块或分配消耗轨迹，不能把它直接写成“12GB物理内存不足”、单纯增加heap即可解决，或归因唯一驱动。UEFI可分配区与XNU/ADT拥有窗口是不同问题，本轮未改任一内存数值。

## 恢复、分区与停工

初次恢复进程recovery.json启动时没有nuwa fastboot/ADB，原脚本随后只等待ADB；最终等待180秒超时。保留这份真实失败，不以新成功覆盖。用户按要求长按电源+音量下并回复“已回fastboot”，H-004记录后续完成。

单独执行recovery-after-keys.json，从已识别nuwa fastboot再次reboot bootloader后，临时加载SHAef558db2…的201326592B已验证Android备份boot：Sending196608KB OKAY4.484s/Booting OKAY0.117s；01:25:30.932871+08识别实际nuwa/kalama且sys.boot_completed=1。postcondition.json重新确认完成1并核对boot_a/vendor_boot_a/init_boot_a三分区全量SHA与试前相同。当前仍为既有自定义/rooted Android，不称完整原厂恢复；未flash/erase/改槽。其他enuma设备未作为目标。

**按用户要求，本轮在恢复/文档后停止，未继续改变源码、生成镜像或做第二次R-009试验。** 下列只供下一轮参考，不是本轮待执行动作：

1. 从运行时UEFI可分配map/空闲量/初次分配失败入手，再审查必需架构协议提供者及DEPEX；不要凭照片直接选新heap基址/容量或调整ADT窗口。
2. 审查SPSS metadata失败是否独立阻塞，保留PIL/真实驱动的来源与依赖，不直接切R-009 B。
3. 恢复工具现有等待模式不会自动接管随后才出现的fastboot；必要时先完善这一路径，保留“只发原恢复boot、无flash/slot”的约束。
