# STATUS

> 87b14624实机确认FV→只读BlockIo→FAT→unixnu.toml发现通过，已出现目标NUWA VOLUME PROBE菜单。尚无XNU入口或iOS执行证据；本轮Android恢复待闭环。

用户两原图确认NuwaEmbeddedVolumeDxe发布4MiB块设备Success及精确探针配置/菜单项。包无内核/ADT；timeout=60、唯一action=exit，用户所述停留后无OS/回充电界面符合探针退出路径，非完整系统引导验收。原chosen仍envelope absent，与大负载运输问题分开记录。

来源：CI39988591973/source b4f9075、固件00a37d9、包87b14624e95a4b608435da96c4a7f939893bef7c94186af9d2f157eacef0e496/3153920B。实际资源SHA和全部41行内存表保持一致，9项固件主机测试/新scope门及严格容器通过；未改board/bringup/内存图或_verified。

87b本轮已完成120秒USB观察，恢复工具正在等待Android或fastboot；需补Android完成1和三分区postcondition，a22e9a44已恢复不代替本轮。人工按键等待不阻塞离线分析，不启动下一包。照片、preflight/launch/recovery见reports/embedded-probe-trial/2026-10-24/。

下一主线：真实Darwin22负载/NativePrelink ABI与目标Apple ADT、连续可分配内存窗口和条件sidecars。现有源内核仅主机ParseKernel通过，不能充当完整可启动prelink。CPU Vectors缺项和TZ/SPSS/Rsc独立问题保留跟进。详见operations/2026-10-24-embedded-volume-trial.md；主线交接同步。
