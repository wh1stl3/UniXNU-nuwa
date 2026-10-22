# UniXNU 的 49 个 XNU 补丁对 8796.141.3 的可移植性试算

## 结论与选路

**选择先 rebase 到 8796，直达 iOS 16（D-006），暂不改 feeds。** 独立检查为 **38/49 静态检查通过，11/49 失败**；不能写成整套补丁通过，更不能写成编译、QEMU 或实机通过。

这不是只剩头文件/文档的问题：有启动汇编、构建配置、PGZ allocator、根卷挂载和观测钩子的版本差异。但本次没有找到必须先切 iOS 17 iPhone donor 的 ABI/PAC 阻塞证据。pmap 的失败来自 8796 不存在的 SPTM 分支；对实际存在的普通 pmap 分支做单独检查返回 0。故不把文件路径缺失直接解释成 pmap 算法移植失败，也不机械地以“11 > 10”更换 donor。

这是限定范围的工程路线决策，不是 iOS 16 可启动的证明。下一道门是按依赖顺序完成 8796 补丁适配及整套累积检查，再做编译/链接；若出现实际 ABI/PAC 或 pmap/SMMU 语义阻塞，另记决策重新评估。iPhone10,3 / d22ap / iOS 16.7.16 / 20H392、4 KiB 与 `ipad_identity = true` 保持既定决策。

## 输入与方法

### 2026-10-22 06:30 复跑

执行 `& ./scripts/check-xnu-patch-portability.ps1 -Output reports/patch-portability-8796-recheck`，返回 0，输出 `PASS=38 FAIL=11`。
新证据：[results.json](../../reports/patch-portability-8796-recheck/results.json)。与初次记录逐项比较 `patch / sha256 / exit_code`，差异为 0；XNU HEAD、基座 HEAD 和 feeds SHA-256 与下表一致。XNU 前后 status 返回 0 且输出为空，基座 tracked status 为空。普通 pmap 排除 SPTM 路径的补充检查仍返回 0。原始证据未覆盖，失败分类与 D-006 保持有效。

比较命令（PowerShell；`$prior`、`$now` 分别为两个 results.json 的 `ConvertFrom-Json` 结果）：

```powershell
Compare-Object ($prior.results | ForEach-Object { "$($_.patch) $($_.sha256) $($_.exit_code)" }) ($now.results | ForEach-Object { "$($_.patch) $($_.sha256) $($_.exit_code)" })
```

输出为空。此次仍仅为独立静态检查，没有应用补丁、编译、QEMU、镜像生成或设备操作；未执行任何 Git 写操作。

| 输入 | 精确基线 |
| --- | --- |
| 只读 XNU 树 | `D:/Code/PortingiOS/common/sources/xnu-ios16-full` |
| XNU HEAD | `1b191cb58250d0705d8a51287127505aa4bc0789`，提交正文为 `xnu-8796.141.3 / Imported from xnu-8796.141.3.tar.gz` |
| 只读 UniXNU | `D:/Code/PortingiOS/common/sources/UniXNU`，HEAD `75bc13dd34dc4e403826793739e316a264ce00dd`，tracked 工作树干净 |
| 补丁范围 | `patches/xnu/*.patch`，按文件名排序，恰好 49 个；每个 SHA-256 见 JSON |
| Feed | 仍为 `xnu-10063.141.1`；`feeds.toml` SHA-256 `dec145fe25ed9cf1c50292a1e16ccbaa690b450a1de9e1ed687395e5fef88294` |
| 工具与原始输出 | [results.json](../../reports/patch-portability-8796/results.json)，含时间、Git 版本、输入提交、前后 source status 和全部结果 |

复现命令（仓库根目录，Windows PowerShell）：

```powershell
& ./scripts/check-xnu-patch-portability.ps1
```

每次检查命令如下；各补丁日志第一行保存实际完整命令：

```text
git -c safe.directory=D:/Code/PortingiOS/common/sources/xnu-ios16-full --no-optional-locks -C D:/Code/PortingiOS/common/sources/xnu-ios16-full apply --check --verbose <patch-absolute-path>
```

没有执行 `git apply` 写入、checkout/reset、worktree 或 clone。`safe.directory` 仅命令级配置，没有改全局配置。XNU 检查前后 `status --porcelain --untracked-files=all` 均为空、返回 0。日志仅写本仓。脚本独立检查每个补丁，**不累积应用成功补丁**，因此保留前置依赖造成的失败，不扣除或重算成更高的通过率。

## 11 个失败：逐项分类

以下路径均相对上述只读树或基座；日志是完整错误证据。类型按失败 hunk 与补丁内容判断，不能仅按补丁名判断。

| 补丁与原始日志 | 失败位置 / 类型 | 解释与适配工作 |
| --- | --- | --- |
| [apple-only-cpu-tunables](../../reports/patch-portability-8796/apple-only-cpu-tunables.patch.log) | `osfmk/arm64/start.s:33`；启动汇编上下文 | 8796 第 35 行多出 `#include "assym.s"`；tunables include 和 `APPLY_TUNABLES` 仍存在（36、780 行）。需重定位 Apple 专用 guard，不能当文档修改，也没有证据表明指令 ABI 不兼容。 |
| [external-archive-dependencies](../../reports/patch-portability-8796/external-archive-dependencies.patch.log) | `makedefs/MakeInc.kernel:187`；构建/链接依赖上下文 | 外部 archive 参与增量链接的规则要按 8796 链接目标重定位；不是头文件或 pmap 改动。未验证实际链接。 |
| [native-aes-personality](../../reports/patch-portability-8796/native-aes-personality.patch.log) | `iokit/KernelConfigTables.cpp:61`；IOKit personality 表上下文 | 补丁锚点是 10063 的 `IOExclaveProxy`，8796 表尾只有 `IOPanicPlatform`。需将 NativeAES、Virtio、RamBlock、UFS personality 插入 8796 表；驱动绑定/ABI 未验证。 |
| [offline-owner-systemos-mount](../../reports/patch-portability-8796/offline-owner-systemos-mount.patch.log) | `bsd/kern/kern_exec.c:183`；头文件上下文 + 根卷/exec 逻辑 | 8796 的 `kern_exec_internal.h` 后没有补丁所匹配的 Entitlements/exclaves includes。不能据此判定后续挂载逻辑兼容；需分开头部适配与根卷逻辑审查。 |
| [pgz-aligned-validation](../../reports/patch-portability-8796/pgz-aligned-validation.patch.log) | `osfmk/kern/zalloc.c:1474`；allocator API/实现版本差异 | 8796 没有 `zone_id_require_aligned`，存在 `zone_id_require`（1467 行）、`__pgz_decode`（5307 行）。不能把新 API 修补直接搬入或以改行号解决；需核查 8796 对应调用路径及是否需要此修复。不是 SMMU，也不是已证实的用户 ABI 阻塞。 |
| [public-entitlements-header](../../reports/patch-portability-8796/public-entitlements-header.patch.log) | `bsd/net/necp_client.c:68`；头文件/版本特性 | CoreEntitlements 头文件 hunk 可匹配，但 8796 `necp_client.c` 没有要替换的 CodeSignature include；Web Browser Engine entitlement 定义是否需要，须按 8796 使用点判断。整个补丁仍失败。 |
| [published-freezer-condition](../../reports/patch-portability-8796/published-freezer-condition.patch.log) | `bsd/kern/kern_memorystatus_freeze.c:133`；版本专属条件修复 | 补丁修复 10063 的畸形 `#if (XNU_TARGET_OS_IOS && ...`；8796 没有这个条件块，第 120 行直接 `memorystatus_freeze_enabled = FALSE`。不可为满足 apply 而引入 17.x freezer 策略。 |
| [source-machine-layer](../../reports/patch-portability-8796/source-machine-layer.patch.log) | `config/MASTER.arm64.bcm2837:16`、`osfmk/conf/files.arm64:34`；架构构建选择 | `config/MASTER` hunk 匹配；bcm2837 配置和 AMCC 文件集合不同。涉及 `nos_arm_asm/nos_arm_pmap/apple_amcc` 的选择，须逐项审查，不能归入纯文档失败。未验证 machine layer 链接。 |
| [zzx-pmap-sync-64bit-pa](../../reports/patch-portability-8796/zzx-pmap-sync-64bit-pa.patch.log) | 缺少 `osfmk/arm64/sptm/pmap/pmap.c`；pmap 版本分支缺失 | 普通 pmap hunk 匹配 6877 行；不存在的 SPTM 文件使整补丁失败。只排除该路径后静态检查通过，见下节。适配应保留普通 pmap 的 PA 位宽修复；内存字段不变。 |
| [zzy-native-gpu-addon-mount](../../reports/patch-portability-8796/zzy-native-gpu-addon-mount.patch.log) | `bsd/kern/kern_exec.c:7193`；前置依赖 | 需要 systemos 补丁添加的 `native_owner_data_prepare`，原始树不存在。其余 bindfs/startup 文件检查可匹配。整套顺序应用后的结果未验证。 |
| [zzz-boot-progress](../../reports/patch-portability-8796/zzz-boot-progress.patch.log) | `bsd_init.c:773`、`kern_exec.c:7389`、`sleh.c:1`、`kern/Makefile:114`、`kern_exit.c:1893`；前置依赖 + 版本上下文 | 部分依赖 sheng PMGR/SystemOS 前置补丁；另有版权头、导出列表与 critical-exit 代码差异，不能把全部失败都归因于依赖。需逐 hunk rebase。 |

按整补丁计：头文件相关 2（其中 SystemOS 同时含运行逻辑），构建 2，启动汇编 1，personality 1，allocator 1，版本条件 1，pmap 分支缺失 1，依赖/混合观测钩子 2；纯文档失败 0。**不是“38 个可用、剩下 11 个都容易修”**。

## pmap / SMMU / ABI 专项解释

补充命令及输出见 [pmap-existing-path-only.log](../../reports/patch-portability-8796/pmap-existing-path-only.log)：

```text
git -c safe.directory=D:/Code/PortingiOS/common/sources/xnu-ios16-full --no-optional-locks -C D:/Code/PortingiOS/common/sources/xnu-ios16-full apply --check --verbose --exclude=osfmk/arm64/sptm/pmap/pmap.c D:/Code/PortingiOS/common/sources/UniXNU/patches/xnu/zzx-pmap-sync-64bit-pa.patch
exit_code=0
Skipped patch 'osfmk/arm64/sptm/pmap/pmap.c'.
Checking patch osfmk/arm/pmap/pmap.c...
Hunk #1 succeeded at 6877 (offset -186 lines).
```

这只是隔离失败原因，**没有修改补丁、源码或原始 38/49 统计**。8796 `osfmk/arm/pmap/pmap.c:6880` 仍有 `(pp << PAGE_SHIFT)`，因此不能直接丢掉整个修复。

`non-apple-iommu-bootstrap.patch`、`non-apple-pmap-field.patch`、`native-4k-user-abi.patch`、`native-4k-bootstrap-capacity.patch`、`native-4k-signature-hash-cache.patch` 独立静态检查均返回 0（见同名 `.patch.log`）。这证明相应 hunk 可匹配；**SMMU 驱动编译、设备 DMA、4 KiB 用户态 ABI/PAC、签名验证均未验证**。

## 范围限制与下一步

基座 `scripts/build-xnu-4k-baseline.sh:41` 还会应用 `kits/NativePrelink/patches/*.patch`。其中 `xnu-10063.141.1-security-init.patch` 和 `xnu-10063.141.1-sparse-index.patch` **不在这次指定的 49 个内**；必须在实际切 feed 前纳入移植与累积验证，不能拿 38/49 替代完整构建兼容性结论。

1. 建立 8796 专用补丁覆盖，保留原始补丁哈希和逐 hunk 适配理由；所有写操作仅本仓，旧树只读。
2. 按基座真实顺序检查完整集（含 NativePrelink 两项），处理跨补丁依赖。当前未执行。
3. 审核 Darwin 22 的 driver/static archive/预链接接口后才形成可切换 feed 的提交；本次没有改 `feeds.toml`。
4. 板级配置仍需硬停审阅；未知 chip/board 身份、IPSW 组件哈希、LBA、prelink 数值、内存/bootimg 地址全部 TODO，不借 sheng/fuxi 数值填空。

本次没有构建、QEMU 执行、镜像生成或设备动作。WSL 枚举在当前沙箱返回 `Wsl/EnumerateDistros/Service/E_ACCESSDENIED`；本轮是 Windows Git 的文本补丁检查，不以此替代后续 WSL 构建。
