# 日志导出通道离线评估

时间：2026-10-22 21:04（Asia/Shanghai）。仅离线读取源码和既有CI产物；设备访问保持暂停，没有生成或重写镜像。

## 结论

可以设计普通USB线连接电脑的日志通道，优先评估复用现有高通USB设备栈，在DXE增加CDC ACM日志功能，让Windows串口采集程序保存文件。本轮只确认接口/源码候选及打包记录，没有完成该功能，更没有nuwa实机枚举或传输证据。

当前故障可能早于DXE，故建议配套早期RAM日志：有可证实的安全缓冲区后记录阶段标记，USB就绪后导出积累内容。若卡在USB初始化之前，仍需独立UART或已证明可读回且能跨重启保留的RAM通道；不能承诺一根普通USB线获取所有BootShim/SEC故障日志。

## 本仓现状与证据

只读源码根：`D:/Code/PortingiOS/common/sources/mu-nuwa-firmware`，固件固定输入见`config/firmware-ci-inputs.json`（Mu-Silicium 6c6755012728c9f7de748228758bad94d1e9a660）。下列源码路径相对此根：

- `Silicon/Silicium/SiliciumPkg/Library/FrameBufferSerialPortLib/FrameBufferSerialPortLib.c:243`：SerialPortWrite实际向屏幕绘字；`:326`初始化没有建立USB/UART。SEC当前链接此库，见Q-060审查与`reports/arm64-sec-entry-audit/audit.json`，名称中的Serial不能作为物理串口存在证据。
- `Platforms/Xiaomi/nuwaPkg/Include/DXE.inc:88,96-99`：列入UsbfnDwc3Dxe、UsbMsdDxe、UsbDeviceDxe、UsbConfigDxe、UsbInitDxe。USB主机端UsbBus/键盘/存储驱动不能代替连接PC所需的设备端日志功能。
- `Silicon/Qualcomm/QcomPkg/Include/Protocol/EFIUsbDevice.h:168,202,289,359-369`：已有Send、HandleEvent、Start及传输缓冲区接口契约。调用者仍须提供描述符、控制请求处理、事件服务和收发管理；只有头文件不能证明二进制驱动运行成功。
- CI39764322744既有包`out/firmware-ci/39764322744/nuwa-firmware-39764322744/build/FV/Ffs/`包含上述驱动的GenFfs/GenSec记录，例如`94F8A6A7-DC34-4101-88C1-99179CCEAE83UsbfnDwc3Dxe/94F8A6A7-DC34-4101-88C1-99179CCEAE83.ffs.txt:1`及`3299A266-15F0-4346-8318-716336736D3EUsbDeviceDxe/3299A266-15F0-4346-8318-716336736D3E.ffs.txt:1`。这是构建打包证据，不是实机执行证据；对应供应商模块来自Device-Binaries，不能称为已获完整开源控制器实现。

复核命令（只读，无设备命令）：

```powershell
$r='D:/Code/PortingiOS/common/sources/mu-nuwa-firmware'
rg -n 'Usbfn|UsbDevice|UsbConfig|UsbMsd|UsbInit|ULog' "$r/Platforms/Xiaomi/nuwaPkg/Include/DXE.inc"
rg -n 'USB_DEVICE_SEND|USB_DEVICE_HANDLE_EVENT|USB_DEVICE_START|struct _EFI_USB_DEVICE_PROTOCOL' "$r/Silicon/Qualcomm/QcomPkg/Include/Protocol/EFIUsbDevice.h"
rg -n 'MODULE_TYPE|LIBRARY_CLASS|PcdAdvancedLogger' "$r/Common/Mu/AdvLoggerPkg/Library/AdvancedLoggerLib/PeilessArm/AdvancedLoggerLib.inf"
```

## 可选通道与覆盖范围

| 通道 | 能覆盖的阶段 | 尚需落实 / 代价 |
| --- | --- | --- |
| USB CDC ACM → Windows COM口 → 本仓文本日志 | USB控制器、设备栈和导出驱动就绪后的DXE/BDS | 实现CDC描述符/控制请求/事件服务；核对USB角色、PHY、电源、端点、驱动协议；设备重连处理。当前未验证 |
| 早期RAM记录 → DXE通过USB补发 | 缓冲区已确认可写之后的SEC，BootShim须另做极小记录入口 | 缓冲区所有权/地址/长度、cache一致性、HOB传递和覆盖保护全部需证据；未到DXE则不能靠此路径直接读出 |
| 硬件UART | 路由和初始化成立后，可用于更早入口 | nuwa引脚、复用、电平、时钟、调试线均TODO，可能涉及拆机；不编地址/电压、不直接套同SoC参数 |
| 写FAT卷日志，包括后续可读出的卷或OTG U盘 | 存储和文件系统初始化之后 | 依赖可写卷/主机角色及正确驱动；不能解决早期挂死，不使用未知LBA或随意写手机分区 |

Windows对符合CDC ACM描述符的设备可加载自带Usbser.sys，适合由主机持续采集文件：[Microsoft文档](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-driver-installation-based-on-compatible-ids)。USB功能驱动需要实际服务端点与事件，不能把一次写寄存器当作建立USB日志：[UEFI USB功能协议](https://uefi.org/specs/UEFI/2.11/17_Protocols_USB_Support.html)（本轮搜索可获取索引，打开正文返回403；本地高通协议头为本仓接口审查依据）。

## 优先复用的开源日志组件

本地已有`Common/Mu/AdvLoggerPkg/`（`.gitmodules`指向microsoft/mu_plus），无需自造完整日志框架：

- `Library/AdvancedLoggerLib/PeilessArm/AdvancedLoggerLib.inf:14-19`为AARCH64 SEC候选；源码`:77-79`依赖PcdAdvancedLoggerPages/Base，`:110`建HOB。地址/保留契约仍是前置条件，不能直接填数启用；构造器和HOB可用时间不等于BootShim最初指令可记录。
- `AdvancedSerialLogger/Dxe/AdvancedSerialLoggerDxe.inf`通过SerialPortLib消费日志，若仍接FrameBufferSerialPortLib仍只输出屏幕，并不会自动变成USB。
- `AdvancedFileLogger/AdvancedFileLogger.inf`消费SimpleFileSystem协议，可作为后期文件导出候选，不能替代早期记录。
- 所读文件声明BSD-2-Clause-Patent。以上仅候选，未移植；导入补丁前仍需固定mu_plus子模块提交并记录文件哈希及依赖，不将本地存在等同已匹配当前固件输入。供应商ULogDxe的存在也不代表本仓SEC DEBUG已向其写入。

## 最小实现顺序与未验证项

1. 离线先固定可复用组件版本，确认安全RAM缓冲区候选及生命周期；地址/页数保持TODO，不改board/bringup-plan。
2. 源码层设计有界日志和阶段标记：BootShim入口/复制结束、SEC入口、SMMU前后、内存初始化、DXE入口。记录不能无限等待USB、重入打印或阻塞启动。
3. DXE导出驱动复用现有USB设备协议，Windows采集端写`reports/`下日志；先回传历史记录，再服务实时记录。CDC与供应商bulk端点可二选一，优先CDC便于Windows读取。
4. 到新诊断/固件镜像生成前，按AGENTS硬停规则提交具体候选范围审阅；本轮没有命中该动作。后续实机动作还须先解除当前设备暂停。RAM跨重启保留、fastboot读RAM、UART可用、USB通信和XNU日志接线均未验证。

早期日志导出成功也只证明对应固件阶段执行，不自动等于XNU内核或iOS启动。退出Boot Services后继续USB输出需要内核侧独立驱动/接管，不能默认UEFI USB栈持续运行。
