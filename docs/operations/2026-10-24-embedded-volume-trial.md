# 内嵌配置卷实机发现通过（87b14624）

## 来源和启动

CI39988591973/source b4f9075，固件00a37d9，FD70b266b3，v4包SHA87b14624e95a4b608435da96c4a7f939893bef7c94186af9d2f157eacef0e496/3153920B。完整容器、新旧诊断标记、实际4MiB RAW资源SHA和41行内存全表一致已核验；见reports/embedded-probe/39988591973/。

用户本轮确认“可以，继续录像测试”，新鲜preflight确认nuwa/kalama、Android完成1、原厂恢复输入及过程录像门后通知并临时启动。fastboot exit0和120秒USB观察在launch.json，仅是命令/USB证据，无flash/erase/改槽。

## 实机结果

两张用户原图分别确认：

1. 原chosen发布器仍envelope result0/Not Found；随后NuwaEmbeddedVolumeDxe调度，`[NUWA-FV-PROBE] block device bytes=0x400000 status=Success`。
2. UniXNU显示`NUWA VOLUME PROBE`，config路径`\EFI\UniXNU`，菜单项`Volume config loaded - action`，与唯一探针配置相符。

这证明本轮FV资源读取、只读BlockIo发布、FAT挂载与unixnu.toml发现链在实机上通过，解决了此前“系统卷完全未发现”的诊断缺口。没有因此设置任何_verified标志；小探针不证明大负载运输、DarwinBoot交接或XNU/iOS运行。

用户报告菜单停留较久再报无OS并回充电界面。配置明确timeout=60、唯一项action=exit，含4MiB配置卷但无内核/ADT，自动退出后的无OS路径符合这一探针用途；原图本身不提供精确停留时长，仍保留“约60秒为配置解释”的来源边界，不把它描述成已测量的卡顿根因。

## 其他错误

RscDxe No mapping与原chosen Not Found仍出现，未宣称修复；前者没有阻断本轮FV配置发现。CPU Vectors/FeatureEnabler/TZ/SPSS审查仍见2026-10-24-error-triage-and-initboot.md。新增固定EnvDxe离线xref显示0x1e0c查询CPU Vectors，失败打印后0x1e40返回；成功时进入固定0xa7600000的后续处理。它是被跳过的真实处理路径，不是ArmCpuDxe自身断言停机，也不能据此称其无害；未更改内存表。

## 下一主线

进入实际内核输入阶段，保持已通过的小卷作对照。当前内核仅源编译/ParseKernel主机解析通过，完整NativePrelink donor运行ABI、目标Apple ADT、可用连续内存窗口及条件sidecars未验收；不能往菜单随意挂一个kernel文件就称可启动。应先核对真实负载、ADT消费者和运行内存证据，再形成可审阅构建候选，不沿用其他板地址或未知占位值。

本轮恢复及postcondition见reports/embedded-probe-trial/2026-10-24/；当前恢复工具正在等待nuwa返回Android或fastboot，上一包恢复不替代本轮。人工按键等待不阻塞离线分析，未闭环不启动下一包。

2026-10-24T00:57:15.571203+08:00：87b14624本轮恢复闭环完成。recovery.json确认Android完成1；postcondition.json确认nuwa/kalama、slot_a及boot/vendor_boot/init_boot三个分区SHA与本轮preflight一致。无需继续人工恢复；新包试验另需新鲜日志/恢复门，不沿用本轮确认。配置发现已实机通过，XNU/真实ADT/NativePrelink仍未验收。
