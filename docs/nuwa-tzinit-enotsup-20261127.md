# nuwa: tzinit exit 45 (ENOTSUP) 离线分析 — 2026-11-27

状态：**仅主机静态分析 / self-checked**；本轮未接设备、未刷写、未启动。
基线：`research/nuwa-ufs-owner-api-20261126` @ `91cfdf0`。
本文只写能从源码和 20H392 二进制直接核对的事实；§4 的两个来源是待验证假设，
不是已证根因。

## 1. `/private/var` 是 donor APFS 经 `mount("apfs", …)` 挂载，不是合成 VFS

- 挂载点：`#define NUWA_DATA_MOUNT_POINT "/private/var"`
  （`package/nuwa-data/nuwa_data_mount.c:45`）。
- `nuwa_data_mount.c:501-522` 构造 `mount_args`，`copyout("apfs", request.type, 5)`、
  `copyout("/private/var", request.path, …)`，最后调用 `mount(p, &request, &result)`
  （`:507-522`）。
- 挂载后 `nuwa_data_mount.c:529-553` 用 `vnode_lookup("/private/var")`、
  `vfs_devvp` / `vnode_specrdev`、`vfs_statfs(...)->f_fstypename == "apfs"` 和
  `MNT_RDONLY` 校验 device、文件系统类型与方向。
- 工程提供的只是块层：`NativeRamBlock : IOBlockStorageDevice`
  （`package/nuwa-ramblock/NativeRamBlock.cpp:355`，读写入口 `:454`），
  Data overlay 为 `NuwaData::Disposable` / `DualBankLogOverlay`
  （`package/nuwa-data-write/DisposableData.h:5-6`、
  `DualBankLogOverlay.h:9-10`）。
- `package/` 内没有 `vfs_fsadd` 或 `vnodeopv` 注册；只有
  `package/nuwa-systemos/nuwa_systemos.c:31,144` 的注释提到 `VNOP_MKDIR`。
  因此该挂载的 symlink/readlink 语义由 XNU 的 APFS 文件系统实现提供，
  不是本工程合成的 VFS。

## 2. `disable-jobs=` 只写 system 域 `disabled.plist`，不能禁用 `tzinit`

- `package/nuwa-watchdog/nuwa_watchdog_policy.c:197-202` 只解析
  `disable-jobs` / `sheng-disable-jobs`。
- `:225-350` 只写 `/private/var/db/com.apple.xpc.launchd/disabled.plist`
  （`NUWA_POLICY_PATH`，`:33`），并创建同目录 `disabled.migrated`
  （`:35`）；这是 launchd system 域的 label→true 表，不修改
  `/System/Library/xpc/launchd.plist`，也不写 user 域的 `disabled.501.plist`。
- 20H392 的 `/sbin/launchd`（541,600 B，SHA-256
  `12370e5ee35bf28ae479b6c4b4455f4f4693ab803e37c5eb3032537c18cac61c`，
  LC_UUID `5C15DB07-B3BC-3DF3-B62F-3E498B993B8E`）内嵌 boot task 表：
  `__TEXT.__config` 的 plist 从 VMA `0x100064886` 开始，
  `tzinit` key 在 `0x1000656b3`，程序路径 `/usr/libexec/tzinit` 在
  `0x1000656e7`（未滑动 VMA；该段 fileoff 与 VMA 相差 `0x100000000`）。
- boot task 分发函数在 `0x10003f794`：它查询全局 boot task 字典
  （`"boot task dictionary is not populated"`、`"undefined boot task %s"`、
  `"Skipping boot-task"`），只检查条目的 `Perform*` 键后转到执行体
  `0x10003f970`，不查询 `disabled.plist`。
- `tzinit` 的调用点在 `0x10004033c`（`adr x0, "tzinit"`）/
  `0x100040348`（`bl 0x10003f794`），位于早期 boot task 序列函数
  `0x100040138` 内（同一函数还按序执行 `mount-phase-1`、`mount-phase-2`、
  `data-protection`、`fips`、`keybag`、`usermanagerd` 等，末尾打印
  `"Early boot complete. Continuing system boot."`）。
- `disabled.plist` 读取/迁移函数在 `0x100045d18`：
  `%s/disabled.plist` 字符串引用在 `0x100045d5c`、`0x100045e5c`，
  `%s/disabled.migrated` 在 `0x100045ddc`。它从同一早期序列的
  `0x10004036c`（`bl 0x100045d18`）被调用；该点比 `tzinit` 分发点晚
  `0x24` 字节，两点之间是直线代码，无反跳。
- 结论：静态顺序上 `tzinit` boot task 分发先于 `disabled.plist` loader；
  `tzinit` 也不按 launchd job label 查找，所以 `disable-jobs=tzinit`
  不会阻止它。设备侧已有的 `tzinit[17] exited … status 45` 观测
  （`docs/nuwa-postevent-20261127.md:15-16`）证明该 boot task 确实执行过，
  不是仅存在于 plist 中。

## 3. 20H392 `tzinit` 与退出 45

- 来源镜像：`out/root-inputs-20261113/ipsw/20H392/087-86698-044.dmg`
  （4,730,814,044 B，SHA-256
  `80f426d5b8fca8552f95be427434f1911dbb4c2c6d28aad94f2426ddd0c92483`，
  与同目录 `.dmg.json` 一致）。其 UDIF footer 的 raw 大小为 11,006,019 个
  512 B sector，即 5,635,081,728 B，与解码后的
  `out/root-inputs-20261113/os-window.raw` 大小一致；该 raw 的 APFS volume 0
  （Role: System）UUID 为 `DADD93F8-DBBF-4B17-A1DF-0F11E64172F7`。
- `/usr/libexec/tzinit`：126,640 B，SHA-256
  `1e13c6f7c32b810a043a5e28dccc1d24ddf83b69ddc3323d500d3aefa91ff9ef`，
  LC_UUID `0BA1BCF4-B37E-3A86-B9AD-98E40F9BF8CE`，版本串
  `@(#)PROGRAM:tzinit PROJECT:TimeZoneUpdates-81.4`。
- 入口在 `0x100006c88`（LC_MAIN entryoff `0x6c88`）。全文件只有一个
  `_exit` 调用点 `0x1000071b4`，位于 main 的 catch（`0x10000717c`，
  warning 文本 `"Last resort force_system_dataset() failed"`）：
  `0x1000071ac` 调 `__error`、`0x1000071b0` 取 errno、`0x1000071b4` 调
  `_exit`；`0x100007194`/`0x1000071a4` 只允许 errno 在 1..255 内退出。
  该路径没有硬编码 45。
- 本二进制中会把 libc symlink 相关 errno 带入异常路径的包装：
  - `read_symlink`（`0x100003d98`）调 `_readlink`（`0x100003dd8`）；
    errno 2（ENOENT）按“无 symlink”返回空，其他 errno 打印
    `"read_symlink: %s"` 并以 `__error` 构造异常（`0x100003e64`-`0x100003e70`）。
  - `create_symlink`（`0x100003e8c`）调 `_symlink`（`0x100003ec4`）；
    失败时打印 `"create_symlink: from %s to %s"` 并以 `__error` 构造异常
    （`0x100003f18`-`0x100003f24`）。
- Darwin `ENOTSUP` 为 45（`bsd/sys/errno.h:146`，XNU 8796 基座）。
  因此进入 `_exit` 的 45 是某个失败的 errno 值，不是 tzinit 里硬编码的
  常量；本版本中会把 libc `_readlink`/`_symlink` 的 errno 带入 C++ 异常
  路径的包装是 `read_symlink`/`create_symlink`。具体观测到的 45 由哪一次
  libc 调用产生、是否经过中间 catch，静态分析不能单独证明（见 §5）。

## 4. 候选 ENOTSUP 来源（待验证假设，不是已证根因）

- **H1：APFS vnode 向量走了 `err_symlink` / `err_readlink` 或未实现项。**
  XNU 的 `err_symlink`、`err_readlink` 直接返回 `ENOTSUP`
  （`bsd/vfs/vfs_support.c:516-520`、`:586-590`）。如果 APFS 给该卷安装的
  vnode 向量把 symlink/readlink 指到这些默认项，`create_symlink`/
  `read_symlink` 就会拿到 45。尚未验证：APFS 实际选用的 vnode 向量未在
  设备上采样。
- **H2：`NativeRamBlock` 对 FUA 写或 cache synchronize 返回
  `kIOReturnUnsupported`。** 在 `NUWA_DISPOSABLE_DATA` 下，FUA 写直接返回
  `kIOReturnUnsupported`（`NativeRamBlock.cpp:460-465`）；在
  `NUWA_DATA_CANDIDATE` + `NUWA_DISPOSABLE_DATA` 下，
  `doSynchronizeCache()` 在 online 且非 `directFailed` 时也返回
  `kIOReturnUnsupported`（`:328-344`）。`IOService::errnoFromReturn` 把
  `kIOReturnUnsupported` 映射为 `ENOTSUP`
  （`xnu/iokit/Kernel/IOService.cpp:8102-8103`）。若 APFS 的 symlink 元数据
  写或 flush 经过该路径并把错误带回 vnode 操作，tzinit 会看到 45。尚未
  验证：没有运行时 IO 栈 trace，不能证明该路径在本次启动中被走到。

两条都只作为候选；不能把任一条写成已证根因。

## 5. 现有边界

- 未取得运行时 syscall / IO 栈 trace；无法把观测到的 45 归因到某一次
  `_symlink`、`_readlink`、写或 flush。
- APFS 在该 donor 卷上实际选用的 vnode 向量未在设备上采样。
- 反汇编地址是 20H392 二进制未滑动 VMA；设备上 launchd 为 PIE，运行时
  地址会随 slide 变化。
- 本轮无设备访问、刷写、启动；设备侧只有既有记录中的
  `tzinit[17] … status 45`，不是本轮新观测。
- 本文不改变 `disable-jobs` 策略、Data 写门或认证状态。

## 来源与复现

- DMG：`sha256sum 087-86698-044.dmg` =
  `80f426d5b8fca8552f95be427434f1911dbb4c2c6d28aad94f2426ddd0c92483`。
- raw 解码结果：`os-window.raw` 5,635,081,728 B；APFS volume 0 以只读方式
  挂载后取 `/usr/libexec/tzinit` 与 `/sbin/launchd`。
- 反汇编：`llvm-objdump --macho --arch=arm64 --disassemble --no-show-raw-insn`
  （LLVM 14.0.0）。tzinit 与 launchd 的 SHA-256 见 §2、§3。
