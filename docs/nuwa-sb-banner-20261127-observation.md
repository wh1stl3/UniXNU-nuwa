# SpringBoard banner r2 outer 刷写、直接 reboot 与 120 秒采样 — 2026-11-27 observation

状态：用户断电复位后，nuwa 的四个门禁变量两轮共 8 次全部稳定读回；banner r2 outer
`7211a988…4495` 经唯一一次 `flash vendor_boot_a` 被 bootloader 接受（`Sending`/
`Writing OKAY`，exit 0）。随后按用户要求**直接**执行一次 `fastboot reboot`（exit 0），
120 s 采样内 nuwa **未**回到 fastboot，且完全不出现在主机 USB 枚举中；`adb` 全程无
设备。主机侧 **self-checked**。无屏幕、启动阶段、用户态或认证证据。

## 本轮授权与门禁

- 授权：识别唯一 nuwa；对 `product`、`is-userspace`、`current-slot`、
  `partition-size:vendor_boot_a` 连查两轮（共 8 次），任一次失败即停、不刷写；8 次全稳
  后只刷一次 `vendor_boot_a`；刷写成功后**直接**执行一次 `fastboot reboot`，随后 120 s
  每 10 s 采样 `fastboot devices`/`adb devices`；异常即停。
- 明确不做：不刷其他分区、不切槽、不初始化、不写 `userdata`/`metadata`。
- 产物：`out/nuwa-sb-banner-20261127-package-r2/vendor_boot.img`。**审查留痕**：本轮
  写入前的审查来自 `reviewer` 会话 `ses_de2cdddc5ffePUw2gq6wva4G7o`，结论
  **PASS WITH CONDITIONS**，不涉及 `deep_reviewer`。本记录未持有条件原文，故不复述
  条件内容；写入按该审查结论放行。
- `fastboot devices` 两台：一台为 `product=enuma`（未操作）；nuwa serial 与前几轮
  相同（不入库），本轮固定使用。

## 前置：断电复位前的 getvar 不稳定

- 本轮首次尝试时第一轮 4 次查询全部成功，第二轮 `is-userspace` 返回
  `FAILED (remote: 'unknown command')`、`partition-size:vendor_boot_a` 返回
  `FAILED (remote: 'GetVar Variable Not found')`，`product`/`current-slot` 仍正常。
  按门禁「任一次失败即停」**未刷写、未 reboot**。
- 该签名与 `docs/nuwa-fua-fallback-recover-20261127-observation.md` 记录的
  「被拒 download 之后同一变量随机 `Variable Not found`/`unknown command`」一致；该文
  记录的唯一恢复手段是 bootloader 复位。
- 用户随后彻底断电复位并重新进入 fastboot；下文全部读数均为复位后重新采集，不沿用
  复位前判断。

## 断电复位后 8 次门禁核对（21:36:50–21:36:55）

每轮顺序 `product` → `is-userspace` → `current-slot` → `partition-size:vendor_boot_a`。
判定按输出文本（`fastboot getvar` 失败时 exit 仍为 0，不能只看退出码）。

| # | 墙钟（+08:00） | 变量 | 输出 | exit | FAILED |
| --- | --- | --- | --- | --- | --- |
| R1.1 | 21:36:50.812 | product | `nuwa` | 0 | 否 |
| R1.2 | 21:36:50.998 | is-userspace | `no` | 0 | 否 |
| R1.3 | 21:36:51.046 | current-slot | `a` | 0 | 否 |
| R1.4 | 21:36:51.091 | partition-size:vendor_boot_a | `0x6000000` | 0 | 否 |
| R2.1 | 21:36:54.845 | product | `nuwa` | 0 | 否 |
| R2.2 | 21:36:55.058 | is-userspace | `no` | 0 | 否 |
| R2.3 | 21:36:55.114 | current-slot | `a` | 0 | 否 |
| R2.4 | 21:36:55.162 | partition-size:vendor_boot_a | `0x6000000` | 0 | 否 |

8/8 全部成功且值符合预期，无 `Variable Not found`、无 `unknown command`。`adbd` 在复位
后与采样全程均无设备。

## 产物实算（21:37:00.225）

```text
size   100663296                 (期望 100663296, match=True)
sha256 7211a98853226d4b1ca3345d1b5300bcfcf08b667a3b342b2cacc779082e4495
                                (与授权值逐字一致, match=True)
```

包内 `audit.json`（`out/` 内，不入库）：`kernel_sha256`
`f076163f46d3821c894eb8a4c38b6e1ca4c220a52029d587c844e8ccb7aee75a`、`outer_sha256`
同上、`chmh_sha384` `0c19132e19f4aa0576cfff00a25c0d4db9e3fcc4618995cd43b1a45289d349b42186a4dd75fa414ec02f9bebd04452a4`、
`fat_sha256` `281856345047c07834664081d2e09d3f347912deeda915ba5d88a319737535a0`、
`seed_sha256` `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e`、
`template_outer_sha256` `18fa4941696667d1813442022ea71fc48e4c414b1abadb1caf73774fcc76202a`、
`fat_free_bytes` 11,021,312、`diagnostic_arg` `nuwa-disposable-data=1`。
包内 `vendor_boot.json` 记录 `stock_sha256`
`5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23`（`vendor_boot_b.img`）。

启动参数取自包内 `unixnu.toml`：`-v serial=3 native-ufs-root=1 native-ufs-lun=0
nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1
disable-watchdogd=1 build-tag=data-trial boot-progress-scale=3 sheng-data-persist=2
sheng-log-reserve=1024 offline-mobile-graphics-load=1 … nuwa-lite=1 nuwa-mg-reset=1
nuwa-hid-standin=1 nuwa-sb-stack=900
disable-jobs=com.apple.iconservices.iconservicesagent nuwa-ufs-neon=1
nuwa-disposable-data=1`。

## 唯一一次刷写（21:37:04.967–21:37:07.429）

```text
fastboot -s <nuwa-serial> flash vendor_boot_a <...>/vendor_boot.img
  Sending 'vendor_boot_a' (98304 KB)  OKAY [  2.263s]
  Writing 'vendor_boot_a'             OKAY [  0.036s]
  Finished. Total time: 2.331s
```

- 开始 `21:37:04.967`，结束 `21:37:07.429`，命令耗时 2.462 s，**exit 0**。
- 输出**没有** `partition-size: 0` / AVB footer 警告；与「会话能读到分区大小时客户端先
  截断 AVB footer 再发送」的既往判读一致。
- 只刷一次，未重试；未切槽、未刷其他分区、未初始化、未写 `userdata`/`metadata`。

## 唯一一次直接 reboot 与 120 s 采样

```text
fastboot -s <nuwa-serial> reboot
  Rebooting                                          OKAY [  0.000s]
  Finished. Total time: 0.000s
```

- 发起 `21:37:18.191`，返回 `21:37:18.364`，**exit 0**；只执行一次，未在采样后追加
  重启。
- 采样：自 reboot 返回起每 10 s 一点，共 13 点（+0…+120 s）。`+0 s` 点中 nuwa 行以
  `????????????` 出现（serial 不可读、USB 正在重枚举），该点计入「稳定 fastboot 态已
  被打断」。

| 采样 | 相对 | 墙钟（+08:00） | nuwa 在 fastboot | `????????????` | adb |
| --- | --- | --- | --- | --- | --- |
| S0 | +0 s | 21:37:18.378 | 否 | 是 | 无 |
| S1 | +10 s | 21:37:28.391 | 否 | 否 | 无 |
| S2 | +20 s | 21:37:38.387 | 否 | 否 | 无 |
| S3 | +30 s | 21:37:48.381 | 否 | 否 | 无 |
| S4 | +40 s | 21:37:58.374 | 否 | 否 | 无 |
| S5 | +50 s | 21:38:08.383 | 否 | 否 | 无 |
| S6 | +60 s | 21:38:18.372 | 否 | 否 | 无 |
| S7 | +70 s | 21:38:28.386 | 否 | 否 | 无 |
| S8 | +80 s | 21:38:38.382 | 否 | 否 | 无 |
| S9 | +90 s | 21:38:48.373 | 否 | 否 | 无 |
| S10 | +100 s | 21:38:58.379 | 否 | 否 | 无 |
| S11 | +110 s | 21:39:08.389 | 否 | 否 | 无 |
| S12 | +120 s | 21:39:18.385 | 否 | 否 | 无 |

- 时间线：`+0 s` 离开 fastboot 稳定态；`+10 s` 起连 `????????????` 行也不再出现，
  nuwa 从主机 USB 完全消失；到 `+120 s` 未回到 fastboot。`adb` 13 点全程无设备。
- 采样窗口外一次确认（`21:39:30.223`）：`fastboot devices` 仅 enuma；
  `adb devices -l` 无设备；Windows 在场 PnP 设备中唯一 Android 类节点是
  `USB\VID_18D1&PID_D00D\<enuma-serial>`（enuma bootloader），无任何 nuwa 节点——既不是
  fastboot，也不是 adb/MTP，也不是 `VID_05C6&PID_9008`(EDL)。
- 按指令「设备离开 fastboot 且持续不在即停止采样并报告」：120 s 窗口结束后未再重启、
  未重刷、未追加采样。

## 判读

- 本次只证明 bootloader 接收了 `7211a988…4495` outer（`Sending`/`Writing` OKAY）。
  无 `fastboot fetch` 或分区回读，**不证明盘上字节内容**。
- 本候选在 120 s 内**没有**出现 `docs/nuwa-fua-fallback-recover-20261127-observation.md`
  记录的「+10 s 回到 fastboot」行为：那一次是 r6 诊断 outer `b9103e97…97b8`，本次是
  banner r2 `7211a988…4495`，输入不同，两次结果不能互证也不能直接比较优劣。
- 设备从 USB 完全消失有三种未区分解释：启动中但未建立 USB/ADB；启动早期 panic/掉电；
  仍在运行但无 USB 报文。无屏幕、串口、adb 三者任一证据，**无法区分**，不据此判定任何
  启动阶段。
- `+0 s` 的 `????????????` 只证明 USB 重新枚举、fastboot 稳定态被打断；10 s 采样粒度
  不给出确切离开时长。
- 10 s 内回落的已知现象在本轮未复现，这与 r6 那轮不同；差异原因未证。

## 边界

- 未验证：内核是否开始执行、banner 是否显示、显示服务、用户态、持久化与断电重启。
  认证 **NOT REACHED**，本轮不涉及。
- 采样期间设备不在 USB 上，因此没有刷后 `product`/`current-slot` 复读；本轮最后一次
  成功读到槽位是刷前门禁 `current-slot=a`。
- 设备当前未连接主机（无 fastboot、无 adb）。下一次设备动作需单独授权；恢复连接需要
  用户现场断电重入 fastboot。
- 前置 getvar 不稳定再次出现并再次被断电复位消除，说明该状态可复现且非本轮独有；
  具体触发条件仍未证。
- 该 banner r2 包在 `docs/` 侧没有构建记录：生成/打包日志只在 `out/`
  （`nuwa-sb-banner-20261127-build-r2.log`、`nuwa-sb-banner-20261127-package-r2.log`，
  均被 `.gitignore` 排除）。生成该 outer 的源码与测试（11 个文件）已随源码提交
  `3335a3d483da80214af36b4275e5e4aa03bf5523` 入库；**从已提交源码重建是否逐字节一致
  尚未验证**。
