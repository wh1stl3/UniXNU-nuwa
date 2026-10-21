# 交接：以 UniXNU 为底座改造 nuwa 跑 iOS

> 来源：`D:\Code\PortingiOS\docs\handoff-unixnu-route-2026-10-22.md`（2026-10-22 01:33 原件，仅拷入，不再改）。
> 原文写「工作目录 `D:\Code\PortingiOSWithUniXNU`」，**该目录已废弃**；现行工作目录是本仓库 `D:\Code\UniXNU-nuwa`，其余内容仍然有效。
> 与 `AGENTS.md` 冲突时以 `AGENTS.md` 为准。
> **2026-10-22 03:00 追加**：本文写于 01:33，当时还不知道官方移植指南。现行权威是
> `docs/inherited/unixnu-official-2026-10-22.md`（官方 porting/devices 摘录）+ `docs/DECISIONS.md` D-002/D-003。
> 本文里「4K/16K 岔路」「三段式架构」等表述以官方文档为准重新对齐，冲突时以官方为准。

交付对象：**WorkBuddy 新会话**
编写：宿主会话，2026-10-22 01:33 CST
状态：**方向已由用户确认，尚未开始动手。本文不含任何已执行的构建或设备动作。**

---

## 0. 一句话目标

**把 UniXNU 当作底座，改造使小米 13 Pro（nuwa，SM8550）运行 iOS 16**，而不是继续在自建 P16 链路上加补丁。

用户原话：

> 我的目标是复用 unixnu 并改造为 nuwa 跑 iOS。

## 0.5 如何开始（WorkBuddy 新会话读到这里）

你在一个**全新的 WorkBuddy 会话**里，没有任何上文。按以下顺序启动，不要先问用户重复确认：

1. 工作目录设为 `D:\Code\PortingiOSWithUniXNU`；**目录不存在就自己新建**（这是你要做的第一件事，用户明确要求由新会话来建）。
2. 建 `docs/STATUS.md`、`docs/WORKLOG.md`，把本文的 §7 风险与 §9 禁令抄进去。
3. 按 §5 执行第一阶段探针。**探针只做输入准备，不编译内核、不生成镜像、不碰设备。**
4. 完成后按 §10 格式汇报，并就 §4 的 4K/16K 岔路给出带证据的建议，等用户拍板。
5. 重活（长时间编译、CI）可以交给 Codex CLI，也可以自己跑；但**判断与汇报由你负责**，不要把结论外包。

**不要做的事**：不要修改 `D:\Code\PortingiOS`；不要在没有 §5 结论前开始大规模 rebase；不要碰设备。

## 1. 工作目录约定

**新建**：`D:\Code\PortingiOSWithUniXNU`（与 `D:\Code\PortingiOS` 同级）

> ⚠️ **大小写必须严格照抄。** Windows 不敏感，但本项目的构建全在 WSL 里跑，`/mnt/d/Code/...` **区分大小写**；写成 `portingioswithunixnu`、`PortingIosWithUnixnu` 之类会直接 `No such file or directory`，而且报错位置常常离真正原因很远。
>
> 命名依据：前缀沿用现有仓库 `PortingiOS` 的写法，后缀用上游官方写法 `UniXNU`。同理，引用的上游目录也必须按真实大小写：`UniXNU`、`UniXNU-sheng`、`xnu-ios16-full`、`ios-sweet`（`ios-sweet` 是全小写，不要写成 `iOS-Sweet`）。

规则：

- 新仓库里做所有实际工作：构建脚本、补丁、配置、报告、提交。
- `D:\Code\PortingiOS` **只读参照**，不得修改、不得在其中提交。它是旧路线（自建 P16 链路）的存档，同时存放所有上游源码副本。
- 新仓库建议第一次提交就把 `docs/STATUS.md`、`docs/WORKLOG.md`、`AGENTS.md` 建起来，规则沿用旧仓的纪律（见 §8）。
- 上游源码**不要复制**进新仓库，用路径引用或符号链接：
  ```
  D:\Code\PortingiOS\common\sources\UniXNU          # 框架 + 驱动 + 49 个内核补丁
  D:\Code\PortingiOS\common\sources\UniXNU-sheng    # SM8550 板级（同 SoC！）
  D:\Code\PortingiOS\common\sources\xnu-ios16-full  # XNU 8796 树
  D:\Code\PortingiOS\common\sources\ios-sweet       # 81 个 iOS16 人格补丁
  ```

## 2. 为什么换这条路线（宿主实测，不是推断）

### 2.1 UniXNU 的补丁大部分能吃下 8796

在 `xnu-ios16-full`（8796）树上逐个 `git apply --check` UniXNU 的 49 个补丁：

```
可 apply: 38 / 49
失败: 11
```

失败的 11 个（需 rebase，**不可跳过**）：

```
apple-only-cpu-tunables.patch        external-archive-dependencies.patch
native-aes-personality.patch         offline-owner-systemos-mount.patch
pgz-aligned-validation.patch         public-entitlements-header.patch
published-freezer-condition.patch    source-machine-layer.patch
zzx-pmap-sync-64bit-pa.patch         zzy-native-gpu-addon-mount.patch
zzz-boot-progress.patch
```

其中 `zzx-pmap-sync-64bit-pa`、`pgz-aligned-validation`、`offline-owner-systemos-mount` 是核心功能。

⚠️ **`git apply` 成功不等于语义正确**：context 可能落到相邻函数上。38 个必须逐个核对落在哪一行。

### 2.2 UniXNU 有完整开源驱动，这是最大的价值

| 目录 | 文件数 | 行数 | 内容 |
| --- | --- | --- | --- |
| `drivers/NativeUfs` | 21 | 3,712 | UFS 存储 |
| `drivers/NativeAdreno` | 82 | 8,875 | GPU |
| `drivers/NativeMobileDisplay` | 7 | 998 | 显示 |
| `kits/ArmSmmu4K` | 23 | 2,662 | SMMU |
| `kits/AdrenoFirmware`, `AdrenoPM4` | — | — | GPU 固件/命令流 |

`NativeUfs` 只依赖标准 IOKit KPI（`IOService` / `IOMemoryDescriptor` / `IOBlockStorageDevice` / `IOLib`），**无版本绑定 API**，跨 8796/10063 成本可控。

### 2.3 sheng 与 nuwa 同 SoC

`UniXNU-sheng/board.toml`：

```toml
name = "sheng"
soc  = "SM8550"
description = "Xiaomi Pad 6S Pro"
```

SoC 级资源（GIC、timer、UFS、SMMU、DVFS 时钟树）大概率可复用；板级外设（屏幕、触控 IC、GPIO）必须换 —— sheng 是平板，nuwa 是手机。

### 2.4 版本是参数化的，不是硬编码

`UniXNU/feeds.toml` 开头注释：

> Everything that depends on the Darwin version is set here and passed to the kernel scripts.

```toml
[[source]]
name = "xnu"
ref = "xnu-10063.141.1"
darwin = "23.6.0"
version = "10063.141.1"
trustcache_tag = "xnu-8796.101.5"    # 已经在用 8796 的 TrustCache 头
```

### 2.5 两套补丁零重叠 —— 这是最容易踩的坑

| | 补丁数 | 内核 | 页大小 | donor | 目标机器 |
| --- | --- | --- | --- | --- | --- |
| `ios-sweet` | **81** | 8796 | 16K | iOS 16.7.16 | SM7150 手机 |
| `UniXNU` | 49 | 10063 | 4K | iPadOS 17.7.11 | SM8550 平板 |

按文件名比对，**同名的 0 个**。因为两者解决同一问题的哲学不同：

- **sweet**：伪装成 Apple 平台（machine = SWEET），代价是大量 AMFI / AKS / BearSSL / entitlements 补丁（81 个里大半是这些），换来 iOS 用户态能跑。
- **UniXNU**：不伪装，提供 native 驱动 + `OWNER_*` 用户态挂载 + mockfs + trust cache。

**结论：不能二选一，必须组合。**

## 3. 目标架构（三段式）

```
骨架   UniXNU：build driver + UEFI(sheng, 同 SoC) + 驱动(UFS/Adreno/Display/SMMU) + prelink
        ↓
内核   XNU 8796 + sweet 的人格补丁主干（iOS 16 用户态需要）+ UniXNU 中能套的 38 个
        ↓
衔接   BootArgs 736 字节 + 我们的 entry stub（已在 nuwa 真机跑通）
```

旧仓库里这些已经完成、**可直接借鉴不要重做**：

| 资产 | 位置 | 状态 |
| --- | --- | --- |
| P16 boot_args 736 字节布局适配 | `PortingiOS/nuwa/` 相关补丁 | 已完成 |
| 自定义入口 stub + UTS 同次回传 | `f467359`、`nuwa/diagnostics/` | **真机已验证** |
| 恢复路径实测（C1/C2） | `docs/operations/2026-10-22-nuwa-recovery-path-verification.md` | 真机已验证 |
| ABL 入口 x0 = 0xB5DB1000 | 同上 | 真机已验证 |
| 16K MMU 候选镜像 | `nuwa/artifacts/mmu16/…/nuwa-mmu16-v4.img` | QEMU 通过，实机未跑 |

## 4. 必须先拍的一条：4K 还是 16K

| | 4K（UniXNU 路线，**建议默认**） | 16K（sweet 路线） |
| --- | --- | --- |
| 内核补丁 | `native-4k-*` 三件套，**上游已用真机验证过** | `#define __ARM_16K_PG__ 1` 一行 |
| 与 iOS donor(16K) | 靠 `native-4k-signature-hash-cache` 桥接 | 天然一致 |
| 工作量 | 顺路，直接用 | 要把 4K 补丁**反过来改** |
| 风险 | 签名哈希桥接是单点，错了静默失败 | 无 |

**决定权在用户。** 在 §5 的可行性试验出结论前，不要擅自锁定页大小；报告里必须明确写的哪一档。

## 5. 第一阶段任务（P0）：可行性探针，不编译内核

目的：用最便宜的方式回答三个问题，**不产生任何镜像、不碰设备**。

### 步骤

1. 建目录 `D:\Code\PortingiOSWithUniXNU`，按 §1 建 `docs/STATUS.md`、`docs/WORKLOG.md`。
2. 把 UniXNU 的 `feeds.toml` 复制一份到新仓库，做**只改配置**的试验副本：
   - `xnu`: `ref`/`commit`/`version` 指向 **8796.141.3**（本地树 `xnu-ios16-full`，不必联网拉）
   - `darwin`: 改为 **22.6.0**
   - donor/IPSW: 指向 **iPhone X / iOS 16.7.16**
3. 只跑**输入准备**阶段（source checkout + patch apply + donor 解析），**不进入内核编译**。
4. 对 38 个"能 apply"的补丁逐个记录：**落在哪个文件哪一行**，并标注是否落在预期函数里。
5. 对 11 个失败补丁，逐个给出 rebase 难度评估：只差行号 / 差上下文 / 目标代码已重构。
6. 跑一次 UniXNU 的 `NativePrelink`，看它能否解析 iOS 16.7.16 的 donor 镜像结构。

### 判据（写入报告）

| 项 | 通过标准 |
| --- | --- |
| 补丁 | 38 个里 ≥30 个落在预期函数；11 个里有明确 rebase 方案 |
| donor 解析 | `NativePrelink` 能读出 iOS16 kernelcache 的元数据，或明确指出缺什么 |
| 页大小 | 给出 4K 与 16K 各自的额外工作量，附证据 |
| 结论 | 给出 `GO` / `NO-GO` / `CONDITIONAL`，并说明单点风险 |

**这一阶段禁止**：编译完整内核、生成固件镜像、任何设备命令。

## 6. 后续阶段的顺序（等 §5 结论再细化）

1. 补丁合并与去重（sweet 81 + UniXNU 38，按功能去重，不是按文件名）
2. 8796 + 4K（或 16K）内核编译通过（CI，与旧仓同法）
3. sheng 板级 → nuwa 板级（SoC 部分继承，外设替换）
4. 驱动接入：先 `NativeUfs`（3.7k 行、依赖最干净），再 Display，再 SMMU，最后 Adreno（8.9k 行）
5. 与旧仓已完成件对接：BootArgs 736、entry stub、恢复路径

## 7. 已知风险（务必写进 STATUS）

1. **容器版本**：旧仓构建的是 v1 候选，设备原镜像是 v4；ABL 是否接受未验证。
2. **内存所有权**：28 个动态 reserved 节点实际分配未知；只能证明"避开已知冲突"，不能证明"ABL 交接时归我们"。
3. **4K 签名桥接**：`native-4k-signature-hash-cache` 一旦有偏差，表现为 App 静默起不来，无 panic，极难定位。
4. **sheng 是平板**：屏幕/触控/GPIO 不可复用，别照抄。
5. **补丁语义漂移**：`git apply` 成功但落错函数，编译通过、行为错。

## 8. 纪律（沿用旧仓，不得放松）

- 改动以下四类前**必须写 `docs/NEED-REVIEW.md` 并直接向用户确认**，不得自行执行：
  1. 修改任何 `bringup-plan.json`
  2. 任何 `fastboot boot` / `flash` / `erase` / 切槽 / `adb reboot`
  3. 新建或重写任何诊断/固件镜像
  4. 把任何 `*_verified` 置为 `true`
- 只差用户按实体键的项 → 写 `docs/PENDING-HUMAN.md` 记为待办，**继续下一项**，不要整轮停工。
- 每个里程碑往 `docs/WORKLOG.md` 追加一行。
- 结论必须带证据（文件:行号、命令输出、哈希），**模拟器/QEMU 结果不得写成实机通过**。
- 不修改 `D:\Code\PortingiOS`。
- 如果用户暂时离开，不要空转造产出：把待确认项写清楚就停下。

## 9. 明确不要做的事

- 不要为了"跑通"去伪装成 Apple 设备身份（sweet 那条路的副作用），除非有明确证据说明必要且写清代价。
- 不要在没有 §5 结论时就开始大规模 rebase 或编译。
- 不要把 sheng 的板级配置直接套到 nuwa（平板 ≠ 手机）。
- 不要用旧仓的 `nuwa-mmu16-v4.img` 去验证这条新路线（它是 P16 链路的产物）。
- 不要删除或覆盖 `D:\Code\PortingiOS` 里的任何东西。

## 10. 汇报格式

第一次汇报请按此结构，不要写成散文：

```
目录: <是否已建，路径>
探针结果:
  补丁 apply: 38/49（复核后 n/49）
  落错位置的补丁: <列表>
  11 个失败: <每个一行，rebase 难度>
  donor 解析: <成功/失败 + 缺什么>
页大小: 4K 额外 <...> / 16K 额外 <...>
结论: GO | NO-GO | CONDITIONAL
单点风险: <1-3 条>
下一步: <最便宜的一个动作>
```
