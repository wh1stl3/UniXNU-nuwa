# NEED-REVIEW

> 需要用户拍板才能落地的改动。**没有 open 项时，这里保持空表。**
> 硬停四类：改内存相关字段 / 设备写入类 fastboot 动作 / 新建或重写镜像 / 置 `_verified=true`。

## 判定规则

立项必须写清：编号、背景、**至少两个候选**、各自代价、你的倾向及理由、需要用户批准的最小范围。
只写「是否继续」不算合格条目。

## Open

| 编号 | 主题 | 需要用户做什么 |
| --- | --- | --- |
| — | 无 | — |

## R-007 · 新SEC阶段诊断镜像（approved A，构建/试启动/恢复已完成）

背景：独立固件CI39805110487的四EFI/FD/BootShim及665项下载产物静态检查通过，但旧v4实机仅黑屏，未定位BootShim/SEC/DXE。新FD含Darwin22加载器修复，但不含XNU；不能期待该ABI修复本身解决未到加载器的黑屏。既有R-004 A只覆盖固定接线构建与审查，新SEC诊断改动和新boot容器超出这次已完成范围。触发AGENTS.md§3第3类：“新建或重写任何诊断 / 固件镜像”。

**候选A（倾向）：生成有限SEC阶段标记诊断版，沿已有可恢复授权临时试启动。** 源码补丁0005-nuwa-sec-stage-trace.patch已准备，固定原SEC LF SHAfd28b903，补丁SHAae5d5e16，patched SHA6af8dd4d；RAM应用与git apply --check通过。只在既有帧缓冲出口增加六个阶段WARN与阶段返回状态/已有x0值，并移除SEC全屏清零以保留文字；原SMMU、内存、HOB、解压和DXE调用不跳过，不增MMIO/内存地址。完整范围见operations/2026-10-22-dedicated-firmware-build.md和sec-trace-preview.json。

代价/限制：需另一次四EFI/FD/BootShim构建、独立静态检查及新v4临时boot容器；仍依赖面板显示，不能导出USB文本或定位ABL/BootShim/最早汇编，未显示时结论仍有限。打印与flush可能改变时序，不能把实验版当生产修复。后续试启动需用户查看屏幕，按D-016隔离bootloader状态，结束恢复Android=1；不刷分区、不改槽位。

**候选B：先完成独立USB日志驱动与早期RAM记录/回收，再生成诊断镜像。** 优点是DXE可向电脑回传文本，具备证据的RAM通道才能补早期日志；代价是USB描述符/事件/PHY角色、RAM所有权/cache/跨重启回读需实际开发与验证。当前没有安全缓冲区/持久回读证明，Android ramoops与固件FD重叠，不能直接选用；只做DXE USB仍不能覆盖更早入口。未实现、未估计完成时间。

倾向A：已有可审查的单文件补丁与匹配的当前splash保留区证据，先以有限范围缩小SEC的平台初始化/内存/解压阶段；不承诺一定可见，若仍黑屏再转独立通道/ABL交接排查。

**需要用户批准的最小范围：A这一份补丁对应的诊断四EFI/FD/BootShim生成及静态审查，并仅复用原厂已接受的v4头重新打包raw shim+FD临时容器（只更新kernel_size，无新增DTB/FAT/XNU）；临时设备操作沿既有可恢复fastboot授权，执行前重新核对nuwa和原厂恢复源，结束恢复Android=1。** 不包含v1大ramdisk对照、FAT/内核预链接、任何board/内存/地址/slot/flash/erase或_verified=true。新容器的完整SHA待获批构建后记录，当前不编造。

用户明确批准：“批准 R-007 A，继续构建 SEC 阶段诊断固件、检查产物并准备临时启动包，按既有授权试启动，结束后恢复 Android 并确认 boot_completed=1。”暂停解除；源码5e4a8c8/CI39809636575真实构建与产物检查通过，v4诊断包fbb7940a已临时试启动。Sending/Booting OKAY、用户“fastboot之后黑屏”、15次采样fastboot持续可见，SEC/DXE未验证。按D-016重新进入bootloader后临时加载已验证Android备份boot，00:09确认nuwa Android boot_completed=1；boot/vendor_boot/init_boot三个分区SHA与试前相同。实际结果见reports/sec-trace/39809636575/trial-summary.json及对应operations。Git操作已有持续授权，不重复申请。

## R-004 · 加载器候选编译与产物审计（approved A，已完成）

用户明确批准：“批准 R-004 的 A，继续编译 EFI/FD 和 BootShim 并检查产物”。本轮按A完成：CI39764322744成功，四EFI/FD/BootShim下载静态检查通过，见operations/2026-10-22-firmware-candidate-build.md；以下保留原候选与边界。暂停解除，不再请求同范围批准。

触发来源：本仓 AGENTS.md §3 第3类“新建或重写任何诊断 / 固件镜像”。Git/gh/workflow授权已明确，不重复请求；这里仅请求新的EFI/FD/BootShim产物生成范围。审批时尚未编译或生成这些产物；当前完成状态见上文。

背景：CI15自己的8796内核已链接ArmCpu/ArmDTPlatform。三份源码候选补丁完成了BootShim头修正、四模块DSC/FDF/包路径/库接线，并将sheng的initrd发布模块裁剪为只读BlockIo，去掉AddMemory/GCD扩展。75项静态检查及两来源树git apply --check通过；内核、来源、补丁、board/feed哈希固定。详细变更和来源见 [接线报告](operations/2026-10-22-loader-source-integration.md) 与 config/loader-candidate.json。

原厂表已独立提取，DXE Heap209.75MiB，隔壁的6GiB高地址Conv和AddDynamicMem转AddMem不能直接继承。尚无nuwa最终UEFI map和initrd保留/映射证据；四模块真实编译、FV容量/分派也尚未验证。本项不询问已作废容量选择。

**候选 A（倾向）：先只构建加载器固件候选并静态审计产物。**

最小范围：允许在独立GitHub Actions临时源树中，使用清单固定的mu-nuwa-firmware、UniXNU和uefi-sheng输入及三份补丁，生成四模块的EFI文件、nuwa FD和BootShim编译/头校验所需二进制；下载后核对模块GUID/DEPEX/协议依赖、FV大小、FD大小及shim头/拷贝长度，保存日志、输入版本和哈希。沿用固定固件来源的Resources/Configs/nuwa.toml及内存表，不改board/feed、内存/地址、设备槽位或_verified。只生成构建验收用产物，不打Android boot.img、不生成预链接/负载镜像、不执行fastboot或将固件送上手机。实际kernel payload仍固定CI15，完整预链接待另外完成。

代价：需要一次固件CI，可能暴露Mu/EDK版本、库依赖或3MiB FD空间问题；产物不能因此称可启动。若需要改地址/容量或扩展镜像范围，继续单独提出具体审批，不自动扩大。收益：先把可编译性与布局问题从内存策略、XNU运行配置和设备问题中分开取证。

**候选 B：推迟所有固件产物，继续源码/ABI与内存语义审查。**

在当前三补丁基础上继续检查Darwin22运行provider/时钟/回调、NativePrelink编码、原厂动态内存语义和initrd生命周期，期间不生成EFI/FD/BootShim/boot镜像。代价：实际EDK依赖、FV容量和模块格式错误仍要到后续构建才能发现，不能靠静态审查验收；最终运行map仍可能需要单独获批的实机验证。

倾向 A：源码候选已具体且可审阅，先获取真实编译证据能缩小后续调试范围；不会把旧内核/旧FD混进来，也不会继承隔壁的容量批准。**需要用户批准的最小范围就是A所列固件构建与静态产物审计；设备执行、board内存/地址变更及完整boot.img均不在其中。**

## R-005 · 恢复核对后准备固件入口包（已授权范围内实施，完成准备）

授权来源为用户“可以随意推送镜像，只要能恢复回fastboot”及“先核对恢复路径和DT/initrd映射，再准备试启动包”，无需为同范围生成/临时原厂恢复重复询问。本项记录具体实现选择，不声称用户逐字选择过下面字母。

候选A（本轮采用）：先临时加载哈希锁定的原厂nuwa boot恢复Android，再复用已被ABL接受的v4原厂头，仅改kernel_size，装入本仓验收的raw shim+FD；DT/原始ramdisk走现有vendor_boot，无新增FAT/XNU。代价：候选实际ABL放置、SEC DT访问和DXE仍需实测，原厂临时恢复不修复持久A槽标志。收益：已知头与恢复源可核对，避免编造legacy基址。

候选B：沿固定Mu的v1/gzip/附加DT/5B ramdisk配方生成。代价：上游DT含旧initrd属性，参考日志有Load Error且缺目标身份；mkbootimg默认base与参考仓不同。需额外核验，不能直接称比A可用。

A的输入、实现和报告见operations/2026-10-22-trial-boot-preflight.md。当前仅原厂boot临时恢复实机通过，新的3153920B固件包只静态检查通过；没有执行新包、flash或改槽位。board/内存字段和_verified审批仍独立，H-001未验证。不新增open审批项。

## R-006 · 已准备v4固件入口包临时启动（approved，已执行并恢复）

用户明确批准“临时启动咱们已准备的v4固件入口包，检查ABL、SEC和DXE/BDS的实际结果”。最小范围为SHA12864ac6…的既有3153920B包单次临时启动、只读观测及原厂ef558db2…恢复；不生成镜像、不flash/erase或改槽位。

候选A（获批执行）：对已核对nuwa执行fastboot boot现有包，记录屏幕/USB/命令，结束回Android。代价是现有日志通道有限，黑屏可能无法定位早期阶段，需原厂恢复。

候选B：先停留只读源码/入口与日志通道审查，再准备后续有观测手段的实验。代价是推迟现有包的命令接受结果，后续新增诊断范围另具体落实。

本轮A结果：Sending/Booting OKAY、黑屏、约29s内15次采样fastboot始终可见；SEC/DXE/BDS未验证。直接原厂恢复先Load Error，reboot bootloader后同一原厂boot成功，最终nuwa Android boot_completed=1。见operations/2026-10-22-v4-firmware-trial.md和reports/v4-firmware-trial/。未以ACK替代阶段通过，未置_verified。

## 后续授权记录（2026-10-22）

用户追加：“这个设备日常不需要用 可以随意推送镜像 只要能恢复回fastboot就行”。后续镜像推送/试启动在可恢复fastboot条件下已有授权，无需重复请求相同范围许可；优先临时加载并依据具体镜像、分区和恢复证据决定是否写入，不把此授权当作任意底层分区擦写可恢复的证明。H-001实体键恢复演练仍未验证；只差按键的项保留PENDING-HUMAN并继续软件工作。该授权不替代board/bringup-plan内存/基址审批或_verified实证。本轮仅完成R-004产物检查，未推送或启动镜像。


用户在官方CI接入核验后指定GitHub账号`wh1stl3`，确认目标仓库尚未创建，并明确“Git的所有命令都允许”。此前仅允许status/diff/log/show的Git命令限制已解除，不再为云端checkout/clone/apply范围重复请求批准。两个旧仓及上游来源树仍只读；四类硬停、feed不变、未知板值TODO及证据纪律继续有效。Actions主机方向见DECISIONS D-008，R-003 A保留为历史审批记录。

用户随后进一步明确：“有关Github的命令以后都无需问我要授权 都允许”。这是持续授权，不再重复向用户请求GitHub操作许可；不解除四类硬停或只读资料库边界。

## 审批记录：R-003

### R-003 · WSL工具链与Darwin22构建路线（approved A，第一阶段进行中）

用户本轮选择A，批准保留WSL的工具链预检/适配第一阶段；并确认没有额外Linux clang、IIG或sysroot输入。继续本仓内工作，原暂停解除；来源树、Git、feed、board和镜像边界保持。预检与非执行式适配计划已落地，9项自身测试通过，现有MIG后端代码生成及宿主头文件语法样例通过；完整工具输入仍未落实，详见[本轮报告](operations/2026-10-22-wsl-firststage-adapter.md)。以下保留审批时背景与候选。

触发来源：用户本轮第2项明确要求“要么拿出可在本机跑通内核构建的证据，要么列为不可行并写进docs/NEED-REVIEW.md……后停”。这次停下不是新增板值审批，也不是认为WSL先天不能构建XNU。

**现状结论：当前本机输入、现有基座入口和不执行Git写操作的约束下，直接完成8796内核构建不可行；没有完整内核构建通过证据。** 主线暂停于工具链门，未启动默认clone/apply入口。

背景与证据：

- [审查报告](operations/2026-10-22-darwin22-interfaces-and-wsl.md)及 `reports/darwin22-audit/interfaces.json`：8796产出.unstripped，多个基座消费者使用.unstripped.noctf；archive/编译记录生产者仍绑定Darwin23/ios17或来自sheng；13项回调只在参考树找到实现。NativePrelink kmod局部布局静态一致，但目标符号/完整ABI未验证。
- `reports/darwin22-audit/wsl-toolchain.log`：WSL可运行；默认clang14对三项XNU内建的__has_builtin探测均为0；xcrun/xcodebuild/IIG等不在PATH；有限范围没有找到已验证SDK。已有Linux MIG/cctools prefix与Python3.12可复用，没有被误判为缺失。
- watchdog参考实现有非union环境路径的scratch重叠风险；不能用导入sheng archive绕开接口适配。
- board仍example=true，feed未改。两个旧仓及上游源树保持只读，没有生成镜像或操作设备。

**候选 A：保留WSL要求，先建立经验证的Linux交叉构建输入与无Git写入适配器（倾向）。**

第一阶段交付应为：含所需XNU内建的Linux ELF编译器与版本/哈希/特征证据；MIG/IIG与宿主工具的Linux生产链；明确目标/宿主sysroot；设备仓中的8796产物/编译记录/archive调度适配设计。只用常规clang14或仅包一层xcrun脚本不算通过。随后才讨论完整源内核编译，必须单独提供真实compile/link日志、产物格式/符号检查，不能用生成数据库替代。

代价：需工具链移植或宿主提供已构建工具、对应头文件/sysroot；IIG、XNU内建与编译记录生成均是实际工作，时间和成功率未验证。还需宿主明确提供独立可写补丁应用视图，或另行批准构建视图方案，不能修改只读来源、在本仓复制整份上游源码或调用Git写命令。优点：保持当前所有构建在WSL的边界，避免引入第二个构建主机。现有Linux MIG/cctools可复查后复用，但不继承旧P16/SWEET内核结论。

**候选 B：批准仅内核与archive编译改用macOS/Xcode主机，WSL保留编排和证据审计。**

以同一8796输入和设备仓补丁选择集在用户提供的macOS主机/受控执行环境构建；回传编译记录、archive符号报告和内核哈希。本地只做读取、验证与后续集成。使用基座已有Xcode调用方式可减少宿主工具移植，但仍须修正8796产物名/版本依赖、重建driver/回调、处理watchdog风险，并核验编译器内建与SDK，不能把“有Mac”当作8796已通过。

代价：显式改变“构建全在WSL”的边界，需要额外主机/执行环境及传输、版本固定、成本与可复现性管理；主机是否可用、费用和交付时间均未验证。当前没有启动任何远端任务或外发源码/凭据，也没有新建CI workflow。

倾向 A：符合用户既定WSL主线，并能把缺失输入与接口门槛逐项验证；若用户优先减少宿主工具移植工作，B是需要明确批准的替代路径，不自动切换。两条路径均保留iOS16/iPhone donor与4KiB，均不使用iOS17 donor绕过问题。

**需要批准的最小范围：选择 A 或 B 的方向与第一阶段范围。** 选择A仅批准本仓内无Git写入的工具链预检/适配工作及输入清单落实；工具安装、外部目录写入、来源树复制/覆盖视图等需明确范围后才做。选择B需明确批准macOS内核构建例外，再确认可用执行环境，不能直接启动外部任务。

本项不请求解除Git只读限制，不授权feed切换、board内存/地址修改、移除example保护、镜像生成、设备动作或_verified=true。原暂停已由用户选择A解除；工具链输入未落实时不能宣称构建可执行。

## 审批记录

### R-002 · 首版设备描述（approved，已落地）

用户本轮回复 A，批准候选 A 的精确范围。已创建根目录 board.toml，内容与下方获批代码块逐字一致（忽略末尾换行）。没有填写内存/地址、额外IPSW字段或prelink值；example=true 与 ipad_identity=true 保持。以下背景与候选保留为审批记录，不再是 open 待办。

审批前背景：49项检查已复现38通过/11失败，D-006继续适配8796。当时本仓没有 board.toml；基座 `scripts/unixnu/config.py:73-79` 在读取模块前就要求该文件和板名。用户本轮第六条明确把 **IPSW身份** 列为硬停字段，因此即使 donor 已定，也先提交具体写入范围再停，获批前没有创建 board.toml。

候选 A（倾向）：创建下列不可构建的最小占位文件，只写已定产品身份；未知项用注释 TODO，保留缺失而不填假的数值。代价：可以为后续 status/模块解析准备入口，但不能构建、生成ADT或镜像，完整性仍不合格；`example = true` 也会拒绝 build/bootimg（`config.py:101-103`）。

```toml
[board]
name = "nuwa"
soc = "SM8550"
description = "Xiaomi 13 Pro / iOS 16 bring-up"
example = true
# TODO: kit，尚无经审查的nuwa平台kit，不能照抄sheng实现。

[ipsw]
product = "iPhone10,3"
version = "16.7.16"
build = "20H392"
device_class = "d22ap"
# TODO: url/chip_id/board_id/sha256；缺donor BuildManifest及组件哈希核对。

[payload.adt]
ipad_identity = true
# TODO: tool/chip_id/cpu_regs/psci_method等，待nuwa ADT来源核对。
# TODO: owned_memory_size，缺UEFI可用连续区证据；D-002先512MiB–1GiB，上限8GiB。
# TODO: [payload] dram_size，物理DRAM描述尚需核对，不能当作窗口大小。
# TODO: [userdata] LBA与lba_bytes，缺本轮GPT证据核对。
# TODO: [kernel] defconfig/archives，缺8796配置及Darwin22接口审查。
# TODO: [kernel.prelink] 全部数值，缺donor kernelcache分析；不借sheng/fuxi值。
# TODO: [firmware] 配置/路径，uefi-nuwa尚未建立。
# TODO: [bootimg.image] 地址/offset/pagesize/header_version，缺nuwa装载证据。
```

这些都是官方现有键；TODO注释不作为TOML字段，不引入新schema键。身份依据 D-004，安全属性依据官方摘录与 D-004；schema依据官方摘录§2及上述本地基座入口。未声明完整板级配置静态检查通过。

候选 B：暂不创建 board，先完成8796补丁覆盖、NativePrelink/接口审查和donor manifest核对，再一次性审阅更完整配置。代价：模块状态只能继续静态阅读，完整 board 仍要等待UEFI内存/bootimg证据；优点是减少占位文件的后续修改。

倾向 A：已定身份有明确来源，`example=true`限制构建，能以最小配置为设备仓接入做准备；不提前选择任何内存/基址值。

**请求批准的最小范围：仅创建上述 A 的 board.toml 内容。** 不包含内存/地址数值、bootimg字段赋值、其他IPSW字段、prelink值、镜像生成、Git写操作、设备动作或任何 `_verified=true`。若批准仅对此范围落地，后续触及其他硬停项仍单独审阅。原暂停要求已由用户选择 A 解除；批准只覆盖上述最小文件内容。

## Closed

| 编号 | 主题 | 结论 |
| --- | --- | --- |
| R-001 | 内存窗口怎么声明（nuwa DRAM 不连续 11.22 GiB） | **answered by D-001 → 修正为 D-002**：单窗口为硬约束，排除「14 段全给」；原 A 提案区间不连续，不成立；首选主 bank `0x8c0000000` / 9216 MiB，退路 A′ 768 MiB。详见 `DECISIONS.md` D-001 |
| R-002 | 首版 board.toml 最小占位 | **approved，已落地**：用户选择 A；精确内容见上方及根目录 board.toml，未授权其余硬停项。 |
| R-003 | WSL工具链路线 | **approved A，范围已明确**：用户保持WSL主线；本仓预检/适配计划已落地，工具输入仍未落实；未批准安装或其他目录/源树写入。 |
