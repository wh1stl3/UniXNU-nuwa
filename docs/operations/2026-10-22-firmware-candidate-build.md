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
