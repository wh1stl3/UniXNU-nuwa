# r35l 候选清单与官方差距（2026-11-21）

状态：self-checked，静态包内数据；非运行时观测、非认证。未构建、未操作设备。
对照本地 UniXNU `693f5d9cae8a408dd18b39f3f9fdc4228c934241`
的 `docs/zh/porting/{device-tree,platform,steps}.md`；条件项不当作无条件必需。

## 包身份

- outer SHA-256：`14a3bc83eb416b6eb318cd92b89d597b1214f0330567b5133f410fa502f5523e`
- FAT SHA-256：`58a380d5154515ffb47d1f609314b2dadd4efc36195b1e5c698beee1c79730ad`
- kernel SHA-256：`e969f5e55ab8e4ad3c279e37a7a38820fac4243ff57ae4c30ef5a57d44418d9e`
- derived ADT SHA-256：`d96d229015c04db7ef307428ae6fe8115087c5c639bcea074f4672f51f13528f`

来源 `out/nuwa-r35l-regs-package-20261121/{outer-record,record}.json`；
outer readback 是既有审计记录，非本次重新提取。静态 ADT 占位符不等于运行时填充值。

## 实际 boot-args

```text
-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1 build-tag=nuwa-r35 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024
```

来自包内 `unixnu.toml`，`initrd = "Payloads/scratch-data.img"`。

## CHMH

`/chosen/boot-manifest-hash` 为 48 字节 SHA-384
`861d5e2fdd9ea6324fdd4cffee84cf7143b5615ea50bdc2d3a737dd0fac17555607da57b91e058d84071a32b4922f21f`。
`record.json` 的 `material_hex` 包含域 `Nuwa.HostBootSetIdentity.v1`，按顺序绑定以下有标签的 SHA-256：

| 输入 | SHA-256 |
|---|---|
| kernel | `e969f5e55ab8e4ad3c279e37a7a38820fac4243ff57ae4c30ef5a57d44418d9e` |
| loader | `692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5` |
| trust | `eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3` |
| args | `8de5c7dd84a0c3fb3f949dadef2770d3a0ff017df489d22de3c1ee22b9c86e36` |
| parent-adt | `885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4` |

parent-adt 是派生前 ADT，不是最终 ADT；seed/config/FAT 有独立哈希记录，但不在所列 CHMH material 内。
BNCH 是另一属性，不等同 CHMH。此身份为主机实验值，认证 NOT REACHED，不是 Apple 签名或硬件认证。

## 官方逐项对照

“有”表示包内存在及可检查宽度，不证明硬件值正确或服务运行。

| 要求 | 状态 | 实际与边界 |
|---|---|---|
| `/chosen` | 有 | 节点存在 |
| random-seed 64 字节 | 值不符 | 实际 256 字节；目标消费者是否接受未验证 |
| unique-chip-id u64 / chip-id u32 | 有 | 宽度 8/4；唯一 ID 脱敏，正确来源未核对 |
| osenvironment | 有 | main |
| dram-base / dram-size u64 | 有 | 各 8 字节；未对照实际 UEFI RAM/保留区 |
| NVRAM proxy 四属性 | 有 | size=8192、count=1、current=0、data=8192；CHRP 与校验待验证 |
| crypto-hash-method / root-matching | 有 | sha2-384、171 字节；字典语义未核对 |
| ephemeral-storage | 缺 | 仅适用临时 Data 策略 |
| darwinboot-memory-size | 有 | 1 GiB，在官方区间内 |
| amfi-only-platform-code / boot-manifest-hash | 有 | 1 / 48 字节；后者为未认证实验 CHMH |
| memory-map TrustCache | 有 | 16 字节全零占位；trust sidecar 有数据，运行时是否填充未证 |
| memory-map PackedRAMDisk | 有 | 16 字节全零占位；运行时是否填充未证 |
| memory-map RAMDisk | 缺 | dense 输入的条件项，本包为 packed 输入 |
| `/cpus` 与 CPU 属性 | 有 | cpu0–cpu7 均有 reg/state/device_type/compatible/timebase-frequency；SMP 未证 |
| `/psci` | 有 | 存在；次核和 IPI 未验证 |
| `/arm-io` | 有 | 有 address/size cells 与 ranges；硬件映射未验证 |
| `/defaults`、`/options` | 有 | options 仅 name；平台默认策略未验证 |
| `/product`、`/buttons` | 缺 | product 有，buttons 缺；官方未列为 configure 顶层必需 |
| 显示服务 | 缺 | 现有记录为 GopFramebuffer 未接；并非单凭 ADT 判定 |
| VerifiedRoot / 信任 | 值不符 | 认证 NOT REACHED；零占位不能证明运行时 trust 指针的值 |
| 固件内存与 DMA | 缺 | 未核实 UEFI 内存所有权、DMA/IOVA 与 SMMU |
| OS ABI / 归档与运行 | 缺 | prelink 有记录，但 ABI/runtime 未 qualify |

## 对显示或 SpringBoard 的影响

- GopFramebuffer 服务缺口直接阻止 UI；诊断色带不等于显示服务。`display-scale` 与 product artwork
  描述显示，但存在不证明匹配成功。
- 官方说明 identity 缺失可导致 `gethostuuid()` 等待；本包 identity 属性存在，不能据此解释 SIGTRAP。
  product 和缺失的 buttons 被 MobileGestalt/平台消费，影响路径尚需实证。
- trust/AMFI 和数据卷可能影响用户态启动；实验策略和占位符不能证明 SpringBoard SIGTRAP 的原因。

## prelink

当前 board.toml stage-5 基线 roots（不是 r35l 实际 roots）：

```text
com.apple.AppleFSCompression.AppleFSCompressionTypeZlib
com.apple.driver.AppleARMPlatform
com.apple.driver.AppleARMWatchdogTimer
com.apple.driver.AppleAudioClockLibs
com.apple.driver.AppleEffaceableStorage
com.apple.driver.AppleIISController
com.apple.driver.AppleM2ScalerCSCDriver
com.apple.driver.AppleMobileFileIntegrity
com.apple.driver.ApplePMGR
com.apple.driver.IODARTFamily
com.apple.iokit.CoreAnalyticsFamily
com.apple.iokit.IOAudio2Family
com.apple.iokit.IOCECFamily
com.apple.iokit.IOCryptoAcceleratorFamily
com.apple.iokit.IOGPUFamily
com.apple.iokit.IOHDCPFamily
com.apple.iokit.IOReportFamily
com.apple.iokit.IOSlowAdaptiveClockingFamily
com.apple.iokit.IOStorageFamily
com.apple.iokit.IOSurface
com.apple.kec.corecrypto
com.apple.kec.pthread
com.apple.kext.AppleMatch
com.apple.kext.CoreTrust
com.apple.security.AppleImage4
com.apple.security.sandbox
com.apple.iokit.IOHIDFamily
com.apple.iokit.IOHIDEventDriver
```

历史 APFS 构建保存的显式 roots；不能单凭该文件断言是 r35l 实际 roots：

```text
com.apple.AppleFSCompression.AppleFSCompressionTypeZlib
com.apple.driver.AppleARMPlatform
com.apple.driver.AppleARMWatchdogTimer
com.apple.driver.AppleAudioClockLibs
com.apple.driver.AppleEffaceableStorage
com.apple.driver.AppleIISController
com.apple.driver.AppleM2ScalerCSCDriver
com.apple.driver.AppleMobileFileIntegrity
com.apple.driver.ApplePMGR
com.apple.driver.IODARTFamily
com.apple.iokit.CoreAnalyticsFamily
com.apple.iokit.IOAudio2Family
com.apple.iokit.IOCECFamily
com.apple.iokit.IOCryptoAcceleratorFamily
com.apple.iokit.IOGPUFamily
com.apple.iokit.IOHDCPFamily
com.apple.iokit.IOReportFamily
com.apple.iokit.IOSlowAdaptiveClockingFamily
com.apple.iokit.IOStorageFamily
com.apple.iokit.IOSurface
com.apple.kec.corecrypto
com.apple.kec.pthread
com.apple.kext.AppleMatch
com.apple.kext.CoreTrust
com.apple.security.AppleImage4
com.apple.security.sandbox
com.apple.iokit.IOHIDFamily
com.apple.iokit.IOHIDEventDriver
com.apple.filesystems.apfs
```

r35l prelink.json 不记录 roots，记录最终 components（含传递依赖，不能冒充 roots）；实际 roots 完整清单尚未闭合。候选实际 components：

```text
com.apple.AppleFSCompression.AppleFSCompressionTypeZlib
com.apple.driver.AppleARMPlatform
com.apple.driver.AppleARMWatchdogTimer
com.apple.driver.AppleAudioClockLibs
com.apple.driver.AppleEffaceableStorage
com.apple.driver.AppleIISController
com.apple.driver.AppleM2ScalerCSCDriver
com.apple.driver.AppleMobileFileIntegrity
com.apple.driver.ApplePMGR
com.apple.driver.IODARTFamily
com.apple.filesystems.apfs
com.apple.iokit.CoreAnalyticsFamily
com.apple.iokit.IOAudio2Family
com.apple.iokit.IOCECFamily
com.apple.iokit.IOCryptoAcceleratorFamily
com.apple.iokit.IOGPUFamily
com.apple.iokit.IOHDCPFamily
com.apple.iokit.IOHIDFamily
com.apple.iokit.IOReportFamily
com.apple.iokit.IOSlowAdaptiveClockingFamily
com.apple.iokit.IOStorageFamily
com.apple.iokit.IOSurface
com.apple.kec.corecrypto
com.apple.kec.pthread
com.apple.kext.AppleMatch
com.apple.kext.CoreTrust
com.apple.security.AppleImage4
com.apple.security.sandbox
```

## derived ADT 属性清单

ADT 不携带通用类型标签；type 为字节形态分类，hex 是原始字节。random-seed、unique-chip-id、NVRAM bank 可能含设备身份或种子，按规则不入库；原值只在本地 out/derived.adt。

| 节点 | key | type | 字节 | value |
|---|---|---|---:|---|
| `/` | `name` | NUL strings | 12 | `"device-tree\u0000"` |
| `/` | `compatible` | NUL strings | 30 | `"D22AP\u0000xiaomi,nuwa\u0000qcom,sm8550\u0000"` |
| `/` | `#address-cells` | binary hex | 4 | `02000000` |
| `/` | `#size-cells` | binary hex | 4 | `02000000` |
| `/` | `model` | NUL strings | 11 | `"iPhone10,3\u0000"` |
| `/` | `target-type` | NUL strings | 4 | `"D22\u0000"` |
| `/chosen` | `name` | NUL strings | 7 | `"chosen\u0000"` |
| `/chosen` | `random-seed` | binary redacted | 256 | `redacted sha256 1c7e573e88e23dfa83ef8becdd8f897bfd922a8121ba9ccddc4df0d16ee1d559` |
| `/chosen` | `dram-base` | binary hex | 8 | `000000c008000000` |
| `/chosen` | `dram-size` | binary hex | 8 | `0000004002000000` |
| `/chosen` | `nvram-bank-size` | NUL strings | 4 | `"\u0000 \u0000\u0000"` |
| `/chosen` | `nvram-bank-count` | binary hex | 4 | `01000000` |
| `/chosen` | `nvram-current-bank` | NUL strings | 4 | `"\u0000\u0000\u0000\u0000"` |
| `/chosen` | `nvram-proxy-data` | binary redacted | 8192 | `redacted sha256 3c6e675b2f28d917c292a325131c6c868d6ddb82ed8a74fd90c607cdb7fb3525` |
| `/chosen` | `unique-chip-id` | binary redacted | 8 | `redacted` |
| `/chosen` | `chip-id` | binary hex | 4 | `dbb8ca4a` |
| `/chosen` | `darwinboot-memory-size` | NUL strings | 8 | `"\u0000\u0000\u0000@\u0000\u0000\u0000\u0000"` |
| `/chosen` | `osenvironment` | NUL strings | 5 | `"main\u0000"` |
| `/chosen` | `crypto-hash-method` | NUL strings | 9 | `"sha2-384\u0000"` |
| `/chosen` | `certificate-production-status` | NUL strings | 4 | `"\u0000\u0000\u0000\u0000"` |
| `/chosen` | `effective-production-status-ap` | NUL strings | 4 | `"\u0000\u0000\u0000\u0000"` |
| `/chosen` | `certificate-security-mode` | binary hex | 4 | `01000000` |
| `/chosen` | `effective-security-mode-sep` | binary hex | 4 | `01000000` |
| `/chosen` | `amfi-only-platform-code` | binary hex | 4 | `01000000` |
| `/chosen` | `mix-n-match-prevention-status` | NUL strings | 4 | `"\u0000\u0000\u0000\u0000"` |
| `/chosen` | `boot-manifest-hash` | binary hex | 48 | `861d5e2fdd9ea6324fdd4cffee84cf7143b5615ea50bdc2d3a737dd0fac17555607da57b91e058d84071a32b4922f21f` |
| `/chosen` | `root-matching` | NUL strings | 171 | `"<dict><key>IOProviderClass</key><string>IOMedia</string><key>IOPropertyMatch</key><dict><key>UUID</key><string>DADD93F8-DBBF-4B17-A1DF-0F11E64172F7</string></dict></dict>\u0000"` |
| `/chosen` | `display-scale` | binary hex | 4 | `03000000` |
| `/chosen/memory-map` | `name` | NUL strings | 11 | `"memory-map\u0000"` |
| `/chosen/memory-map` | `TrustCache` | NUL strings | 16 | `"\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000"` |
| `/chosen/memory-map` | `PackedRAMDisk` | NUL strings | 16 | `"\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000"` |
| `/chosen/manifest-properties` | `name` | NUL strings | 20 | `"manifest-properties\u0000"` |
| `/chosen/manifest-properties` | `BNCH` | binary hex | 48 | `48a52bb4b176c8c6d156262eb1abb626cf1b8e16afec6d8839b0f5eb1e8bad05c2ba46d971f5ba7febfa0caf374a60ec` |
| `/cpus` | `name` | NUL strings | 5 | `"cpus\u0000"` |
| `/cpus/cpu0` | `name` | NUL strings | 5 | `"cpu0\u0000"` |
| `/cpus/cpu0` | `reg` | NUL strings | 4 | `"\u0000\u0000\u0000\u0000"` |
| `/cpus/cpu0` | `state` | NUL strings | 8 | `"running\u0000"` |
| `/cpus/cpu0` | `device_type` | NUL strings | 4 | `"cpu\u0000"` |
| `/cpus/cpu0` | `compatible` | NUL strings | 16 | `"arm,cortex-a510\u0000"` |
| `/cpus/cpu0` | `timebase-frequency` | binary hex | 4 | `00f82401` |
| `/cpus/cpu1` | `name` | NUL strings | 5 | `"cpu1\u0000"` |
| `/cpus/cpu1` | `reg` | binary hex | 4 | `00010000` |
| `/cpus/cpu1` | `state` | NUL strings | 8 | `"waiting\u0000"` |
| `/cpus/cpu1` | `device_type` | NUL strings | 4 | `"cpu\u0000"` |
| `/cpus/cpu1` | `compatible` | NUL strings | 16 | `"arm,cortex-a510\u0000"` |
| `/cpus/cpu1` | `timebase-frequency` | binary hex | 4 | `00f82401` |
| `/cpus/cpu2` | `name` | NUL strings | 5 | `"cpu2\u0000"` |
| `/cpus/cpu2` | `reg` | binary hex | 4 | `00020000` |
| `/cpus/cpu2` | `state` | NUL strings | 8 | `"waiting\u0000"` |
| `/cpus/cpu2` | `device_type` | NUL strings | 4 | `"cpu\u0000"` |
| `/cpus/cpu2` | `compatible` | NUL strings | 16 | `"arm,cortex-a510\u0000"` |
| `/cpus/cpu2` | `timebase-frequency` | binary hex | 4 | `00f82401` |
| `/cpus/cpu3` | `name` | NUL strings | 5 | `"cpu3\u0000"` |
| `/cpus/cpu3` | `reg` | binary hex | 4 | `00030000` |
| `/cpus/cpu3` | `state` | NUL strings | 8 | `"waiting\u0000"` |
| `/cpus/cpu3` | `device_type` | NUL strings | 4 | `"cpu\u0000"` |
| `/cpus/cpu3` | `compatible` | NUL strings | 16 | `"arm,cortex-a715\u0000"` |
| `/cpus/cpu3` | `timebase-frequency` | binary hex | 4 | `00f82401` |
| `/cpus/cpu4` | `name` | NUL strings | 5 | `"cpu4\u0000"` |
| `/cpus/cpu4` | `reg` | binary hex | 4 | `00040000` |
| `/cpus/cpu4` | `state` | NUL strings | 8 | `"waiting\u0000"` |
| `/cpus/cpu4` | `device_type` | NUL strings | 4 | `"cpu\u0000"` |
| `/cpus/cpu4` | `compatible` | NUL strings | 16 | `"arm,cortex-a715\u0000"` |
| `/cpus/cpu4` | `timebase-frequency` | binary hex | 4 | `00f82401` |
| `/cpus/cpu5` | `name` | NUL strings | 5 | `"cpu5\u0000"` |
| `/cpus/cpu5` | `reg` | binary hex | 4 | `00050000` |
| `/cpus/cpu5` | `state` | NUL strings | 8 | `"waiting\u0000"` |
| `/cpus/cpu5` | `device_type` | NUL strings | 4 | `"cpu\u0000"` |
| `/cpus/cpu5` | `compatible` | NUL strings | 16 | `"arm,cortex-a710\u0000"` |
| `/cpus/cpu5` | `timebase-frequency` | binary hex | 4 | `00f82401` |
| `/cpus/cpu6` | `name` | NUL strings | 5 | `"cpu6\u0000"` |
| `/cpus/cpu6` | `reg` | binary hex | 4 | `00060000` |
| `/cpus/cpu6` | `state` | NUL strings | 8 | `"waiting\u0000"` |
| `/cpus/cpu6` | `device_type` | NUL strings | 4 | `"cpu\u0000"` |
| `/cpus/cpu6` | `compatible` | NUL strings | 16 | `"arm,cortex-a710\u0000"` |
| `/cpus/cpu6` | `timebase-frequency` | binary hex | 4 | `00f82401` |
| `/cpus/cpu7` | `name` | NUL strings | 5 | `"cpu7\u0000"` |
| `/cpus/cpu7` | `reg` | binary hex | 4 | `00070000` |
| `/cpus/cpu7` | `state` | NUL strings | 8 | `"waiting\u0000"` |
| `/cpus/cpu7` | `device_type` | NUL strings | 4 | `"cpu\u0000"` |
| `/cpus/cpu7` | `compatible` | NUL strings | 14 | `"arm,cortex-x3\u0000"` |
| `/cpus/cpu7` | `timebase-frequency` | binary hex | 4 | `00f82401` |
| `/psci` | `name` | NUL strings | 5 | `"psci\u0000"` |
| `/psci` | `compatible` | NUL strings | 13 | `"arm,psci-1.0\u0000"` |
| `/psci` | `method` | NUL strings | 4 | `"smc\u0000"` |
| `/arm-io` | `name` | NUL strings | 7 | `"arm-io\u0000"` |
| `/arm-io` | `device_type` | NUL strings | 7 | `"arm-io\u0000"` |
| `/arm-io` | `#address-cells` | binary hex | 4 | `02000000` |
| `/arm-io` | `#size-cells` | binary hex | 4 | `02000000` |
| `/arm-io` | `ranges` | binary hex | 24 | `000000000000000000000017000000000000000100000000` |
| `/arm-io/intc` | `name` | NUL strings | 5 | `"intc\u0000"` |
| `/arm-io/intc` | `compatible` | NUL strings | 11 | `"arm,gic-v3\u0000"` |
| `/arm-io/intc` | `reg` | binary hex | 32 | `0000100000000000000001000000000000001800000000000000200000000000` |
| `/arm-io/intc` | `#interrupt-cells` | binary hex | 4 | `04000000` |
| `/arm-io/intc` | `interrupt-controller` | binary hex | 0 | `(empty)` |
| `/arm-io/intc` | `redistributor-stride` | binary hex | 8 | `0000040000000000` |
| `/arm-io/intc` | `phandle` | binary hex | 4 | `01000000` |
| `/defaults` | `name` | NUL strings | 9 | `"defaults\u0000"` |
| `/defaults` | `kern.maxvnodes` | binary hex | 4 | `00040100` |
| `/defaults` | `no-effaceable-storage` | binary hex | 4 | `01000000` |
| `/options` | `name` | NUL strings | 8 | `"options\u0000"` |
| `/product` | `name` | NUL strings | 8 | `"product\u0000"` |
| `/product` | `product-name` | NUL strings | 9 | `"iPhone X\u0000"` |
| `/product` | `product-description` | NUL strings | 9 | `"iPhone X\u0000"` |
| `/product` | `artwork-device-idiom` | NUL strings | 6 | `"phone\u0000"` |
| `/product` | `artwork-display-gamut` | NUL strings | 3 | `"P3\u0000"` |
| `/product` | `compatible-device-fallback` | NUL strings | 10 | `"iPhone9,2\u0000"` |
| `/product` | `artwork-scale-factor` | binary hex | 4 | `03000000` |
| `/product` | `artwork-device-subtype` | binary hex | 4 | `84090000` |
| `/product` | `product-id` | binary hex | 20 | `fd079b298144a7deb4d7c87fef3eb474d8f0e7eb` |

合计 19 节点、110 属性；使用 `scripts/nuwa_launch_context.py` 解析，校验边界、重复键和完整消费。
