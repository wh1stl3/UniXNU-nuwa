# 根卷架构核对 — 2026-11-24

主机只读检查，**self-checked**；没有访问设备。缓存只有 arm64，三个可执行文件也是 arm64；没有 arm64e 缓存。

## 输入与封装

输入 `UniXNU-nuwa/out/root-external-policies-20261113/candidate/userdata/userdata-root.img`，长度 8,446,279,680 B。`docs/nuwa-launchd-reached-20261115.md` 记录写入及设备回读 SHA-256 为 `da429da64b4d91a08b8adb1d3162f8348b37b358509ab1bd5d8bf09abdbf68d7`；本次未重算整镜像哈希，也未重新读取设备，因此源文件与记录的当前一致性依赖该既有记录。

按 `.cache/ci-porting-134fd4e/tools/scripts/unixnu/userdata.py` 的 SHNGROOT 定义解析：版本 2、4 项，manifest 自身 SHA-256 核对成功。偏移和长度均为字节，偏移相对镜像起点：

| 名称 | 偏移 | 长度 | block_size | flags | 类型 |
|---|---:|---:|---:|---:|---|
| OS | 1,048,576 | 5,635,081,728 | 512 | 1 | 只读块设备窗口 |
| SystemOS | 5,637,144,576 | 2,743,074,816 | 512 | 1 | 只读块设备窗口 |
| OS.vroot | 8,380,219,392 | 44,024,096 | 4096 | 3 | 内核数据对象 |
| SystemOS.vroot | 8,424,259,584 | 21,430,272 | 4096 | 3 | 内核数据对象 |

OS 窗口内 GPT 首分区从 LBA 34 开始，APFS 容器在整个镜像偏移 1,065,984；SystemOS APFS 容器位于窗口起点。使用本地 `sgan81/apfs-fuse@66b86bd525e8cb90f9012543be89b1f092b75cf3` 的 `-s` 参数直接只读挂载原镜像，`findmnt` 确认两者 `ro`；没有复制窗口。Windows 挂载点被 FUSE 拒绝，因此挂载点在 WSL `/tmp/nuwa-root-inspect-20261124/{os,systemos}`，各文件系统实际根目录为其下 `root/`。

## 缓存目录

OS 窗口无 `root/System/Library/Caches/com.apple.dyld/`。SystemOS 窗口该目录全部条目如下；均为 **arm64**，无 arm64e 或无架构标记的条目。大小为字节：

| 名称 | 大小 |
|---|---:|
| dyld_shared_cache_arm64 | 393216 |
| dyld_shared_cache_arm64.01 | 114638848 |
| dyld_shared_cache_arm64.02 | 98304 |
| dyld_shared_cache_arm64.03 | 115769344 |
| dyld_shared_cache_arm64.04 | 180224 |
| dyld_shared_cache_arm64.05 | 114540544 |
| dyld_shared_cache_arm64.06 | 376832 |
| dyld_shared_cache_arm64.07 | 115408896 |
| dyld_shared_cache_arm64.08 | 278528 |
| dyld_shared_cache_arm64.09 | 115752960 |
| dyld_shared_cache_arm64.10 | 409600 |
| dyld_shared_cache_arm64.11 | 115818496 |
| dyld_shared_cache_arm64.12 | 393216 |
| dyld_shared_cache_arm64.13 | 107970560 |
| dyld_shared_cache_arm64.14 | 409600 |
| dyld_shared_cache_arm64.15 | 115097600 |
| dyld_shared_cache_arm64.16 | 458752 |
| dyld_shared_cache_arm64.17 | 97419264 |
| dyld_shared_cache_arm64.18 | 376832 |
| dyld_shared_cache_arm64.19 | 107610112 |
| dyld_shared_cache_arm64.20 | 262144 |
| dyld_shared_cache_arm64.21 | 115130368 |
| dyld_shared_cache_arm64.22 | 442368 |
| dyld_shared_cache_arm64.23 | 115015680 |
| dyld_shared_cache_arm64.24 | 507904 |
| dyld_shared_cache_arm64.25 | 83607552 |
| dyld_shared_cache_arm64.26 | 245760 |
| dyld_shared_cache_arm64.27.dylddata | 187105280 |
| dyld_shared_cache_arm64.28.dyldlinkedit | 19922944 |
| dyld_shared_cache_arm64.29 | 115539968 |
| dyld_shared_cache_arm64.30 | 507904 |
| dyld_shared_cache_arm64.31 | 103677952 |
| dyld_shared_cache_arm64.32 | 573440 |
| dyld_shared_cache_arm64.33 | 115785728 |
| dyld_shared_cache_arm64.34 | 638976 |
| dyld_shared_cache_arm64.35 | 115769344 |
| dyld_shared_cache_arm64.36 | 491520 |
| dyld_shared_cache_arm64.37 | 114917376 |
| dyld_shared_cache_arm64.38 | 573440 |
| dyld_shared_cache_arm64.39 | 86933504 |
| dyld_shared_cache_arm64.40 | 557056 |
| dyld_shared_cache_arm64.41.dylddata | 102547456 |
| dyld_shared_cache_arm64.42.dyldlinkedit | 334102528 |
| dyld_shared_cache_arm64.symbols | 592101376 |

主文件 magic 为 `dyld_v1   arm64`，UUID `8F970452-C9E3-3E88-B114-FEB1864BC9E0`。

## Mach-O 头

均从 OS 窗口实际文件开头读取，数值按小端解释，均为非 fat 的 64 位 Mach-O：

| OS 根相对路径 | 文件大小 | magic | cputype | cpusubtype | 架构 |
|---|---:|---|---|---|---|
| `/sbin/launchd` | 541600 | `0xfeedfacf` | `0x0100000c` | `0x00000000` | arm64 |
| `/System/Library/CoreServices/SpringBoard.app/SpringBoard` | 112960 | `0xfeedfacf` | `0x0100000c` | `0x00000000` | arm64 |
| `/usr/libexec/lsd` | 57424 | `0xfeedfacf` | `0x0100000c` | `0x00000000` | arm64 |

`0x0100000c` 为 ARM64；subtype 低 24 位 `0` 为 arm64、`2` 为 arm64e，高 8 位是能力位。本次三个原始 subtype 都是零。两卷的缓存与这三个二进制架构一致。

## 符号化输入

对 `0x42611030`、`0x42622db8`、`0x42611524`、`0x0db6a308` 应以 SystemOS 的 arm64 缓存集为候选，不应预设 arm64e。当前只读挂载路径：

`/tmp/nuwa-root-inspect-20261124/systemos/root/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64`（393,216 B），同目录须保留上表 42 个编号分片和 `.symbols`（592,101,376 B）。使用支持 split cache 的符号化工具，以主文件为入口并让其读取同目录分片；不应直接拼接成单文件。若工具仅支持单文件，须先用该工具支持的转换方式，不能假定拼接等效。

这些数值是缓存相对 VM 偏移，不是主文件字节偏移；具体分片须由缓存映射确定。运行时缓存 UUID 尚未观测，故架构一致不等于运行时缓存身份已独立确认；本记录未执行符号化。
