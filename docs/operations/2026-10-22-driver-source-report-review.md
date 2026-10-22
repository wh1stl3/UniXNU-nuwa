# driver-sources.md只读复核

2026-10-22。来源D:/Code/PortingiOSWithUniXNU/docs/driver-sources.md只读，原件SHA与核对文件见reports/driver-source-report-review.json。将其当作评估对象，不执行文末“加feeds、填参数、diff固件”的指令。本轮无设备操作、源码/镜像生成、feed/board改动。

结论：通用模块索引与“复用开源实现、按板取证”的方向可采纳，但有会选错协议的触控品牌错误，以及来源解析、上游支持状态和适配成熟度方面的错误；不能直接作为实施方案。

## 必须纠正

| 原报告位置 | 原结论 | 本仓核对与影响 |
| --- | --- | --- |
| :84、:97、:108 | nuwa为FocalTech，按0xC0/0xC1协议新写，缺现成协议参考 | 当前实机绑定fts_touch_spi，DT st,spi，固件st_fts_m2.ftb；是ST FTS SPI路线。fts缩写不能判厂商。固定LineageOS fts_spi实现已有ST版权、5.2.4.1版本、st,spi匹配与fts_touch_spi构建目标。应审查该实现与Nuwa事件/复位/固件契约，不按FocalTech设计协议。精确芯片修订仍未读出。 |
| :29、:85、:114 | sheng GPU不可用、仅显示与触控可用 | 官网当前sheng页GPU表及支持矩阵明确列原生Metal/GPU桌面合成、每进程设备和pipeline cache工作，同时UFS根也列可用。报告这部分已与当前官方说明不符。它只提供sheng已实现路线的依据，绝不等于nuwa/iOS16已通过。 |
| :6、:14、:21、:127 | 驱动从不在设备仓；通用件靠base feeds拉取；设备没有feeds等于没接入且不可复现 | 固定base75bc13d的feeds.py:3-14、:141-155按CLI/local/device/base目录再git源解析，设备可以有自身驱动或覆盖。当前base feeds.toml五项全是refer（Apple源和edk2），通用drivers由base目录解析。设备feeds是可选额外来源，不是接入门槛；完整源commit/hash/实际argv才能说明可复现范围，不能用有无该文件判断。保持feed不变。 |
| :31、:81-82 | 同控制器/ADT写好即可直接用ArmCpu/NativeUfs | 可以优先复用源码，不能直接验收运行。ArmCpu/ArmDTPlatform目前已在8796真实链接，但timer/startup/GIC/PSCI仍待运行核验；NativeUfs寄存器窗口/SID仅静态对应，Darwin22 ABI、PHY/时钟/PMGR、DMA/SMMU、根卷及策略输入尚需验收。报告自己提到的PMGR也说明并非只填DT/UUID。 |
| :83、:121、:126 | NativeMobileDisplay通用件够，下一步只差DTBO面板参数 | NativeGOPWire.h:2说明是固件scanout传输；NativeGOPPresenter.cpp:54-66依赖PE_current_console、32bpp/几何/缓存属性及映射一致，后续transfer把像素送入已有scanout。这不是已具备任意面板DSI/DSC/电源初始化的证明。nuwa运行态活跃m2_38_0c_0a已在本仓记录，后续按该版本取参数；还须UEFI/GOP交接及iOS16 ABI，不止填面板表。 |
| :55、:61、:116-120 | sheng是板级值基线；同SoC社区仓都只是复制 | 同SoC仓优先对照结构/通用实现与依赖，但具体板值必须nuwa证据，donor/prelink值不能继承。package也可含实质平台/电源/诊断代码，不能凭.gitmodules或空kits/patches判定整个设备仓价值。仓库清单/数量须标查询时间和固定提交，不作兼容证明。 |
| :92、:108 | 触控是唯一必须新写且是阶段7硬前提 | 触控是交互可用性的关键部分，但官方阶段7判据是用户态launchd等，不应把输入支持等同内核/用户态到达判据。其余子系统的nuwa适配范围也尚未查全；“唯一”缺证据。先复用匹配ST参考，再确定Darwin层需重写部分。 |

触控证据：reports/android-driver-evidence/20261022T092529Z/的spi-bindings.txt、selected-dt-properties.json及touch-firmware-release.txt；docs/operations/2026-10-22-android-driver-evidence.md。ST来源固定为[LineageOS 9d5787a9的fts_spi](https://github.com/LineageOS/android_kernel_xiaomi_sm8550/tree/9d5787a9b37e3ed5e368b7e635ad6e436a629cfa/drivers/input/touchscreen/fts_spi)，有界原始行和hash见reports/driver-reuse/st-spi-source-crosscheck.json。无需再次读取触控寄存器或执行固件命令。

上游状态引用[UniXNU官方sheng设备页](https://unixnu.com/zh/devices/sheng) GPU章节及设备支持表（本次读取2026-10-22）。官方页描述的是其既定sheng/iPadOS路线，不能推广为我们的nuwa/iPhone donor/Darwin22验收；本轮未跟进任何上游新提交。

报告中的Linux源码不能“直接搬进XNU”应拆开理解：Linux内核接口和Darwin框架确实需要适配；逐文件许可/依赖需保留核对，不能仅用一句GPL概括所有实现的复用结论。行数也不等于完整度、移植工时或测试覆盖。

## 可以吸收的部分与当前优先级

- 保留通用源码候选：ArmCpu/ArmDTPlatform、NativeUfs、NativeMobileDisplay/NativeGOPPresenter、NativeGeniSpi、NativeHidInput、NativeAdreno及其kit；先逐项记录固定commit、实际依赖和Darwin22接口。
- 触控用ST FTS SPI参考替换错误FocalTech方向；复用Geni SPI传输与HID出口，但SPI模式/频率/时钟/引脚/DMA/IRQ、事件格式及坐标缩放仍需本机证据。Novatek探针架构可参考，协议和板参数不照搬。
- 显示按已确认活跃m2配置追DTB/DTBO与源文件，先验证UEFI/GOP保留/交接，再扩展到刷新、电源及重初始化。解DTBO有后续价值，不覆盖当前固件入口与DT映射主线。
- 报告描述的是另一个设备仓当时的状态。当前本仓已实际链接两平台archive、已编四EFI/FD/BootShim、已有v4固件入口包；不把其“空目录/未接”的描述写回本仓状态。

主线顺序保持：先验证已经准备的固件入口候选与恢复/DT访问，再完成Darwin22运行provider、时钟/boot-progress/watchdog及NativePrelink门，之后逐步接通UFS、显示与ST触控。完整核验前不把“有源码/同SoC/能链接”写成实机通过。原报告原件没有修改。
