# STATUS

> 用户明确要求“先停下 落实文档”：主线已暂停。新启动输入诊断包完成离线验收，尚未在手机执行；恢复工作须等用户明确续接，并重新确认本轮录像条件。

新包 a2dc8195b4368da37276a4618dca90fd556f1d5de72fd58faff0b600936ba65b，3153920B。CI39995937843成功，构建设备提交84c88f8057a808670fc84d151ad0b4128ce91013，固件6176a822e66b846620b5bcd2739a0666814ee663。实际NuwaBootAuditDxe PE/DEPEX/标记、4MiB FAT资源及容器逐字节复验通过；41行2952B SEC内存表与基线一致。10项固件宿主测试、2项旧包冒充/空录像拒绝通过；实际新包缺preflight在设备子进程前拒绝。全部仅静态/主机检查，ReadyToBoot回调、内存范围、EL/MPIDR/CNTFRQ尚无实机证据。

最近一次真实设备证据仍是reports/embedded-probe-trial/2026-10-24/postcondition.json：UTC 2026-10-23T16:56:45.092564，即北京时间2026-10-24 00:56:45；nuwa/kalama、Android完成1、slot_a、三分区SHA不变。本轮没有ADB/fastboot命令或模式切换，不能把历史状态当作当前实时查询。87b14624的小配置卷FV→BlockIo→FAT→唯一配置发现已实机通过，未执行XNU。

当前77742999内核已生成分析用预链接5a128fb2/58335232B：65348项绑定逐项读回、30段组件/native执行字节保持；DarwinBoot主机解析通过，20项ADT回归和4项常量池拒绝回归通过。早期安全initializer为空、完整ABI未验收，loadable=false；不得放入启动菜单。

续接顺序：取得用户恢复工作指令→新鲜录像及恢复门→临时启动a2dc8195采集ReadyToBoot快照→Android完成1/三分区核验→据实准备连续窗口/目标ADT方案；然后完成真实安全初始化、ABI和大负载运输。未修改board/bringup/内存基址或_verified。细节见operations/2026-10-24-boot-input-audit.md和operations/2026-10-23-mainline-handoff.md。
