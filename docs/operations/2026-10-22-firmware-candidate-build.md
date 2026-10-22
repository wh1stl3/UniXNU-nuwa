# 受限固件构建与产物检查

R-004 A已获用户明确批准。范围仅四模块EFI、nuwa FD、BootShim及静态检查；不生成boot.img/负载/预链接镜像，不操作手机，不改board/feed/内存表/板地址。

## 第一轮 39761427579（2026-10-22 18:18结束，failure）

设备仓输入25450ad80a166e2aa74f39ae299fd58423d59fac。来源checkout、LF归一化hash、三补丁应用、依赖安装、BootShim、DeviceBuild setup/update均实际成功。固件首次EDK解析失败：`ShengBootMemoryDxe.inf(27): error 4000: Value of Guid [gSiliciumEntryArgHobGuid] is not found`；尚未取得EFI/FD成功产物。实际build.log、failure.json、commands.json、inputs.json及最终run.json在reports/firmware-ci/39761427579/。

BootShim已编出：112字节，SHA256 9346a527441b242c69414fd7e3d6fa17813f281d562fef13d9ba8373d39007a9；头部image_size=3,145,840，_Payload=112。下载后独立解码MOVZ X6，拷贝计数为3,145,728，未误含shim。证据shim-inspection.json。仅编译及静态检查通过，未执行。

## 首错修复

固定uefi-sheng的本地稀疏检出未包含SEC实现；使用GitHub contents API读取同一329b473d提交的4个文件，仅在内存比较、生成差异，不把上游源码复制入本仓。固定Git blob与原始SHA见reports/firmware-ci/sec-hob-source.json。

增加0004-sec-entry-argument-hob.patch：复用SiliciumPkg DEC的已有GUID、Sec.inf声明、入口x0保存和InitializeMemory/PlatformPeim之后的BuildGuidDataHob生产逻辑。未引入源分支其他SPSel/显示PCD差异，不更改地址、容量或内存表。补齐真实生产者，而非只加一个GUID声明或伪造HOB。83项静态检查通过，新增补丁git apply --check退出0；真实重编译待下一轮。

入口x0有效性、固件区可写/初始缓存状态、HOB指向DT的生命周期和initrd保留/映射仍未验证；沿用该实现不能代替设备证据。本轮构建批准不含上机。

## 下载检查器

scripts/ci/inspect-firmware-candidate.py只在内存展开下载FD的LZMA嵌套FV，验证FV/FFS校验、四模块GUID/FFS类型/AARCH64 PE32+/子系统、应用与注册器同FV、注册器变量协议DEPEX、发布器TRUE DEPEX、PE内应用/loader协议GUID，核对独立EFI与内嵌PE哈希，并检查shim头、_Payload和机器码中的FD拷贝长度。只写JSON，不修改镜像。

用隔壁已有SHA21c029eb的旧FD校验解析器，得到2个FV/154个FFS，目标四模块均未出现；8项有效/损坏格式检查通过。记录reports/firmware-ci/inspector-tests.json。此基准只验证解析路径，不是新固件结果，更不是QEMU或实机通过。


## 第二轮39762744079（18:30结束，failure）

输入6304c6c。安装阶段用时约5分52秒后成功，未取消运行。源码归一化hash全过；第4份补丁的Sec.c/Sec.inf/ModuleEntryPoint.S在Linux git apply --check失败。与本机差异为上游Git blob含CRLF，本机文本视图/候选补丁为LF。尚未验证本轮SEC编译，也无新EFI/FD产物。

修复仅在独立云端源树，对已通过LF哈希闸门的精确补丁目标做CRLF→LF，保存原始/转换后hash；继续严格git apply --check，不启用ignore-whitespace或改源码逻辑。第三轮仍沿用四补丁、同来源与板配置。产物检查器同时加入SEC TE和发布器PE内入口HOB GUID的配对检查。


## 第三轮39764322744（18:43结束，success）

设备输入a8425b3db88e78f4630ad18aed9288e7f5e1edca。固定Mu/UniXNU/sheng checkout、全部来源LF hash、四补丁严格apply、BootShim、DeviceBuild setup/update/build成功；编译步骤约1分45秒。原板/配置/内存表保护检查通过，未打boot.img、未包含kernel、未操作设备。run.json记录成功状态与输入；全部源/子模块版本、命令、pip/toolchain及CRLF转换前后hash均归档于reports/firmware-ci/39764322744/。

下载命令：`gh run download 39764322744 --repo wh1stl3/UniXNU-nuwa --dir out/firmware-ci/39764322744`。本地产物根为out/firmware-ci/39764322744/nuwa-firmware-39764322744/；二进制只留out，不入Git。

| 产物 | 字节 | SHA256 |
| --- | ---: | --- |
| build/FV/SILICIUM_UEFI.fd | 3145728 | a0bbb9645f4af2de66e4e29e1b5deaf508e95c41f33de4fd9f811ab03bde1c83 |
| shim/shim.bin | 112 | 9346a527441b242c69414fd7e3d6fa17813f281d562fef13d9ba8373d39007a9 |
| build/AARCH64/UniXNU.efi | 97792 | 2b5ec9d5d1765d5f97f7f00fe353d42e8847fceae42afac81a59be5956ae30a2 |
| build/AARCH64/UniXNUDxe.efi | 22016 | f0eee6690dc87e686bea005ab0d98f1c40b21b263c0c4172088bd703cc5d9114 |
| build/AARCH64/DarwinBoot.efi | 31232 | cb47c3bf27401852b80d759639e0bb91d4a7ee5dc5bdc91007900db119195a31 |
| build/AARCH64/ShengBootMemoryDxe.efi | 23040 | 09bc718ee85743a24dd725def32cd97a55e25f78b5287ee584b58db57395c9e3 |

检查命令：`python -X utf8 -B scripts/ci/inspect-firmware-candidate.py out/firmware-ci/39764322744/nuwa-firmware-39764322744 --output reports/firmware-ci/39764322744/inspection.json`。

665份文件通过大小与SHA核对；实际FD展开2个FV，四EFI各出现一次且独立EFI/内嵌PE一致，AARCH64/PE32+/子系统/协议GUID通过。SEC TE生产者及发布器含入口HOB GUID。BootShim头image_size3145840、_Payload112、实际MOVZ拷贝3145728。build.log:2413-2415记录内层FV9932800B/3136B空余，外层FD3145728B/1375544B空余；内层是自动定长，不是3MiB FD溢出。所有结论为静态检查通过，未QEMU、未实机。

### DEPEX检查器更正（固件无需重编译）

首版检查器只计算模块INF，首次下载检查报Registrar DEPEX mismatch。实际BUILD_REPORT.txt:9921-9933显示注册器为两个变量协议AND gEfiPcdProtocolGuid；10226-10235显示发布器TRUE AND gEfiPcdProtocolGuid，优化为PUSH PCD/END。来源是Mu_Basecore cfb93724的MdePkg/Library/DxePcdLib/DxePcdLib.inf [Depex.common.DXE_DRIVER...]，不是新增未知依赖。

检查器保留严格字节码预期，显式加入该已证实库依赖，并核对实际FD存在PCD驱动FILE_GUID 80cf7257-87ab-47f9-a3fe-d50b76d89541及其PE中的协议GUID。固定源MdeModulePkg/Universal/PCD/Dxe/Pcd.c通过InstallMultipleProtocolInterfaces生产gEfiPcdProtocolGuid；nuwa Include/APRIORI.inc将PCD列在DXE core后。四项仅内存负向检查（移除PCD、移除SEC HOB GUID、移除注册器PCD依赖、发布器改TRUE）均被拒绝，原始产物通过，见inspector-regression.json。未改任何二进制或放宽为任意DEPEX。

build.log:133仍有上游HwResetSystemLib类声明警告（ArmPsciResetSystemLib.inf未声明该library class）；没有编译错误。构建成功不证明复位路径、初始缓存、DT/initrd生命周期或最终内存map可用。后续实机恢复评估须核对该项。

R-004 A的构建与静态检查范围已完成。用户在本轮追加“这个设备日常不需要用 可以随意推送镜像 只要能恢复回fastboot就行”，记录为可恢复fastboot条件下的后续镜像试启动授权；本轮没有实施设备动作。H-001实体键恢复演练仍未验证，不阻塞后续软件审查，也不冒充硬挂恢复已通过。
