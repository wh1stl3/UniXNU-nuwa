# STATUS

更新：2026-10-24 20:25（北京时间），接手离线审计；没有新设备动作。

**iOS 尚未启动。已确认 UEFI 负载准备和 DarwinEnter 绿色帧缓冲写入；XNU 首条指令及初始化是否执行仍待独立证据。** 旧“Apple 安全链锁导致退出”的判断已被固定版本固件源码反证，详见 [接手审计](operations/2026-10-24-first-entry-provenance.md)。

## 当前有效事实

- 设备仓 D:/Code/UniXNU-nuwa，远程 wh1stl3/UniXNU-nuwa；接手基线 main@b295013，比远程 main@54b3674 超前两个提交。原有三个未跟踪项保留。
- 固件仓 D:/Code/uefi-nuwa，远程 wh1stl3/uefi-nuwa；codex/nuwa-sec-handoff-trace@a155c495，与远程同分支一致，工作区干净。
- 首次入口试验使用包 aa2dfb5d、内核 1aeebf13、FD 2d606985（CI40014018074）。内核资格标志仍 loadable=false/runtime_qualified=false；不修改 _verified。
- 1 GiB 窗口被分配，负载加载调用成功，绿色横条出现；录像显示随后黑屏约19秒，再进入 Android。原始画面和时间线保留在 reports/xnu-first-entry-trial/2026-10-24/ 与 reports/xnu-first-entry-video/2026-10-24/。
- 首次试验 postcondition 时间 2026-10-24T11:33:59Z（北京时间19:33:59），Android完成1/A槽/三分区SHA与试前一致。其后交接记载 fastboot 只读取证并恢复 Android完成1，来源 fastboot-varall.txt 和旧工作日志；本轮没有刷新设备状态，不能称手机“当前在线”。
- R-012 A 已批准并落地 dram_size=0x240000000、owned_memory_size=0x40000000。ADT生成器、board参数重放、FDT输入核对、10用例通过；board仍 example=true，其余TODO保留。
- 文件运输/SHA已在独立FV诊断实机通过；native Darwin22内核构建成功、零未定义符号。donor/native C++及结构ABI仍未完整资格化。

## 本轮纠错

1. SecurityLock/LockCapsuleInterface 是 Project Mu 的 CapsuleRuntimeDxe 在 ExitBootServices 中关闭 Capsule 接口的审计，不是 Apple/SEP 故障。GUID正确值42857F0A-13F2-4B21-8A23-53D3F714B840。
2. 实际DarwinEnter反汇编证明绿色写入发生在缓存处理、关MMU和br x1之前。绿条不证明XNU已执行，旧“内核静默退出”改为“交接后黑屏，退出位置未定位”。
3. slot-retry-count:a:6 是剩余次数，不是累计6次失败；无前后差分，不能关联本次故障。
4. App Log Flush有Qualcomm固件启动实录来源，不能当XNU日志。kext加载Success不等于初始化或ABI验证。旧AppleARMPlatform/IODTNVRAM转录仍须独立核对。

复核：scripts/audit-first-entry-provenance.py 14项静态检查通过；报告 reports/xnu-first-entry-provenance/2026-10-24/audit.json 含固定源码URL/哈希/行号、实际FD一致性与148字节完整反汇编。无新构建或实机通过声明。

## 下一步

主线改为定位 **DarwinEnter交接尾部 → XNU首条指令 → 早期建表/初始化** 的实际执行边界。先设计各阶段独立标记和异常记录，再离线构建与验收；当前不因错误归属的SecurityLock调整AMFI或认证策略，也不向Android分区写日志。

受审内存/基址、Heap/HOB保护、认证策略与_verified保持。新包启动前仍需本包录像与恢复条件、离线验收和即时通知；结束恢复Android完成1并核对三分区。旧交接历史由 [主线交接](operations/2026-10-23-mainline-handoff.md) 保留，本状态及其顶部纠错优先。
