# D-001 · 物理内存窗口按 boot_args 单窗口声明，首选主 bank（0x8c0000000 / 9216 MiB）

- 状态：**superseded by D-002**（2026-10-22 03:00，官方文档给出真实控制点与 8 GiB 上限；§2/§3 的内核侧事实仍有效，§5 的「首选 9216 MiB」作废）
- 否决的原提案：`NEED-REVIEW.md` R-001 的 A / B / C 三选一（那份题面把问题问错了）
- 证据基线：`docs/inherited/nuwa-observed.json`、`docs/inherited/meminfo.txt`
- 代码基线：`D:\Code\PortingiOS\common\sources\xnu-ios16-full`（只读）

## 1. 结论

1. **窗口只能是一个连续区间** —— 不是策略选择，是内核代码写死的。
2. 因此 **C（全 14 段）在当前 pmap 下不可实现**，直接排除；它不是「改动量大」，是需要重做 physmap。
3. **首选 B**：`gPhysBase = 0x8c0000000`、`memSize = 9216 MiB`。这不需要改 pmap 一行代码，改的是 loader 填的 `boot_args`。
4. **A 按提案原文是错的**：低 4 GiB 区间并不连续，`0x80000000` 起 2 GiB 这个区间根本不存在（见 §3）。若 B 的装载位置验证不通过，退路是 **A′ = 0xa4a81000 起 768 MiB**（低区最大连续块），代价是只能跑到内核起来，用户态必然 OOM。

## 2. 代码证据：单窗口是硬约束

`osfmk/arm64/arm_vm_init.c`

```
1832:  gPhysBase = args->physBase;
1834:  real_phys_size = args->memSize + (shadow_ptop - shadow_pbase);
1836:  real_phys_size = args->memSize;
1961:  real_avail_end = gPhysBase + real_phys_size;
```

```
378:  if (__improbable((pa < gPhysBase) || ((pa - gPhysBase) >= real_phys_size))) {
380:      panic(...pa, gPhysBase, real_phys_size);
382:  return pa - gPhysBase + gVirtBase;
```

- `gPhysBase` / `real_phys_size` 全部来自 **`boot_args`**，所以选哪个窗口是 **loader 的事**，不是 pmap 的事。
- `pa < gPhysBase` 也会 panic：**内核自身、boot_args、ramdisk 必须都落在窗口内**。这一条决定了 B 能不能用（见 §4）。
- physmap 只有 `[gPhysBase, gPhysBase + real_phys_size)` 一个区间，落在窗口外的 DRAM 段无法进入 physmap。多段 DRAM 需要重写 physmap，不是加个字段。

## 3. 实测：低 4 GiB 是碎片，不存在 2 GiB 连续块

`nuwa-observed.json` 的 14 段里，4 GiB 以下共 11 段，最大的单块是：

| 区间 | 大小 |
| --- | --- |
| `0xa4a81000 – 0xd4cfffff` | 768 MiB ← 低区最大连续块 |
| `0xe7cb0000 – 0xff7fffff` | ≈379 MiB |
| `0x82800000 – 0x8a7fffff` | 640 MiB |
| 其余 8 段 | 均 < 130 MiB |

`0x811d0000` 是 DRAM 起点，不是 `0x80000000`；`0x811d0000` 到 `0xffffffff` 之间被 bootloader 保留区切成 11 段。
所以 A 的「0x80000000 起 2 GiB 连续窗口」既起点错、也不连续 —— 按它声明会让 physmap 把保留区当普通 RAM 用。

能给出「够大且连续」的只有一段：`0x8c0000000 – 0xaffffefff` = **9216 MiB**。

## 4. PA 位宽不是障碍（R-001 高估了这个风险）

`osfmk/arm64/proc_reg.h`

```
972:  #define TCR_IPS_VALUE TCR_IPS_42BITS     // __ARM_42BIT_PA_SPACE__
974:  #define TCR_IPS_VALUE TCR_IPS_40BITS     // 默认
```

40 位 PA = 1 TiB 寻址。`0x8c0000000` 是 36 位地址、`0xaffffefff` 是 36 位顶端，**离 40 位上限还有 4 位余量**。
`gPhysBase` / `pa` 在代码里是 `unsigned long long`，无 32 位截断点。
→ 「基址在 35 GiB 需要改 pmap」这个担心不成立；要改的是 loader 侧的装载地址与 `boot_args`。

## 5. B 的真实门槛（这是下一步唯一要验证的事）

B 成立的前提是：**loader 能把 kernel + boot_args + ramdisk 全部放到 ≥ `0x8c0000000`**，否则 §2 第 378 行的 `pa < gPhysBase` 立刻 panic。

验证方法（离线可做，不需设备）：
1. 查 boot image header 的 `kernel_offset` / `ramdisk_offset` / `tags_offset` 是否支持 64 位地址、能否被设到 `0x8c000000+`；
2. 查 ABL 是否限制 payload 装载窗口（在 `docs/inherited/iomem.txt` 之外，看 UniXNU 的 loader 代码与 nuwa 的 dtbo/boot 配置）；
3. 若两者都允许，写 B；若任一不允许，退 **A′（768 MiB）** 并把「用户态内存不足」记为已知限制，不要为了凑容量去改 pmap。

## 6. 对 R-001 的处置

- R-001 由本决策**结案**，`NEED-REVIEW.md` 里标 `answered by D-001`。
- 不再向用户问 A/B/C。若 §5 的验证结论与本文冲突（例如 header 只支持 32 位 offset），按 §5 退 A′，并在 `DECISIONS.md` 追加 `D-002` 说明推翻理由 —— 这是技术事实更新，不是重新征询意见。

---

# D-002 · 内存窗口的真实控制点是 `darwinboot-memory-size`，上限 8 GiB

- 状态：**accepted**（2026-10-22 03:00，依据官方文档原文）
- 取代：D-001 §5 的「首选 9216 MiB」与「改 loader 塞 boot_args」这条操作路径
- 依据：`docs/inherited/unixnu-official-2026-10-22.md` §4，原文 https://unixnu.com/zh/porting/device-tree

## 结论

1. **上限是 8 GiB，不是 9216 MiB**。ADT `/chosen` 的 `darwinboot-memory-size` 明确规定 256 MiB–8 GiB、2 MiB 步进。nuwa 主 bank 是 9216 MiB，**整块用不上**，最大只能要 8192 MiB。
2. **不需要动 boot_args、也不需要改 pmap**。窗口是通过 ADT 声明的：
   - `dram-base` / `dram-size`（64 位）描述物理 DRAM；
   - `darwinboot-memory-size`（64 位，≤8 GiB）是连续窗口请求；
   - 板级侧对应 `[payload] dram_size` 与 `[payload.adt] owned_memory_size` 两个键（sheng 分别是 `0x80000000` 和 `0x130000000`，二者不等价）。
3. **容量不是 bring-up 的前置条件**。阶段 1–5 只需要「能装下内核 + boot_args + ramdisk 的一块连续区」。先从 512 MiB–1 GiB 起，过了阶段 5/6 再往 8 GiB 抬；一次到位反而把问题搅在一起。
4. D-001 §2/§3 仍然有效，别推翻：XNU 侧 physmap 只有单窗口（`arm_vm_init.c:378,1961`），`pa < gPhysBase` 会 panic，低 4 GiB 最大连续块只有 768 MiB。**这些是「为什么必须声明一个连续窗口」的理由，不是「必须选哪个基址」的理由。**

## 待验证（唯一一条，交给 bring-up 阶段 1/2 一并看）

UEFI 内存映射在 `0x8c0000000` 附近能否给出连续可用块。查法：阶段 2 的 UniXNU 日志会报内存/entry 信息；`docs/inherited/iomem.txt` 只反映 Android 视角，不能直接当 UEFI 视角用。
若不能 → 退到低区连续块并接受 768 MiB 上限，同时把「用户态内存不足」写进 STATUS 的已知限制。

## 不再做的事

- 不要再纠结「A 2 GiB / B 9216 MiB / C 14 段」三选一：C 在单窗口模型下不可能，B 的尺寸超官方上限，A 的区间在实测里不存在。**这三个选项全部作废**，问题已变成「先要多大窗口够过阶段 5」。

---

# D-003 · 内核页大小走 4 KiB（官方主线），16K 不进本仓

- 状态：**accepted**（2026-10-22 03:02，用户明确「4kb」）
- 依据：官方「移植总览」把「4 KiB XNU 补丁」列为 UniXNU 自带能力；sheng 的观测状态写的是「source 4K XNU to console」，`sheng_defconfig` 带 `CONFIG_XNU_NATIVE_CS_HASH_CACHE`；fuxi 直接沿用 sheng 的内核预链接。

## 理由

- 官方栈的补丁集、预链接、defconfig 示例、QEMU fixture 全部围绕 4 KiB 构建。选 16K 等于自维护一整套补丁并与官方文档脱钩，出问题时无法对照。
- 旧仓 `nuwa P16/16K` 那条线是自建的，`docs/operation/2026-10-21-nuwa-mmu16.md` 的边界与结论**不能平移**到本仓。
- 4 KiB 的代价是 mmu16 镜像（40,423,424 B）那套工作不直接复用；收益是能站在 sheng/fuxi 的既有数值上。

## 若用户坚持 16K

需要单开一条分支、自维护 16K 补丁集、并放弃与 sheng/fuxi `[kernel.prelink]` 对齐。届时在本文追加 `D-004` 说明代价，不在 bring-up 中途切换页大小。

---

# D-004 · 目标身份是 iOS（iPhone donor），不是 iPadOS —— 但别被 `ipad_identity` 这个键名骗了

- 状态：**accepted**（2026-10-22 03:02，用户明确「nuwa 的目标是跑 iOS 而不是 iPadOS」）

## 1. `ipad_identity = true` 与「跑不跑 iPadOS」无关

查基座源码 `docs/zh/guide/skip-setup.md`：

> 使用 `--ipad-identity` 时，ADT 会加入四个 `/chosen` 属性：
> `certificate-production-status = 0`、`effective-production-status-ap = 0`、
> `certificate-security-mode = 1`、`effective-security-mode-sep = 1`
> 这些属性描述一个 **dev-fused、未 demote 的板子**。`mobileactivationd` 通过 MobileGestalt 读取它们。

所以它是**安全/激活身份**（让 `mobileactivationd` 走原生激活路径），不是平台身份。
**不要因为名字把它关掉** —— 关掉大概率先把激活打坏。nuwa 应保持 `ipad_identity = true`。

## 2. 真正决定 iOS / iPadOS 的是这四处

| 位置 | 作用 | sheng 的值（不可照抄） |
| --- | --- | --- |
| `[ipsw] product / version / build / device_class / chip_id / board_id` | 取哪份原厂 kernelcache / DeviceTree / trust cache | iPad7,1 / iPadOS 17.7.11 / 21H461 / j120ap / 0x8011 / 12 |
| ADT `/product` 节点 | MobileGestalt 读到的产品名与型号 | 由 ADT 生成器写死 |
| `[kernel.prelink]` 的 `kernelcache_sha256` / `slide` / `early_security_init` / `roots` | 预链接哪份 Apple 二进制、地址在哪 | 全部绑 iPadOS 17.7.11 那份 kernelcache |
| 板级 `-disable-jobs` 之类启动参数 | 停掉平台不跑的服务 | sheng 用 `sheng-disable-jobs=com.apple.identityservicesd,...` |

**结论：sheng/fuxi 的 `[kernel.prelink]` 数值一个都不能抄**，它们绑在 iPadOS 17.7.11 的 kernelcache 上。抄了必炸且极难查。

## 3. donor 沿用旧仓已定的 iPhone，不重开题

旧仓 `docs/nuwa-ios-porting-plan.md` 已定：

> 首个候选采用 iPhone X `iPhone10,3 / d22ap` 的 iOS `16.7.16 / 20H392` 用户态，结合公开 XNU `8796.141.3` 参考源码。

那是为「plain arm64 手机用户态」选的，正好满足「iOS 16 + 手机形态」。本仓沿用这个 donor，不再讨论换不换 iPhone 型号，除非出现 ABI/PAC 级别的硬阻塞。

---

# D-005 · 4K 基座钉在 xnu-10063，而 iOS 16 是 8796 —— 版本落差怎么处理（待定，不阻塞）

- 状态：**proposed**（2026-10-22 03:02）
- 后续：**superseded by D-006**（2026-10-22；保留本节作为试算前的候选与启发式规则）。

## 事实

- 基座 `feeds.toml` 钉死 `xnu` = **`xnu-10063.141.1`（darwin 23.6.0，对应 17.x）**，49 个补丁是对这棵树写的。
- sheng = iPadOS 17.7.11（`21H461`）↔ 10063，配套成立。
- **iOS 16 = xnu-8796（darwin 22.x）**，与 10063 差一个大版本。4K 补丁集、预链接、defconfig 静态库都按 10063 写的。

→ 「4 KiB + iOS 16」这个组合**官方没有现成答案**，成本全在把 49 个补丁 rebase 到 8796。

## 三个选项

| | 做法 | 代价 | 何时能看到画面 |
| --- | --- | --- | --- |
| A | feeds 换 8796，49 补丁全部 rebase | 未知，可能半数要手改 | 最晚 |
| B | 先用 iOS **17.x** 的 iPhone donor（如 iPhone15,2）打通全链，之后再降版本 | 偏离 iOS 16，但最快见到 iOS 用户态 | 最快 |
| C | 先花半天对 8796 做 `git apply --check` 批量试算，按失败面决定走 A 还是 B | 半天 | 视结果 |

## 宿主立场

**先做 C 的那次 `git apply --check`，不要凭感觉选。** 旧仓对 sweet 补丁做过同样的事（38/49 可 apply），一次跑完就知道失败面量级：

- 失败 ≤10 个且都是文档/头文件类 → 走 A，直达 iOS 16，符合目标。
- 失败 ≤10 个但有 pmap/SMMU/ABI 类 → 先 B 通链，再逐个补回。
- 大面积失败 → 走 B，把「iOS 16」降级为后续里程碑，别一步到位。

判定前**不要动 `feeds.toml` 的 xnu 版本**（会连带影响 49 个补丁的基准，难回滚）。

---

# D-006 · 先适配 8796 直达 iOS 16；feed 切换以完整补丁集与接口审查为门

- 状态：**accepted**（2026-10-22；依据 D-005 试算，细化其按失败数量/文件名选路的启发式）。
- 证据：[完整报告](operations/2026-10-22-patch-portability-8796.md)、`reports/patch-portability-8796/results.json`、`reports/patch-portability-8796/pmap-existing-path-only.log`。
- 基线：UniXNU `75bc13dd34dc4e403826793739e316a264ce00dd`；XNU `1b191cb58250d0705d8a51287127505aa4bc0789`（8796.141.3）。

49 项独立检查为 38 项静态检查通过、11 项失败。失败不全是头文件：包括启动汇编、machine layer 配置、PGZ 和根卷/观测钩子。但普通 pmap 的 PA 修复 hunk 匹配；整个 pmap 补丁失败来自不存在的 SPTM 文件，排除此路径后返回 0。两项晚期补丁还含前置依赖，故不把“11 项失败”当成 11 个独立核心阻塞。

选择 A（先适配 8796），因为本次没有确认必须换 donor 的 ABI/PAC 或 pmap/SMMU 语义硬阻塞；先走 B 会另引入 17.x iPhone donor 与预链接工作，而不能消除最终 8796 适配。这里是基于失败性质的工程判断，不声称已验证 ABI 兼容。不套用 D-005 的“触及 pmap 就 B”粗分类。

执行边界：本次不改 feed；先在设备仓维护补丁适配，核查 NativePrelink 的额外两项及完整依赖顺序、Darwin 22 静态库/接口，再单开 feed 切换提交。出现实际核心语义阻塞时追加新决策，不静默更换 donor。D-002/003/004 均保持有效，未知板级值留 TODO；board 身份/内存/bootimg 地址落地前仍须 NEED-REVIEW。编译、QEMU 和实机均未验证。

---

# D-007 · 8796候选选择不强搬不存在的PGZ接口与17.x freezer条件

- 状态：**accepted**（2026-10-22；候选补丁选择，不是feed或构建兼容性验收）。
- 证据：[选择集报告](operations/2026-10-22-8796-selected-sequence.md)、`reports/xnu-8796-sequence/results.json`；8796 `osfmk/kern/zalloc.c:1467`、`bsd/kern/kern_memorystatus_freeze.c:120`；基座 `patches/xnu/offline-pgz-alignment-probe.patch:51,77`。

保留8796原allocator接口与freezer策略。`pgz-aligned-validation.patch`修补的zone_id_require_aligned在8796不存在；不为凑apply通过而新建17.x接口。依赖它的可选offline PGZ alignment probe延期移植，未来配置不得启用该probe直到等价实现/验证完成。`published-freezer-condition.patch`修复的10063畸形条件在8796不存在，视为不适用。

51项来源中暂选48项，包含NativePrelink两项及8个设备仓适配候选。内存顺序模拟和最终合并diff只读检查通过，不等同实际应用或编译。所有上游补丁仍只读保留，feed不改；后续若发现8796也需对应修补，以新证据追加决策，不静默丢弃安全/接口问题。D-006路线及D-002/003/004继续有效。

---

# D-008 · 采用官方macOS Actions方向准备内核构建，保持设备仓独立

- 状态：**accepted**（2026-10-22；主机/集成方向，不是构建通过）。
- 用户依据：提出使用GitHub Actions，回复继续，指定账号wh1stl3，并明确Git所有命令允许；R-003 A的WSL预检历史保留，不再作为“禁止macOS”的现行边界。
- 证据：[官方CI接入审查](operations/2026-10-22-official-ci-route.md)、`reports/official-ci-plan/remote-audit.json`；官方e95b提交存在macos.yml、archive/bootstrap调度，仍固定10063/iOS17并在kernel后调用prelink。

基座fork承载官方构建入口，UniXNU-nuwa继续独立设备仓，uefi-nuwa继续独立固件仓。首轮范围为明确的内核源构建验证；不以iPad或iOS17配置替代既定iOS16/iPhone donor。macos-15-intel/Xcode16.4仅为当前候选主机输入，须记录实际镜像/SDK/编译器并验证，不宣称标签保证长期可用。

本轮不整体跟进e95b的491项路径/blob变化，不切feed；75bc输入上的48项静态结论继续限定在原输入。后续确定最小基座集成及8796覆盖后再编译。允许Git命令不解除资料库/来源树只读边界，也不解除四类硬停；board和未知板值保持原约束。
