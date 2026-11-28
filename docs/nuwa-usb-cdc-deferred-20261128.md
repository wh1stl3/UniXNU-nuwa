# nuwa USB CDC 调试通道暂缓 — 2026-11-28

状态：**deferred，主机资料与候选静态核对 self-checked**。先推进存储主线，收敛后再
评估 USB CDC-ACM；接入前先只读核对固件交接。本轮不接设备、不构建、不修改驱动、
固件或启动配置。当前没有 nuwa 上 USB 调试通道可用的实机证据。

## 现状与扫描边界

- 核对的是 UniXNU `693f5d9cae8a408dd18b39f3f9fdc4228c934241` 的 nuwa
  XNU 工作树，XNU 基底为 `1b191cb58250d0705d8a51287127505aa4bc0789`
  （8796.141.3）；未找到 USB device-mode gadget 框架、CDC-ACM 类驱动或
  Qcom USB debug 接入。板级组件和参数也未选择该通道。仅加 boot arg 不能创建驱动。
- 明确的候选为[无字形 FUA 包](nuwa-no-glyph-examples-20261128.md)的
  `out/nuwa-no-glyph-20261128-build/kernel.macho`，SHA-256
  `1faf93575a20568066f8f9c7f5f99c3022b20645591eb2e51a54536b5e6d685d`。
  其 `prelink.json` 的 `components` 共 **31** 项，bundle 名称按不区分大小写的
  `usb|cdc|dwc|otg` 扫描为 0。解析最终 Mach-O 的 `__PRELINK_INFO` 得到
  **39** 项：31 个组件、1 个 codeless 组件和 7 个 KPI；bundle identifier/name
  同样无上述命中。本地 SBTH r5 与 v1 shape 的最终内核也各为 39 项。
- 任务输入给出的“66 个 kext”未指定对应文件，在上述候选中未复现；不能把
  66 写成这些候选的实测结果。`llvm-nm -P` 对该无字形内核列出 **50,294**
  个符号；按相同子串扫描有两个命中：
  `_sk_netif_compat_usb_eth_rx_ring_sz` 和 `_sk_netif_compat_usb_eth_tx_ring_sz`。
  它们是通用网络调优变量，**不是 USB 控制器或 CDC 驱动符号**；没有发现相应
  USB device/CDC/DWC/OTG 驱动符号。不能将全符号表原始子串命中数写成 0。
- `kernel.macho` 中 `IOUSBDeviceController` 有三处文本，文件偏移分别为
  `0x12aa8d3`、`0x1300f43`、`0x1303f13`；按该构建的 `prelink.json` extent
  均落在 `com.apple.security.sandbox` 的 `__TEXT`，附近是 sandbox 客户端名称。
  这些文本不是已链接 USB 驱动的符号或设备服务。

## 可复用实现与先例

| 项目、版本 | 范围与许可证 |
| --- | --- |
| [FFT-infra/QcomXnuUsbDebug](https://github.com/FFT-infra/QcomXnuUsbDebug/tree/18bcc385bc0c97ff38343a83040f19711392867b)，`18bcc385bc0c97ff38343a83040f19711392867b` | DWC3 CDC-ACM 日志后端，含 SM8550 配置与 Darwin 22 / XNU 8796.141.3 钩子。`usb/Dwc3.c` 和 `kernel/QcomXnuUsbDebug.c` 标注 MIT；`usb/Dwc3Regs.h` 保留 TI BSD/GPL 双许可，树内 Apple XNU fixture 另有其许可，不能把整仓所有文件简化成 MIT。运行参数 `qcom-usb-debug=1`，双向控制可选 `qcom-usb-ctl=1`；编译宏 `XNU_QCOM_USB_DEBUG=1`。[接入说明](https://github.com/FFT-infra/QcomXnuUsbDebug/blob/18bcc385bc0c97ff38343a83040f19711392867b/docs/integration.md)要求内核钩子、归档及 prelink/链接接线。 |
| [alioth](https://github.com/FFT-infra/UniXNU-alioth/blob/8540a2638aeb768567cc25f478572b7225be0a7d/feeds.toml) / [munch](https://github.com/WuBarlynn/unixnu-munch/blob/7f9b3e690dd9d356f4fb054b2edc135820e4da83/board.toml) | 两个板配置均选择 QcomXnuUsbDebug；alioth feed 明确钉上面的提交，munch 的板配置说明用于 CDC-ACM 日志。均是 SM8250 板级先例，不是 nuwa 的运行证明。实现许可见上一行。 |
| [giulia](https://github.com/tycykp/UniXNU-OnePlus-Ace5/blob/aaa100d19f6fb14e5897a7e496edf7838d4d4e9f/scripts/prepare-ios16.py)，`aaa100d19f6fb14e5897a7e496edf7838d4d4e9f` | SM8650 CDC 调试先例；其生成脚本使用 [vermeer_usb_debug.c](https://github.com/xyyyds0106/ios-vermeer-lab/blob/d68e05df683f863f054b0f9c063c54d2b1342b2a/xnu/vermeer/vermeer_usb_debug.c)（vermeer `d68e05df683f863f054b0f9c063c54d2b1342b2a`）。giulia 自有仓库声明 BSD-2-Clause-Patent；所引用 vermeer 源文件/仓库未见许可声明，按 **NOASSERTION** 处理。此版本未找到名为 `UsbDebugCdc` 的 giulia 源文件。 |
| [j716f J716fUsbDebugCdc](https://github.com/Denis0x00/UniXNU-j716f/blob/9d0f1230c294109507768d94c8d60cdb9b76c71b/package/usb/J716fUsbDebugCdc.cpp)，`9d0f1230c294109507768d94c8d60cdb9b76c71b` | SM8250 裸机 DWC3 CDC-ACM；源文件 SPDX 为 **BSD-2-Clause-Patent**。其 README 声称在该设备上验证，不能转为 nuwa 验证。 |
| [starlte](https://github.com/Scion-Project/scion-starlte/blob/077d97f29fbbba873ce4f6235b5f293530f421af/README.md)，`077d97f29fbbba873ce4f6235b5f293530f421af` | Exynos 9810 的 CDC-ACM 日志先例，非 UniXNU 构建树；设备仓自身文件 MIT，但其 [Scion 内核 USB 驱动](https://github.com/Scion-Project/scion-kernel/blob/adbb15d6a90cc6754c23e9bbf1eb1597ec6f77ef/drivers/usb/hakios.dwc3.c)按该仓 `drivers/` 许可为 **APSL-2.0**，不能把设备仓 MIT 外推到内核驱动。 |

官方 [UniXNU/QcomDwc3](https://github.com/UniXNU/QcomDwc3/tree/f5edd26d8c539a4faff2c6de151ba4a3c8796bde)
`f5edd26d8c539a4faff2c6de151ba4a3c8796bde` 面向 iPadOS 27 的 Apple
USB device/host 栈，不是此处的独立 CDC 日志后端；该候选缺其系统 USB 栈，不能直接
当成 iOS 16 等价接入。其 PHY 文件为 GPL-2.0-only，其他部分为 BSD-2-Clause-Patent。
本轮仅列来源，没有引入任何第三方代码。

## 接入前提与未证交接

1. `dts/nuwa.dts` 加入 `sm8550.dtsi` 后有 GIC、UFS/UFS PHY、GPU/GMU 等
   节点，但没有 `dwc3`/`ssusb`；本机资源值和使能状态仍须 nuwa 证据。
   若采用依赖 IOKit personality 的设备树匹配路线，须描述并导出相应节点和属性。
   当前 `scripts/unixnu/devicetree.py:370-377` 对带 `unixnu,adt-name` 的
   **启用硬件节点动态导出**到 `/arm-io`，并非固定硬件节点名单；只有
   `defaults`/`options`/`product`/`buttons` 等配置型根节点按固定名单处理。
2. 对 `IONameMatch`，XNU 默认 `IORegistryEntry::compareName` 比较注册表名称；
   本树的 `IOPlatformDevice` 经 `IODTPlatformExpert` 调用 `IODTCompareNubName`，
   还比较 `name`、`compatible`、`device_type`、`model`，并支持末尾 `*`。
   因此不能笼统写成“只精确匹配节点名”。上述 QcomXnuUsbDebug 的文档描述的是
   直接链接静态库、从内核钩子启动的单例，而非已证明依赖 `IONameMatch` 的
   personality；不能断言新增 ADT 节点是它的无条件前提。
3. 若后续选该模块，需按其接口评估 catalog/组件、归档、内核补丁、
   prelink/链接次序和编译宏；复核 nuwa 自身板级资源与 XNU ABI，不照抄其他
   设备的寄存器、PHY 或 SMMU 配置。相关启动链、DMA/IOMMU 和并发改动须
   `deep_reviewer` 审查，本轮没有实现。
4. 启动参数需和现有上限一起核算。无字形包现有 **602 B 正文**；
   arm64 `CommandLine[608]` 含末尾 NUL，正文上限 **607 B**。
   仅追加 ` qcom-usb-debug=1` 即为 **619 B**，再加
   ` qcom-usb-ctl=1` 为 **634 B**；都超过上限。未来必须在候选整体参数中
   腾出空间，不能直接追加；见[现有长度记录](nuwa-no-glyph-flash-20261128-observation.md)。
5. **关键未证前提**：该 Qcom 后端依赖固件在 `ExitBootServices` 前准备 USB
   供电、时钟和 PHY，并在进入 XNU 后有安全的控制器独占交接。nuwa 固件树
   `121df32d292df1499fb75638bfc19e1a041bd2a9` 的
   `Platforms/Xiaomi/nuwaPkg/Include/{DXE,APRIORI}.inc` 列出
   `UsbfnDwc3Dxe` 和 `UsbDeviceDxe`；列入固件配置不证明实际已初始化、
   已停止旧 DMA 或完成交接。先检查固件源码、既有日志与交接记录，明确旧
   host/OTG、回调、DMA 和内存所有权，再决定可否接入；本轮没有设备观测。

## 硬件

CDC-ACM 是通过 USB 数据通道提供的虚拟串口；若设备端驱动和交接均已工作，
主机加普通可传数据的 USB-C 线即可，不需要额外 UART 硬件。真 UART 是另一条
物理串口：若走 USB-C SBU 调试路径，则需要相应 SBU/工程线及电平适配；
nuwa 的 UART 引脚和可用性本轮未验证。
