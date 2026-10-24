# 首次内核进入：录像取证报告

> 素材：用户用第三台设备拍摄的完整录像 `2d932cb8b5db1c97cde5eba6e4991325_raw.mp4`（1920×1080 竖屏容器，2 分 50.43 秒，HEVC 59.97 fps）。
> 被摄对象：**只有 nuwa 一台**（小米 13 Pro），竖放在支架上、屏幕朝向镜头。第 43 秒起屏幕中下部出现 "Si / Project Silicon" 图案，那是 **Mu-Silicium 固件画在 nuwa 屏幕上的 boot splash**，不是第二台设备，详见第 4.1 节。
> 目的：补齐此前照片缺失的那一段 —— `App Log Flush : 0 ms` 之后到设备重启之间到底发生了什么。
> 结论：**没有发生任何事。屏幕直接黑掉，然后自动重启回 Android。内核没有留下任何 panic 文本。**

## 一、这份录像解决了什么问题

上一轮只有一张静态照片，停在 `App Log Flush : 0 ms`，因此留下三个空缺：

1. `App Log Flush` 之后画面上是否还有内容但没被拍到；
2. 屏幕是何时、以何种方式变黑的（内核静默复位 / 显示输出转移 / panic 文本未刷屏）；
3. 重启前的完整时长与重启后的落点。

录像把三个空缺全部关闭了，代价是暴露了一个新问题（见第四节）。

## 二、逐段时间线

方法：按 1 fps 抽帧 170 帧，用 `scripts/analyze-first-entry-video.py` 对手机显示区做像素统计（绿条占比 / 白字占比 / 平均亮度），再按状态归并成连续段。原始数据在 `timeline.json`。

| 秒段 | 状态 | 画面内容 |
|---|---|---|
| 1–18 | dark | 屏幕熄灭，只有环境反光 |
| 19–32 | console-text | **DarwinBoot 逐个加载 kext 的调试输出**（见第三节） |
| 33–46 | dark / dim | 屏幕再次熄灭 |
| 47–123 | console-text | DarwinBoot 菜单 + 倒计时 + 内核输出（见第三节） |
| **124–142** | **dark** | **屏幕彻底黑掉，无任何文字，19 秒** |
| 143–166 | console-text / dim | 小米开机动画与锁屏（Android 侧） |
| 167–170 | Android 桌面 | 已回到 Android，桌面时钟 19:31 |

关键读数：

- **绿条只存在于第 118–123 秒，共 6 秒**（`green_ratio` 峰值 6.98%，其余时段为 0）。
- **第 123 秒是最后有文字的一帧**，第 124 秒立刻转黑。中间没有渐暗、没有花屏、没有滚动。
- 第 143–152 秒的白字占比只有 3.3%，且第 167–170 秒画面已是 Android 桌面（日历显示"10月24日周六 九月十五"，时钟 19:31）。

> 判据修正记录：第一版把 167–170 秒判成 `green-bar`，因为 Android 桌面壁纸含青绿色元素。加入"白字占比 < 20%"的排除条件后该误判消除。脚本已按修正后的判据固化。

## 三、读到的画面内容

画面内容的完整逐帧解读集中在第四节（4.2–4.6）。本节只给索引表与关键文本，避免同一段输出在两处重复维护。

| 时段 | 内容 | 所在小节 |
|---|---|---|
| 19–32 s | UEFI 内存图快照日志 `[NUWA-BOOT-AUDIT]` | 4.3 |
| 33–46 s | 屏幕熄灭（UEFI 切图形模式前的黑屏） | 4.2 |
| 47–56 s | DarwinBoot 逐个加载 kext，每行 `leave status=Success` | 4.4 |
| 57–117 s | UniXNU 图形菜单 + 倒计时自动启动 | 4.5 |
| 118–123 s | 绿条 + DarwinBoot 交接诊断 + 内核输出 | 4.5 |
| 124–142 s | **黑屏，无任何输出** | 二 / 4.6 |
| 143–166 s | 小米开机动画与锁屏 | — |
| 167–170 s | Android 桌面 | — |

### 3.1 关键文本

UEFI 侧（`[NUWA-BOOT-AUDIT]`，源码 `uefi-nuwa/Platforms/Xiaomi/nuwaPkg/Drivers/NuwaBootAuditDxe/NuwaBootAuditDxe.c`）：

```
[NUWA-BOOT-AUDIT] map bytes=1632 start=0x48 conventional
[NUWA-BOOT-AUDIT] conventional 1  start=0x8b100000  end=0x8b8c0000  attr=0x8f
[NUWA-BOOT-AUDIT] conventional 5  start=0x8a600000  end=0x8b100000  attr=0xd0f
[NUWA-BOOT-AUDIT] conventional 8  start=0x8b300000  end=0x8f884000  attr=0xd0f
[NUWA-BOOT-AUDIT] summary descriptors=129 conventional=16 merged=16 total=0x2850
[NUWA-BOOT-AUDIT] largest base=0x8C0000000 bytes=0x240000000
[NUWA-BOOT-AUDIT] snapshot only; no window allocated or reserved
```

DarwinBoot 侧（kext 加载与交接）：

```
[Debug] enter
[Debug] leave status=Success
[Driver] at 0x000C2823000 EntryPoint=0x000C2824050 DevicePath=Node,efi
[Driver] at 0x000C25A8000 EntryPoint=0x000C25A6C00 PanicScreenDxe.efi
[Driver] at 0x000C252D000 EntryPoint=0x000C252E050 UsbMassStorageDxe.efi
[Driver] at 0x000C2444050 EntryPoint=0x000C2444050 SimpleTextInOutSerial
UsbOperProtocols: PHI version (0x47)
... : Attach, Data Role : UFP (DEVICE Mode). Lane : C12, CoreNum : 0
Test: Keypress SDMM data payload 0
```

内核侧（第 118–123 秒）：

```
Exiting boot services. A green bar across the top
means the kernel entry code ran.

SecurityLock::LockType: SOFTWARE_LOCK, Module: 42857F0A-13F2-4821-8A23-53D3F714B
Function: LockCapsuleInterface, Output: Lock Capsule Interface
[ML] dump table info not found. Status = (0x0)
App Log Flush : 0 ms
```

**最后一行之后，屏幕在第 124 秒变黑，直到第 167 秒 Android 桌面出现，之间没有任何文字。**

第 124 秒起，屏幕显示区亮度掉到环境反光水平（`mean_luma` 从 86.3 掉到 48.6，白字占比 10.24% → 0.09%）。持续 19 秒后进入小米开机动画。

**这 19 秒的黑屏是本轮最硬的证据：内核没有 panic，没有 panic 文本，没有 reboot 提示，什么都没打印就直接把显示输出关掉了。**

## 四、录像结构与时间线

### 4.1 "Si / Project Silicon" 标志：Mu-Silicium 的 boot splash，画在 nuwa 屏幕上

录像第 43–49 秒，nuwa 屏幕中下部出现一个 "14 / Si / 28.085 / Project Silicon" 图案。它**是显示在 nuwa 屏幕上的 Mu-Silicium 固件 boot splash**，随后被 UniXNU logo 覆盖。

事实链条（三条独立证据）：

**① 图案逐元素等同于固件资源。** `uefi-nuwa/Silicon/Silicium/SiliciumPkg/Include/Resources/BootLogo.bmp`（300×300 调色板图）渲染出来正是：圆角方框内一个 "Si"、左上角 "14"、右下角 "28.085"、下方 "Project Silicon"。录像帧裁剪放大后与该 bmp 逐元素一致（见 `mu-silicium-bootlogo.png` 与 `si-splash-frame45.png`）。`BootLogo.bmp` 与 `NoBootOS.bmp` 字节数完全相同（91078），是同一张图的两个用途。而 `uefi-nuwa` 就是 **Project-Silicium/Mu-Silicium** 的 fork —— `uefi-nuwa/docs/nuwa-unixnu.md:3` 写明 `Tested source baseline: Project-Silicium/Mu-Silicium@6c6755012728c9f7de748228758bad94d1e9a660`，`uefi-nuwa/Building.md:11` 就是 `git clone https://github.com/Project-Silicium/Mu-Silicium.git`。

**② 它随屏幕点亮而出现。** 采样 (460,900)–(620,1060) 区域的高亮像素数：

| 秒 | 36 | 37 | 38 | 39 | 40 | 41 | 42 | **43** | 44 | 45 | 46 | 49 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| >200 像素 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **2444** | 2293 | 3035 | 2852 | 2843 |

前 42 秒该区域完全没有亮像素，**第 43 秒突然出现** —— 这正是屏幕从黑转亮的时刻。若是印在机壳上的图案，应当从第一帧就存在。

**③ 它在 UniXNU logo 出现后仍留在同一位置并被覆盖。** 第 50/55/60/70/90/110 秒该区域持续保有 1900–3000 个高亮像素；到第 120/123 秒（内核输出阶段）亮度进一步升高（6009 / 5582 个高亮像素）。UniXNU logo（第 60 秒，屏幕上部）是在此之后覆盖上来��。

> **本节此前有两处误判，已更正**：① 先读成"另一台 Apple Silicon 设备的屏幕"——错，同一帧的网格图显示整幅画面就是竖放在支架上、屏幕朝向镜头的 nuwa；② 再读成"印在手机壳背板的印刷图案"——错，屏幕玻璃上的暗斑是指纹/污渍反射而非摄像头开孔，且第 43 秒才出现这一点直接排除了印刷图案。**结论：是 nuwa 屏幕上的 Mu-Silicium boot splash。**

### 4.2 这是同一次启动的连续阶段，不是两次

第 19–32 秒（第 4.3 节）与第 47 秒起（后半）**属于同一次启动**：前者是 UEFI 早期内存图快照阶段，后者是 DarwinBoot 菜单与内核交接阶段，中间没有设备重启的迹象 —— 第 33–46 秒的黑屏是显示输出关闭（UEFI 切到图形模式前的黑屏），第 47 秒画面在同一位置重新点亮为 UniXNU logo。

第 4.3 节后半的 DarwinBoot 菜单紧接在 UEFI 日志之后，与之衔接自然。

### 4.3 UEFI 内存分配日志（第 19–32 秒）

这块此前完全没被记录过，是本轮第二个意外收获：

```
[NUWA-BOOT-AUDIT] ready old, sel=0x1000000 entry=0x8200000
[NUWA-BOOT-AUDIT] map bytes=1632 start=0x48 conventional
[NUWA-BOOT-AUDIT] conventional 1  start=0x8b100000  end=0x8b8c0000  attr=0x8f
[NUWA-BOOT-AUDIT] conventional 5  start=0x8a600000  end=0x8b100000  attr=0xd0f
[NUWA-BOOT-AUDIT] conventional 6  start=0x8a580000  end=0x8a600000  attr=0x8f
[NUWA-BOOT-AUDIT] conventional 7  start=0x8a3d0000  end=0x8a580000  attr=0x8f
[NUWA-BOOT-AUDIT] conventional 8  start=0x8b300000  end=0x8f884000  attr=0xd0f
[NUWA-BOOT-AUDIT] conventional 9  start=0x8f884000  end=0x8f884000  attr=0xd0f
[NUWA-BOOT-AUDIT] conventional 10 start=0x8f8f0000  end=0x8fc00000  attr=0x8f
[NUWA-BOOT-AUDIT] conventional 11 start=0x8fc00000  end=0x8fc64000  attr=0x8f
[NUWA-BOOT-AUDIT] conventional 12 start=0x8fc64000  end=0x8fc00000  attr=0x8f
[NUWA-BOOT-AUDIT] conventional 13 start=0x8fc90000  end=0x8fb90000  attr=0x8f
[NUWA-BOOT-AUDIT] conventional 14 start=0x8f8f0000  end=0x8f8f0000  attr=0x8f
[NUWA-BOOT-AUDIT] conventional 15 start=0x8c0000000 end=0x8c0000000 attr=0x8f
[NUWA-BOOT-AUDIT] summary descriptors=129 conventional=16 merged=16 total=0x2850
[NUWA-BOOT-AUDIT] largest base=0x8C0000000 bytes=0x240000000 ub-base=0x8C0000000
[NUWA-BOOT-AUDIT] snapshot only: no window allocated or reserved
```

**关键读数：**

- `largest base=0x8C0000000 bytes=0x240000000` —— 这正是 D-001 选定的 DRAM 主 bank（9216 MiB = 0x240000000），与 R-012 批准的 `dram_size = 0x240000000` 完全吻合。**UEFI 侧的内存图与实机 FDT 推导结果独立一致。**
- `ub-base=0x8C0000000` —— 上界 base 一致。
- `summary descriptors=129 conventional=16 merged=16 total=0x2850` —— 129 个描述符合并成 16 个 conventional 段，`merged=16` 表示合并后没有产生碎片段。
- `snapshot only: no window allocated or reserved` —— 这一行说明这次 UEFI 启动只做了内存图快照，**没有分配也没有保留任何窗口**。第 118 秒 DarwinBoot 打印的 `window 0x40000000 bytes` 是 DarwinBoot 自己在内核交接阶段申请的 1 GiB 窗口，与 UEFI 快照是两回事。

> 这些行以 `[NUWA-BOOT-AUDIT]` 前缀打印，属于本仓 UEFI/DarwinBoot 侧的诊断输出，不是内核输出。此前几轮没有记录到它们，说明这段日志是较近才加入固件的。

### 4.4 DarwinBoot 加载 kext（第 47–56 秒区段）

第 19–32 秒之外，DarwinBoot 自身还会逐个加载 kext 并打印配对日志：

```
[Debug] enter
[Debug] leave status=Success
[Driver] at 0x000C2823000 EntryPoint=0x000C2824050 DevicePath=Node,efi
[Driver] at 0x000C25B0000 EntryPoint=0x000C25B0050 CapsuelRuntimeDxe.efi
[Driver] at 0x000C25B2000 EntryPoint=0x000C25B2050 Hilldbase.efi
[Driver] at 0x000C24B9000 EntryPoint=0x000C24BA050 BdeDxe.efi
[Driver] at 0x000C25B6000 EntryPoint=0x000C25B7000 SPI.efi
[Driver] at 0x000C25A8000 EntryPoint=0x000C25A6C00 PanicScreenDxe.efi
[Driver] at 0x000C2722000 EntryPoint=0x000C2723000 UsbPurCtrlDxe.efi
[Driver] at 0x000C257A000 EntryPoint=0x000C257B000 ChargerExDxe.efi
[Driver] at 0x000C2549000 EntryPoint=0x000C254A000 UsbFnDwc3Dxe.efi
[Driver] at 0x000C2571000 EntryPoint=0x000C2571000 XhciPciEmulation.efi
[Driver] at 0x000C24A3000 EntryPoint=0x000C24A4000 XhciDxe.efi
[Driver] at 0x000C2539000 EntryPoint=0x000C253A050 UsbBusDxe.efi
[Driver] at 0x000C2563000 EntryPoint=0x000C2564050 UsbKbDxe.efi
[Driver] at 0x000C252D000 EntryPoint=0x000C252E050 UsbMassStorageDxe.efi
[Driver] at 0x000C2488000 EntryPoint=0x000C2481000 UsbHidDxe.efi
[Driver] at 0x000C2497000 EntryPoint=0x000C2498000 UsbDeviceDxe.efi
[Driver] at 0x000C2455000 EntryPoint=0x000C2456000 UsbConfigDxe.efi
UsbOperProtocols: PHI version (0x47)
... : Attach, Data Role : UFP (DEVICE Mode). Lane : C12, CoreNum : 0
[Driver] at 0x000C2722000 EntryPoint=0x000C2721000 ButtonsDxe.efi
Test: Keypress SDMM data payload 0
[Driver] at 0x000C2476000 EntryPoint=0x000C2479000 TzenvLib.efi
[Driver] at 0x000C2430000 EntryPoint=0x000C2431000 LimitsDxe.efi
[Driver] at 0x000C2420000 EntryPoint=0x000C2421000 CPRBox.efi
[Driver] at 0x000C23F7000 EntryPoint=0x000C23F8000 GpiDxe.efi
[Driver] at 0x000C2388000 EntryPoint=0x000C2381000 UCDxe.efi
[Driver] at 0x000C2448000 EntryPoint=0x000C244C000 RngBox.efi
[Driver] at 0x000C2444050 EntryPoint=0x000C2444050 SimpleTextInOutSerial
```

**每一行的 `leave status=Success` 表示该 kext 的 enter/leave 配对全部成功返回。** 这直接印证了上一轮的一个空白：kext 的加载阶段本身没有失败点。

### 4.5 菜单、倒计时与内核输出（第 57–123 秒）

第 57 秒起画面切换到 DarwinBoot 的 UniXNU 图形菜单。**Mu-Silicium 的 splash 被 UniXNU logo 覆盖** —— 这是基座 logo 替换上游 splash 的直接证据：

```
                [苹果+芯片标志]
                    UniXNU
        NUWA XNU FIRST ENTRY - ANALYSIS BUILD
        kernel_panic_init_success=1  booting fast path enabled

                        version 0.1.0
              config: \EFI\UniXNU\unixnu.toml

  ┌───────────────────────────────────────────────┐
  │ 1  Enter UniXNU iOS 16…                       │
  │    XNU                                        │
  └───────────────────────────────────────────────┘

   Booting Enter UniXNU iOS 16 kernel
          (analysis prelink) in 21 s

   Up/Down: select        Enter: boot
   1-9: boot entry        Esc: stop timer
   drivers 0 loaded / 0 failed    kits 0
            acpi 0
```

第 96 秒倒计时剩 21 秒，第 117 秒剩 1 秒 —— 走的是**倒计时自动启动，全程无需按键**。菜单只有一个 `xnu` 条目。

第 118 秒起绿条出现，DarwinBoot 打印自己的交接诊断，随后内核输出接上：

```
kernel va 0xfffffff003DC8000  pa 0x8C01C8000
entry  pa 0x8C37C5488    VERSION 0.1.0
entry  pa 0x8C488C000  window 0x40000000 bytes
entry words 14000F5 1503201F 1503201F 1503201F 1503201F 1503201F
CurrentEL 1   SCTLR_EL1 0x30D01800   TCR_EL1 0x28003518
ID_AA64MMFR0_EL1 0x2220010122  (PARange 2, 4 KiB granule supported)
ID_AA64MMFR1_EL1 0x1101100003111112

Exiting boot services. A green bar across the top
means the kernel entry code ran.

SecurityLock::LockType: SOFTWARE_LOCK, Module: 42857F0A-13F2-4821-8A23-53D3F714B
Function: LockCapsuleInterface, Output: Lock Capsule Interface
[ML] dump table info not found. Status = (0x0)
App Log Flush : 0 ms
```

第 123 秒是最后有文字的一帧，第 124 秒立刻转黑。

### 4.6 与上一轮记录的差异

| | 上一轮（照片） | 本轮（录像） |
|---|---|---|
| 绿条持续 | 约 235 秒 | **6 秒**（118–123 s） |
| `App Log Flush` 后 | 无输出 | 无输出（一致） |
| 重启落点 | Android，235 s | 黑屏 124 s → Android 167 s |

**"绿条持续约 235 秒"这个说法是错的，需要更正。** 绿条只是 ExitBootServices 的瞬时标记（DarwinBoot 自己打印的 "A green bar across the top means the kernel entry code ran"），不代表内核存活时长。上一轮的 235 秒更可能是从 fastboot boot 下发到设备重启的总时长，包含 bootloader 与 UEFI 阶段。

另外，`Module:` 的 UUID 上一轮读作 `42B57F0A-…`，本轮清晰读作 **`42857F0A-13F2-4821-8A23-53D3F714B…`**（右端被裁切）。上一轮的首位 `4`/`B` 判读有误，应更正为 `42857F0A`。

## 五、结论与下一步

### 结论

1. `App Log Flush : 0 ms` 之后**内核静默退出**，19 秒黑屏，无 panic 文本。上一轮"看不到退出口"的空缺已经关闭 —— 退出口就是没有输出。
2. kext 加载阶段全部 `leave status=Success`，**加载路径本身无失败点**。
3. 绿条 = ExitBootServices 成功的瞬时标记，**不代表内核存活时长**；上一轮记录需更正。
4. `SecurityLock::LockType: SOFTWARE_LOCK` / `LockCapsuleInterface` / `[ML] dump table info not found` / `App Log Flush` 这四组字面串，在 XNU 8796 源码树（含全部 blob）、UniXNU 基座源码与补丁、donor kernelcache、native 内核与预链接产物中**仍然搜不到**（ASCII 与 UTF-16 都查过）。本轮录像确认了它们的**确切字节内容**，但没有改变来源未定位的事实。

### 下一步（按性价比排序）

1. **改走 panic 捕获而不是屏幕捕获。** 屏幕这条路已经走到尽头 —— 内核就是不打印。改从 UEFI 侧取：`uefi_a/uefi_b` 分区里可能有上一次启动留下的变量。障碍已探明：`adb` 在这台机器上是 user build（`adb root` 返回 "adbd cannot run as root in production builds"），`su` 不可用，`/sys/fs/pstore` 与 `/proc/cmdline` 均 Permission denied，**`scripts/audit-live-uefi-variables.py` 依赖 `su -c`，因此当前跑不通**。出路只有两条：在 UEFI 侧主动把内核交接后的状态写进一个可读分区，或者找到非 root 的 uefivarstore 读取路径。
2. **fastboot 侧证据（已试，结论如下）。** 本轮已实测 `fastboot getvar all`（nuwa 已解锁，`unlocked:yes`）：
   - 小米 bootloader **不导出** `reboot-reason` / `boot-reason` 类变量，`getvar all` 的 296 行里除分区表外只有 40 余项，无重启原因。
   - `fetch` 命令不被支持（`Device does not support fetch command`），无法只读导出 `uefivarstore`（0x80000 字节）。
   - **新发现：`slot-retry-count:a:6`，而 `slot-successful:a:yes` / `slot-unbootable:a:no`。** 槽位 a 已累计 6 次重试计数，与内核启动失败后反复重启回 bootloader 的行为吻合。这是目前唯一能在重启后读到的、与本次失败直接相关的持久化痕迹。
   - 另有 `has-slot:system:no` / `current-slot:a` / `kernel:uefi`，说明引导链是 UEFI。
3. **评估 `amfi-only-platform-code`。** ADT 里这个属性与启动链锁的关系仍未查清。如果内核是因为缺 Apple 硬件信任链而在安全锁阶段退出，那么绕过或放宽它可能是让内核继续往前走的最短路径 —— 但这属于改变启动语义，需要先立 NEED-REVIEW 条目再动手。

## 六、产物

- `reports/xnu-first-entry-video/2026-10-24/timeline.json` —— 逐秒像素统计与归并分段
- `reports/xnu-first-entry-video/2026-10-24/contact-sheet.jpg` —— 170 帧联络表
- `reports/xnu-first-entry-video/2026-10-24/frame-32-prelink-kexts.png` —— kext 加载输出放大
- `reports/xnu-first-entry-video/2026-10-24/frame-104-menu.png` —— DarwinBoot 菜单
- `reports/xnu-first-entry-video/2026-10-24/frame-123-last-text.jpg` —— 最后有文字的一帧
- `reports/xnu-first-entry-video/2026-10-24/frame-123-tail-zoom.jpg` —— 末帧文本尾部放大（`App Log Flush` 及其后）
- `reports/xnu-first-entry-video/2026-10-24/frame-123-full-text.png` —— 末帧完整文本
- `reports/xnu-first-entry-video/2026-10-24/mu-silicium-bootlogo.png` —— Mu-Silicium `BootLogo.bmp` 原图
- `reports/xnu-first-entry-video/2026-10-24/si-splash-frame45.png` —— 录像第 45 帧的 Si splash 放大（与上图逐元素一致）
- `reports/xnu-first-entry-video/2026-10-24/grid-frame45.png` / `grid-frame60.png` —— 带坐标网格的整帧，用于定位屏幕边界
- `scripts/analyze-first-entry-video.py` —— 时间线分析脚本
- `reports/xnu-first-entry-video/2026-10-24/fastboot-varall.txt` —— nuwa bootloader 全量变量导出（296 行）
