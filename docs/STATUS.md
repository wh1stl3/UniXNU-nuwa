# STATUS

> 当前唯一真相：47b5c4b1实机照片确认HOB查询返回并进入DXE，用户报告进入UniXNU菜单；尚未进入XNU。

CI39962464061（4d4571b）包47b5c4b1/3153920B、FD fb28d9ee已临时启动。照片6cddd1c1显示row=93至99、matched、query-leave、fv-decompress Success及DxeCore加载。用户报告随后failed to find an operating system并回充电界面。证据reports/hob-query-trial/2026-10-23-evening/screen-observation.json；不能由一次进展认定MMU故障根因已修复。

恢复等待超时，后续只读检查仍未识别到唯一nuwa ADB；Android完成1与三分区哈希尚待补齐。人工恢复不阻塞离线分析/构建，未确认恢复时不启动下一包。

新照片已取得SHENGMEM：识别FDT，但initrd被“not a whole number of sectors”分支拒绝；后续DXE MMU after-cache/Mmu leave Success，UniXNU.efi启动并出现四条FAT挂载日志。未由模糊地址计算实际长度，FAT来源尚未确定。下一步接通有明确边界的载荷运输，不向上取整整个chosen范围。当前包不含FAT/ADT/XNU；现有64MiB FAT探针仅离线组件，不能把ABL拼接后的整个initrd直接当FAT。固件来源uefi-nuwa，诊断CI暂仍由设备仓驱动。4KiB/iOS16/8796/board example=true及板值与验证标记不变。
