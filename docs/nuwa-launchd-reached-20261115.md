# nuwa 里程碑：原生 UFS 根卷 → launchd 用户态（2026-11-15）

状态总览（逐项标签见各节，不在此处提升等级）：

- 主机侧全部产物：**self-checked**（无独立 `verifier` 复跑）。
- 根卷与 launchd：设备侧结果为**主控转述的用户实机观测**，无机器日志或截帧入库；本轮
  代理未运行任何设备命令。
- 认证：**NOT REACHED**。CHMH 仍为实验性、未认证的启动集身份。

本记录只写事实、路径与哈希；serial、ECID、照片/录像、Apple 组件与镜像一律不入库。

## 1. 达成的事实

1. `userdata` 前 8446279680 B 写入并按整镜像回读校验：installer `exit 0`，
   `bytes=8446279680`，`sha256=da429da64b4d91a08b8adb1d3162f8348b37b358509ab1bd5d8bf09abdbf68d7`
   （126 个窗口：125×67108864 + 57671680），`backup_policy=without-backup`、
   `userdata_rollback=false`。写入授权为当轮「无备份写入指定 userdata 前缀」，
   不含 root 启动、不含启动分区写（启动分区写随后另有当轮授权，见第 2 节）。
   标签：self-checked（设备侧）；安装器源码/测试另有独立 `verifier` r3 复跑（47 tests OK，
   installer `1d8d077e…`、tests `bb97229c…`、manifest `bc344eb1…` 均同值），但该复跑
   为纯主机执行、`device_calls=0`，**不构成设备写入的独立验证**。
2. 根卷：`native-ufs-root=1`、`native-ufs-lun=0`、`rd=uuid` +
   `boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7`，`Ramdisk_bytes: 0`（无 ramdisk/
   RamBlock 内存根），PMGR 高级阈 `nuwa-pmgr=2`。现象：root 卷挂载后不再因
   `rootvp not authenticated after mounting` panic，内核继续到 BSD 初始化。
3. trust cache：`trust_cache_runtime_init()` 与 `load_static_trust_cache()` 在
   `machine_lockdown()` **之前**执行，`query_trust_cache()` 不再在
   `lck_rw_lock_shared` 上 panic。当前派生 ADT 的 `/chosen/memory-map` `TrustCache`
   条目仍为 `{0, 0}`，因此 `load_static_trust_cache()` 实际为**空操作**。
4. initproc 首次 exec 不再被 MAC/AMFI 策略拒绝杀死：`process_signature()` 对
   `p == initproc` 记录 `nuwa_exec_policy_error` 并放行（EXEC/8 SIGKILL 路径不再触发）。
5. launchd 在用户态运行：观测内核的面板色带证据为主控转述的用户实机观测——
   **青带 3**（`___mac_execve` 中 `bl _process_signature` 返回后 `error == 0` 且
   `p == initproc`）与**橙带 15**（`unix_syscall()` 首次以 `initproc` 进入）同时出现，
   即 initproc 的 exec 走完并**回到内核**。配合 19:56–20:02 窗口内 adb/fastboot 全程
   不枚举（`WRITE-r9` 记录），与「Android/TWRP/recovery 均已不在跑」一致。
   **边界**：色带只证明 exec 成功与 initproc 的 syscall 入口，不证明 launchd 完成
   初始化、不证明显示服务、不证明持久交互。

## 2. 设备写入（启动载荷进设备）

当轮授权：写 `boot` / `vendor_boot` 槽，不动 `xbl*/abl*/tz/hyp/modem/persist/RPMB`、
不改 slot active、不再写 `userdata`。

| 分区 | 内容 | 字节 | SHA256 |
| --- | --- | --- | --- |
| `boot_a` | Mu-Silicium UEFI loader + DarwinBoot（`692cfcca…`） | 1495040 | `692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5` |
| `vendor_boot_a` | 包 r7 | 100663296 | `24258f44c5a0869fa9ff6358cb13771f8c889d9721795b237a31af431a55a418` |
| `vendor_boot_a` | 包 r8（二模块 trust bundle） | 100663296 | `8e09fae228f985eb4efc7bcf9d8c2c55b594f499af1f48a91f53db431e1ff66e` |
| `vendor_boot_a` | 包 r9（观测内核） | 100663296 | `37b665da4629f69ad97fca1335c91f99f81780c896ebceac4dd419264de8667f` |

- 写入通道：`fastboot flash vendor_boot_a`（单次、有界超时、`exit 0`）。bootloader 无
  `fastboot fetch`、fastboot 模式下无 adb，因此三次写入均**只有 bootloader 写确认，
  无设备侧回读**；r9 写前 host 侧哈希与 `vendor_boot.json` 记录一致。
- 回滚：`out/nuwa-boot-payload-write-20261115-01/` 的 `PLAN.md`、`BACKUP.json`、
  `ROLLBACK-r7/r8/r9.md` 保留原厂 `boot_a`/`vendor_boot_a` 备份与回滚步骤。
- 标签：self-checked（host 侧哈希与写入结果）；设备端写入确认来自 bootloader 应答。

## 3. 载荷 / 内核链（host 产物）

| 步骤 | 内核 SHA256（55545856 B，r6a 同） | 目的 |
| --- | --- | --- |
| r3 | `f0d53c88d7ec89016399e1cef3d6f797b113dd98d136015535efbcdd0e6d8596` | root auth 跳过 |
| r4 | `d658267e36b0854e1583879afc7e8ec6a3dc2730b9c9cf7a19304a22c8b7e475` | trust cache 早初始化 |
| r5 | `77149bd5f89012e3cae1cc9e59577187b7119899566c934d13e327cd208b4e84` | 初始化挪到 `machine_lockdown()` 前 |
| r6a | `75182b341f98c1e27bdda8121b5da164ccab01ef03c175e128a3e6b39aa86bcd` | 额外调用 `load_static_trust_cache()`（当前 ADT 下空操作） |
| r7/r8 | `2561c0c527bfa85dda4de218f933eb17a14c821edd20573755aa7b6efdb7872b` | initproc exec 策略跳过 |
| r9 | `b1029f3d32d1db3ae0bca1b85a665a6758c608ee9f9a5aaffbc55589f83d3764` | r7 + 观测色带 3/15（临时观测构建） |

- 三个绕过补丁：`patches/xnu/8796-nuwa-root-auth-skip.patch`、
  `patches/xnu/8796-nuwa-trust-cache-init.patch`、
  `patches/xnu/8796-nuwa-exec-policy-skip.patch`。三者均为 **opt-in**
  （`-DXNU_NUWA_ROOT_AUTH_SKIP=1` / `-DXNU_NUWA_TRUST_CACHE_INIT=1` /
  `-DXNU_NUWA_EXEC_POLICY_SKIP=1`，未定义时行为不变），按既有约定（同
  `8796-nuwa-pmgr-root-publication.patch`）**不列入 `patches/xnu/series`**，由设备
  host 构建显式加定义应用。
- trust cache bundle：二模块 `eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3`
  （67764 B，OS 2760 条 + `Cryptex1,SystemTrustCache` 61 条，两模块原样拼装，不改
  cdhash、不加条目）；历史单模块 `367e051548f9f0407fa9fe9d40007fa4e7c5ff27c45f5a7a30cedf344e24d98e`
  （66272 B）仍在 `board.toml [payload] trust_cache_sha256` 中。
- r9 载荷绑定：ADT `9d76537a5743fc973e9bfcade2115d209b125ba1531a76f7efa938f10c212b91`，
  payload `7587079c8060cb3cd8a5e4c448e19af3d8e1d4404f4ba29283b8931bc4dede65`，
  CHMH SHA384 对 r9 内核重新绑定（`841f20fe…d1a359`），args 材料
  `d71b8f4a6c283f902374d9d6697e4d4f66616e135f3a3654f54c31ab79f6cb4a`（与 r5/r7/r8 同）。

## 4. 卡点绕过台账（现象 / 绕过 / 代价 / 解除条件）

| 现象 | 绕过方式 | 代价 | 解除条件 |
| --- | --- | --- | --- |
| root 卷挂载后 `panic("rootvp not authenticated after mounting")` | `8796-nuwa-root-auth-skip`：只记录 `nuwa_root_auth_error` 与 errno、继续启动 | root 封印/认证未做；认证 NOT REACHED，内核不再对根卷做该 ioctl 判定 | 真实 trust cache/IPSW 认证链可用后删除该分支 |
| `query_trust_cache()` 在 `lck_rw_lock_shared` 上 panic（非睡眠 RW 锁 + 抢占，`trust_cache_rt_lock` 全零） | `8796-nuwa-trust-cache-init`：在 `startup.c` 的 BCM2837 分支恢复 `trust_cache_runtime_init()` + `load_static_trust_cache()`，且必须在 `machine_lockdown()` 前（`trust_cache_rt_storage` 是 `SECURITY_READ_ONLY_LATE`） | 当前包内 ADT `TrustCache` 条目为 `{0,0}`，加载为空操作；bundle 的 cdhash 尚未被运行时消费验证 | ADT `/chosen/memory-map` 指向真实打包的 trust cache |
| launchd exec 被 AMFI 拒（`OS_REASON_EXEC` / `EXEC_EXIT_REASON_SECURITY_POLICY=8`），XNU 对 initproc `SIGKILL` 后 panic | `8796-nuwa-exec-policy-skip`：仅对 `initproc` 忽略 `ip_mac_return`，记录 `nuwa_exec_policy_error`；其他进程行为不变 | initproc 首次 exec 不再受签名策略约束；`amfi_get_out_of_my_way=1`（r6b 包）主控转述无效，boot-arg 路径在本配置未放行 | 非空运行时 trust cache 让 AMFI 正常放行后删除该分支 |
| 显示服务缺失：只有 `vinfo` 直接绘制的观测带，没有 UI | 未绕过，标 `deferred` | 无界面可交互，只能靠色带/panic 读取进度 | 接 `GopFramebuffer` 显示路径与 launchd 显示服务 |

## 5. 证据路径

- 写入授权与结果：`out/nuwa-userdata-write-20261115-03/REPORT.md`（installer 结果、
  126 窗口、watchdog、失败 claim 归档）；`out/nuwa-userdata-install-execution/`；
  `out/nuwa-userdata-final-verifier-20261115-r3/`（独立 host 复跑 47 tests、哈希）。
- 启动载荷写入：`out/nuwa-boot-payload-write-20261115-01/REPORT.md` 与
  `WRITE-r7/r8/r9-vendor_boot_a.json`、`ROLLBACK-r*.md`。
- 内核与 CHMH：`out/nuwa-root-auth-skip-20261115-r1/REPORT.md`、
  `out/nuwa-trust-cache-init-20261115-r2/REPORT.md`、
  `out/nuwa-lck-rw-20261115-r1/frames.json`（21 帧符号化）、
  `out/nuwa-exec-skip-20261115-r6/REPORT.md`、
  `out/nuwa-ufs-apfs-root-chmh-20261115-r7|r8|r9/`（record/audit/vendor_boot）。
- trust bundle：`out/ios16-system-trust-bundle-20261115-r1/inputs.json`
  （含 10 项 parser 负例结果）。
- 观测带构建：`out/nuwa-observe-20261115-r1/REPORT.md` + `selfcheck.json`
  （青带 3 行区间 `[3/16,4/16)`、橙带 15 行区间 `[15/16,16/16)`，只存储不取锁）。

## 6. 未验证 / 边界

- 认证未达成；CHMH 为未认证实验身份，`authentication: NOT REACHED`。
- launchd 之后的一切（launchd 初始化完成、Job 启动、锁屏/桌面、reboot 后仍回到同系统）
  均未验证；「断电重启一次仍可交互」这一交互目标**未达成**。
- root 卷当前是否是真实可写持久根（Data 卷写入/跨重启保留）未验证；本轮只证明挂载与
  init 进入用户态。
- 三处绕过都在启动链安全边界上；任何新的内核都需要重新绑定 CHMH，不能复用旧包。
- 观测带内核为临时构建，不入库、不长期使用；`8796-nuwa-observe-markers.patch` 与
  `8796-nuwa-observe-log.patch` 保持未跟踪，待观测结束统一清理。

## 7. 复跑（host，WSL，cwd 设备仓）

```sh
PY=/home/wh1stl3/.local/bin/python3.11
# 观测内核（r1）+ 自检
$PY out/nuwa-observe-20261115-r1/build.py
$PY out/nuwa-observe-20261115-r1/selfcheck.py
# 载荷包（显式内核/哈希/profile，审计目录复现同一 outer）
$PY -B scripts/build-ufs-apfs-root-chmh.py --kernel out/nuwa-observe-20261115-r1/kernel.macho \
    --kernel-bytes 55545856 \
    --kernel-sha256 b1029f3d32d1db3ae0bca1b85a665a6758c608ee9f9a5aaffbc55589f83d3764 \
    --profile nuwa-ufs-apfs-root-chmh-20261115-r9 --output out/nuwa-ufs-apfs-root-chmh-20261115-r9
# 安装器定向测试
$PY -B scripts/test-nuwa-userdata-install.py
```
