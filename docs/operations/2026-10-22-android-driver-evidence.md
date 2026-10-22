# Android 实机驱动取证与开源来源对照

2026-10-22 17:37，用户提供已解锁、root、ADB在线的nuwa，并允许从互联网、MiCode及社区查资料。全部设备操作是只读ADB；没有重启、刷写、固件升级、读取原始分区或修改板配置。采集前后sys.boot_completed=1。**本报告是Android运行态观测，不是XNU实机通过。**

## 实际绑定

证据目录：`reports/android-driver-evidence/20261022T092529Z/`。`commands.json`及各`*-command.json`记录原命令、退出码，`manifest.json`记录采集字节与LF规范化哈希。Android原输出的行尾空格保留；提交检查仅对两份原始输出gpu-storage.txt/touch-firmware-release.txt豁免该空格，其他路径检查通过。没有保存原始DTB、镜像、设备序列号；不需要的demura-panel-id值已从公开文本省略。主采集器为`scripts/collect-android-driver-evidence.py`。

| 项目 | 实际观测 | 对适配的影响 |
| --- | --- | --- |
| 系统 | nuwa；Linux 5.15.195-MorizukiNeko-260620LTSC；su uid=0 | 当前为自定义Android内核，公开源码不自动等于当前模块的精确构建输入 |
| 触控 | `/sys/bus/spi/devices/spi0.0`绑定`/sys/bus/spi/drivers/fts`，模块`fts_touch_spi`；DT `st,spi`、status=ok | 采用ST FTS SPI方向；不以fts缩写误判FocalTech，不套sheng Novatek |
| 触控配置 | 固件名`st_fts_m2.ftb`；SPI上限12000000；TLMM phandle0x79已对到kalama-pinctrl-v2，IRQ GPIO25、reset GPIO24 | 仅记录Android证据，不写board、不把GPIO号直接当GIC IRQ；精确芯片修订、SPI模式与完整时序仍TODO |
| 坐标 | DT `fts,x-max=14400`、`fts,y-max=32000`，支持super-resolution；Android显示1440×3200 | 不能把触控坐标原样当像素；后续核对固件事件格式及缩放 |
| 触控固件版本 | appid缓存输出`EXT Release =22 20 00 00 00 00 00 00` | 对应源码show函数仅格式化systemInfo缓存；未执行升级、selftest、stm命令或总线寄存器读写 |
| 虚拟输入 | `uinput-goodix`位于`/sys/devices/virtual/input` | 不能用其名称确定实体触控IC；DT中的Goodix备用节点也不代表实际绑定 |
| 活跃面板 | `mi_display/disp-DSI-0/panel_info`和msm_drm `dsi_display0`均为`mdss_dsi_m2_38_0c_0a_dsc_cmd`；DSI-1 connected/enabled、1440×3200多模式 | 活跃面板已确认到配置名称；具体DDIC、电源/DSC/GOP交接仍需源码与固件证据 |
| 默认面板陷阱 | display-primary的default-panel phandle0x755，而活跃m2节点phandle0x75d；另有m2a备用节点0x781 | 按运行态参数选择，不能盲从DT默认指针或任意存在的面板节点 |
| GPU | `Adreno740v2`；kgsl驱动；compatible `qcom,adreno-gpu-gen7-2-1` | 与SM8550通用Adreno路线对照，电源、GMU、SMMU和iOS ABI未验证 |
| UFS | KIOXIA `THGJFJT1E45BATPC`、rev0300；host `ufshcd-qcom`，PHY `ufs_qcom_phy_qmp_v4_kalama` | 优先审查UniXNU真实NativeUfs/GccUfs/SmmuTakeover，不改现有分区/加密策略 |

`selected-dt-properties.json`保存原始hex和按字段类型解释的字符串/大端cell。UFS interrupt tuple=[0,265,4]、iommus=[62,96,0]等原始值只作为后续控制器/phandle/schema审查输入，不直接填成最终板级IRQ/SID。`iomem.txt`是当前Android内存资源表，不能替代UEFI可用连续内存图，也不能据此改D-002窗口。

## 已固定的公开来源

1. 小米[发布索引](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/README/README.md)将13/13 Pro列入fuxi-t-oss；固定核源码提交`7fad87dc178d09489b74a714e4a525d56f546855`。包含nuwa配置，但此次树清点没有发现当前所需fts_spi目录；不把普通stmfts I2C实现视为匹配版本。
2. [MiCode/kernel_devicetree](https://github.com/MiCode/kernel_devicetree/blob/5647c799a064dfec73332a4fe2ef7aa3fb2f4887/xiaomi/nuwa-sm8550.dtsi#L105)，固定`5647c799a064dfec73332a4fe2ef7aa3fb2f4887`。nuwa节点105起的st,spi、GPIO25/24、14400/32000、12MHz及st_fts_m2.ftb与实机对应。qcom与xiaomi两份路径分别核对，保留各自blob/hash。
3. **匹配的ST SPI实现候选**：[LineageOS/android_kernel_xiaomi_sm8550](https://github.com/LineageOS/android_kernel_xiaomi_sm8550/tree/9d5787a9b37e3ed5e368b7e635ad6e436a629cfa/drivers/input/touchscreen/fts_spi)，固定`9d5787a9b37e3ed5e368b7e635ad6e436a629cfa`。Makefile生成fts_touch_spi，fts.c:7766匹配st,spi，ftsIO.c使用spi_sync，fts.h版本5.2.4.1；GPL通知逐文件保留。候选源码头默认SALIXP/0x36,0x40是编译选择，**不是已读出的本机芯片ID**。不把Linux源码直接复制编译成Darwin驱动。
4. **排除为直接版本**：LineageOS的sm8550-modules固定`92a9fde479d3262da080cfd28bab0775b0da500a`中`touch-drivers/st/`为4.2.14/I2C一系，sysfs接口与实机不同。可作历史对照，但当前优先上一项fts_spi。
5. MiCode/vendor_xiaomi_proprietary_touch-driver没有fuxi-t-oss分支；main固定`1dce59696e662b830e47d170b669b5e99f961283`清点没有取得匹配实现。该结果仅覆盖本次分支范围，不能声称小米所有版本都未公开。Telegram可继续用于发现维护者/仓库线索，本轮没有读取私有群或向任何人发消息，也未用未核实聊天替代源码证据。

树元数据、文件hash及有界行号摘录见`reports/driver-reuse/*-inventory.json`、`android-source-crosscheck.json`及`st-spi-source-crosscheck.json`。来源文件仅经API在内存阅读，没有整树复制或向两个只读资料库写入。

## 如何用于主线

- 先完成CPU/GIC/平台专家的Darwin22真实链接及启动基础，再沿UniXNU接UFS、显示与HID。Android模块`.ko`与XNU不兼容；可复用的是真实协议/寄存器实现及板证据，不是原二进制。
- 触控候选已从未知品牌收窄到ST FTS SPI：后续分别审查SPI传输、固件依赖、reset/IRQ、事件/坐标解析、HID映射与源文件许可，保留最小依赖，不导入整套Linux/Android服务。未生成触控archive或新固件。
- 面板按实机m2运行态名称追源码；当前MiCode DT树路径搜索未找到对应面板源文件，仍TODO，不搬sheng面板参数。GPU/UFS继续优先UniXNU现有实现，按本机控制器/PHY证据比对。
- CI15已完成ArmCpu+ArmDTPlatform真实重链接，与本次Android观测分别验收。feed、board、donor身份和所有_verified字段不变；未QEMU、未执行本仓XNU内核。


补充静态对照：UniXNU 75bc13d的NativeUfs/GccUfs.h:9为0x01d84000，NativeUfs.cpp:156注释的host窗口0x3000及:272的stream0x60与本机DT原始cell对应。见reports/driver-reuse/ufs-local-crosscheck.json。仅数值对应不足以证明DMA/SMMU接管可运行，不导入任何旁路或MMIO写动作。
