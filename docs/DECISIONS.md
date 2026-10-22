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

---

# D-009 · 新工具链适配保留8796的数据接口

- 状态：**accepted，实际编译验证进行中**（2026-10-22）。
- 后续：UIO部分继续有效；IIG deployment-target候选被真实生成否证，**该部分 superseded by D-010**。
- 证据：CI39716728005的UIO对齐与IORPC.kernelContent错误；CI39717772747的实际IIG帮助和旧/新模板字符串；`reports/kernel-ci/39716728005/compatibility-check.json`。

UIO缓冲区继续是原UIO_SIZEOF(niov)字节，按原_Alignof(union iovecs)对齐；仅把对齐施加到声明，不把元素扩大8倍或取消对齐。36处调用使用声明宏，原typedef保留。

IORPC继续使用8796的四字段定义，不为新IIG生成结果补kernelContent。下一轮通过Makefile现有OTHER_IIG_FLAGS传`--deployment-target 22.0`选择旧DriverKit生成目标；这是有实际工具帮助支持的候选，不是已证明ABI兼容。是否选中旧模板以生成结果和真实编译为准；不能将类型同名或编译成功推为完整driver ABI通过。

---

# D-010 · 8796源CI保留内联RPC，关闭缺失公开实现的性能采样

- 状态：**accepted，兼容候选待真实编译**（2026-10-22）。
- 证据：[第三轮分析](operations/2026-10-22-ci-third-failure.md)、`reports/kernel-ci/39718507532/`。

第三轮仍生成51个含kernelContent的文件，IORPC原头未变；实际错误为OSObject生成代码访问不存在字段，以及缺少公开源码osfmk/arm64/kpc.c。短CI 39722376512对真实OSObject.iig使用16/19/20/21/22五个目标，结果字节和哈希完全相同。因此不再以deployment-target作为旧RPC模板开关。

使用固定IIG DriverKit-427.100.5生成器的内联消息分支建立受限文本适配候选：仅识别叶子KERNEL条件中的split-content/对应消息指针类型，采用其现有内联分支；KERNEL定义、其余内核条件、消息字段声明和IORPC头不改。未知版本、未知残留模板立即失败。生成内容和适配哈希进入云端报告，完整ABI与driver archive仍需后续独立验证。

仅源CI的BCM2837配置关闭KPC及依赖它的KPERF；后者kperf_kpc.c有无条件kpc调用，不能只删缺失源文件或塞空实现。代价是该源内核没有性能计数采样能力，不能把它当完整donor ABI闭包。正式nuwa配置尚未建立。本决策不切feed、不改board、不生成固件/诊断镜像、不改变任何_verified。

D-010补充（2026-10-22 12:40）：第四轮主动拒绝未知回调赋值模板；取得短CI39723294640的17个真实生成文件后，仅补入rpc.kernelContent = &msg->content.__hdr精确规则。17文件432块静态转换通过，仍待完整编译/ABI。原始模板和全集hash见reports/kernel-ci/39723011018/。

D-010补充（2026-10-22 14:22）：第五轮51个IIG生成实现均无kernelContent残留且原IORPC头不变，实际失败移至ast.c无条件包含/调用已关闭的KPERF接口。仅增加include和AST处理块的KPERF条件保护，52项212 hunks静态检查通过，真实修复待第六轮；证据见operations/2026-10-22-ci-fifth-failure.md。

D-010补充（2026-10-22 14:35）：第六轮首错移至processor.c定时器表无条件引用KPERF枚举/回调；timer_call.h枚举已有KPERF guard，现仅给表项加相同条件，保留表长度static_assert。53项213 hunks静态检查通过，待第七轮。证据reports/kernel-ci/39733594660/及第五轮分析的第六轮节。

D-010补充（2026-10-22 14:48）：第七轮确认ast.o/processor.o均实际生成，首错移至t_kpc初始化与结构KPC条件不一致。仅补初始化guard；同类源码检查另补scheduler/KTRACE对关闭性能模块的引用边界，保留量子定时器与KDEBUG路径，无stub。56项222 hunks静态检查通过，新增候选待第八轮；证据reports/kernel-ci/39734939751/，不混称实际链接错误。

D-010补充（2026-10-22 14:54）：ARM64上下文两处kpc_off_cpu调用仍引用关闭模块，只给include和回调加KPC条件，不改变pmap/上下文切换。第八轮请求取消以合并该已确认源码缺口；取消不作构建验证。57项225 hunks静态检查通过，待后续真实编译。证据reports/kernel-ci/39736351595/kpc-context-review.json。


# D-011 · 源CI的可选archive调用与构建条件一致

- 状态：accepted（2026-10-22 15:09；源构建链接条件，不是设备功能验收）。
- 证据：第九轮39736926012原始行851223-851227；基座baseline:319,600-614；reports/kernel-ci/39736926012/。

第九轮到达最终链接，唯一缺失符号为native_legacy_display_probe。保持源CI可选设备archive关闭的范围，仅使bsd_init中运行时probe分支服从已有XNU_NATIVE_LEGACY_DISPLAY开关；开启功能时仍必须提供真实archive并完成Darwin22接口审查。保留完整链接错误和make退出码检查，无stub或忽略undefined-symbol行为。58项226 hunks静态检查通过，实际修复待第十轮。feed/board、未知板值和实机边界不变。

D-008/D-010/D-011补充（2026-10-22 15:28）：第十轮39738601892已完成完整源配方与链接，下载产物SHA与runner一致，普通ARM64、LC_SOURCE_VERSION8796.141.3、Darwin22.6.0、未解析符号0、两项NativePrelink标记1，静态检查通过。云端macOS工具链路线取得真实源内核构建证据；WSL本机、完整driver/RPC ABI、donor预链接与nuwa可启动性仍未验证。源CI性能及可选设备archive保持关闭。证据reports/kernel-ci/39738601892/与operations/2026-10-22-ci-source-kernel-success.md。

# D-012 · 真实编译时生成记录并独立审查Darwin22平台archive

- 状态：accepted，实际archive编译待CI（2026-10-22 15:40）。
- 证据：8796 MakeInc.rule:403,427与MakeInc.def:955-970；reports/driver-archives-plan/；operations/2026-10-22-darwin22-archive-build.md。

在C/C++规则中用Clang -MJ生成逐对象fragment，保留实际编译和完整链接，不采用替换编译的数据库模式。archive只重用同轮真实IOPlatformExpert命令，保留ABI、清除原对象/依赖输出副作用，重建三项基座通用平台库并检查ARM64/iOS16格式与符号名闭包。此步骤不把archive接入内核或board，不验收硬件、完整C++/donor ABI；boot-progress/watchdog继续关闭。feed、板值和镜像硬停不变。

D-004补充（2026-10-22 15:54）：独立只读Restore/BuildManifest核对既定iPhone身份、d22ap/CPID0x8015/BDID6及KernelCache成员名；真实donor SHA与并行预链接产物报告一致。证据reports/parallel-progress-review/donor-and-relocation-review.json。只记录证据，不改board/IPSW字段；预链接、内存及可启动性仍未验收。

D-012补充（2026-10-22 16:03）：第十一轮真实源内核再次构建成功并生成933份C/C++记录，四份关键记录及原对象通过检查；首次ArmCpu编译失败为原命令中的不存在EXPORT_HDRS/libsa搜索路径被-Werror拒绝。只在该精确目录不存在时去掉并记录路径，保留其余目录/警告/ABI及真实编译，4项保护测试通过。实际archive仍待重跑；证据reports/kernel-ci/39742250205/。

# D-013 · 用真实VFS实现补齐已观测的iPhone donor符号缺口

- 状态：accepted，实际编译/目标导出与donor ABI未验证（2026-10-22 16:14）。
- 证据：reports/donor-compat/；operations/2026-10-22-donor-vfs-bridge.md。

对同一真实donor的65,348项指针表，当前内核唯一缺失为APFS使用的_vfs_getvfs_with_vfsops，参考run24为0。回移真实上游函数、声明和导出，不填假地址或成功stub；函数及底层mount查找的锁/引用语义静态一致。保持feed、board、原48项选择和既定iOS16目标；下一轮增加1项donor候选，与11项CI兼容分别计数。仅指针名清点不构成完整布局/指令/ABI验收，后续仍以实际Mach-O和只读plan为证据。

D-012补充（2026-10-22 16:21）：第十二轮无效libsa路径已实际移除、源内核和933份记录仍成功；平台编译被26条诊断升级拒绝。仅missing-designated-field-initializers、suggest-override、suggest-destructor-override三类保留为可见警告，不改旧头文件/结构/初始化，不关闭其余-Werror；五项C导出补与真实定义一致的前置声明，missing-prototypes检查保留。该诊断范围取代此前无例外的-Werror描述，未将风格警告当作ABI失败或成功。证据reports/kernel-ci/39744948467/，实际archive待后续CI。


D-013补充（2026-10-22 16:47）：CI13实际内核包含VFS桥接，65,348项绑定零缺失、官方只读plan布局/指针检查通过。静态候选已取得真实编译和产物证据；参考roots/slide未写入board，12处指令豁免和完整ABI仍未验收，无emit或新镜像。证据reports/donor-compat/ci13-*。

D-012补充（2026-10-22 16:47）：CI13的ArmCpu真实对象和242704字节archive已生成；ArmDTPlatform首错为真实不返回复位函数缺noreturn。仅加单翻译单元前置属性声明，不关闭该诊断或更改复位代码。三个archive的完整闭包待下一轮。


D-012补充（2026-10-22 17:29）：CI14真实源内核及ArmCpu/ArmDTPlatform/ArmVirtPlatform三库编译、符号名闭包通过，见reports/kernel-ci/39750542014/。下一阶段仅复用同轮make参数追加ArmCpu+ArmDTPlatform实际重链接，保持所有运行开关，不启用正式硬件profile、不替换crypto/pthread检查。真实链接与完整ABI仍待验证。

# D-014 · 优先复用已有开源驱动并以本机绑定筛选板级适配

- 状态：accepted（2026-10-22；用户明确要求尽可能使用UniXNU及其他开源/机型适配，并授权只读ADB获取硬件信息）。
- 证据：operations/2026-10-22-driver-reuse-and-platform-link.md；reports/driver-reuse/固定本地和远端提交、文件hash和许可。AGENTS第7节记录约定。

优先沿已有真实实现做Darwin22最小适配；按驱动模块核对依赖与许可证，源树只读引用，不复制整棵树。相同SoC只作为筛选条件，触控IC/面板/MMIO/IRQ/电源/固件等须本机证据。Android绑定及DT只是Android观测，不将其转换成XNU实机通过或_verified=true；仍保留板字段和镜像硬停。

D-014补充（2026-10-22 17:37）：本机触控实际为fts_touch_spi/st,spi，MiCode nuwa DT在GPIO/坐标/SPI频率/固件名上对应；优先固定LineageOS SM8550内核fts_spi真实实现审查。sm8550-modules的旧st/I2C实现不作为直接版本，虚拟uinput-goodix不作为IC依据；面板以mi_display和msm_drm运行态一致的m2_38_0c_0a选择，不盲从default-panel指针。该项只确定来源方向，未移植/编译XNU触控、未改板值或镜像；详见Android取证报告。

D-012补充（2026-10-22 17:49）：CI15实际重链接成功，ArmCpu/ArmDTPlatform五项导出已由下载内核独立核对，undefined=0、SHAa9e08c69与runner一致；65,348个donor指针绑定零缺失。源链接门取得真实证据；后续转向provider/时钟/平台启动条件，现有运行开关不变，不以链接通过验收硬件或完整ABI。证据reports/kernel-ci/39755850870/与reports/donor-compat/ci15-kernel-bindings.json。


# D-015 · 固定本仓真实平台内核，分开复用加载器接线和原厂内存证据

- 状态：accepted，源码候选静态检查通过；固件生成待R-004（2026-10-22 18:04）。
- 证据：operations/2026-10-22-loader-source-integration.md；config/loader-candidate.json；reports/loader-integration/。

当前内核输入固定为CI15 SHA a9e08c69（ArmCpu/ArmDTPlatform真实链接），不以隔壁预链接内核或旧FAT代替。复用BootShim长度修正、UniXNU应用/注册器/DarwinBoot协议链及sheng只读initrd BlockIo实现，后者移除DRAM/GCD扩展，只保留发布功能并检查入口HOB长度。原厂XBL配置以独立提取的8342字节原文为准；NoMap/AddDynamicMem、FD拆分和参考高地址策略分别审查，不整表套用或推翻D-002。源码候选不构成编译/分派/内存所有权/硬件通过；下一镜像生成步骤按R-004硬停。


D-015补充：用户明确批准R-004 A，允许独立Actions临时源树生成四模块EFI、nuwa FD及BootShim并静态检查；不包含boot.img/负载/预链接镜像、设备执行或板内存地址修改。来源由config/firmware-ci-inputs.json钉版并记录LF归一化哈希，固件入口直接调用DeviceBuild，避开build_uefi.py的boot打包阶段。


D-015补充（2026-10-22 18:48）：R-004 A已完成；CI39764322744四EFI/FD/BootShim真实编译、665份下载文件hash、嵌套FV/PE/DEPEX/SEC-HOB/PCD/shim机器码检查通过。FD SHA a0bbb964，未包含内核、未生成boot.img、未执行设备；运行内存与完整iOS链路仍未验证。后续用户授权可恢复fastboot前提下推送/试启动镜像，具体恢复条件须证据支持，见NEED-REVIEW授权记录。


D-015补充（2026-10-22 19:06）：原厂nuwa v4 boot临时加载回Android boot_completed=1取得实机证据；当前boot_a/init_boot_a hash与原始输入相同，A槽先前unbootable状态未被本轮改写。首个固件入口包复用原厂v4头仅改kernel_size，raw CI39764322744 shim+FD、不加DTB/FAT/XNU；3153920B/SHA12864ac6。容器静态检查通过，候选执行、实际DT/initrd布局和DXE仍未验证。来源与两方案记录见R-005和试启动报告，未采用上游DT的旧initrd属性为运行地址。


# D-016 · 实机容器对照隔离bootloader状态，命令接受与固件执行分开验收

- 状态：accepted（2026-10-22 20:22）。
- 证据：reports/v4-firmware-trial/launch.json、recovery.json、reset-bootloader.json、recovery-after-loader-reset.json、post-recovery.json；operations/2026-10-22-v4-firmware-trial.md。

固定v4候选命令OKAY、屏幕黑屏且fastboot持续可见，不构成BootShim/SEC/DXE通过。同一原厂输入在候选后直接恢复报Load Error、重新进入bootloader后成功恢复Android=1，说明实验必须控制状态；尚不能归因某个内部缺陷。以后各镜像对照从重新进入的bootloader开始，恢复也先重进bootloader；保留原始失败证据，不凭单次Load Error外推唯一版本/大小门槛。未得到入口日志的阶段写未验证，不用ACK或黑屏替代执行证明。


D-016补充（2026-10-22 20:53）：离线实际FD/TE/map入口一致，SEC WARN/ERROR已开但DebugLib和异常仅走FrameBufferSerialPortLib，正常横幅前还有SMMU调整/清屏。没有独立早期出口，黑屏不能定位SEC或证明未进入。后续先澄清ABL交接契约与可回收早期日志通道，不用更多屏幕DEBUG替代观测；33项静态断言见reports/arm64-sec-entry-audit/audit.json。设备暂停持续，无镜像/板值修改。

# D-017 · 以CI15实际DWARF固定Darwin22加载器ABI

- 状态：accepted，源码候选/布局编译通过，完整固件和运行ABI未验证（2026-10-22 21:52）。
- 证据：reports/official-site-audit/ci15-boot-args-dwarf.json；reports/darwin22-loader/；operations/2026-10-22-darwin22-loader-fix.md。

本机固定iOS16/XNU8796负载使用608B CommandLine与0x2e0 boot_args，不沿用Darwin23的1024B/0x480。设备专用patch同时调整局部缓冲区与复制边界，超长/非ASCII直接拒绝，保留终止符；不只缩短结构或静默截断。补丁适用原75bc基线和合并后固定DarwinBoot模块，应用前后均有哈希门。此决策不切换4KiB、窗口或身份，不证明当前无XNU的v4黑屏原因；未来多ABI需明确构建/协议选择。

# D-018 · 独立固件仓保留Mu历史并与设备仓分工

- 状态：accepted，源码和本地检出完成，新固件尚未编译（2026-10-22）。
- 证据：用户要求补齐uefi-nuwa并追问本地目录；reports/uefi-nuwa/；operations/2026-10-22-dedicated-uefi-repository.md。

设备脚本/板描述/补丁与证据留在UniXNU-nuwa；固件改动在独立uefi-nuwa维护，使用固定提交接入。已有enuma处于同一GitHub fork网络，使用独立Git仓导入Mu历史，保持enuma和上游main不变；nuwa开发分支从已验证6c67550建立，不直接升级Mu基线。已入固件仓的patch不重复应用，旧manifest和patch保留以复现历史。用户要求的D:/Code/uefi-nuwa作为独立本地源码目录，旧资料库保持只读；源码仓建立和静态检查不构成镜像或实机阶段验收。


D-017/D-018补充（2026-10-22 23:47）：独立固件CI39805110487及665项下载产物静态检查通过，Darwin22 ABI补丁完成真实DarwinBoot EFI编译链接；FD3MiB/SHA7f6f16c8、shim112B保持9346a527。未生成Android容器或执行设备，运行ABI未验证；新SEC阶段诊断范围另列R-007，未应用。证据reports/firmware-ci/39805110487/。


D-016/D-018补充（2026-10-23 00:11）：R-007 A诊断固件5e4a8c8/CI39809636575编译和静态审计通过，v4包fbb7940a临时命令OKAY但用户黑屏、15次fastboot持续，无SEC/DXE证据。按D-016前后均bootloader复位，已验证Android备份boot恢复后nuwa boot_completed=1，boot/vendor_boot/init_boot三个分区hash未变。此实验只验收命令接受与本次恢复，不证明入口执行或修复根因；后续转向ABL交接/独立观测。证据reports/sec-trace/39809636575/trial-summary.json。

# D-019 · BootShim Image头使用相对装载偏移，FD复制目标独立保留

- 状态：accepted，R-008 A源码/构建与单变量试启动完成（2026-10-23）。
- 证据：operations/2026-10-23-abl-handoff-and-relative-offset.md、operations/2026-10-23-relative-offset-trial-and-pil-stop.md；reports/relative-offset/package.json及两次launch/recovery；源码910ee079。

头+8的text_offset不能填绝对FD_BASE；本机普通ABL变量分支会将其加到KernelBaseAddr。获批候选改为0，FD复制/入口目标仍A7100000，全部指令不变。WSL实际112B新shim与旧版只差offset10/11，容器只差4106/4107；两次实机fastboot枚举行为改变且用户有日志照片，但运行变量/PC/具体候选SEC阶段仍未验证，不把条件算术模型写为已捕获的实际错误码。后续构建/检查应分别描述relative text_offset和FD destination，不用旧header=FD_BASE门验收新shim。新FD的PIL策略另列R-009，未纳入本决策或R-008审批。
