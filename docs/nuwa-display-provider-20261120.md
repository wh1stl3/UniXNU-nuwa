# nuwa GopFramebuffer 板级 provider（2026-11-20）

状态：**self-checked（主机侧、未独立复核）**；本文件所有结论都来自本地源码与产物，设备侧零观察。

## 0. 结论

`package/NuwaLegacyDisplay.cpp` 是 nuwa 自己的 Legacy 显示 provider，已经把基座
`drivers/GopFramebuffer@e47c1b8` 在板级这一侧需要的生命周期、失败码顺序和 CPU 拷贝策略补齐；
**但当前不构建**：defconfig 没开、两个 hook 补丁没进设备 series、ABI 头刚生成而绑定缺 9 个胶水符号、
没有设备侧 builder 把 `libNativeLegacyDisplay.late.a` 拼出来。`board.toml` 里加
`GopFramebuffer` 只是选中组件（该组件 `build = []`），不产出任何归档。

## 1. provider 提供什么

| 项 | 内容 |
| --- | --- |
| `native_legacy_display_probe()` | 早期 probe：`OSMetaClass::preModLoad` → `__GLOBAL__sub_I_NativeLegacyDisplay.cpp` → `postModLoad` → 校验 `PE_current_console()` → `native_legacy_display_allocate()` → `init()`。门控 `offline-legacy-register=1`，与驱动的 `registerService()` 门控同一个 boot arg。 |
| `native_legacy_display_late_probe()` | 晚 probe：等 `IOCoreSurfaceRoot`（5 s）→ 建固件 GOP 范围的 `IOPlatformDevice` nub → `/arm-io` 下 `device_type="display-subsystem"` → `attach/probe/start/registerService`。 |
| `native_legacy_prepare_scanout()` | 驱动 `kickOnce()` 唯一的 console-release 点（`NativeLegacyDisplay.cpp:592/626/669/687`），桥接到内核 `boot_progress_prepare_scanout()`（r34 `BootProgress.c:983`、r35 `:1025`）。中断上下文或关中断时返回 false，`kickOnce()` 丢帧而不是猜一个 true。 |
| `native_legacy_gpu_offer()` | 恒 `false`：拒绝 GPU hand-off 不等于宣称完成拷贝，渲染仍走 CPU 路径。 |
| observation / guard | 其余 `native_legacy_*_observed` 为空实现；`native_legacy_backend_guard()` 对未限定后端槽直接 panic。 |
| 不定义 | 7 个 IOSurface 字段读取、`native_legacy_set_refresh_properties()`、`native_legacy_vsync_notify()` 属 ABI 派生入口，留给 builder；`native_legacy_<counter>` 数据符号仍由 `package/boot-progress-r13/nuwa_boot_progress_stubs.c` 以绝对 0 拥有，避免重复符号。 |

失败码 `refused stage=N reason=M` 与 enuma 的 provider 同序：1 早期建对象、2 initialized、
3 进入晚 probe、4 已注册。

## 2. 形状来源与“零 enuma 数值”

形状参照 enuma 的 BSD-2-Clause-Patent 文件
`out/enuma-gop-legacy-20261114-r2/package/EnumaLegacyDisplay.cpp`：同样的 probe/late-probe 拆分、
同样的失败码顺序、同样在固件 GOP 范围上建 `IOPlatformDevice` nub。nuwa 侧所有板级数值都来自
`PE_current_console()` 运行时读数和本镜像：没有从另一块板复制 frame 地址、几何或 display class。
reviewer 已判定该形状复用不违反“nuwa 与 enuma 资产不跨用”。

## 3. 为什么当前不构建（reviewer 缺件清单）

1. `configs/nuwa_defconfig` 没有 `CONFIG_XNU_NATIVE_LEGACY_DISPLAY=y`；两个 hook 补丁
   （`offline-component-load-probes.patch`、`offline-legacy-start.patch`）只在基座
   `profiles/arch/arm64/patches/xnu/series`，nuwa 的 `patch_series` 只有 `device:` 一个源。
2. `package/OriginalLegacyFramebufferABI.h` 与 `package/original-bindings.S` 已由本轮的
   `scripts/derive-nuwa-display-abi.py` 生成，但 `original-bindings.S` 只覆盖 7 个 Legacy 入口；
   驱动还需要的 9 个胶水符号仍未派生：
   `native_legacy_surface_{descriptor,width,height,stride,allocation,format,planes}`、
   `native_legacy_set_refresh_properties`、`native_legacy_vsync_notify`。
3. 没有设备侧 builder（`build-nuwa-legacy-display.py`）：需要生成头/绑定、把
   `NativeLegacyDisplay.o` + `NativeGOPPresenter.o` 去 `__mod_init_func` 并全局化
   `__GLOBAL__sub_I_*`、再与 provider 和 `original-bindings.o` 打成
   `build/native-legacy-display/libNativeLegacyDisplay.late.a`。
4. `board.toml [kernel] archives` 还没有这条归档；`[components] include` 里的
   `GopFramebuffer` 因 `build_stage = "embedded"`、`build = []` 不产出归档。
5. 两个 hook 补丁对 8796 工作树可打但 `bsd_init.c` 带 fuzz 1；是否原样引用还是落成本地
   `8796-` 移植版仍需 reviewer 决定。

## 4. 复核方式

- 源码：`package/NuwaLegacyDisplay.cpp` 与基座 `e47c1b8` 的 `NativeLegacyDisplay.cpp` 对照；
  `native_legacy_prepare_scanout()` 的四个调用点已逐一核对行号。
- ABI 头/绑定的复算：见 `docs/nuwa-display-abi-20261120.md` 的生成器命令。
- 本文件没有构建、没有上机；`GopFramebuffer` 仍为 `deferred`，交互目标未达成。
