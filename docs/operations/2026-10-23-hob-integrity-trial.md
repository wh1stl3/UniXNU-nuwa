# HOB完整性诊断实测（dd1ef825）

## 包与证据

CI39973030321/source4139464，固件uefi-nuwa@150b5ec加固定补丁链。临时v4包SHA256 dd1ef82517d256a44b05b5d72e132fe4a37078e2e12cf82f40302b408886034e，70266880B；FD8e37ba79。实际SEC新标记、41行2952B内存表及完整容器复验通过，见reports/hob-integrity/39973030321/。

用户本轮确认通知后录像，preflight门通过后临时启动，launch.json保留实际命令。没有flash/erase/改槽。原视频D:/Code/VIdeos-nuwa/dd1ef825.mp4共约73.598秒，190343254B，摘要见video-source.json；不把该录像描述成完整120秒连续视频。二进制原视频保留原路径，不提交仓库。

## 两次query的含义

用户两张照片显示：第一处在Mmu enter后，第二处在after-library-constructors、before-fv-decompress后。两处list均BAB00000，查询目标GUID不同。这是同一条HOB链的不同查询，不是创建了两条HOB链；GetFirstGuidHob的每次调用都会打印query，不能把照片中的两处说成整次启动只有两次调用。

第一处对应ArmMmuLibConstructor对gArmMmuReplaceLiveTranslationEntryFuncGuid的查找，源码与0012补丁明确该调用。第二处在解压路径，对ExtractGuidedSectionLib保存数据GUID的查找；固定源码PrePiExtractGuidedSectionLib.c定义PRE_PI_EXTRACT_GUIDED_SECTION_DATA_GUID=385A982C-2F49-4043-A51E-4901025C8B6B，GetSavedData调用GetFirstGuidHob。照片GUID数字有模糊部分，未将模糊值作为可靠完整转录。

本次照片BAB00718条目type=3 len=30（日志使用%x，长度0x30=48B），随后推进BAB00748。相比前包同地址type=0 len=0重复，这是不同运行间的有效差异；不据此宣布缓存、覆盖、创建或链指针中的任何一个根因已确定。用户未看到invalid；已审查图片也未见该行，不等于逐帧证明整个录像从未打印。

## 启动进展与未完成项

照片显示Lzma构造成功及after-library-constructors。录像35秒确认UniXNU内置配置/三动作/no boot entry found，未见NUWA VOLUME PROBE - NO XNU探针标题；45秒回固件USB发现回退，71.6秒显示小米Android启动标志。尚无XNU入口证据，也没有证明封装卷被发布。

下一步逐帧定位NuwaBootMemoryDxe至RamManagerDxe的窗口，读SHENGMEM及NUWA-VOLUME的chosen/result/BlockIo状态；确认载荷不存在、范围拒绝、CRC拒绝还是文件发现失败。不能用内置菜单推断已挂载目标探针。

## 设备恢复

本轮recovery.json等待超时，没有确认Android完成1。本轮待补真实nuwa/kalama、sys.boot_completed=1和三分区postcondition；不能借用前轮已恢复证据，也不能把Android标志当完成1。人工恢复待办不阻塞离线分析；下一次设备启动须恢复闭环、新鲜录像确认及通知。
