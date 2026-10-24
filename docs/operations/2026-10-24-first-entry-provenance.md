# 接手审计：纠正首次内核交接证据归属

时间：2026-10-24 20:25（北京时间）。全离线；没有查询、重启、启动或刷写手机。

## 结论

**撤回“Apple 启动链安全锁导致内核退出”的首因判断。** 显示的 SecurityLock/LockCapsuleInterface 来自本次固件实际使用的 Project Mu CapsuleRuntimeDxe，而非 Apple 模块。当前最可靠的实机里程碑是：UEFI 完成负载准备、取得 1 GiB 窗口、进入 DarwinEnter 的绿色帧缓冲写入路径，随后黑屏并恢复 Android。是否到达 XNU 第一条指令、早期初始化与 panic 路径，仍需独立证据。

## 固定源码和实际产物

- 原试验包 reports/xnu-first-entry/package-01.json：镜像 aa2dfb5d65a9ae2f62cfde28055631623e36ea3d91bdcc368db3299b49ade8fc；FD 2d606985ad768dcfaab66c2b28073c0a4c2820126b42b23286623fdc450e848f；内核 1aeebf1352a86b0d31612a6bd6e77bd7292f676ad2ce43a99ec4a8f3999eedb6。
- CI40014018074 的 submodules-final.txt 固定 Mu_Basecore cfb93724a06ff86ff5ba971413368a7809ee42a5，unixnu-submodules.log 固定 DarwinBoot d099354d0eab34df5088ca1ba89c9c88bc3260bb。没有用当前固件 HEAD 代替旧产物来源。
- Mu CapsuleRuntimeDxe.inf:19 的 GUID 是 **42857F0A-13F2-4B21-8A23-53D3F714B840**。旧记录的 4821/B940 是图片误读，不再沿用；原图保留。
- CapsuleService.c:410-418：LockCapsuleInterface 设置 mAfterLocked，并报告 SOFTWARE_LOCK。476-482：注册到 gEfiEventExitBootServicesGuid。SecurityLockAuditDebugMessageLib.c:43 提供屏幕同款格式字符串。该路径为正常固件接口关闭审计，不是缺 SEP 的报错。
- 实际 BUILD_REPORT.txt 包含 CapsuleRuntimeDxe、同 GUID 和 SecurityLockAuditDebugMessageLib；实际 FD 哈希与试验包一致。
- 实际 DarwinBoot.efi SHA256 3313e8568b97432675c33e76dc3b8a7240cfff66a1cd0559ba33e2f512440145。PE/map 反汇编 DarwinEnter RVA 0x5d40、148 字节，完整解码；绿色 stp 写入在缓存清理、关 MMU 和最终 **0x5dd0 br x1** 之前。绿条只能证明执行到了写入，不能证明后面的跳转或 XNU 执行。

来源及可复核行号/哈希：reports/xnu-first-entry-provenance/2026-10-24/audit.json；14 项静态检查通过。下载的固定版本源仅放聊天 work/handoff-audit，不向设备仓复制上游源码。

公开原始资料：

- [Mu 固定版本 CapsuleService.c](https://github.com/microsoft/mu_basecore/blob/cfb93724a06ff86ff5ba971413368a7809ee42a5/MdeModulePkg/Universal/CapsuleRuntimeDxe/CapsuleService.c)
- [Mu 固定版本日志实现](https://github.com/microsoft/mu_basecore/blob/cfb93724a06ff86ff5ba971413368a7809ee42a5/MdeModulePkg/Library/SecurityLockAuditDebugMessageLib/SecurityLockAuditDebugMessageLib.c)
- [DarwinBoot 固定版本 Entry.S](https://github.com/UniXNU/DarwinBoot/blob/d099354d0eab34df5088ca1ba89c9c88bc3260bb/DarwinBootPkg/Driver/Entry.S)
- [Linaro Qualcomm 启动实录](https://www.linaro.org/blog/let-s-boot-the-mainline-linux-kernel-on-qualcomm-devices/)：App Log Flush 出现在 UEFI End 和 Linux 首条日志之前，不能拿它当 XNU 输出。本机该字符串的精确模块仍未定位。
- [AOSP A/B 定义](https://source.android.com/docs/core/ota/ab/ab_implement#kernel-slot-arguments)：slot-retry-count 表示**剩余重试次数**。一次 a:6/b:7 快照不是累计失败次数，也没有证明本次试验改变了计数。

补充：原记录 TCR_EL1=0x28003518 的 TG0 实际为 00（4 KiB），不是 01；IPS 位在 [34:32]，该值为 0，不能把 PARange=2 当成当前 TCR.IPS=2。该读数是关 MMU 前的固件状态，不能作为 XNU 页表已启用的证据。

## 首因排序和最小证伪

1. **首要工作假设（中等置信）：交接尾部至 XNU 极早期入口之间故障，缺少独立阶段标记。** 支持：绿条位于跳转之前；没有已归属且按时间确认的 XNU 新输出。反对：尚未捕获异常 PC，不能区分缓存循环、关 MMU 后取指、br 目标与内核第一阶段。下一步在实际 DarwinEnter 最终分支前、实际 XNU 入口最初指令及建表后分别设计独立标记，先核对链接/指令和 framebuffer 的物理访问条件，再构建候选。
2. XNU 已进入、但因 ABI/ADT/平台初始化故障而无法输出（中低置信）。需要内核内标记或异常寄存器，不能用 EFI 负载读取成功代替初始化成功。
3. 安全策略初始化后续问题（低置信）。现有 SecurityLock 文本不支持此假设；暂不因它改变 AMFI、认证策略或信任链。

屏幕上 AppleARMPlatform/IODTNVRAM 的旧转录尚未得到本轮可归属的源码/逐帧确认，不能用于绕过入口证据缺口。黑屏 19 秒和随后 Android 恢复是实测现象；“内核静默退出”“没有 panic”超出证据，只能说未拍到 panic。kext leave Success 证明加载调用返回成功，不证明 kext 初始化/ABI 已通过。

## 续接

已有复核命令（源目录需为上述固定版本下载文件）：

```powershell
& 'C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe' -B scripts/audit-first-entry-provenance.py --sources C:/Users/Administrator/Documents/Codex/2026-10-24/ios-nuwa-d-code-unixnu-nuwa-2/work/handoff-audit --artifact out/upstream-firmware-40014018074/nuwa-firmware-40014018074 --output reports/xnu-first-entry-provenance/2026-10-24/audit.json
```

继续离线入口和异常可观测性设计。暂不引入 Android 分区写日志；没有新包或新实机动作。下一次启动按 AGENTS 的新鲜录像/恢复门处理；所有内存、板值和 _verified 约束保留。
