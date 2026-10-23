# 独立FV配置探针（离线准备）

依据：a22e9a44原图证明chosen范围缺封装；2026-10-23-offline-initrd-and-volume-probe.md备选B。独立固件00a37d9新增NuwaEmbeddedVolumeDxe，普通DSC/FDF不包含；设备仓0016仅在embedded-probe profile添加模块和固定FREEFORM RAW资源。原chosen发布器及所有诊断保留。

探针为确定性4MiB FAT16，512B扇区，固定日期，VFAT长名unixnu.toml（扩展名4字符不能仅用8.3）；仅EFI/UniXNU/unixnu.toml和返回固件动作，无XNU/ADT。脚本build-embedded-probe.py生成，SHA c097413db551aac705e530cef697fdbc54ae9a9c4ea8ae86be175ba5bdd15796。WSL mtype按精确路径读回237B与配置逐字节一致；初稿只有8.3的错误在验证时发现并修正，未进入profile。

驱动用DxeServicesLib的GetSectionFromAnyFv分配资源副本；校验长度、引导签名和固定CRC54fe5070后发布只读BlockIo。安装失败释放，成功保留BootServices pool供协议读取直到ExitBootServices。复用本仓BSD-2-Clause块读取实现，设备路径GUID独立；无全局内存搜索或地址假设。生成物不提交固件仓，CI按生成器SHA与完整资源SHA验证。

9项主机C测试通过，新增项覆盖资源读取错误、长度/签名/CRC错误、成功时保留及安装失败释放、尾扇区读取边界；这些服务为替身，不证明实际FV/UEFI成功。43输入/8补丁/12后哈希静态通过；完整编译待运行。板级内存表未变，但解压FV和资源pool增加内存压力，必须实际产物和实机分别验收。不宣称这条小探针运输了真实XNU。

2026-10-24T00:48:14.773032+08:00：CI39988591973/source b4f9075成功，实际新驱动DEPEX/PE和完整RAW资源SHA通过，FD70b266b3；41行2952B内存表与dd1ef825相同。包87b14624e95a4b608435da96c4a7f939893bef7c94186af9d2f157eacef0e496/3153920B（ramdisk0，FV内含4MiB FAT16）逐字节复验通过。新EMBEDDED-PROBE-OFFLINE scope校验和缺录像/预检时设备子进程前拒绝通过；新增旧包冒充/空录像2项回归通过。用户已本轮确认“可以，继续录像测试”，下一动作刷新preflight、通知后临时启动一次。目标为NUWA-FV-PROBE block Success和探针配置菜单；不是XNU。新证据目录reports/embedded-probe-trial/2026-10-24/。
