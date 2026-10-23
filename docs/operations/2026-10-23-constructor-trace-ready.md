# 构造诊断固件构建及下一轮实测清单

2026-10-23T19:26:45+08:00。本轮没有设备命令，Android保持最近一次18:30:39完成1状态的历史证据；未重新查询设备。

CI [39943865806](https://github.com/wh1stl3/UniXNU-nuwa/actions/runs/39943865806)成功，19:07:24—19:12:41（Asia/Shanghai），5分17秒。设备脚本7ebb58d，固件源码ddd794fc及0011补丁SHA76f614fac9bc0c1919487b63e32587b6a1ab236c6c782b8eb628b1232dff16c4。真实run/workflow完整日志、命令与输入均保存，不能只用旧firmware commit区分新旧包，新增补丁是配方身份的一部分。

下载后666个清单文件大小/SHA通过；实际SEC8条NUWA-CTOR、4条HANDOFF及原ENTRY全部存在。反汇编actual-path.json保存每个日志xref及实际调用，Debug enter/leave在前，之后Extract、Mmu、Lzma及HANDOFF after；首选A710地址不是实际PC。当前晚间旧包反汇编另存evening-actual-path.json，未改原证据。

全部41条72B内存描述符共2952B与R-011完全一致。原PILDxe89e030af、空AUTO dbc9ee6e、112B shim8a3b5476、relative offset0均保持；四模块/PCD/DEPEX通过。共享库日志使DXE核心改为45570d705dc4b075bd799751d2c984d92e8cd81034b41f7e8ab2481159c2d8cb，原分配诊断仍完整存在，不能宣称核心与旧8fccb5c9相同。

| 文件 | SHA256 |
| --- | --- |
| FD 3145728B | a47d8289b8c954bf7004c038489f97c8c23f470d95a19e8c7e439b6a69170573 |
| 实际SEC TE | 20b7768119a096ec86d4e4f024a1641091d9e3b15352e11ca432c110ebe24e37 |
| 唯一v4包3153920B | 530f56b49c8b6f785c9869612af338bc4ef64098dcad4051b4bd723460784d50 |

包路径：`out/trial-boot/constructor-trace-39943865806/boot-constructor-trace-v4.img`。原Android头仅改kernel_size，完整原头＋shim＋FD＋零填充重建检查通过。无FAT、ADT、XNU、新DTB或ramdisk；原boot恢复输入ef558db2哈希复查通过。所有二进制留out，不提交。constructor-trace的严格scope已接入现有trial/preflight，两包纯文件回归通过；只通过文件验证不代表当下日志/恢复门已刷新。

## 还需要的实机验证

1. 下次启动前重新确认人在场且录像、通知倒计时，刷新nuwa身份/Android完成1/三分区/原boot/恢复依据；不能沿用18:30的fresh记录。
2. 只临时启动530f56b4包，记录NUWA-CTOR Debug、Extract、Mmu、Lzma各自enter/leave及status。最后一个enter没有leave可缩小范围，但不替代异常PC或排除日志通道问题。
3. 若四库均返回，则跟进HANDOFF after、FV解压、DXE/BDS；若到UniXNU，取SHENGMEM实际x0/initrd长度/状态。该包无系统卷，NoBootOS不是内核panic。
4. 完整保留连续录像（默认USB采样120秒不是录像），记录错误后恢复Android完成1并核对三分区SHA；不flash/erase/改槽。

当前无需重复旧2d833461。新包实机未验证；用户本轮问是否还需实机，答案是需要这轮更细日志定位，当前先将可审查包准备好，未自动启动。共享库诊断改变时序，需要结合原包停点解读，不以“新包通过/失败”直接证明原根因修复。

## 可复查命令

summary.json列下载、实际固件检查、2952B表回归和打包命令；proposal/profile-check记录固定Mu来源、许可及调用返回静态等价。scripts/audit-sec-handoff-path.py仅增加显式artifact/output/fd-sha256参数，保留旧默认输入；未覆写旧报告。预研系统卷/启动载荷和board/feed/bringup-plan/验证标志均保持。
