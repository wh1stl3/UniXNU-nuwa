# HackiOS、P16、UniXNU/U17 与当前 nuwa 路线比较

核查日期：2026-10-22。方法：GitHub 实时 API、公开源码静态阅读、两个本地项目文档对照。没有执行下载仓库中的构建/部署脚本，没有运行其预编译产物，没有设备操作。本报告不能作为独立复现实机结果。

## 结论

HackiOS 已公开 kernel 和 userland 两个实际实现仓库。先前 GitHub 组织网页缓存只列 hackios-web，实时 API 列出了新仓库，故不能再按“只开源官网”评价。

三者共同目标都是让 XNU 与 Apple 用户态在非 Apple ARM64 硬件上运行。关键区别是：HackiOS 主要自行补齐用户态要求的内核服务，并注入用户态兼容库；UniXNU 通过 NativePrelink 合并源码内核与供体 kernelcache 中的 Apple 组件。P16/sweet 也采用自行补齐服务的思路，但原始参考的引导、文件系统及图形实现不同。

当前 D:/Code/UniXNU-nuwa 是“UniXNU 底座 + 4K + XNU 8796/iOS 16/iPhone donor”，已经不是历史的 U17/iPadOS17 配方，也不是旧 P16/16K 配方。

## 固定输入

- HackiOS kernel：`8e61187098f2c26c5daee8f9f72b6416aa64b9ab`。
- HackiOS userland：`906425b75e02b4f99eb5d7bb1ef7c9583472d772`。
- 本地旧资料：D:/Code/PortingiOS/docs/nuwa-porting-design.md、nuwa-ios-porting-plan.md、nuwa-ios4k-build-candidate.md。
- 当前设备仓：D:/Code/UniXNU-nuwa/docs/STATUS.md、DECISIONS.md、operations/2026-10-22-darwin22-interfaces-and-wsl.md。STATUS 为其他工作会话持续更新的文件；本文只报告读取时完整内核构建仍未通过的边界。

## 技术路线对照

| 维度 | HackiOS 新公开实现 | P16 / ios-sweet 原始参考 | UniXNU / U17 参考 | 当前 UniXNU-nuwa |
|---|---|---|---|---|
| 内核/用户态 | 8796.121.2 / iPhone X iOS16.5，20F66 | 8796 世代 / iPhone X iOS16.7.16；本地参考源码8796.141.3 | 10063.141.1 / sheng的iPadOS17.7.11参考 | 8796.141.3 / iPhone10,3 iOS16.7.16，20H392 |
| 页大小 | 默认BCM2837配置为4K内核，属于源码配置判断 | SWEET参考16K | 原生4K，含用户map、commpage和代码签名适配 | 明确选择4K，正在回移适配 |
| 引导 | Mu-Silicium → 自有xnuloader | 原sweet是ABL → 裸机shim → XNU；旧nuwa的P16加载器已经另外接入UEFI | Mu-Silicium → UniXNU → DarwinBoot | 沿用UniXNU三仓结构与设备覆盖方式 |
| Apple闭源内核服务 | MiniIOSurface、MiniIOMobileFramebuffer、MiniAppleKeyStore、miniamfi等替代实现 | 自建/裁剪服务及HID等开源组件 | NativePrelink保留供体Apple kext与平台服务，并重绑定符号 | 延续NativePrelink，需重新解决Darwin22及iPhone供体绑定 |
| 用户态适配 | 选取Apple系统文件，加自有init、任务列表，向backboardd/SpringBoard/mediaserverd等注入库 | 提取OS/SystemOS/AppOS，合并HFS+并做启动服务调整 | 原始OS/SystemOS镜像和Data配套 | 目标保持iPhone供体，尚未完成系统集成 |
| 文件系统 | 自己实现APFS和ramfs；自建root.apfs/system.apfs | HFS+ root位于userdata | 供体原始APFS镜像窗口，NativePrelink组件配套 | 按UniXNU方向适配；挂载与完整闭包未验证 |
| 图形 | 当前公开主路径为EAGL/OpenGL ES → Mesa freedreno → Adreno642L；Metal另有实现与实验 | CPU软绘制、framebuffer复制 | sheng的NativeMetal → metal2vulkan → SPIR-V → Turnip/NIR → A740 IR3；有离线AirNir支线 | nuwa同为A740，但iOS16 ABI、板级与显示接管仍需移植 |
| Wi-Fi | Linux/FreeBSD LinuxKPI适配层承载ath11k，接XNU网络KPI和自有Apple80211兼容服务 | 原始参考无Wi-Fi | 各设备需有对应Darwin实现；不从UEFI或Android支持推导 | 未验证 |
| 构建 | Linux clang + Theos cctools/iOS16.5 SDK，使用IIG替代实现 | macOS Actions参考流程 | macOS/Xcode及对应工具链/archives | 当前通过macOS Actions推进8796源编译 |
| 调试 | 保留UEFI，不调用ExitBootServices；XNU返回加载器，USB控制、日志、会话运行 | sweet framebuffer与userdata持久日志 | DarwinBoot退出Boot Services后交接XNU | 仍需适合nuwa的可观测硬件引导闭环 |

页大小不等于系统版本，U17不天然等于iPadOS。上表的iPadOS是sheng所选供体。HackiOS的4K仅指源码默认内核配置，没有据此独立证明其全部用户态页策略与UniXNU一致。

## 最有价值的差异

### 1. 替代服务与保留供体组件

HackiOS 的 MiniIOSurface 明确声明为 Apple IOSurface.kext 的替代物，按 iOS16.5 的 selector/数据布局实现部分功能。MiniAppleKeyStore提供无密码、无真实SEP密钥的兼容行为。用户态的注入机制通过kern.exec_inject添加DYLD_INSERT_LIBRARIES，在运行时补HID、容器、图形及媒体接口。

UniXNU NativePrelink读取原kernelcache的__PRELINK_INFO，选取组件，将段复制到源码内核并处理slide、指针、模块和导入。其优点是复用Apple原服务实现；代价是强绑定供体版本、符号、ABI与初始化路径。HackiOS避开了这条大型预链接依赖，但把工作转移到接口覆盖与用户态兼容上。两种策略都需要大量工程，不能从“内核可链接”推导系统完整。

### 2. Linux构建直接相关，但不是等价替代

HackiOS的gen-iig-stubs.py对已有内核_Impl提供直接跳转包装，其余缺失方法返回kIOReturnUnsupported，明确不支持用户态DriverKit驱动。README还要求make -k，并说明导出检查和symbolset阶段会失败、make退出2。

这提供了Linux工具链包装、MIG和依赖准备的参考，却不能证明当前nuwa项目可以用同样方法通过完整DriverKit/RPC及供体ABI验收。当前项目使用真实IIG并处理8796模板差异，两条路线接受的功能缺口不同。

### 3. 返回加载器适合早期bring-up

loader_return.c明确保留UEFI环境，经/chosen/loader-return返回，收集日志后恢复加载器。它还明确要求避免XNU与UEFI同时接管同一硬件。此机制不是Android宿主或QEMU；手机上的XNU直接执行，但采用可返回的固件协作模型。

该机制值得优先研究，尤其是无串口时的日志闭环。不过nuwa的GIC、计时器、USB、保留内存、看门狗和CPU上下文必须独立核验，不能直接套用redwood地址或固件。

### 4. GPU主路径不同

HackiOS公开的桌面加速是OpenGL ES/Mesa freedreno方向；Metal代码含RedwoodMetalDevice、资源及计算/渲染工作，AIR frontend直接将AIR转成NIR，再由ir3生成Adreno代码。文档中存在阶段不同的计数和说明，不能把shader翻译/编译数量当作完整应用Metal兼容率。

UniXNU的官方sheng文档描述NativeMetal/metal2vulkan/Turnip运行链和系统合成、特定客户端设备支持。它更接近nuwa同代Adreno740；但这是上游声明及源码路线，不能算我们已在nuwa复现，更不能直接套用iOS17的archive到8796。

### 5. 新硬件仍需独立适配

HackiOS当前公开的手机目标是redwood/SM7325/Adreno642L/WCN6750，触控为Goodix GT9916。nuwa是SM8550/Adreno740，本地实测树为ST SPI触控。GPU固件、GIC几何、DMA/SMMU、PMIC、屏幕、相机和音频均不能因“都是高通”而直接复用。

## 对当前工作的建议

继续以UniXNU-nuwa为主线，没有足够证据支持仅因HackiOS公开就整体换底座。优先把HackiOS当作独立对照实现：

1. 先研究Linux构建包装、缺失Apple源码的处理方式，逐项标注真实实现与桩的边界。
2. 再研究可返回加载器、USB日志与会话控制，评估能否改善nuwa早期观测。
3. 对照IOSurface/HID/媒体与图形协议，帮助定位iOS16用户态要求，不混装16.5注入地址与16.7.16缓存。
4. 较后阶段评估ath11k/LinuxKPI、QMI/GLINK的复用；完整Wi-Fi仍包含固件、互连、DMA和安全世界接口。

当前项目的实质成本是“UniXNU为10063准备的内核/驱动/预链接体系 → 8796/Darwin22”，随后才是nuwa板级和iPhone用户态运行。HackiOS的出现提供了第二种绕过部分闭源组件依赖的工程样本，没有自动解除这些门槛。

## 主要证据链接

- [HackiOS kernel README](https://github.com/oosexgang/hackios-xnu-kernel/blob/8e61187098f2c26c5daee8f9f72b6416aa64b9ab/README.md)
- [HackiOS内核构建与实现说明](https://github.com/oosexgang/hackios-xnu-kernel/blob/8e61187098f2c26c5daee8f9f72b6416aa64b9ab/xnu/README.md)
- [IIG替代生成器](https://github.com/oosexgang/hackios-xnu-kernel/blob/8e61187098f2c26c5daee8f9f72b6416aa64b9ab/xnu-deps/gen-iig-stubs.py)
- [返回加载器实现](https://github.com/oosexgang/hackios-xnu-kernel/blob/8e61187098f2c26c5daee8f9f72b6416aa64b9ab/xnu/files/osfmk/arm64/loader_return.c)
- [MiniIOSurface](https://github.com/oosexgang/hackios-xnu-kernel/blob/8e61187098f2c26c5daee8f9f72b6416aa64b9ab/xnu/files/iokit/Kernel/MiniIOSurface.cpp)
- [HackiOS移植指南](https://github.com/oosexgang/hackios-xnu-kernel/blob/8e61187098f2c26c5daee8f9f72b6416aa64b9ab/docs/PORTING.md)
- [HackiOS userland](https://github.com/oosexgang/hackios-xnu-userland/blob/906425b75e02b4f99eb5d7bb1ef7c9583472d772/README.md)
- [注入库与供体地址绑定](https://github.com/oosexgang/hackios-xnu-userland/blob/906425b75e02b4f99eb5d7bb1ef7c9583472d772/userland/src/inject.c)
- [AIR frontend](https://github.com/oosexgang/hackios-xnu-userland/blob/906425b75e02b4f99eb5d7bb1ef7c9583472d772/tools/mesa/air/air_to_nir.c)
- [RedwoodMetalDevice](https://github.com/oosexgang/hackios-xnu-userland/blob/906425b75e02b4f99eb5d7bb1ef7c9583472d772/userland/src/redwoodmetal.m)
- [P16/ios-sweet](https://github.com/dipa-studio/ios-sweet)
- [UniXNU分层与启动](https://github.com/UniXNU/UniXNU/blob/main/docs/zh/guide/overview.md)
- [UniXNU预链接](https://github.com/UniXNU/UniXNU/blob/main/docs/zh/concepts/prelink.md)
- [UniXNU 4K策略](https://github.com/UniXNU/UniXNU/blob/main/docs/zh/xnu/four-k-page-tables.md)
- [UniXNU Adreno740官方说明](https://unixnu.com/drivers/native-adreno)
