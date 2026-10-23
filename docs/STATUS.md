# STATUS

> a22e9a44实测已确定：chosen内没有封装卷，publisher返回Not Found。Android恢复和三分区核验完成；转独立FV小探针离线构建。无XNU入口证据。

原图：DTB b5db1000/938800B，initrd [b5fb2000,b7fff1d4)/33870292B，envelope result0，与历史Android范围相同；不能仅凭地址长度宣称字节相同。固定ABL中有版本>=4的init_boot选择路径，支持运输/选择方向但不是动态执行证明。六张原图及转录在reports/volume-status-trial/2026-10-24/。

恢复：recovery-after-keys确认Android完成1，postcondition确认nuwa/kalama及三分区SHA与本轮preflight一致。首次超时记录保留，不代表当前状态。无flash/erase/改槽。

其他错误已逐项审查：CPU Vectors是明确命名契约缺口；TZ/FeatureEnabler、SPSS和RscDxe真实失败保留追踪，未证实导致本次封装缺失；USB是后续回退失败。见operations/2026-10-24-error-triage-and-initboot.md。

下一步embedded-probe独立profile：固件00a37d9、确定性4MiB FAT16/精确VFAT配置路径；9项C主机测试、WSL精确文件读回和43输入/8补丁/12后哈希通过，完整CI待执行。内存表/board/bringup/_verified未改。小探针不解决完整XNU运输。下轮设备动作另刷新录像、身份、包复验与恢复门并通知。详见operations/2026-10-24-embedded-volume-probe.md和主线交接。
