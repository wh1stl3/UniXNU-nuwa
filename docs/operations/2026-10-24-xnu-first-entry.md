# 首次内核进入试验：内核入口执行，XNU 走到启动链锁后重启

2026-10-24 19:26–19:33。本轮是本项目第一次让 iOS 16 内核在 nuwa 上真正执行。

## 结论

**内核入口代码执行了。** DarwinBoot 打印 `Exiting boot services. A green bar across the top means the kernel entry code ran.`，屏幕顶部出现绿色横条（ExitBootServices 成功的标志），随后 XNU 自身在控制台输出了 `AppleARMPlatform: IODTNVRAM from …`、`SecurityLock::LockType: SOFTWARE_LOCK, …`、`LockCapsuleInterface`、`App Log Flush : 0 ms`。约 235 秒时设备自动重启回 Android。

这比"进入内核"更进一步：XNU 已经跑到 Apple 的启动链安全锁阶段。**但 iOS 没有启动**，内核在打印完 `App Log Flush` 之后退出，画面上没有出现 panic 文本。

## 确切的屏幕读数

从原图（881×1920）裁剪放大后读出，`reports/xnu-first-entry-trial/2026-10-24/crop-*.png`：

DarwinBoot 交接前的诊断大字（`DarwinBoot.c:669-682`）：

```
kernel   va 0xfffffff003DC8000  pa 0x8C01C8000
entry    pa 0x8C37C5488   version 0.1.0
args     pa 0x4C408000  window 0x40000000 bytes
video    base 0xB8000000  1440x3200 , row 5760 bytes  32 bpp
entry words 1400006F5 IE503201A IE503201A IE503201A
CurrentEL 1  SCTLR_EL1 0x3D0018D0  TCR_EL1 0x28003518
ID_AA64MMFR0_EL1 0x2220010122  (PARange 2, 4 KiB granule supported)
```

关键点：

- **`window 0x40000000 bytes`** —— ADT 里 `darwinboot-memory-size` 的 1 GiB 被 DarwinBoot 正确采用（`DarwinBoot.c:559`、`672`），并且 `AllocateWindow` 成功了。所以 blocker 3 的"固件能否给出连续窗口"这一问，答案是**能**，至少能给 1 GiB。
- **`pa 0x8C01C8000`** —— 内核物理基址落在主 bank `0x8c0000000` 内，与 D-001 选定的主 bank 一致。
- **`TCR_EL1 0x28003518`** —— T0SZ=0x28（40 位 VA）、TG0=01（4 KiB granule）、IPS=2（40 位 PA）。**与 D-003 的 4 KiB 页大小决策相符**，且 PARange 2 表示硬件支持 4 KiB granule。
- `CurrentEL 1` —— 交接时处于 EL1，符合 `DarwinBoot.c:508` 的 `DarwinCurrentEl () != 4` 检查（EFI 阶段的 CurrentEl 为 4）。

菜单侧：`NUWA_UNIXNU_BOOT_MENU` 只渲染出一个 `xnu` 条目并高亮选中，`Booting Enter UniXNU iOS 16 kernel (analysis prelink) in 1s` 表示**走的是倒计时超时自动启动分支**（`Menu.c:191`），不需要任何按键。`drivers 0 loaded / 0 failed  kits 0  acpi 0` 说明本次没有任何驱动或 kit 被加载。

## 关于"按电源键"

不是 Enter。`Menu.c:219-236` 只处理 UP/DOWN/HOME/END、`1`-`9`、Enter(CR/LF)/空格/→/SCAN_SUSPEND，代码里没有电源键分支。菜单唯一的高亮项本来就是默认项，加上 1 秒倒计时，**这次启动全程不需要按键**。

## 恢复闭环

设备自动重启回 Android，无需人工按键。`reports/xnu-first-entry-trial/2026-10-24/postcondition.json`：`device=nuwa`、`soc=kalama`、`android_boot_completed=1`、`slot=_a`，**boot_a / vendor_boot_a / init_boot_a 三个分区 SHA 与试前完全一致**。没有 flash、erase 或改槽。

## 失败点判断

**首要原因（置信中高）：内核在 Apple 启动链安全锁阶段因缺少硬件信任根而终止。**

支持证据：最后可见输出是 `SecurityLock::LockType: SOFTWARE_LOCK, Module: 42B57F0A-13F2-4821-8A23-55B3F714B940, Function: LockCapsuleInterface, Output: Lock Capsule interface`，紧接着 `[ML] dump table info not found, Status = (0x0)` 与 `App Log Flush : 0 ms`，此后无任何输出。`42B57F0A-…` 是 Apple 的 boot policy 模块标识，`LockCapsuleInterface` 属于 iBoot 信任链接口，这类校验需要安全协处理器状态、硬件密钥与 Apple 签发的信任链。

备选原因（置信低，顺序）：① `App Log Flush` 之后的某个早期 panic，画面未刷新到；② 内核在缺 trust cache / SEP 的情况下走了静默复位路径；③ 屏幕输出在 `App Log Flush` 之后转到别的控制台。

**反证与空白**：`SecurityLock`、`LockCapsuleInterface`、`SOFTWARE_LOCK`、`App Log Flush`、`dump table info not found` 这些字面串在 XNU 8796 源码树（含全部二进制 blob）、UniXNU 基座全部源码与补丁、donor kernelcache 文件、native 内核与预链接产物里**都不存在**（ASCII 与 UTF-16 都搜过）。所以这些输出的确切来源尚未定位，不能据此断定它属于 XNU 源码路径还是某个未注入的闭源组件。主机只有 COM1（ACPI 物理串口），**没有连到手机 9008 串口**，因此拿不到内核 panic 的串志。

## 未验证

- 内核退出的确切原因（无串志、无 panic 画面）。
- `App Log Flush` 之后屏幕是否还有内容但未被拍到。
- 23 项 AMFI ops 回调是否被调用过、AMFI 策略是否真正注册成功。
- 任何用户态、任何 iOS 服务。

## 下一步

1. 复现时把观察窗口延长到 600 秒，并请用户把镜头对准屏幕直到设备重启，拍下重启前最后画面（当前照片停在 `App Log Flush`）。
2. 若能接上手机 UART/9008 串口，串志是定位退出口最直接的手段。
3. 在不依赖 Apple 信任链的前提下继续推进：先确认内核能稳定运行到 `App Log Flush` 之后（例如用 `early_security_init` 之外的路径，或评估 `amfi-only-platform-code` 策略对启动链锁的影响）。

## 证据

| 文件 | 内容 |
| --- | --- |
| `reports/xnu-first-entry-trial/2026-10-24/screen-01.jpg` | 原始照片，SHA256 86b7d30044d5fcd086d2ad96a71c43ed21e97358e28098d706aaa733f7774790 |
| `reports/xnu-first-entry-trial/2026-10-24/crop-diag.png` | DarwinBoot 交接诊断区放大 |
| `reports/xnu-first-entry-trial/2026-10-24/crop-xnu.png` | XNU 自身输出区放大 |
| `reports/xnu-first-entry-trial/2026-10-24/crop-menu.png` | 菜单区放大 |
| `reports/xnu-first-entry-trial/2026-10-24/preflight.json` | 启动前基线（nuwa/kalama/完成1/槽_a/三分区 SHA） |
| `reports/xnu-first-entry-trial/2026-10-24/launch.json` | 启动记录，fastboot ACK=0，235 秒时 adb 重新出现 |
| `reports/xnu-first-entry-trial/2026-10-24/postcondition.json` | 恢复闭环，三分区 SHA 未变 |
| `reports/xnu-first-entry/package-01.json` | 启动包：镜像 `aa2dfb5d…`、内核 `1aeebf13…`、ADT `e7a03577…` |
