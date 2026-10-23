# BlockIo → FAT → 配置发现：离线接口审查

本轮无设备命令、模式切换、镜像重写或固件修改。目的在于把可独立审查的连接顺序、驱动存在性和内存类型与未知的候选 initrd 分开，避免所有问题都等待 SHENGMEM。

证据：`reports/system-volume-audit/discovery-chain.json`；复现命令 `python -B scripts/audit-volume-discovery-chain.py`（要求报告路径尚不存在）。读取固定 Git 对象、已有 FD 和固定 Mu 源码文本，文本仅在内存审查，没有复制上游源码进设备仓。

## 发现链路

| 环节 | 固定源码与实际产物证据 | 仍未验证 |
| --- | --- | --- |
| 发布块设备 | 固件1ccf760的NuwaBootMemoryDxe.c/inf，DEPEX TRUE；实际FD有对应唯一PE | 该次入口FDT、initrd、InstallMultipleProtocolInterfaces返回状态 |
| DiskIo绑定 | Mu cfb93724的DiskIo.c从BlockIo绑定并安装DiskIo；实际FD存在DiskIoDxe PE | 实机ConnectController返回及实际协议安装 |
| FAT绑定 | 同提交Fat.c要求DiskIo及BlockIo，Init.c安装SimpleFileSystem；实际FD有Fat及EnglishDxe PE | BPB识别、内存可读性、卷挂载与字符排序协议可用性 |
| 连接控制器 | UniXNU75bc13dd的UniXNUDxe.c把unixnu:firmware写入LoadOptions；应用识别后在Main.c:81先ConnectAll，再ConfigLoad | 本次启动确实使用该选项及实际连接结果，不能仅凭菜单推定 |
| 搜索配置 | Config.c:1501、1505先自身DeviceHandle后所有SimpleFileSystem卷；TryVolume读指定文件并解析 | 实机找到探针配置和正确处理内容 |

源码中已有递归ConnectController，不能把“还需要补一个ConnectAll”当作已定位缺陷。Fat.c的绑定支持检查没有LogicalPartition门槛，故不能仅凭发布器LogicalPartition=FALSE便断言必须先增加GPT/MBR；这也不证明任意镜像已经能挂载。

DSC/FDF的包含不代替实际二进制核验。本轮从固定R-011 FD SHA aca853390666e48dfd3901bdfca2a9deab0d7978a02152c4ad497564f0b8b4d6内解包并核对四个基础模块、NuwaBootMemoryDxe及UniXNU的唯一文件GUID、AARCH64 PE和文件摘要，均通过。包括Fat、DiskIoDxe、PartitionDxe、EnglishDxe；因此没有发现这些驱动漏装进该FD，但未宣称它们全部实机绑定成功。

## 内存描述符格式修正与保留边界

审查发现既有 `audit-factory-heap-artifact.py` 注释把ResourceAttribute记为UINT64，实际固定Mu的 `MdePkg/Include/Pi/PiHob.h:241` 定义为UINT32。此前只按Name、Address/Length定位并逐字节比较整表，其72字节步长和比较结论不依赖该错误注释；本轮新字段解码初稿据此出现类型错位，尚未提交即已修正。

实际结构布局如下：

| 偏移 | 字段 | 字节 |
| --- | --- | --- |
| 0 | Name | 32 |
| 32 / 40 | Address / Length | 各8 |
| 48 / 52 / 56 | HobOption / ResourceType / ResourceAttribute | 各4 |
| 60 / 64 | MemoryType / ArmAttributes | 各4 |
| 68 | 尾部对齐填充 | 4 |

现解析为 `<QQIIIII4x`（从偏移32开始），MemoryType偏移60，保持整体stride72；与固定MemoryMapLib.h宏和Mu UefiMultiPhase.h枚举核对实际SEC全部41行MemoryType，均一致。旧新表完整字节比较回归仍通过：只改变获批Heap地址/长度，原SHA05a59df6、新SHA7694de6c不变；见 `descriptor-layout-regression.json`。

恢复后Android快照的initrd区间完整落在实际SEC的Kernel记录 `[0xa8000000, 0xb8000000)`，MemoryType=0（EfiReservedMemoryType）。MemoryInitPei.c会为此系统内存行生成分配HOB并建立对应映射；RamManagerDxe按已有内存描述符扣除占用范围后才添加缺口。这是**固定二进制与历史Android区间的静态对应**，不是候选该次UEFI内存图或整个使用期所有权的证明。

NuwaBootMemoryDxe自身仍不检查GCD/MMU映射、UEFI内存类型，也不独立保留传入initrd；因此取得候选区间后还必须确认它被正确映射和保留，不能把任意chosen指针直接当安全可读FAT。没有因此扩大内存表、修改board/bringup-plan或添加保留区。

## 来源、许可和依赖

- UniXNU/UniXNU@75bc13dd34dc4e403826793739e316a264ce00dd：UniXNU.c、UniXNUDxe.c、Main.c、Inject.c、Config.c，BSD-2-Clause-Patent。依赖UEFI LoadedImage、DriverBinding、SimpleFileSystem及配置解析库。
- microsoft/mu_basecore@cfb93724a06ff86ff5ba971413368a7809ee42a5：DiskIo、Partition、Fat、English及类型定义，BSD-2-Clause-Patent。文件SHA、固定源码URL和关键词行号均在JSON；未使用主分支浮动文件。Fat的UnicodeCollation2依赖仍需运行协议证据。
- wh1stl3/uefi-nuwa@1ccf760d667b9eec6dd3491c90cc04ebb7c58340：既有nuwa发布器与内存机制。发布器BSD-2-Clause、MemoryInit/RamManager保留原文件许可声明，本轮仅审查，未导入或改写。
- 既有同SoC发布器适用边界沿用 `same-soc-contracts.json`；不复制其DRAM/GCD扩展策略，也不以其他板块设备成功替代nuwa运行验收。

## 下一步

本轮排除了“实际FD里缺Fat/DiskIo模块”和“正常固件入口源码完全没有预连接步骤”这两个猜测，仍需候选实际initrd、协议返回及FAT识别日志。已有离线探针只验证制卷工具与配置字节，未接入启动包。

不依赖实机的后续工作仍有：检查真实Darwin22预链接负载与EFI的接口匹配、Apple ADT生成器的必需节点/类型契约、平台定时器/watchdog及boot-progress提供者闭包。这些可以与卷接线并行推进工作项，但各自静态检查均不等同XNU或iOS实机运行。
