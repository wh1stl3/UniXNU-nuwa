# SEC handoff诊断固件：构建及晚上实测准备

更新：2026-10-23T15:26:32+08:00。本轮无ADB/fastboot操作。

## 结果

CI [39915967862](https://github.com/wh1stl3/UniXNU-nuwa/actions/runs/39915967862) 于15:09:28—15:15:19（Asia/Shanghai）成功，5分51秒；设备脚本abe4be9，固件ddd794fc。run.json、完整workflow.log和commands.json记录真实命令与阶段，不是仅凭输入检查判成功。

下载后核对666个清单文件的大小/SHA，四个加载器模块和PCD/DEPEX门通过；原PILDxe和空AUTO配置保持，DXE核心仍8fccb5c9。新SEC四条NUWA-HANDOFF日志均实际存在。与R-011比较，41条72B描述符共2952B全部相同，表SHA7694de6cf91ac305c82b3a2a82ad717a3155f88d59a185093a2a74a1a42bbdda；并非仅检查Heap行。

| 产物 | 字节 | SHA256 |
| --- | --- | --- |
| FD | 3145728 | fcf2f829fb4748034014f8913b967a928cdbafe16836b9992eee5a13d838ac24 |
| 实际SEC TE | 65192 | fad4af6b4c2b8422f4951f71b2ea9f9b00b5813485e9820db668f2f35e5840aa |
| BootShim | 112 | 8a3b54765c895a0366539130fdf6e4e4a01e364fe7de067a38d0193606f9d462 |
| v4临时包 | 3153920 | 2d8334613a415c24574f93c0bcb30ba50d32175ff062d8ec2cc149651bcde846 |

临时包：`out/trial-boot/sec-handoff-39915967862/boot-sec-handoff-v4.img`。保留原Android v4头，只改kernel_size；kernel字段为112B shim＋3145728B FD，4096B页对齐；无新增ramdisk、FAT、ADT、XNU、DTB或签名。打包后独立回读边界、长度、原头和内容校验通过，恢复boot原件ef558db2 SHA同时复查通过。二进制留out，不提交。

## 晚上的顺序

1. 用户在场后先通知录像，刷新实际nuwa/kalama身份、Android完成1及三分区SHA；核对原boot SHA、此前实际恢复证据与按键回fastboot路径。本轮未执行这些当晚前置条件，不能沿用中午记录当新门。
2. 本包标为SEC-HANDOFF-OFFLINE／ready_to_execute=false，表示包自身不能替代运行前门。严格新scope已经接入trial/preflight：重查固定recipe、实际FD/TE、四条日志、Heap/PIL/shim、原boot、容器原头/内容/填充全部字节；不能用R-011标签冒用本包。晚上仍须刷新D-021日志/恢复门（15分钟内、具体用户录像与身份/完成1/原boot/恢复证据），启动前通知用户；本轮未执行门刷新或设备动作。
3. 仅临时启动此唯一候选，不flash、不改槽；录像覆盖完整ENTRY/HANDOFF/DXE/菜单，保留至少120秒连续观察，若明确失败先记录并恢复。试启动脚本已将USB观察默认延长为120秒（范围120—600），每条记录附ACK后的相对秒数。USB采样不等于屏幕录像，不充当阶段日志；捕获具体失败可结束观察转恢复。
4. 记录四条新日志最后可见项与list/data数字及相对时刻。after-entry-arg-hob说明该调用返回；after-library-constructors说明该调用返回。缺失日志仍可能是输出通道问题，不能当作精确PC；空data需要记录而不能直接跳过HOB。
5. 若到UniXNU，继续记录SHENGMEM（无initrd／整扇区错误／发布结果），因本包无系统卷，NoBootOS不算XNU panic。若未到DXE，则保留SEC定位证据。结束后仅用已校验原boot恢复，确认Android完成1、三分区SHA不变。

设备前缺具体日志或恢复依据则按AGENTS§3写审阅并停，不先启动。H-009为晚上拍摄配合待办；本轮没有新设备实测通过。新包目的是缩小阶段范围，不是进入XNU的系统负载包。系统卷、目标ADT、NativePrelink运行ABI和EL1交接仍未验收。

## 可复查证据

reports/sec-handoff/39915967862/下summary.json包含完整复查命令；artifact-inspection.json、descriptor-comparison.json、package.json、inputs.json、result.json、shim.json、inventory.json和workflow.log分别记录下载核验、表对比、容器及真实构建。源码/依赖及同SoC评估见前篇2026-10-23-sec-handoff-diagnostic.md。

## 试启动工具离线接线检查

scripts/sec_handoff_package.py重建整个原Android头＋shim＋FD＋零填充并逐字节比对，而非只信任可编辑的包JSON；从artifact重跑实际固件检查并逐项比对包metadata。record-nuwa-trial-state.py和trial-v4-firmware.py接入此独立scope。旧profile和原D-021新鲜度/照片来源/恢复证据检查保留。只执行了纯文件validate、语法检查及--help，无设备查询/重启/临时启动命令；trial-scope-integration.json记录结果与元数据说明文字更新前后SHA，镜像SHA未变。

晚间使用的新包报告为reports/sec-handoff/39915967862/package.json，先运行record-nuwa-trial-state.py生成当晚fresh preflight；人在场且已通知拍摄后，再交给trial-v4-firmware.py的launch（--observation-seconds 120），结束后recover及postcondition。不能提前生成或复用中午的fresh记录。具体命令与当晚输出届时写入独立reports目录，防止覆盖本轮纯离线证据。
