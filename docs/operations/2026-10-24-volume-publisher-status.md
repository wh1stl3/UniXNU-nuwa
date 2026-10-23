# 卷发布错误传播与恢复闭环（2026-10-24）

## 本轮实证

只读ADB按ro.product.device选择唯一nuwa，未向同时连接的enuma发设备动作。
reports/hob-integrity-trial/2026-10-23-evening/postcondition.json记录本轮查询时间、nuwa/kalama身份、Android完成1、slot_a及三分区SHA与上轮preflight一致。补齐dd1ef825后的恢复闭环；没有执行重启、临时启动或刷写。

复查原视频171a0a39：抽查19至35秒含25.80秒末次HOB匹配、27.25秒ArmCpuDxe/MMU和其他驱动、30.25秒控制台驱动、30.85秒BGRT、31至34秒Silicium启动图、34.5秒内置菜单。未取得可读的NUWA-VOLUME结果，不从抽样缺失推出驱动未调度或某个具体根因。交接原先建议30至32秒的窗口不足以定位此驱动。

## 修正

uefi-nuwa@79c516a（含测试LF修正固定bc38be0）：NuwaBootMemoryDxe不再将所有失败当EFI_SUCCESS。
缺HOB/chosen/envelope为EFI_NOT_FOUND，非法指针/属性为EFI_INVALID_PARAMETER，映射拒绝为EFI_ACCESS_DENIED，损坏FDT/envelope为EFI_COMPROMISED_DATA；InstallMultipleProtocolInterfaces返回原状态。FDT头和完整范围检查保留，initrd越界在扫描/CRC前拒绝，无放宽映射、无原始initrd回退。

新日志区分入口DTB、FDT头映射/格式/总长、chosen及最终状态。正常构建无延时；独立volume-status profile以0015将宏设为5000000，仅在驱动最终状态打印后停留5秒，便于新鲜录像。此停留不证明显示可靠，也不阻止后续驱动清屏；仍须实际录像验收。

## 验证与来源

`wsl -d Ubuntu-22.04 -- bash -lc 'cd /mnt/d/Code/uefi-nuwa && python3 -B -m unittest discover -s tests -v'`：8项通过。新测试直接编译实际发布器C和主机服务替身，UBSan覆盖未映射FDT在读前拒绝、无效输入、initrd越界在CRC前拒绝、只读BlockIo发布/读写范围及安装错误传播。FDT服务为替身，不验证真实libfdt或ABL。

`python -B scripts/check-volume-status.py`：41输入、7补丁、10补丁后哈希通过。完整固件编译及实际产物验收待完成；不称实机通过。旧profile不变，board/bringup-plan/内存图/验证标志不变。

源码源于已固定nuwa发布器，BSD-2-Clause，依赖FdtLib/HobLib/MemoryMapLib/UEFI Boot Services；不新增同SoC板值或来源。上游资料库保持只读。

## 下一步

构建volume-status，下载实际FD/EFI/BootShim，强制新旧诊断标记及41行内存全表核验，打包同一配置探针并逐字节复验。产物就绪后才刷新设备身份、恢复与用户录像门，通知后执行；本轮没有新鲜录像确认，不直接启动。

## 构建与设备门推进

2026-10-24T00:17:00.937798+08:00：设备仓b8e6e2a已推送，CI39985245383启动，源固定bc38be0。新scope VOLUME-STATUS-OFFLINE接入原严格包复验、新鲜录像和恢复门；旧scope不变。2项反向测试确认旧HOB产物即使伪造profile元数据仍被实际PE标记拒绝，空录像确认拒绝；原5项MMU门回归通过。无设备模式切换。

## 实际产物验收与本轮录像

2026-10-24T00:23:43.134759+08:00：CI39985245383成功；实际FD SHA ff218da439aebf32cdbd649c37021e1333ab3efb4d09b2fb454c8ce388644811，新旧日志标记通过，全部41行2952B内存表SHA7694de6c与dd1ef825完全相同。完整包a22e9a44561c85c52aa5697d0452c38dc8bdd1f5b2c7c7a40e79f5396a27f9f0/70266880B逐字节复验通过。实际包缺录像/预检时均在设备子进程前拒绝，证据reports/volume-status/39985245383/。用户本轮确认“可以，现在准备录像”；准备刷新本轮设备门并通知后临时启动，尚未执行。
