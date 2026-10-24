# STATUS

> **iOS 16 内核已在 nuwa 上实际执行（2026-10-24 19:2x）**：DarwinBoot 打印 `Exiting boot services`，屏幕出现绿色横条，XNU 自身输出 `AppleARMPlatform: IODTNVRAM from …` / `SecurityLock::LockType: SOFTWARE_LOCK` / `LockCapsuleInterface` / `App Log Flush : 0 ms`，约 235 秒后设备自动重启回 Android。**iOS 未启动**；恢复闭环完成，三分区 SHA 未变。记录：[首次内核进入](operations/2026-10-24-xnu-first-entry.md)。
>
> 早于本轮：6b3e5bfd 单次实机文件校验通过（18:09:48），照片 PASS exact length, EOF and SHA256。

## 本轮（2026-10-24 19:2x，实机）：首个内核进入试验

内核候选 `1aeebf13`（带 `early_security_initializers` 的分析预链接）经 `fastboot boot` 临时启动，未 flash。确切的屏幕读数（`reports/xnu-first-entry-trial/2026-10-24/crop-*.png`）：

- `kernel va 0xfffffff003DC8000  pa 0x8C01C8000` —— 内核物理基址落在 D-001 选定的主 bank 内。
- `args pa 0x4C408000  window 0x40000000 bytes` —— **ADT 的 1 GiB 窗口请求被采用且分配成功**，blocker 3 的"固件能否给出连续窗口"得到肯定答案。
- `TCR_EL1 0x28003518` / `ID_AA64MMFR0_EL1 (PARange 2, 4 KiB granule supported)` —— 4 KiB granule，与 D-003 一致。
- `CurrentEL 1` —— 交接时在 EL1，满足 `DarwinBoot.c:508` 的检查。
- 菜单只渲染一个 `xnu` 条目并高亮，`in 1s` 说明走倒计时自动启动，全程无需按键。

失败点判断（置信中高）：内核在 **Apple 启动链安全锁**阶段终止 —— 最后可见输出是 `SecurityLock::LockType: SOFTWARE_LOCK, Module: 42B57F0A-13F2-4821-8A23-55B3F714B940, Function: LockCapsuleInterface`，随后 `App Log Flush : 0 ms` 之后再无输出。这类校验需要 SEP/硬件密钥/Apple 信任链。**反证空白**：这些字面串在 XNU 8796 源码树（含全部二进制 blob）、UniXNU 基座全部源码与补丁、donor kernelcache、native 内核与预链接产物里都不存在，来源未定位；主机无 9008 串口，拿不到 panic 串志。

恢复：设备自动重启回 Android，无需人工按键；`postcondition.json` 确认 nuwa/kalama/完成1/槽_a 且三分区 SHA 与试前一致。

## 本轮之前（2026-10-24 晚，离线）：ADT 生成器落地 + board 受审字段获批

设备仓此前缺 `make-nuwa-adt.py`，`[payload.adt] tool` 一直是 TODO，OS 入口 blocker 3（真实 nuwa ADT 未提供）无从推进。本轮补齐并拿到批准：

- `scripts/make-nuwa-adt.py` —— 按基座契约生成 `kernel.macho.adt`，补上旧路线实现缺的 `--gpu-addon`/`--text-fixup`/`--persistent-data`（`payload.py:149-170` 会传）。
- `scripts/check-nuwa-adt.py` —— 独立有界解码，不复用生成器编码器。board 配置 21 节点/31 检查、带 sidecar 21 节点/34 检查，**0 失败**。
- `scripts/audit-nuwa-adt-inputs.py` —— 生成器常量对回实机 FDT，14 项对照 **10 项精确相等、0 项不符**。
- `scripts/test-nuwa-adt.py` —— 正负例 **10 用例全部符合预期**：真生成器产物必须过；缺 `/options`、双 ramdisk 占位符、窗口越界三类违约树必须被拒。
- `scripts/check-nuwa-adt-board.py` —— 按 `payload.py:149-170` 从 board.toml 重放参数组装（基座因 `example = true` 跑不起来，`config.py:103`）。

证据 `reports/adt-nuwa/2026-10-24/{min,board,board-with-sidecars,inputs,test}.json`，输入 `out/live-nuwa-dt/android-dt-after-r011/android-live.dtb`（4815 节点）。记录：[ADT](operations/2026-10-24-nuwa-adt.md)。

**R-012 已批准 A**：用户 18:40 批准，只写两个受审字段 `[payload] dram_size = "0x240000000"`、`[payload.adt] owned_memory_size = "0x40000000"`。`example = true`、其余 TODO、所有 `_verified` 未动。

板级值全部有实机依据：timebase 19200000、GIC `0x17100000/0x10000`+`0x17180000/0x200000`、stride `0x40000`、psci smc、8 核 Affinity1 `0x0..0x700`、ufshc `0x1d84000/0x3000`、DRAM base `0x8c0000000`。`/memory` 9 条合并成 8 段，最大段跨度 `0x240000000`，与 D-001 的 9216 MiB 独立吻合。

三处判断留档：① 根 `compatible` 采用实机值（`ArmDTPlatform::configure()` 不匹配该属性，`ArmDTPlatform.cpp:123-142`）；② iomem 的 System RAM 比 FDT 描述只少最后一个 4 KiB 页（`0x1000`），此前"少 55 MiB"的印象是取整错误；③ 修正旧实现强制 `--unique-chip-id`/`--chip-id` 成对的契约不兼容 —— 基座独立传参，board 的 `chip_id` 仍是 TODO，成对校验会让 payload exit 2。

## 本轮之前（2026-10-24 深夜，离线）：早期安全初始化器通路打通

blocker 1 的"not configured"部分已解，qualification 仍缺。关键发现：

- **AMFI 没有 kmod_start。** 228 个 kext 的 start 全是跳转桩（读 `__DATA/__common` 全局槽），AMFI/IONetworkingFamily/AppleARMPlatform 的槽静态为 **0**，corecrypto 的槽是真实函数 —— 空槽即"无 start"。
- **三个 `__mod_init_func` 只做 `OSMetaClass` 静态注册**，与策略注册无关。
- **初始化由 `[kernel.prelink] early_security_init` 驱动**：`emit_prelink.py:138-156` 要求 native 导出 `_native_prelink_security_init_version == 1`；bf14e530 **有且为 1**（`0xfffffff007021760`）。
- **配置后 emit 全部前置检查通过**，记录 `0xfffffff004703c54`（= 原 VA `0x5703c54` + slide）。根因是 `scripts/emit-current-prelink-analysis.py:18,43` 硬编码空映射，这张表从未配置过。
- **注册调用 ABI 静态核对通过**：三参数签名与 `mac_policy.h:6225` 一致，conf 8 个字段偏移全对，`mpc_ops`@+0x20=`0x6cb6e28`，策略名 `AMFI` / `Apple Mobile File Integrity` / label `amfi`。
- 新候选 `1aeebf13` 与 `eb66542c` 同长度，408983 字节差异**全在 `__PRELINK_INFO`**，三个可执行段**零差异**。

证据 `reports/native-prelink-merged/{amfi-callgraph,early-security-init,earlysec-diff,amfi-register-call}.json`。记录：[早期安全初始化器](operations/2026-10-24-early-security-init.md)。

**方法论教训（已写入脚本注释）**：全段一次性 `capstone.disasm` 会在首个无法解码字节处静默停止，本轮首轮扫描因此得出"注册函数无人调用"的错误结论；改为 `array` 按位模式逐字检查后才正确。

## OS 入口四个 blocker（状态更新）

① 早期安全初始化器 —— 静态部分（身份、配置通路、调用 ABI、策略声明）已清空，运行时已有实机证据：内核执行后未观察到 AMFI 相关输出。② donor/native 完整 C++ 与结构 ABI —— 未解。③ 真实 ADT 与运行时窗口 —— **生成器、板值、1 GiB 窗口分配三项已验证**。④ 大负载装载 —— 读取已通过，装载路径本次由 DarwinBoot 实际完成。

分析内核 `1aeebf13` / `eb66542c` 的 `loadable` 仍为 `false`（人工资格化标志），但**实机已证明其可被加载并跳转**。

## 下一步

1. 复现时把观察窗口延到 600 秒，请用户把镜头对准屏幕直到重启，拍下重启前最后画面；当前照片停在 `App Log Flush`，看不到退出口。
2. 若能接手机 UART/9008 串口，串志是定位退出口最直接手段。
3. 评估 `amfi-only-platform-code` 与启动链锁的关系：确认是否能在不依赖 Apple 硬件信任链的前提下让内核继续往前走。

board 剩余 TODO：`[ipsw]` url/chip_id/board_id/sha256、`[payload]` volume/size_mib/kernel_args、`[kernel]` defconfig/archives/prelink、`[firmware]`、`[bootimg.image]`。

任何新包仍需离线验收、新鲜录像与恢复门、启动前即时通知，结束恢复 Android 完成 1 并核对三分区。原 Heap/HOB 保护、认证策略与所有 `_verified` 保持原状。[交接](operations/2026-10-23-mainline-handoff.md)。
