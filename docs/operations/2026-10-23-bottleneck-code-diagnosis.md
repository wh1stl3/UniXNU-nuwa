# 卡点与代码对照诊断（nuwa / enuma）

2026-10-23 12:28。本报告只做静态代码核对与证据充分性判定，不修改板值、不生成镜像、不操作设备。所有结论按证据三级标注：`代码事实`（可直接指到文件:行号）/ `推断`（有代码依据但未运行验证）/ `未验证`。

固件源码位置：`D:/Code/PortingiOS/nuwa/uefi-nuwa`（HEAD `1ccf760`，分支 `codex/nuwa-factory-heap`）、`D:/Code/PortingiOS/enuma/uefi-enuma`（HEAD `7479da1`）。两仓分别对应各自设备仓 `firmware/` 记录的固定提交。

## 0. 结论摘要

| 仓 | STATUS 当前表述 | 代码侧实际判定 |
| --- | --- | --- |
| nuwa | 已到 UniXNU 菜单，卡在"无系统卷 → NoBootOS"；12:15 复测停在 `platform-hobs` 之后 | 菜单结论成立；**"停在 platform-hobs" 证据不足**，不能作为执行停点。真实卡点在 `NuwaBootMemoryDxe` 的发布契约，且有第二道未被人注意的门 |
| enuma | SimpleFb 首测 75 秒无端点，Dispatcher 计数未校准 | 该实验**在设计上不可判定**：唯一输出通道（framebuffer）的三项参数全为假设值，任何失败都表现为同一现象 |

两仓共享同一个方法论缺陷：**诊断通道依赖被诊断对象**。nuwa 用 framebuffer DebugLib 观察启动，enuma 连 framebuffer 参数本身都是猜的。在这个前提下，"屏幕没有新内容"无法区分"没执行"与"执行了但输出失效"。

## 1. nuwa 卡点一：`platform-hobs status=Success` 是恒定输出，不含诊断信息

`Silicon/Qualcomm/QcomPkg/Library/PlatformPeiLib/PlatformPei.c:126-142` 中 `PlatformPeim()` 的唯一返回路径是 `return EFI_SUCCESS;`（第 141 行），没有任何分支返回错误。因此 `Sec.c:125` 打印的 `platform-hobs status=Success` 在任何情况下都会出现。

更具体地说，`PlatformPeim()` 内部三条真实失败路径全部被吞掉：

1. `CreateFvList()` 第 40-43 行：`AllocateZeroPool` 失败即 `goto exit` 返回 NULL；
2. 同函数第 54-58 行：任一 `Lock->InitLock` 失败即 `goto exit` 返回 NULL；
3. `BuildXblHobs()` 第 111-115 行：`FvListAddr == NULL` 时只是**跳过** BuildGuidDataHob，不返回错误；第 89-94 行 `Info Blk` 定位失败也只打一条 ERROR 后继续。

因此这条 Success 日志的真实含义仅为"`PlatformPeim` 被调用且走到了 return"。它对"XBL HOB 是否真的拿到 Scheduler 接口 / FV 锁是否初始化成功"零信息量。

**建议**：把 `PlatformPeim` 改为把上述三处失败上抛（或至少写入一个 HOB 状态字），否则后续每一轮都会在同一处失去区分力。

## 2. nuwa 卡点二：12:15 与 09:22 的差异，目前不能归因为"停在 SEC"

先确认前提：两次是**同一个包**。`reports/initrd-retest/2026-10-23-noon/launch.json` 的 `candidate_sha256 = 8e85215011248b3e9462cace9a92133d4d58f33957ea2534fcb487a401e283c0`，与 STATUS 记录的"唯一 v4 临时包"一致；`authorization` 仍是 R-011 A。

代码上，`Sec.c:125` 之后到 `Sec.c:142`（`before-fv-decompress`）之间只有两条语句：

- 第 135 行 `BuildGuidDataHob (&gSiliciumEntryArgHobGuid, &EntryArg, sizeof (EntryArg))`
- 第 139 行 `ProcessLibraryConstructorList ()`

这段路径极短，且 `BuildGuidDataHob` 只向 HOB 列表追加一个 16 字节描述符（`SecHeap`/`DXE Heap` 空间充足，见 MemoryMapLib 第 32 行 209.75 MiB）。从代码看，这里不存在"能稳定挂住 30 秒以上"的工作量。`ProcessLibraryConstructorList` 是 PrePi 库构造函数，也不含耗时等待。

再看证据强度。`launch.json` 的 `observations` 共 15 条，覆盖 `04:15:25.859` → `04:15:55.354`，即**启动后仅 29.5 秒**；`ended_at` 为 `04:15:57.438`，而恢复流程直到 `04:17:41.331` 才开始。也就是说自动观察在 30 秒处就结束了，之后约 100 秒的窗口没有结构化记录。`screen-observation.json` 的 `photo` 字段只有路径/字节/SHA，**没有拍摄时间戳**，该文件自身的 `limitation` 也写明"Last visible line does not uniquely identify the stopped function"。

因此当前存在三个同样成立、尚未区分开的假设：

- **H1**：DXE 尚未跑完（解压 FV + DXECore 初始化 + 30 余驱动调度，在 30 秒内未完成），照片拍早了；
- **H2**：DXE 起来了，但显示被 DXE 侧重绘/接管，SEC 阶段文本被覆盖，用户看到的是"旧画面残留"；
- **H3**：真的卡在 `Sec.c:135`–`139` 之间（当前代码上无合理解释，除非 HOB 空间异常）。

H1 与 H2 都会产生"屏幕停在 platform-hobs"这一完全相同的观察，而 09:22 那次能看到 BDS 菜单说明 H1/H2 都可以自然解释"有时能看到、有时看不到"。**在补上有时间轴的录像之前，不应把本次记为"停在 SEC"。**

**建议**：下轮复测必须录像而非单张照片，并在报告里按"启动后 N 秒"标注关键帧。仅此一项不改任何代码即可消除歧义。

## 3. nuwa 卡点三：系统卷 —— 512 字节整扇区只是第一道门，不是根因

`Platforms/Xiaomi/nuwaPkg/Drivers/NuwaBootMemoryDxe/NuwaBootMemoryDxe.c:163-166`：

```c
if ((End <= Start) || (((End - Start) % RAM_BLOCK_SIZE) != 0)) {
  DEBUG ((DEBUG_ERROR, "SHENGMEM: initrd 0x%lx-0x%lx is not a whole number of sectors\n", Start, End));
  return;
}
```

`RAM_BLOCK_SIZE` 为 512（第 35 行）。STATUS 记录的 Android initrd 长度 33,870,292 字节：33,870,292 % 512 = **468**，确实不满足，会在第 165 行直接返回、不安装 BlockIo。

但必须指出：**即使放宽这个检查，也到不了 NoBootOS 之外的结果**。该驱动对外只发布一个 512 字节块粒度的只读 `EFI_BLOCK_IO_PROTOCOL`（第 179-187 行 `InstallMultipleProtocolInterfaces`，只挂 DevicePath + BlockIo）。BlockIo 之上没有文件系统。UEFI 的 `\EFI\BOOT\BOOTAA64.EFI` 发现依赖 `SimpleFileSystem`，而那需要 FAT 驱动能解析这块设备——Android GKI 的 initrd 是 cpio/gzip 载荷，不是 FAT32 卷。

所以把 initrd 当"磁盘"发布这条路，天生产不出系统卷。**正确的方向是让 initrd 的内容本身是一个 FAT32 卷**，即已有离线产物的方向（`out` 下 64 MiB FAT32 探针，SHA `bc0b3eae…`）：ABL 把它当 initrd 拼接 → `/chosen` 写入 start/end → 本驱动发布 BlockIo → FatDxe 挂载 → 找到 `unixnu.toml`。这条链的每一环都还需要实机证据，但至少在语义上自洽。

**建议**：不要去放宽 512 字节检查（那是掩盖问题，且会让 ABL 的扇区语义与内核读取不一致）；改为在 FAT32 探针方向上补齐"ABL 拼接 → /chosen 范围 → 整扇区"三段证据。

## 4. nuwa 卡点四：发布链上的三种失败全部静默

`NuwaBootMemoryDxe.c:201-211` 的三个出口都是 `return EFI_SUCCESS;`：

| 行 | 条件 | 日志 |
| --- | --- | --- |
| 203 | 无 `gSiliciumEntryArgHobGuid` HOB | `SHENGMEM: no entry argument HOB` |
| 209 | x0 为 0 / 未对齐 / FDT header 非法 | `SHENGMEM: x0 0x%lx is not a device tree` |
| 164 | initrd 范围非整扇区 | `SHENGMEM: initrd ... is not a whole number of sectors` |

三种不同的根因，都以 `EFI_SUCCESS` 结束，仅靠 DEBUG 文本区分。而 DEBUG 输出走的是 framebuffer（`Sec.c:24` 注释明写 "the existing framebuffer DebugLib is the sole output"），一旦进入 DXE 后屏幕被重绘，这些文本就不再可见。**"看不到 SHENGMEM 日志"因此完全不能推出"没有执行到 SHENGMEM"。**

**建议**：把三种失败分别映射为不同的 `EFI_STATUS`（例如 `EFI_NOT_FOUND` / `EFI_INVALID_PARAMETER` / `EFI_BAD_BUFFER_SIZE`），并在驱动加载失败时让 DXE 的启动管理器把错误码带到可观察位置（BDS 菜单项或一个固定的 RtData magic 地址）。这样即使屏幕被覆盖，仍可通过重启后读内存或 BDS 行为反推。

## 5. enuma 卡点：实验在构造上不可判定

`Silicon/Silicium/SiliciumPkg/Drivers/SimpleFbDxe/SimpleFb.c:88-123` 决定 framebuffer 参数的方式是：

```c
LocateMemoryRegionByName ("Display Reserved", &FrameBufferRegion);   // 97
...
*Width      = FixedPcdGet32 (PcdFrameBufferWidth);                   // 107
*Height     = FixedPcdGet32 (PcdFrameBufferHeight);                  // 108
*ColorDepth = FixedPcdGet32 (PcdFrameBufferColorDepth);              // 109
*BaseAddress = FrameBufferRegion.Address;                            // 120
```

对照 `Platforms/Xiaomi/enumaPkg/Library/MemoryMapLib/MemoryMapLib.c` 的表项 `{"Display Reserved", 0x9C000000, 0x2400000, ...}`，即 framebuffer base 被取成保留区的**起点**（偏移 0）。而 `PcdFrameBufferColorDepth|32` 在 `patches/simplefb-diagnostic-selection.patch` 中自带注释：

```
# Diagnostic metadata hypothesis only; Blt is disabled in this mode.
```

三重假设因此成立：
1. **base**：framebuffer 落在 Display Reserved 偏移 0 —— 未验证；
2. **分辨率**：1600×2560 为 PCD 常量，不是从 DPU/DSI 实际配置读回 —— 未验证；
3. **色深**：32 bpp 为显式假设 —— 未验证。

同时该诊断模式按 `patches/simplefb-diagnostic-selection.patch` 移除了 `CPRDxe` 与 `DisplayDxe`。`CPRDxe` 承担时钟/电源域初始化，DPU 在无 CPR 初始化时是否仍有供电与时钟，代码里没有任何保证。也就是说：**写入一块可能未被供电、且地址/格式都靠猜的显存**。

叠加 STATUS 已记录的事实——`ordinal32` 来自旧布局、当前实际 Dispatcher 计数未校准、UART 未接线——本次实验的三种失败模式（未调度 / 写错地址 / 无供电）在观察面上**完全同形**：都是黑屏 + 无端点。

因此"75 秒未回 ADB/fastboot"这一结果，不能用来支持或否决 SimpleFb 方案本身，也不能用来支持或否决 ordinal32 假设。这是一次信息量为零的实机实验，不是一次失败的实验。

**建议**（按收益排序）：

1. 先解决可观测性：UART 接线，或把 `Log Buffer`（表项 `{"Log Buffer", 0x9FFF7000, 0x8000}`）做成复位后可从 Android 侧读回的持久区。在拿到一条不依赖显示器的日志通道之前，任何显示类实验都是不可判定的。
2. 若要继续 SimpleFb，至少保留 `CPRDxe`，只摘 `DisplayDxe`，把变量从三个减到一个（framebuffer 参数）。
3. framebuffer 三项参数应从真实 DPU 初始化结果读回（或至少做"保留区内偏移扫描 + 逐候选地址写纯色"的有界搜索），不要继续沿用偏移 0 假设。

## 6. 两仓的共同根因与优先级

两仓当前都处在"固件能跑、但没有一条独立于显示器的证据通道"的阶段：

- nuwa 稍好：framebuffer 参数已被实机验证可用（09:22 能显示 BDS 菜单文本），所以显示不是盲区；盲区是**时间轴**（单张照片 vs 录像）和**错误码传播**（三处静默 return）。
- enuma 更差：显示本身就是假设，等于用被怀疑的部件去自证。

按"每轮实验应能产出可区分的信息"这一标准，当前优先级应是：

1. **enuma 恢复后先补日志通道**（UART 或持久 Log Buffer），暂停新的显示类诊断候选；
2. **nuwa 下轮复测改为录像**，并把 `PlatformPeim` 的错误上抛、把 `NuwaBootMemoryDxe` 三态返回改成不同 ErrorCode；
3. 两者都不需要改动内存大小/基址或 `_verified`，不触发 AGENTS §3 硬停。

## 7. 建议措施清单

按"每项消除哪一种歧义"排列。全部措施都不修改内存大小/基址字段、不置 `_verified=true`，因此**均不触发 AGENTS §3 四类硬停**。

| 编号 | 措施 | 落点 | 消除的歧义 | 优先级 |
| --- | --- | --- | --- | --- |
| M1 | 复测改录像，按"启动后 N 秒"标注关键帧 | 操作要求，无代码改动 | H1（拍早了）/H2（屏幕被重绘）/H3（真卡住）不再同形 | P0 |
| M2 | `PlatformPeim` 把 `CreateFvList`/`InitLock`/`Info Blk` 三类失败上抛，不再恒返 `EFI_SUCCESS` | `Silicon/Qualcomm/QcomPkg/Library/PlatformPeiLib/PlatformPei.c:126-142` | 消除 `platform-hobs status=Success` 的零信息量 | P0 |
| M3 | 三个静默出口改为不同 `EFI_STATUS`（`EFI_NOT_FOUND`/`EFI_INVALID_PARAMETER`/`EFI_BAD_BUFFER_SIZE`） | `Platforms/Xiaomi/nuwaPkg/Drivers/NuwaBootMemoryDxe/NuwaBootMemoryDxe.c:201-211`、`:163-166` | 区分"无 HOB / x0 非 DT / initrd 非整扇区"三种根因 | P0 |
| M4 | 失败时向固定 RtData 地址写 magic，复位后可从 Android 侧读回 | 同上驱动，配合 `Log Buffer` 或独立 RtData 页 | 屏幕被 DXE 重绘后仍保留证据 | P1 |
| M5 | 系统卷走"initrd 内容本身是 FAT32 卷"路线，不改 512 字节检查 | `out` 下 64 MiB FAT32 探针（SHA `bc0b3eae…`）+ ABL 拼接链 | 避免用放宽检查换取一个仍然挂不上的卷 | P0 |
| M6 | nuwa 补 ABL 拼接 `/chosen` start/end 与整扇区三段证据 | `reports/system-volume-audit/` 已有离线核对 | FAT32 路线的前置条件 | P1 |
| M7 | enuma 先补 UART，或把 `Log Buffer`（`0x9FFF7000`/`0x8000`）做成复位后可读 | `uefi-enuma` 内存表 + 持久化读取脚本 | 拿到不依赖显示器的日志通道 | P0（enuma） |
| M8 | enuma SimpleFb 诊断保留 `CPRDxe`，只摘 `DisplayDxe` | `patches/simplefb-diagnostic-selection.patch` | 变量从三个减到一个 | P1（enuma） |
| M9 | enuma framebuffer 三项参数从 DPU 实际配置读回，或做保留区内有界偏移扫描 | `Silicon/Silicium/SiliciumPkg/Drivers/SimpleFbDxe/SimpleFb.c:88-123` | 去掉 base/分辨率/色深的三重假设 | P2（enuma） |

## 8. 下一轮 nuwa 复测的判定标准

复测时按屏幕出现的**最靠后一条 ENTRY 打点**判定，而不是凭"最后一行"推断停点。判定表如下（打点均在 `Sec.c:87、91、109、111、123、125、142、144、151、153`）：

| 观察到 | 可判定结论 | 不可判定为 |
| --- | --- | --- |
| `C-before-platform` | 进入 SecMain | — |
| `C-after-platform` | `PlatformInitialize()` 返回 | 平台初始化成功（返回值未检查） |
| `before-memory` / `memory status=...` | 已尝试初始化 DXE Heap | 堆大小是否合适 |
| `before-platform-hobs` / `platform-hobs status=Success` | `PlatformPeim` 被调用并返回 | **XBL HOB、FV 锁是否正常（恒为 Success）** |
| `before-fv-decompress` | 已越过 M2 所指的问题段 | FV 解压是否成功 |
| `fv-decompress status=...` | 解压结果已知 | DXE 是否加载 |
| `before-dxe-core` / `dxe-core returned=...` | 已尝试加载 DXECore | DXE 内部是否初始化完成 |
| `SHENGMEM: ...`（驱动日志） | 驱动已调度 | 重复观察（M4 未落地前，屏幕重绘后不可见） |
| UniXNU 菜单 | BDS 已运行 | 系统卷可发现、XNU 可启动 |

判定的硬要求：

1. 必须有时间轴（录像）；单张照片只能证明"某一帧是这样"，不能证明"之后没变化"；
2. 观察窗口不得短于 120 秒（本轮自动轮询在 29.5 秒即结束，是本次结论失效的直接原因）；
3. 恢复动作与观察窗口要分开记录，避免把"恢复开始时刻"误当成"设备已停止变化"。

## 9. 本报告未做的事

- 未修改任何源码、补丁、`board.toml`、`bringup-plan.json` 或验证标记；
- 未生成镜像、未执行任何 fastboot/adb 命令；
- 未对 nuwa 12:15 复测结果做任何 STATUS 级定性（等待有时间轴证据）；
- 未重新计算 donor 指针绑定、NativePrelink 或 ABI 相关结论。
