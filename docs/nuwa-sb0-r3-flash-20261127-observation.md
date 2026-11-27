# R 只读候选第三次刷入、直接 reboot 与 90 秒采样 — 2026-11-27 实机观察

状态：断电复位后，nuwa 的四个门禁变量单进程连续 8 次全部成功；R outer
`3f5ffaee…b7668` 经唯一一次 `flash vendor_boot_a` 被 bootloader 接受
（`Sending`/`Writing OKAY`，exit 0，无 AVB footer 警告）。随后单次
`fastboot reboot`（exit 0），90 s 采样内 nuwa 未回到 fastboot、完全不在主机 USB
上，`adb` 全程无设备。主机侧 **self-checked**。

**屏幕结果未取得**：本轮是 R 只读候选读 Data 窗口，`BLANK` / `EXACT-SB0` 分类只存在于
设备屏幕，本轮没有照片或读屏，因此本记录**不报告任何 DATA 行内容**，也不把本轮与
R1 的 `BLANK`、R2 的 `EXACT-SB0` 相加或替代。

## 授权与边界

- 授权：核对门禁 → 实算 R outer → 只刷一次 `vendor_boot_a` → 成功即执行一次
  `fastboot reboot` → 90 s 每 10 s 采样；任一门禁失败即停，不重试。
- 明确不做：不刷其他分区、不切槽、不初始化、不写 `userdata`/`metadata`、不 fetch
  分区、不发 adb 写/挂载命令。
- 设备：唯一 nuwa（`product=nuwa`，serial 不入库）；另一台 `d0fd0840` 为
  `product=enuma`，全程未操作。

## 前置：两次门禁失败与断电复位

- 21:51:31 第一轮 4 次查询全部成功；21:51:38 第二轮 `product`、`current-slot` 正常，
  `is-userspace` 返回 `FAILED (remote: 'unknown command')`、
  `partition-size:vendor_boot_a` 返回 `FAILED (remote: 'GetVar Variable Not found')`。
  按「任一次失败即停」**未刷写**。
- 随后一次只读诊断（单进程连续 8 次）扩大到 6/8 失败，仅 `current-slot` 仍应答：
  `product` 与 `partition-size:vendor_boot_a`、`is-userspace` 均
  `FAILED (remote: 'GetVar Variable Not found')`。该结果**否定**了「故障来自跨进程
  调用间隔」的猜测：同一进程内连续查询照样失败。
- 与 `docs/nuwa-fua-fallback-recover-20261127-observation.md` 记录的「被拒 download
  之后会话异常」不同，本次这一启动会话**没有任何 fastboot download**，getvar 仍退化。
  该文那条因果推断至少不完整；本轮只记录现象，不给新机制结论。
- 用户彻底断电复位并重新进入 fastboot 后，21:54 的门禁一次性全过（见下）。本轮所有
  读数均为复位后重新采集。
- 补充事实（跨 worktree）：同一设备在 21:37 曾被另一轮刷入并重启过 banner r2 outer
  `7211a988…e4495`，本轮 R 刷入覆盖了该 `vendor_boot_a` 内容。该轮记录不在本 worktree。
  `boot_a` 本轮未读、未写，内容假设仍为 r4 loader `692cfcca…`，**本轮未验证**。

## 门禁：单进程连续 8 次（21:54:31，跨度 0.39 s）

每轮顺序 `product` → `is-userspace` → `current-slot` → `partition-size:vendor_boot_a`。
判定按输出文本（`getvar` 失败时 exit 仍可能为 0）。

| # | 墙钟（+08:00） | 偏移 | 变量 | 值 | FAILED |
| --- | --- | --- | --- | --- | --- |
| 1 | 21:54:31.377 | +0.01 s | product | `nuwa` | 否 |
| 2 | 21:54:31.466 | +0.09 s | is-userspace | `no` | 否 |
| 3 | 21:54:31.515 | +0.14 s | current-slot | `a` | 否 |
| 4 | 21:54:31.566 | +0.19 s | partition-size:vendor_boot_a | `0x6000000` | 否 |
| 5 | 21:54:31.619 | +0.24 s | product | `nuwa` | 否 |
| 6 | 21:54:31.667 | +0.29 s | is-userspace | `no` | 否 |
| 7 | 21:54:31.717 | +0.34 s | current-slot | `a` | 否 |
| 8 | 21:54:31.769 | +0.39 s | partition-size:vendor_boot_a | `0x6000000` | 否 |

8/8 成功，值全部符合预期，无 `Variable Not found`、无 `unknown command`。

## 产物实算

```text
path   worktree-sb0-wr-20261126/out/R-package-r4/vendor_boot.img
size   100663296                (期望 100663296)
sha256 3f5ffaee9b88439cd7ecbb6f630b4e133b5dbe5a3e5d488d61831c02ee3b7668
```

与授权值逐字一致。该哈希与
`docs/nuwa-sb0-rw-device-20261127-observation.md` 记录的 R1/R2 输入为同一文件。

## 唯一一次刷写（21:54:32.121–21:54:34.505）

```text
fastboot -s <nuwa-serial> flash vendor_boot_a <...>/R-package-r4/vendor_boot.img
  Sending 'vendor_boot_a' (98304 KB)  OKAY [  2.262s]
  Writing 'vendor_boot_a'             OKAY [  0.036s]
  Finished. Total time: 2.333s
```

- **exit 0**，命令耗时 2.384 s。
- 输出**没有** `partition-size: 0` / AVB footer 警告，与门禁中分区大小可读一致。
- 只刷一次，未重试；未切槽、未刷其他分区、未初始化、未写 `userdata`/`metadata`。

## 唯一一次 reboot 与 90 s 采样

```text
fastboot -s <nuwa-serial> reboot
  Rebooting                                          OKAY [  0.000s]
  Finished. Total time: 0.000s
```

- 发起 `21:54:34.513`，返回 `21:54:34.558`，**exit 0**；只执行一次。

| 采样 | 相对 | 墙钟（+08:00） | nuwa 在 fastboot | `????????????` | adb |
| --- | --- | --- | --- | --- | --- |
| S0 | +0 s | 21:54:34.564 | 否 | 是 | 无 |
| S1 | +10 s | 21:54:44.577 | 否 | 否 | 无 |
| S2 | +20 s | 21:54:54.568 | 否 | 否 | 无 |
| S3 | +30 s | 21:55:04.570 | 否 | 否 | 无 |
| S4 | +40 s | 21:55:14.576 | 否 | 否 | 无 |
| S5 | +50 s | 21:55:24.563 | 否 | 否 | 无 |
| S6 | +60 s | 21:55:34.580 | 否 | 否 | 无 |
| S7 | +70 s | 21:55:44.577 | 否 | 否 | 无 |
| S8 | +80 s | 21:55:54.566 | 否 | 否 | 无 |
| S9 | +90 s | 21:56:04.568 | 否 | 否 | 无 |

- `+0 s`：nuwa 行只剩 `????????????`（serial 不可读，USB 正在重枚举），稳定 fastboot
  态已打断；`+10 s` 起该行也不再出现，nuwa 从主机 USB 完全消失；到 `+90 s` 未回来。
- `adb devices -l` 10 点全部无设备。
- 采样窗口内未追加 reboot、未重刷、未发任何 adb 命令。

## 判读

- 只证明 bootloader 接收了 `3f5ffaee…b7668` outer：`Sending`/`Writing` OKAY、exit 0。
  无 `fastboot fetch`（该 bootloader 不支持）或分区回读，**不证明盘上字节内容**。
- USB 行为与 R1、R2 两轮一致：`+0 s` 离开稳定态，随后整段不在总线上。这三个样本
  说明该候选启动时主机侧看不到 USB 是**可重复**现象，但 10 s 采样粒度不能区分
  「加载器已切到内核、内核未建 USB」与「未进入内核」。
- **Data 窗口结果未知**。R 合同的输出是屏幕上的 `BLANK` / `EXACT-SB0`，本轮没有
  照片、读屏或串口，因此本记录不给出该分类，也不改变 R2 `EXACT-SB0` 的既有结论。
- 本轮不重试 W、不涉及 SB0 写入；W 回执 `UNKNOWN` 的既有边界不变。

## 边界

- 未验证：盘上分区字节、`boot_a` 内容、内核是否开始执行、Data 窗口内容、文件系统
  挂载、用户态与认证（NOT REACHED，本轮不涉及）。
- `+0 s` 的 `????????????` 只证明 USB 重枚举；90 s 采样不给出设备离开 USB 的总时长，
  也不排除更晚时候回到 fastboot（本 worktree 前几轮出现过 10 s 内回落，本轮 90 s 内
  没有）。
- 照片/截帧不入 Git；本轮没有照片。
- 原始时间线与命令输出只在本轮主机日志，未落盘为独立证据目录；本文件保留结论与
  时间戳。
