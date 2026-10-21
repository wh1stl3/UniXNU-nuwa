# P0 可行性探针报告

- 日期：2026-10-22
- 范围：只做输入准备与解析验证。**未编译内核、未生成镜像、未执行任何设备命令。**
- 试验树：`.work/tree-8796`（`xnu-8796.141.3`，`1b191cb58250d0705d8a51287127505aa4bc0789` 的完整副本，
  原树 `D:\Code\PortingiOS\common\sources\xnu-ios16-full` 未被修改，探针前后 `git status --porcelain` 均为 0）
- 脚本：`scripts/probe/patch_landing_audit.py`、`scripts/probe/donor_parse_probe.py`

## 1. 结论摘要

| 判据（交接文档 §5） | 通过标准 | 实测 | 判定 |
| --- | --- | --- | --- |
| 补丁 | 38 个里 ≥30 个落在预期函数；11 个有明确 rebase 方案 | 38/49 可 apply；已核对的落点无错位；11 个失败逐个定性 | **通过** |
| donor 解析 | NativePrelink 能读出 iOS16 kernelcache 元数据，或指出缺什么 | 用 UniXNU 自己的解析器读出 239 个 kext、5873 个导出符号 | **通过** |
| 页大小 | 给出 4K 与 16K 各自额外工作量，附证据 | 见 §4，与交接文档结论相反 | **通过** |
| 结论 | GO / NO-GO / CONDITIONAL + 单点风险 | **CONDITIONAL** | — |

## 2. 补丁栈对 8796 的可应用性

### 2.1 两种测法，同一结果

- 单打独斗（每个补丁单独对干净树 `git apply --check`）：**38 / 49**，失败 11。
- 顺序叠加（按 `scripts/build-xnu-4k-baseline.sh:36-46` 的真实顺序，
  `patches/xnu/*.patch` 全量 + `kits/NativePrelink/patches/*.patch` 2 个，累计 51 个）：**40 / 51**，失败 11。
  → 叠加没有救回任何一个，说明这 11 个是真实缺口，不是应用顺序问题。

两种测法得到的失败集合完全一致，与交接文档的"38 / 49、11 个失败"吻合。

### 2.2 11 个失败的定性（按可移植成本分档）

| # | 补丁 | 首个失败点 | 性质 | 难度 |
| --- | --- | --- | --- | --- |
| 1 | `zzx-pmap-sync-64bit-pa` | `osfmk/arm64/sptm/pmap/pmap.c` 不存在 | 8796 没有 SPTM 目录（SPTM 拆分晚于 8796）；**同名函数的 8796 半边可直接 apply** | **低**：丢掉 SPTM 那半，`osfmk/arm/pmap/pmap.c` 的 3 行照打（已验证） |
| 2 | `pgz-aligned-validation` | `zone_id_require_aligned()` 在 8796 不存在 | 目标函数是 10063 新增；8796 只有 `__pgz_decode` | **中**：需按意图重写（这是 zone 调试断言，非启动必需） |
| 3 | `published-freezer-condition` | 8796 的 `kern_memorystatus_freeze.c` 无 `XNU_TARGET_OS_WATCH` 分支 | 修的是 10063 里一处 `#if (A && || B)` 语法错误，8796 无此代码 | **中**：需先确认该文件在 8796 的结构 |
| 4 | `offline-owner-systemos-mount` | `bsd/kern/kern_exec.c:183`（`CoreEntitlements` 头） | 头文件迁移是 10063 特有；主体是 +252 行 owner Data 挂载函数 | **中**：主体可落，include 那 1 行要按 8796 的写法改写 |
| 5 | `zzy-native-gpu-addon-mount` | 依赖 #4 引入的 `native_owner_data_*` | 链式依赖，不是独立缺口 | **低**（等 #4） |
| 6 | `zzz-boot-progress` | 依赖 #5 与 `sleh.c` 改动 | 链式依赖 | **低**（等 #5） |
| 7 | `apple-only-cpu-tunables` | `osfmk/arm64/start.s:33` 上下文 | 上下文差异 | **中** |
| 8 | `external-archive-dependencies` | `makedefs/MakeInc.kernel:187` | 构建系统差异 | **中** |
| 9 | `native-aes-personality` | `iokit/KernelConfigTables.cpp:61` | 上下文差异（需先有 #8） | **中** |
| 10 | `public-entitlements-header` | `bsd/net/necp_client.c:68` | 上下文差异 | **中** |
| 11 | `source-machine-layer` | `config/MASTER.arm64.bcm2837:16`、`osfmk/conf/files.arm64:34` | 配置层差异 | **中** |

> 与交接文档的差别：文档说「`zzx-pmap-sync-64bit-pa`、`pgz-aligned-validation`、`offline-owner-systemos-mount`
> 是核心功能」，把 11 个一律记为「需 rebase，不可跳过」。实测更细：#1 其实是**最容易**的（一半不适用、一半照打）；
> #2/#3 属于「目标代码在 8796 不存在」，是**判断要不要移植**，不是 rebase；#5/#6 是 #4 的下游，会随 #4 一起解。
> 真正需要动脑的只有 #4 与 #7–#11 的上下文适配。

### 2.3 落点是否发生语义漂移

`git apply` 不允许 fuzz、只允许整体偏移，所以"apply 成功"本身就意味着上下文**逐字节**匹配。
剩余风险只有一种：上下文恰好重复出现在邻近函数里。为此统计了 102 个 hunk 的落点偏移：

| 每个补丁的最大偏移 | 补丁数 |
| --- | --- |
| 0 行 | 9 |
| 1–50 行 | 16 |
| 51–100 行 | 8 |
| >100 行 | 5 |

偏移 >100 行的 hunk 共 7 个，全部是**负偏移**（落在比 10063 更早的行），原因一致：
8796 是更早的树，同一段代码前面少了若干行。逐个人工核对结论：

- `offline-legacy-start`: `bsd_init.c` 1282→1096，补丁头自带 `@@ ... bsd_autoconf(void)`，落点在 `bsd_autoconf` 内 ✓
- `offline-owner-z-air-init`: `kern_exec.c` 7400→6884，落点在 `load_init_program` 内（补丁改的是 launchd_suffix 那段）✓
- `null-root-media`: `IOService.cpp` 5257→5178，落点在 `IOService::setRootMedia` 内 ✓
- `mockfs-statfs`: `mockfs_vfsops.c` 286→225，新增的 `mockfs_getattr` 插在 `mockfs_sync` 之后，位置合法 ✓
- `non-apple-iommu-bootstrap`、`offline-native-gpu-broker`、`offline-pgz-alignment-probe`：落点函数与作者处一致 ✓

**结论：38 个可 apply 的补丁中，没有任何一个确认落错函数。** 剩余的语义正确性只能靠编译与运行时验证，P0 不做。

## 3. donor 解析（P0 §5 第 6 步）

### 3.1 输入

本地已有 iOS 16.7.16 donor，无需联网：

- `common/cache/donor-ios16/` 对应 iPhone X（iPhone10,3 / d22ap / 20H392）
- `kernelcache.release.iphone10b` 18,204,358 B，`sha256 2d6a13d040aaf87cec09bb6906d43e9bd8cea951e43d1aa1cd62707dfdc5aaec`
- 上一个会话已解出裸 Mach-O：`nuwa/artifacts/ios16-donor-inspection/20261020T115253317035Z/original-iphone-kernelcache.macho`
  50,937,856 B，`sha256 2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221`

### 3.2 用 UniXNU 自己的解析器复验（不是复述旧报告）

`scripts/probe/donor_parse_probe.py` 直接 import `kits/NativePrelink/native_prelink.py`，
调用它自己的 `macho()` / `exports()` / `unserialize_xml()`：

```
parser          OK            （native_prelink.macho 接受该镜像）
filetype        2             （MH_EXECUTE）
load_commands   25
base_vmaddr     0xfffffff007004000
version         Darwin Kernel Version 22.6.0 ... root:xnu-8796.142.1.703.8~1/RELEASE_ARM64_T8015
export_symbols  5873
prelink_info    __PRELINK_INFO/__info, 3,309,568 B
                parsed_by = unixnu.unserialize_xml
                kext_count = 239
```

三个高价值信号：

1. **基址完全对齐**：donor `__TEXT` 基址 `0xfffffff007004000` ==
   `build-xnu-4k-baseline.sh:748` 的 `ARM64_LINK_ADDR`。不是巧合，是同一个链接地址约定。
2. **普通 arm64，不是 arm64e**：A11 的 kernelcache 是 `arm64` 子类型，
   所以选 iPhone X 当 donor 避免了"内核要按 arm64e 编译"这一整类问题。doc 的 donor 选型得到证据支持。
3. **239 个 kext、5873 个导出符号可枚举**：prelink 阶段的输入是完整的，不存在"解析不了"的阻塞。

### 3.3 一个尚未验证、但比页大小更早卡住的点

donor 内核是 `8796.142.1.703.8`，本地源码树是 `8796.141.3` —— **不是同一个 build**。
239 个 kext 要与我们的内核符号表对接；如果某个 kext 需要 141.3 没导出的符号，prelink 会失败。
这个检查必须先有内核 export 表，属于下一阶段的第一件事，见 §5。

## 4. 4K 还是 16K：与交接文档结论相反

### 4.1 交接文档的说法

- 4K：`native-4k-*` 三件套，上游已用真机验证，工作量"顺路"；风险是签名哈希桥接单点。
- 16K：只是 `#define __ARM_16K_PG__ 1` 一行，但"要把 4K 补丁**反过来改**"。

### 4.2 实测：16K 不需要反改任何补丁

`native-4k-bootstrap-capacity.patch` 与 `native-4k-user-abi.patch` 的每一处页大小分支都长这样：

```c
 #define BOOTSTRAP_TABLE_SIZE (ARM_PGBYTES * 34)
+#elif !defined(APPLE_ARM64_ARCH_FAMILY) && !__ARM_16K_PG__
+/* Native 4 KiB: ... */
+#define BOOTSTRAP_TABLE_SIZE (ARM_PGBYTES * 16)
 #else /* defined(ARM_LARGE_MEMORY) */
```

即：4K 支持是插在既有 `#if/#else` 链里的一个分支，**定义 `__ARM_16K_PG__` 就自动回落到原来的 16K 分支**。
`native-4k-signature-hash-cache` 则由构建期 `XNU_NATIVE_CS_HASH_CACHE=0` 关掉，结构体追加的字段在 16K 下无害。

所以两种路线的真实代价：

| | 4K | 16K |
| --- | --- | --- |
| 补丁动作 | 三件套保持启用（默认行为） | 定义 `__ARM_16K_PG__`，三件套自动编译掉 |
| 反改工作量 | 0 | **0**（交接文档说的"反过来改"不存在） |
| 与 donor 的一致性 | 不一致：donor 内核与 239 个 kext 全是 16K 产物，靠 `native-4k-signature-hash-cache` 桥接 | 一致：不需要任何桥接 |
| 主要风险 | 签名哈希桥接是静默失败型单点（交接文档风险 #3） | 无对应风险 |
| 上游验证 | sheng 上真机验证过 | 未在本项目跑过 |

### 4.3 建议

**建议选 16K，即反转交接文档的默认值。** 理由：

1. 我们要跑的是 iOS 16 用户态 + 239 个 Apple kext，它们**全部**是 16K 原生产物。
   选 16K 直接从风险清单里划掉"签名哈希桥接静默失败"这一条，而这是文档自己列的最难定位的风险。
2. "16K 要把 4K 补丁反过来改"这个成本项经查不存在，文档给出的 4K 优势因此少了一半。
3. 4K 剩下的唯一优势是"上游在 sheng 上真机验证过"，但那验证的是 4K 内核**自身**能起，
   不是 4K 内核 + iOS 用户态能起；而我们恰恰卡在后半段。

会被推翻的情形：如果后续发现 nuwa 的某段板级/驱动代码（UFS、SMMU、Adreno 的页表假设）
在 16K 下不成立，或 sheng 的已验证配置里 4K 之外的部分与 16K 冲突，则回退到 4K。

## 5. 下一步（最便宜的一件事）

**先验 §3.3 的符号覆盖，再谈页大小落地。**

1. 用 `8796.141.3` 走一次 `make installhdrs` + 只编到能产出 export 表的程度（不生成可引导镜像），
   得到内核导出符号集；
2. 用 `native_prelink.py` 的 `plan()` 把它与 donor 的 239 个 kext 的未决符号比对，
   输出缺符号清单；
3. 缺符号清单为空 → 页大小分歧基本不影响可行性，按 §4.3 建议选 16K，进入第二阶段；
   缺符号清单非空 → 先补符号（多半是 141.3 缺 142.1 的新导出），页大小顺延。

这一步仍然不产生镜像、不碰设备，但需要一次真实编译，属于 P0.5，**要用户点头**。
