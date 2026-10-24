# 早期安全初始化器：从"未配置"到 emit 接受

2026-10-24 晚。全离线：无手机、USB、固件或设备动作。

## 结论

blocker 1 原文是"Early security initializer identity/call ABI not qualified or configured"。本轮把它拆成两半，**"not configured" 这一半解掉了**，qualification 仍缺。

三条实证：

1. **AMFI 根本没有 kmod_start。** 228 个 kext 的 `_PrelinkKmodInfo.start` 全部指向同一种跳转桩（`adrp`+`add`+`ldr`+`cbz`+`br`），桩从 `__DATA/__common` 的一个全局槽取真实地址。AMFI、IONetworkingFamily、AppleARMPlatform 的槽静态值为 **0**，corecrypto 的槽是真实函数 —— **空槽就是"该 kext 没有 start"**。所以指望通过 kmod_start 进入 AMFI 初始化是错的。
2. **AMFI 的初始化由 `early_security_init` 驱动。** 基座 `emit_prelink.py:138-156` 校验后把地址写进 `early_security_initializers`，并要求 native 内核导出 `_native_prelink_security_init_version == 1`。native bf14e530 **确实导出且值为 1**（`0xfffffff007021760`）。
3. **配置一旦给出，emitter 全部前置检查通过。** 产出 `early_security_initializers = {AMFI: 0xfffffff004703c54}`，正好等于原 VA `0xfffffff005703c54` 加 slide `-0x1000000`。

根因很具体：`scripts/emit-current-prelink-analysis.py:18` 调 `emitter.emit(..., {})` 硬编码传空映射，第 43 行又把 `early_security_initializers` 硬编码成 `{}`。这张表**从来没有被真正配置过**，所以 blocker 一直挂着。

## 方法与一处必须避免的陷阱

本轮最初的全内核交叉引用扫描给出了错误结论（"注册函数无人调用"），原因是把 23 MB 段一次性交给 `capstone.disasm()` —— 它在第一个无法解码的字节处静默停止，后续全部漏掉。**"没找到"于是变成了假的**。

改为：用 `array` 把文件按 4 字节字解析，按位模式直接识别 `b`/`bl`/`adrp`，全段逐字检查，不存在截断；capstone 只用于候选点附近几十字节的寄存器追踪。脚本 `scripts/audit-amfi-callgraph.py` 对每个区段报告检查指令数与覆盖方式，负结果才可信。

同一类错误还有一次：手算 `adrp 0x7a11000 + 0xa60` 时多写一位得到 `0x7a110a60`，导致读到不受段覆盖的地址。所有这类地址现在都由代码相加，不手打。

## 四条证据链

**构造函数。** `__mod_init_func` 三项（`0x6cb5e20/28/30`）分别指向 `0x6fbe08`、`0x70003c`、`0x707998`，三条都只调用 `OSMetaClass::OSMetaClass`（符号 `__ZN11OSMetaClassC2EPKcPKS_j` 及其带 zone 的重载），**没有任何一条调用策略注册**。它们是 C++ 静态对象注册，与 AMFI 初始化无关。

**kmod start。** `start = 0x570b798`，形态是 `ldr x2,[0x7a11a60]; cbz x2,+8; br x2; mov w0,#0; ret`。全内核 38 MB 可执行段中**没有任何指令写入该槽**，槽在 `__DATA/__common`（BSS）里静态为 0。对照 corecrypto 的槽已有真实函数，说明 0 不是读取错误而是"无 start"。

**注册/初始化函数。** `0x5703c54` 是真函数入口（`sub sp,#0xf0` 序言），内部依次：`IOLockAlloc` → 用 `OSCompareAndSwapPtr(0, lock, &0x7a11ad0)` 做 **once-guard** → `lck_grp_alloc_init` → `os_log_create` → `sysctl_register_oid` → `PE_parse_boot_argn` → `PE_i_can_has_debugger` → `IORegistryEntry::fromPath` → 之后是策略 ops 表写入块。两个调用点 `0x5703bd8`（函数 `0x5703bb0`，先 `blr` 一次 `IOService` 虚表 +0x2c0 再按返回值决定）与 `0x5704328`（函数 `0x5704320`）都没有直接调用者 —— 与"由早期安全路径按配置地址调用"一致，而不是模块内部自调用。

**配置前后对比。** 带配置的候选 `1aeebf13`（58335232 B）与不带的 `eb66542c`（同长度）逐字节比较：408983 字节差异**全部落在 `__PRELINK_INFO`**，`__TEXT_EXEC`/`__PLK_TEXT_EXEC`/`__PRELINK_TEXT` **零差异**。插入一个 metadata 键会让序列化后的 plist 整体位移，所以差异字节数看着很大，但代码一个字节没动。

## 注册调用的 ABI 核对

身份确定后再看调用本身。初始化函数在 `0x5703fa4` 调 `_mac_policy_register`，调用现场是：

```
0x5703f5c  adrp x0, 0x6cb7000 / add x0, x0, #0x8a0   ; x0 = 0x6cb78a0  &mac_policy_conf
0x5703f98  adrp x1, 0x6cb6000 / add x1, x1, #0xe1c   ; x1 = 0x6cb6e1c  &policy handle
0x5703fa0  mov  x2, #0
0x5703fa4  bl   _mac_policy_register
0x5703fa8  cbnz w0, <error>
```

三参数形式。对照固定源码 `security/mac_policy.h:6225`：`int mac_policy_register(struct mac_policy_conf *mpc, mac_policy_handle_t *handlep, void *xd)` —— **参数个数与顺序一致**，返回值按 `int` 判非零。native bf14e530 也确实导出 `mac_policy_register`（`0xfffffff00790a66c`）。

结构布局逐字段核对，`struct mac_policy_conf`（`security/mac_policy.h:6205-6216`，arm64 80 字节）的 8 个字段在调用前全部写入，偏移逐个对上：

| 偏移 | 字段 | 写入 |
| --- | --- | --- |
| `0x00` | `mpc_name` | `stp` 前半 |
| `0x08` | `mpc_fullname` | `stp` 后半 |
| `0x10` | `mpc_labelnames` | `str` |
| `0x18` | `mpc_labelname_count` | `str w20`（=1） |
| `0x20` | `mpc_ops` | `str x8`（`0x6cb6e28`） |
| `0x28` | `mpc_loadtime_flags` | `str wzr`（=0） |
| `0x30` | `mpc_field_off` | `str x8`（`0x6cb6e20`） |
| `0x38` | `mpc_runtime_flags` | `str wzr`（=0） |

`mpc_ops` 存的 `0x6cb6e28` 正是 `amfi-ops-slots.json` 里记录的 `original_ops_address`，两条独立路径互相印证。`mpc_list`/`mpc_data`（`0x40`/`0x48`）留给 `mac_policy_register` 自己填，符合语义。

**所以"call ABI"这一项的静态证据是成立的**：签名、参数位置、结构字段偏移三者都对得上 native 8796 的声明。这仍不等于运行时注册成功 —— 参数指向的字符串、ops 表内容与策略生命周期都还没有执行证据。

## 产物

| 文件 | 内容 |
| --- | --- |
| `reports/native-prelink-merged/amfi-callgraph.json` | 构造/桩/槽/调用点全部锚点与覆盖说明 |
| `reports/native-prelink-merged/early-security-init.json` | ABI marker、五项前置条件、emit 结果与记录值 |
| `reports/native-prelink-merged/earlysec-diff.json` | 两候选按段差异统计 |
| `reports/native-prelink-merged/amfi-register-call.json` | 注册调用的参数寄存器、8 个 conf 字段、native 导出 |
| `out/earlysec-2026-10-24/kernel-prelinked-earlysec.macho` | 带 early_security_init 的分析候选（不启动） |

复现：

```bash
python3 scripts/audit-amfi-callgraph.py --output reports/<新路径>/amfi-callgraph.json
python3 scripts/audit-early-security-init.py --work out/<新目录> --output reports/<新路径>/early-security-init.json
python3 scripts/audit-amfi-register-call.py --output reports/<新路径>/amfi-register-call.json
python3 scripts/compare-prelink-candidates.py --old <旧候选> --new <新候选> --output reports/<新路径>/diff.json
```

## 仍然没证明的

- **运行时未验证。** 证明了签名与结构布局对得上，没证明 `mac_policy_register` 在 nuwa 上真被执行、也没证明 ops 表里 23 个回调能正常工作。这是 blocker 1 剩下的部分。
- `loadable` 仍是 `false`。`emit_current` 与 `emit_prelink` 都把它作为人工资格化标志，本轮没有也不应该改。
- 字段偏移来自固定源码声明，不是本轮 DWARF 读回（`amfi-ops-slots.json` 已覆盖 ops 表那侧）。
- blocker 2（C++/结构 ABI 的其余部分）、blocker 3（真实 ADT 与运行时窗口）、blocker 4（大负载装载）不受本轮影响。
- 两候选只在元数据上不同，**不代表新候选更接近可启动** —— 它只是证明配置通路成立。

## 下一步

blocker 1 的静态部分已基本清空，剩下的是运行时资格化，需要实机或 QEMU 级别的执行证据。离线可继续的方向：核对 `mpc_name`/`mpc_fullname`/`mpc_labelnames` 指向的字符串内容与 `0x6cb6e20`（`mpc_field_off`）的实际用途，确认策略声明完整；再把 `early_security_init` 是否接入 `emit-current-prelink-analysis.py`（当前硬编码空映射属有意保留）作为一次单独的决策。任何实机动作前仍须离线验收、新鲜录像与恢复门。
