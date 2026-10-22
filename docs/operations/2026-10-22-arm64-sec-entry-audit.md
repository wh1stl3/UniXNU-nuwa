# ARM64 / BootShim入口条件与SEC日志出口离线审查

2026-10-22 20:53（Asia/Shanghai）。用户要求先离线分析；实机访问暂停继续生效。本轮只读既有候选/原厂备份、归档ABL、固定源文件及CI构建报告，没有ADB/fastboot/USB查询，没有生成或修改镜像、board/feed或_verified。

## 主要结论

1. **当前SEC日志出口是帧缓冲像素，不是UART/USB或独立持久缓冲。** WARN/ERROR未关闭，异常也走同一出口；无文字不能推断SEC没有执行。
2. **第一条正常横幅之前已经有一段无独立观测的路径。** BootShim、SEC汇编与栈、cache/VBAR、PlatformInitialize的SMMU调整，均在屏幕日志之前；随后还会先清屏。
3. **真实FD的入口接线静态吻合。** reset vector、TE入口、链接map及最初保存x0的机器码一致，不能把“FD直接跳错SEC地址”当作已知故障。
4. **ABL交接状态与加载位置仍是TODO。** BootShim不准备EL/DAIF/MMU/cache；Image头text_offset为FD_BASE数值、无EFI PE头，与原厂Image不同。尚未证明ABL如何解释或选择入口，不能直接宣布字段错误或缺PE导致黑屏。

自动证据reports/arm64-sec-entry-audit/audit.json，33项静态断言通过；脚本scripts/audit-arm64-sec-entry.py只写JSON，不调用设备工具或生成二进制。源文件hash、固定版本、候选/原厂/FD/map/report hash均在证据中。

## 固定输入与证据范围

Mu-Silicium 6c6755012728c9f7de748228758bad94d1e9a660、Mu_Basecore cfb93724a06ff86ff5ba971413368a7809ee42a5；已应用的4份候选补丁见patches/firmware-candidates/。实际固件由CI39764322744生成，审查的是试启动同一SHA12864ac6…的v4包和SHAa0bbb964…的FD。部分原源文件未打补丁，结合0001/0004及实际机器码核对，不将未改动参考树误写成云端已补丁源树。

原厂boot为ef558db2…的只读备份（此前临时启动进入Android已有记录）；归档abl_a为38a837fa917ff45e5be7cf6a421e0417015d875db503d1fb2dbc4d89080b0188。未查询当前安装的ABL，不能将归档版本当成本轮暂停期间的当前设备内容。

## ARM64头与入口契约

| 字段 | 原厂Image | 当前BootShim+FD |
| --- | --- | --- |
| kernel文件字节 | 40417792 | 3145840 |
| ARM64 magic | ARMd | ARMd |
| text_offset | 0 | 0xa7100000 |
| image_size | 41091072（含运行空间） | 3145840（shim+FD） |
| flags | 0xa（页大小标志=4KiB） | 0（页大小未指定） |
| DOS MZ / PE | 存在，PE偏移0x40 | 不存在 |
| 首两字 | fa405a4d / 148b7fff | 10000381 / 1400000f |

这不改变既定4KiB决策；flags未指定不能解释为采用16KiB。原厂PE入口与直接ARM64入口并存的事实，也不能证明ABL实际用了哪一条。

[Linux官方ARM64启动规范](https://docs.kernel.org/arch/arm64/booting.html)将text_offset定义为相对2MiB对齐基址的偏移，描述x0传DTB、非安全EL1/EL2、DAIF屏蔽、MMU关闭及代码cache一致性要求。当前header把上游FD_BASE数值写入该字段；**绝对FD目的地与相对Image放置偏移不能不加证明地等同**。这是一项高优先级契约缺口，仍未证明本机ABL遵循哪种地址计算。v4容器自身没有EL/SCTLR/SPSel/实际PC字段，单凭头与Booting OKAY不能补出运行状态。

归档ABL的ELF内含FV，纯内存展开后找到ARM64 magic检查、BootLinux路径和“Failed to load/authenticate boot image: %r”等诊断字符串。它们说明代码包含相应路径；没有分支/数据流和本轮日志，不能据字符串声称EFI stub必需、PE缺失必失败，或把Load Error直接对应到某一入口阶段。

## BootShim实际机器码与必要条件

- offset0的ADR X1计算出L+112（L为未知的实际Image地址），offset4的B跳到0x40，正确越过64B头。
- X5装入0xa7100000，X6装入3145728，16B前向LDP/STP循环；image_size含shim，但拷贝计数只含FD。最终BR X5。输入FD和已下载固件完全一致。
- x0在shim路径中不被修改；x1–x6为临时值。名字_StackBase/_StackSize实际是头字段标签，不会设置SP。
- 这112B没有EL/DAIF/SPSel设置，也没有MMU关闭、D-cache清写或目的地I-cache同步。SEC的后续cache操作不能倒过来保证之前已经执行的拷贝/取指。

设D=0xa7100000、F=0x300000、H=112、S=L+H。需证明S/D可访问、适合16B拷贝、目的范围[D,D+F)不覆盖正在执行的[L,L+H)及DTB；若S<D<S+F，前向拷贝会覆盖未读源数据，不能当memmove用。S=D时走原位快路径。L与本轮DTB物理范围未知，因此这些条件仍未验证，未给L填假值。

cache要求应明确记录：当前代码没有在BR目的地前主动保证新写指令可见；不能仅凭源Image在交接前已清到PoC，就推定另一个拷贝目的地也满足。入口M/C/I状态、目的地旧I-cache状态及其维护路径需要证据，不能因SEC后来调用invalidate就略去。

## FD→SEC→C入口：已核对的部分

实际FD偏移0的指令0x14002a0e是B +0xa838，物理目标0xa710a838，与TE的ImageBase+EntryRVA及FVMAIN_COMPACT.Fv.map的_ModuleEntryPoint一致。TE头布局还验证了StrippedSize调整与物理基址的关系。

入口ADR指向0xa710a8d8的gSecEntryArg0；下一条0xf9000020保存x0。随后PlatformAssemblyInitialize在固定Kailua实现中仅ret。早期模块代码没有显式选择SPSel；继承值未知，不自动断言必须更改。EL1_OR_EL2只接受EL1/EL2，EL0/EL3落入自旋路径。

源码设置栈[PcdCPUCoresStackBase=0xa760d000, +0x40000)，top=0xa764d000；这是已有CI PCD，不是新选板值。栈准备发生在C入口前。HOB指针生产则更晚：新增0004在InitializeMemory/PlatformPeim之后BuildGuidDataHob，不能期待一进入汇编就已有可用HOB。

编译后SecEntry=0xa7101058；前几条BL分别落到ArmDisableDataCache(0xa7108dd4)、ArmInvalidateInstructionCache(0xa7109274)、ArmEnableInstructionCache(0xa7109028)，随后对stack和FD做InvalidateDataCacheRange，再设置VBAR。异常向量0xa710a000满足2KiB对齐。固定ArmDisableDataCache只清SCTLR.C并做屏障，不包含全体脏数据清写；若更早存储依赖未落地cache，该路径没有可凭空假定的保障。是否在本机发生未验证。

这些静态吻合不构成进入过SEC的实机证据；本轮既有黑屏结果仍维持BootShim/SEC/DXE未验证。

## SEC日志的真实去向与盲区

实际构建报告BUILD_REPORT.txt:1210起的Sec块明确链接：

- BaseDebugLibSerialPort / BaseDebugPrintErrorLevelLib；
- FrameBufferSerialPortLib，而非UART实现；
- DebugAgentLibNull；
- Kailua PlatformSecLib，以及ArmArchTimerLib。

PcdDebugPropertyMask=0x2f、PcdDebugPrintErrorLevel=0x8007ee0f、PcdFixedDebugPrintErrorLevel=0xffffffff：WARN/ERROR可输出，INFO被当前运行mask过滤；ASSERT启用且选择deadloop。FD内确实含版本横幅和同步异常字符串，不是只看源码宏猜测。简单“打开DEBUG”不能建立新的日志出口。

FrameBufferSerialPortLib.c:243-276的SerialPortWrite查Display Reserved，然后直接绘制字符并刷cache；SerialPortInitialize:326只返回成功，没有初始化面板/GOP。Read返回0、Poll返回FALSE、属性控制不支持。没有写UART、USB或结构化持久日志；内存表里有UEFI Log区域并不证明此DebugLib会写它。

当前静态Display Reserved为0xb8000000/0x2b00000；PCD1440×3200×32bpp，以5760B stride绘制，像素区18432000B落在声明的45088768B内。此前原厂Android DT的splash_region声明与该区间相同（原DTB hash在JSON），只证明历史保留声明对应；候选实际scanout、像素格式、stride、面板和SMMU状态未验证。

正常路径顺序如下：

```text
BootShim（无日志）
  → FD reset vector → SEC汇编保存x0/设置栈
  → C入口cache/VBAR准备
  → PlatformInitialize：ArmSmmuDetach（跳过固定MdpStreams，调整其他流/CB）
  → SerialPortInitialize（本身不初始化硬件）
  → ClearFrameBuffer（清Display Reserved整段）→ 版本横幅
  → InitializeMemory/MMU/HOB → PlatformPeim/入口HOB
  → 解压FV → 加载DXE Core → 后续DXE/BDS
```

Sec.c:98/102/108/116/137/144及固定Kailua PlatformSec.c提供源顺序，机器码也能找到横幅前的SMMU寄存器读取。**第一条正常屏幕日志之前已经操作显示相关SMMU，并可能清屏**。黑屏既不能证明完全未进SEC，也不能证明SMMU/清屏就是本次根因。

ArchSec.c:12-46的异常处理只格式化异常类型和ELR，调用同一个SerialPortWrite后CpuDeadLoop；没有独立记录CurrentEL/SCTLR/DAIF/ESR/FAR的出口。显示链不工作时，正常和异常路径的文字都可能不可见。

## 最小后续证据清单（本轮不执行）

| 优先级 | 要回答的问题 | 最小信息/标记 |
| --- | --- | --- |
| 1 | ABL实际把候选放哪、用哪种入口 | L、实际PC/交接路径，区分直接ARM64与EFI入口，不以Booting ACK替代 |
| 2 | BootShim安全前提是否满足 | CurrentEL、DAIF、SPSel、SCTLR.M/C/I、原x0，复制源/目的/DTB是否重叠 |
| 3 | 实际越过了哪一段 | shim入口/复制完成/SEC汇编入口/C入口的可区分标记 |
| 4 | 第一条日志前是否停住 | PlatformInitialize前后、清屏前后、MemoryPeim前后 |
| 5 | 是否真正进入固件后半段 | FV解压完成、DXE Core入口、BDS/应用注册与菜单标记 |

先确定能够回收且不依赖显示链的通道：现成UART路由需要核实真实实现/引脚/宿主连接；若考虑固件自有RAM记录，必须先证明所有权、保留和恢复后的回读路径。两者当前都不能凭名字假定已存在，不能随意挑未确认的MMIO或保留区地址。

后续还可继续离线追归档ABL的加载/交接分支和已有日志实现；只有用户解除本仓实机暂停后才执行设备验证。新增诊断/固件镜像与板字段按具体已授权范围/硬停规则处理。本轮只交付静态证据和待测清单。
