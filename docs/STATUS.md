# STATUS

> **iOS 16 内核已在 nuwa 上实际执行（2026-10-24 19:2x）**：DarwinBoot 打印 `Exiting boot services`，屏幕出现绿色横条，XNU 自身输出 `AppleARMPlatform: IODTNVRAM from …` / `SecurityLock::LockType: SOFTWARE_LOCK` / `LockCapsuleInterface` / `App Log Flush : 0 ms`，设备自动重启回 Android。**iOS 未启动**；恢复闭环完成，三分区 SHA 未变。
>
> **本轮（20:1x）用用户拍摄的完整录像把"退出口"这个唯一空缺关闭了**：内核在 `App Log Flush` 之后**静默退出** —— 屏幕直接黑掉 19 秒，无 panic 文本、无 reboot 提示，167 秒回到 Android 桌面。记录：[录像取证](operations/2026-10-24-first-entry-video-forensics.md)。

## 本轮（2026-10-24 20:1x，实机录像取证）：退出口确认 = 静默退出

用户拍摄了完整启动录像（2 分 50.43 秒，HEVC 59.97 fps），本地按 1 fps 抽 170 帧做像素统计（新增 `scripts/analyze-first-entry-video.py`），重建了从 UEFI 内存图快照到 Android 桌面的完整时间线。

### 关闭的空缺

**`App Log Flush : 0 ms` 之后发生了什么 —— 答案是"什么都没发生"。**

| 秒段 | 状态 | 内容 |
|---|---|---|
| 19–32 | console-text | UEFI 内存图快照日志 `[NUWA-BOOT-AUDIT]` |
| 33–46 | dark | 屏幕熄灭（UEFI 切图形模式前） |
| 47–56 | console-text | DarwinBoot 逐个加载 kext，每行 `leave status=Success` |
| 57–117 | console-text | UniXNU 图形菜单 + 倒计时自动启动（21 s → 1 s） |
| 118–123 | console-text + 绿条 | DarwinBoot 交接诊断 + 内核输出 |
| **124–142** | **dark（19 秒）** | **彻底黑屏，无任何文字** |
| 143–166 | — | 小米开机动画与锁屏 |
| 167–170 | — | Android 桌面（时钟 19:31） |

屏幕显示区 `mean_luma` 从 86.3 掉到 48.6、白字占比从 10.24% 掉到 0.09%，**没有渐暗、没有花屏、没有滚动**。内核没有打印任何 panic 文本就关掉了显示输出。

### 两处必须更正的上一轮记录

1. **"绿条持续约 235 秒"是错的。** 录像量化显示绿条只存在于第 118–123 秒，**共 6 秒**。绿条只是 ExitBootServices 的瞬时标记（DarwinBoot 自己打印 "A green bar across the top means the kernel entry code ran"），不代表内核存活时长。上一轮的 235 秒更可能是从 fastboot boot 下发到设备重启的总时长。
2. **`Module:` 的 UUID 首位判读有误。** 上一轮读作 `42B57F0A-…`，录像清晰读出 **`42857F0A-13F2-4821-8A23-53D3F714B…`**（右端被裁切）。

### 两块新证据

**① UEFI 内存图日志**（此前从未记录到）。前缀 `[NUWA-BOOT-AUDIT]`，源码 `uefi-nuwa/Platforms/Xiaomi/nuwaPkg/Drivers/NuwaBootAuditDxe/NuwaBootAuditDxe.c`：

```
summary descriptors=129 conventional=16 merged=16 total=0x2850
largest base=0x8C0000000 bytes=0x240000000
snapshot only; no window allocated or reserved
```

`0x240000000` 与 D-001 选定的 DRAM 主 bank、R-012 批准的 `dram_size` 完全吻合 —— **UEFI 侧内存图与实机 FDT 推导独立互证**。`merged=16` 表示 129 个描述符合并成 16 个 conventional 段后无碎片。

**② kext 装载全部成功。** DarwinBoot 逐个打印 `[Debug] enter` / `[Debug] leave status=Success`，配对全部成功返回。**装载路径本身没有失败点**，这一空白被填上。

### Mu-Silicium boot splash 在 nuwa 屏幕上

第 43 秒起，nuwa 屏幕中下部出现 "14 / Si / 28.085 / Project Silicon" 图案，第 60 秒被 UniXNU logo 覆盖。这是 **Mu-Silicium 固件画在 nuwa 屏幕上的 boot splash**，不是第二台设备，也不是机身印刷。

依据：① 图案逐元素等同于 `uefi-nuwa/Silicon/Silicium/SiliciumPkg/Include/Resources/BootLogo.bmp`（300×300 调色板图），而 `uefi-nuwa` 就是 **Project-Silicium/Mu-Silicium** 的 fork（`uefi-nuwa/docs/nuwa-unixnu.md:3` 记录 baseline `6c67550`）；② 该区域在第 36–42 秒高亮像素为 0，**第 43 秒随屏幕点亮突然出现**（2444 个亮像素）——印在机壳上的图案不可能如此；③ 第 50–110 秒持续存在，第 120/123 秒随内核输出进一步增亮。

全程只有 nuwa 一台设备。

## 本轮之前（2026-10-24 19:2x，实机）：首个内核进入试验

内核候选 `1aeebf13`（带 `early_security_initializers` 的分析预链接）经 `fastboot boot` 临时启动，未 flash：

- `kernel va 0xfffffff003DC8000  pa 0x8C01C8000` —— 内核物理基址落在 D-001 选定的主 bank 内。
- `args pa 0x4C408000  window 0x40000000 bytes` —— **ADT 的 1 GiB 窗口请求被采用且分配成功**，blocker 3 得肯定答案。
- `TCR_EL1 0x28003518` / `ID_AA64MMFR0_EL1 (PARange 2, 4 KiB granule supported)` —— 4 KiB granule，与 D-003 一致。
- `CurrentEL 1` —— 交接时在 EL1，满足 `DarwinBoot.c:508` 的检查。
- 菜单只渲染一个 `xnu` 条目并高亮，`in 1s` 说明走倒计时自动启动，全程无需按键（电源键无 Enter 分支，`Menu.c:219-236`）。

失败点判断（置信中高）：内核在 **Apple 启动链安全锁**阶段终止 —— 最后可见输出是 `SecurityLock::LockType: SOFTWARE_LOCK` / `LockCapsuleInterface` / `[ML] dump table info not found` / `App Log Flush : 0 ms`。**反证空白**：这些字面串在 XNU 8796 源码树（含全部二进制 blob）、UniXNU 基座全部源码与补丁、donor kernelcache、native 内核与预链接产物里都不存在，来源未定位；主机无 9008 串口，拿不到 panic 串志。

恢复：设备自动重启回 Android，无需人工按键；`postcondition.json` 确认 nuwa/kalama/完成1/槽_a 且三分区 SHA 与试前一致。

## 本轮之前（2026-10-24 晚，离线）：ADT 生成器落地 + board 受审字段获批

- `scripts/make-nuwa-adt.py` —— 按基座契约生成 `kernel.macho.adt`，补上旧路线实现缺的 `--gpu-addon`/`--text-fixup`/`--persistent-data`。
- `scripts/check-nuwa-adt.py` —— 独立有界解码。board 配置 21 节点/31 检查、带 sidecar 21 节点/34 检查，**0 失败**。
- `scripts/audit-nuwa-adt-inputs.py` —— 生成器常量对回实机 FDT，14 项对照 **10 项精确相等、0 项不符**。
- `scripts/test-nuwa-adt.py` —— 正负例 **10 用例全部符合预期**。
- `scripts/check-nuwa-adt-board.py` —— 按 `payload.py:149-170` 从 board.toml 重放参数组装。

**R-012 已批准 A**：`[payload] dram_size = "0x240000000"`、`[payload.adt] owned_memory_size = "0x40000000"`。`example = true`、其余 TODO、所有 `_verified` 未动。

## 本轮之前（2026-10-24 深夜，离线）：早期安全初始化器通路打通

- **AMFI 没有 kmod_start。** 228 个 kext 的 start 全是跳转桩，AMFI/IONetworkingFamily/AppleARMPlatform 的槽静态为 **0**，corecrypto 的槽是真实函数。
- 三个 `__mod_init_func` 只做 `OSMetaClass` 静态注册，与策略注册无关。
- 初始化由 `[kernel.prelink] early_security_init` 驱动；native bf14e530 导出 `_native_prelink_security_init_version=1`，配置后 emit 全部前置检查通过。
- 注册调用 ABI 静态核对通过（三参数签名、conf 8 字段偏移、`mpc_ops`@+0x20、策略名 `AMFI`）。

## OS 入口四个 blocker（状态更新）

① 早期安全初始化器 —— 静态部分已清空，运行时已有实机证据（内核执行后未观察到 AMFI 相关输出）。② donor/native 完整 C++ 与结构 ABI —— 未解。③ 真实 ADT 与运行时窗口 —— **生成器、板值、1 GiB 窗口分配、UEFI 内存图独立互证四项已验证**。④ 大负载装载 —— 读取已通过，装载路径本次由 DarwinBoot 实际完成，且本次录像证明 **kext 逐个 `leave status=Success`**。

分析内核 `1aeebf13` / `eb66542c` 的 `loadable` 仍为 `false`（人工资格化标志），但**实机已证明其可被加载并跳转**。

## 本轮追加（2026-10-24 20:1x，实机 fastboot 取证）

对上一轮"下一步 1"做了实测，结论已写死：

- 小米 bootloader **不导出** reboot-reason 类变量 —— `fastboot getvar all` 共 296 行，除分区表外仅 40 余项，无重启原因。
- `fetch` 不被支持（`Device does not support fetch command`），无法只读导出 `uefivarstore`（0x80000）。
- **新发现：`slot-retry-count:a:6`**，`slot-successful:a:yes` / `slot-unbootable:a:no`。槽位 a 已累计 6 次重试计数，与内核启动失败后反复重启回 bootloader 吻合 —— 这是目前唯一能在重启后读到的、与本次失败直接相关的持久化痕迹。
- 另有 `has-slot:system:no` / `current-slot:a` / `kernel:uefi`，确认引导链是 UEFI。

设备已 `fastboot reboot` 送回 Android，`sys.boot_completed=1`，恢复闭环完成。证据 `reports/xnu-first-entry-video/2026-10-24/fastboot-varall.txt`。

## 下一步

1. **在 UEFI 侧主动落盘内核交接状态。** 屏幕路径已走到尽头（内核不打印），fastboot 侧也没有重启原因变量，而设备是 user build（`adb root` 被拒、`su` 不可用、`/sys/fs/pstore` 与 `/proc/cmdline` 均 Permission denied），**`scripts/audit-live-uefi-variables.py` 依赖 `su -c`，当前跑不通**。可行路径是在 DarwinBoot 交接时把状态写进一个 Android 侧可读分区。
2. **评估 `amfi-only-platform-code` 与启动链锁的关系。** 确认是否能在不依赖 Apple 硬件信任链的前提下让内核继续往前走 —— 这属于改变启动语义，需先立 NEED-REVIEW 条目再动手。
3. **跟踪 `slot-retry-count` 增长。** 该计数随失败次数累加，可作为后续试验是否复现同一失败的快速判据。

board 剩余 TODO：`[ipsw]` url/chip_id/board_id/sha256、`[payload]` volume/size_mib/kernel_args、`[kernel]` defconfig/archives/prelink、`[firmware]`、`[bootimg.image]`。

任何新包仍需离线验收、新鲜录像与恢复门、启动前即时通知，结束恢复 Android 完成 1 并核对三分区。原 Heap/HOB 保护、认证策略与所有 `_verified` 保持原状。[交接](operations/2026-10-23-mainline-handoff.md)。
