# 官方文档全站结构复核与nuwa路线影响

时间：2026-10-22 21:23（Asia/Shanghai）。入口为用户指定的[移植总览](https://unixnu.com/zh/porting/)与[设备总表](https://unixnu.com/zh/devices/)。本轮只读取网站、GitHub公开源码/元数据及本地文件，没有访问手机、生成镜像或变更上游版本。

## 结论

继续UniXNU底座、nuwa设备仓、独立UEFI适配、4 KiB、iPhone X iOS16.7.16的既定路线。官方已把该iPhone IPSW列为第二目标，并收录iOS16社区执行记录；这支持继续Darwin22适配，不能代替nuwa验收。当前最有用的补充是：

1. **装入XNU负载前，补做Darwin22 boot_args布局核对。** 官方明确DarwinBoot示例布局属于Darwin23，本地8796与加载器头文件确有长度/尾字段偏移差异，详见下文；尚未核对CI15编译后的类型，不直接宣称已诊断运行故障。
2. **当前黑屏优先查ABL→BootShim→SEC，以及实际交接FDT中的splash保留/显示属性。** 官方标准包是gzip(shim+FD)+DTB+可选FAT，当前v4候选是raw shim+FD且没有追加DTB。这个差异值得审查，但不是证明v4不支持或强制换v0/v1。
3. **日志先复查已有真实实现。** sheng有UFS持久日志+Linux USB CDC读取器；Ace5文档和源码清单又指向SM8550 vermeer原生XNU USB CDC实现。它们都不能直接覆盖BootShim/早期SEC。
4. **把通用加载器/QEMU和板级固件问题分开取证。** QEMU可验证菜单、协议、ADT/boot_args与内核入口逻辑，不能验证nuwa ABL、显示电源或USB PHY。

## 遍历范围及完整性

`scripts/audit-official-site.py`从两个入口沿导航、正文、页内锚点和前后页链接递归读取中文HTML，保存URL、HTTP状态、SHA256、标题、全部标题/ID和链接。再解析VitePress内嵌`__VP_HASH_MAP__`，以发布清单交叉核对，避免只看导航而漏掉页面。

| 范围 | 页面数 | 结果 |
| --- | --- | --- |
| 全站发布路由 | 144 | 72中文+72英文，源路径逐一配对 |
| 中文实际读取 | 72 | 全部HTTP200；发布清单中未遍历中文页为0 |
| porting | 5 | 总览、设备仓库、UEFI、ADT、bring-up |
| devices | 32 | 总表、设备页及sheng无人值守流程 |
| drivers | 7 | 分层、UEFI、静态XNU、kext、匹配、触控、GPU |
| guide | 8 | 环境、构建、启动、日志、身份、Data/Setup等 |
| reference | 7 | CLI、两种配置、输出、QEMU、排障、术语 |
| concepts / xnu / contributing | 5 / 4 / 2 | 负载/预链接/安全/根布局、4K/补丁、仓库结构 |
| 首页与building | 2 | 首页导航及完整构建流程 |

英文路由已核对配对关系，没有重复抓取全部英文正文。外部GitHub/社群链接已建索引，只继续审查与当前问题直接相关的公开仓库，不递归抓取Telegram、QQ或所有外站。搜索工具无法打开这两个中文入口，但Python HTTPS直接读取成功；`/sitemap.xml`为404，故使用VitePress发布清单校验。

完整页面导航见`reports/official-site-audit/page-index.md`，机器证据为`structure.json`。原始HTML/可读正文保存在Git忽略的`out/official-site-audit/`。发现一个坏锚点：`/zh/guide/mobilegestalt`链接`/zh/guide/requirements#target-ipsw`，中文页面实际ID为中文标题。页面本身可访问，不影响技术内容。

## 对当前黑屏最直接的帮助

官方[UEFI](https://unixnu.com/zh/porting/uefi-firmware)、[启动链](https://unixnu.com/zh/concepts/boot-chain)、[sheng](https://unixnu.com/zh/devices/sheng)共同给出应检查的边界：

- BootShim编译基址/大小、ARM64头、gzip解包后的shim+FD、追加FDT和ramdisk必须分别对账。官方示例header v0及地址只是特定配置，不能自动改写nuwa已测v4或证明大ramdisk是必要条件。
- sheng明确记录ABL在没有`/reserved-memory/splash_region`时关闭面板。nuwa既往Android DT的splash地址与Mu framebuffer静态区一致，但**本次候选实际交给固件的DT、屏幕是否持续扫描、GOP是否已初始化均未验证**。优先离线检查交接树/显示约束，不能直接复制别机节点后宣布修复。
- 必需的EFI协议分开验收：GOP/输入/BlockIo/文件系统/SerialIo/FirmwareVolume2。四EFI已编译、加入FV不等于DXE已dispatch、BDS已运行、负载已发现。
- 官方提供空ramdisk菜单冒烟方式，说明无XNU/无大FAT也可以作为固件隔离目标；仍需nuwa自己的ABL接受与实际执行证据。
- 官方提到Silicium偶发停顿可重试同镜像。本仓D-016要求每次先重进bootloader隔离状态，不能机械照搬重试命令，更不在当前设备暂停期间执行。

当前nuwa的阶段1仍未取得屏幕/独立日志证明，阶段2至7均未实机验收；不因源码内核CI成功跳过阶段1。

## 新发现：Darwin22 boot_args源定义差异

官方[启动链](https://unixnu.com/zh/concepts/boot-chain)标明Darwin23结构。比对本地只读输入：

- `D:/Code/PortingiOS/common/sources/xnu-ios16-full/pexpert/pexpert/arm64/boot.h:26,61-76`：`BOOT_LINE_LENGTH=608`。
- `D:/Code/PortingiOS/common/sources/UniXNU/drivers/DarwinBoot/DarwinBootPkg/Driver/BootArgs.h:7-31`：注明Darwin23，CommandLine为1024，静态断言尾字段偏移0x478、总长0x480。

`scripts/audit-darwin22-boot-args.py`显式按ARM64 LP64（不使用Windows的32位unsigned long）建模，结果见`darwin22-boot-args.json`：

| 字段 | 8796原始头定义 | 当前DarwinBoot头定义 |
| --- | --- | --- |
| Video / DeviceTree / CommandLine偏移 | 0x28 / 0x60 / 0x6c | 相同 |
| CommandLine长度 | 608 | 1024 |
| BootFlags偏移 | 0x2d0 | 0x470 |
| memSizeActual偏移 | 0x2d8 | 0x478 |
| 结构长度 | 0x2e0 | 0x480 |

这说明不能以“前几个字段一致”验收完整ABI。**本轮是源头文件静态比较，尚未从CI15的DWARF或最终编译视图证明实际结构。** 下一步应先核对实际内核布局和加载器构建输入，再设计设备仓Darwin22适配，而非立即改上游或拉长8796结构。当前v4无XNU负载，不能把此差异解释成黑屏原因。

`header-source-pins.json`另核对了[8796固定源码头](https://github.com/apple-oss-distributions/xnu/blob/1b191cb58250d0705d8a51287127505aa4bc0789/pexpert/pexpert/arm64/boot.h)与[本仓固定基座的DarwinBoot头](https://github.com/UniXNU/UniXNU/blob/75bc13dd34dc4e403826793739e316a264ce00dd/drivers/DarwinBoot/DarwinBootPkg/Driver/BootArgs.h)：两份本地文件分别与远端固定版本LF归一化一致。静态布局脚本对完整输入SHA设门，文件变更后须重新审查模型。

## 日志路线：可直接研究的已有实现

| 来源 | 实际机制 | 对本仓的帮助及限制 |
| --- | --- | --- |
| [调试与日志](https://unixnu.com/zh/guide/debugging) | UniXNU写首个EFI_SERIAL_IO_PROTOCOL；支持USB device的板可提供CDC ACM | 后续UEFI CDC接线应考虑发布SerialIo，让既有UNIXNU/DARWINBOOT输出复用；SEC DebugLib需另接，不能以DXE协议覆盖更早阶段 |
| [sheng无人值守](https://unixnu.com/zh/devices/sheng-unattended-test) | BootLog写userdata尾部32MiB；另临时启动Linux，通过CDC取回 | 有可复用格式/读取器，不必重造完整持久日志系统；依赖NativeUfs根布局、日志窗口、PMIC重启、Linux内核/USB，当前nuwa未满足 |
| [Ace5/giulia](https://unixnu.com/zh/devices/giulia) | 文档记录iOS16/Darwin22原生UFS、USB CDC、launchd/Hello | 继续追到SM8550 vermeer USB源码，是比直接新写USB协议更有价值的候选；SM8650测试结果不等于nuwa通过 |
| 既有Mu AdvancedLogger候选 | SEC RAM记录，后期导出 | 对当前早期黑屏仍有价值，但RAM地址、保留/映射、cache和读回必须落实，不填地址猜测 |

读取固定公开源码后的具体证据（文件SHA和已检查行号索引见`source-excerpts.json`）：

- `UniXNU/UniXNU-sheng@b06f2df186c8967fe0cd791d6598d7d86f320d77`，`package/BootLog.c:1-11,19-23,738-742`：MIT声明、NativeUfs接口、等待root layout才启用。`scripts/read-sheng-log.py:1-9,146-151`有解码/USB读取，但端口发现使用macOS的`/dev/cu.usbmodem*`，Windows需要适配；其默认还会请求重启，不能直接在设备暂停期间运行。
- 同版本`package/linux-log/init:19-27,31-40`：Linux configfs ACM gadget，复制分区尾部至RAM；它是独立Linux阶段，不是UEFI CDC。日志/导出区在新版本还有额外窗口，不能只凭“尾32MiB”盲写nuwa userdata。读取器、BootReset与镜像构建均未执行。
- `tycykp/UniXNU-OnePlus-Ace5@346814dded00f7dbbd67f08b83f49812ad1b6c5a`，`ios16/sources.json:8-11`钉住`xyyyds0106/ios-vermeer-lab@d68e05df683f863f054b0f9c063c54d2b1342b2a`，用途明确包含SM8550原生CDC。前者补丁`ios16/0073-giulia-complete-boot-log.patch:252-265`引用`vermeer_usb_debug.c`及RAM日志回放。
- 上述vermeer固定版本`xnu/vermeer/vermeer_usb_debug.c:1-5,381-445`包含真正DWC3端点/控制请求、DMA/cache维护和轮询线程；启动需内核虚拟内存、物理页查找及线程API，故不能直接在BootShim/SEC调用。它依赖ABL保留的PHY/时钟，并核对SMMU identity路由；本仓SEC会调整SMMU，继承条件仍须核对，不能只改机型名启用。
- vermeer和guacamole所读固定树没有发现LICENSE/COPYING/NOTICE路径；vermeer USB文件头也没有SPDX。**许可来源确认仍TODO，不能把公开可见直接视为可分发复用授权。** 本轮只审查，没有导入驱动。Ace5根LICENSE为BSD-2-Clause-Patent，不会自动授予其引用的外部源码许可。

由此补充Q-061：USB不仅有通用可行性，还有明确可研究的现成XNU实现及持久日志读取器；但当前早期SEC故障仍需要更早的记录与回收通道。sheng“USB不可用”功能表与其Linux读取器并不冲突，后者运行在另一个Linux阶段。

## 其他机型如何用于本路线

| 来源 | 优先研究 | 不迁移的内容 |
| --- | --- | --- |
| sheng / SM8550 | 完整基座接线、UFS/PMGR/SMMU、A740、HID、分阶段探针与日志格式 | iPad donor、slide/roots/安全入口、触控IC、分区/内存地址 |
| fuxi / vermeer / nx729j设备仓 | 同SoC配置结构、来源注释、构建组织 | 文档多数未记录运行证据；从sheng继承不代表该机已运行 |
| guacamole / SM8150 / iOS16.7.16 | UniXNU/DarwinBoot与iPhone用户态组合、x0/FDT保存、initrd内存保护、配置卷诊断 | README明确16KiB内核，DarwinBoot补丁按32MiB block对齐；不迁移其页大小、3GiB窗口、保留地址、FAT扫描或GCD扩展 |
| giulia / SM8650 / Darwin22 | USB协议、日志/用户态兼容问题、真实证据组织 | HFSX/ios-sweet系统路线、SM8650寄存器和电源值、未经本仓核对的安全修改 |
| QEMU / DroidVM | 菜单/loader/ADT/IOKit/4K逻辑隔离与virtio测试 | 虚拟机桌面不能当nuwa裸机/USB/UFS通过 |
| uke / oneplus13t / fajita / nabu | 入口检查点、负载发现、不同ABL行为的失败隔离方法 | 其他设备槽位切换、刷boot分区、固定地址或“缺ramdisk”对策 |

guacamole核查固定`wochgn/UniXNU-guacamole@6269d315dbf43c4f7334177721f5c18e9b633f97`：README:59-64明示16KiB/32MiB布局；`patches/aloha-guacamole.patch:22-27,483-486`分别保存x0和保护initrd；不能整块应用其925行固件补丁。既定4KiB不变。

## 配置、身份及用户态方面的补充

- [环境要求](https://unixnu.com/zh/guide/requirements)已列iPhone10,3/10,6 iOS16.7.16/20H392；[构建](https://unixnu.com/zh/building)明确无Mac时使用Actions macOS runner。本仓云端真实构建已有证据，不再把WSL缺Xcode当内核构建停点；WSL本机完整构建仍未验证。
- [静态驱动](https://unixnu.com/zh/drivers/xnu-drivers)要求同轮编译记录、force_load、重链接依赖和KernelConfigTables personality，正好对应CI15已完成部分；Darwin23/iOS17对象ABI示例不能原样作为8796验收。尚欠provider、定时器、boot-progress/watchdog运行接线。
- [kext页](https://unixnu.com/zh/drivers/kexts)说明发布版DarwinBoot拒绝暂存kext请求，不能以在TOML放一个kext目录替代内核静态链接或donor预链接。
- [ADT](https://unixnu.com/zh/porting/device-tree)区分FDT和Apple编码；XNU使用`.adt` sidecar。对xnu菜单项硬塞FDT会被发布版DarwinBoot拒绝。Darwin窗口仍256MiB–8GiB/2MiB步进，执行D-002先512MiB–1GiB。
- [MobileGestalt](https://unixnu.com/zh/guide/mobilegestalt)写明iPhone根model/target-type/product/phone idiom；该页还以iPad生成器解释ipad_identity，其措辞不能覆盖用户已定D-004。[Skip Setup](https://unixnu.com/zh/guide/skip-setup)仍说明四个/chosen安全属性。**保持ipad_identity=true，iPhone产品身份和安全属性分别核对，不回退iPadOS。** 未创建额外board字段。
- Skip Setup示例仍硬编码21H461/17.7.11，不能给20H392套用；根镜像OS/Cryptex布局和Data种子须由本donor manifest确定。日志读取器或别机HFSX根不改变本仓根卷路线。
- [nuwa官方页](https://unixnu.com/zh/devices/nuwa)已经收录wh1stl3，但仍写ArmCpu/archive失败、VFS待编译，落后于CI15和本仓固件试启动记录；页面自己也以本仓STATUS为准。它不是独立的nuwa成功证据，本轮不代用户联系维护者或发PR。

## 上游版本差异与执行顺序

只读观察到UniXNU当前HEAD为`d704728a6df9d1eb113873dc1b57e87f6846e361`，比本仓固定`75bc13dd34dc4e403826793739e316a264ce00dd`前进89提交。GitHub compare接口文件列表截断于300项，本轮另比两份未截断的递归Git树，得到509个非目录变更条目，包含驱动迁为子模块以及构建/文档更新；这不是509个已审阅功能改动。`upstream-compare.json`保留完整树条目差异。**没有更新feed、lock、基座或固件版本**，具体跟进须逐文件diff并单独提交。

建议主线顺序：

1. **P0离线**：先核对CI15实际boot_args类型及当前DarwinBoot来源；继续ABL入口、FDT/splash、x0和initrd保留审查，为最小观测补丁确定出口，当前没有安全RAM地址时保持TODO。
2. **P0日志来源审查**：完成vermeer CDC许可、Darwin22依赖、4K/DMA/SMMU假设审查；UEFI路径则核对高通协议→SerialIo桥接。XNU USB、DXE USB、SEC记录分别列验收门。
3. **P1通用验证**：准备官方QEMU fixture适用性与Windows/WSL工具输入核查。实际运行还须遵守新诊断镜像生成边界，不把网页命令当本轮执行授权；不在此报告声称QEMU已通过。
4. **P1内核负载**：补provider/ARCH_TIMER/PSCI、boot-progress/watchdog与donor ABI审查，才进入本仓源内核的完整预链接/负载集成。沿用CI15内核，不混用参考P16或旧FAT。
5. **P2后期**：UFS/根布局证据成熟后再适配sheng BootLog、读取器、Data/Setup；A740和ST FTS SPI/HID在相应阶段复用真实驱动。

设备暂停持续。本轮只有网页抓取、源码节选/布局静态检查和文档；新镜像、board/bringup内存与基址、实机启动、任何_verified=true均未执行。
