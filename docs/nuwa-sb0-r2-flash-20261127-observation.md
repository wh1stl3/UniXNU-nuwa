# nuwa R2 只读诊断 outer 刷入、单次重启与 90 秒采样 — 2026-11-27 实机观察

状态：**device/self-checked**。唯一 nuwa 在 fastboot；R2 outer
`e4a8aaf1…b03d` 经一次 `flash vendor_boot_a` 被 bootloader 接受，随后一次
`fastboot reboot`；90 秒内设备离开主机 USB，无 nuwa fastboot、无 adb。屏幕
R2 摘要未取得，**不声称回放结果或进入系统**。主机侧命令与输出为本轮记录；
设备行为只到 USB 枚举层。

## 授权与审查

- 用户本轮授权：门禁 → 校验产物 → 只刷一次 `vendor_boot_a` → 一次 reboot →
  90 秒采样；不刷其他分区、不切槽、不初始化、不写 `userdata`。
- 审查：reviewer **PASS WITH CONDITIONS**，session
  `ses_de28b9723ffePflNk4Jxlo2HWn`（主控转述）。本轮未重新发起审查，未使用
  `deep_reviewer`。
- 设备：唯一 nuwa；serial 不入库，本记录统一写 `<nuwa-serial>`。另一台
  `d0fd0840` 为 `product=enuma`，全程未操作。

## 门禁：单进程连续 8 次

第一次门禁在第 4 项被**主机侧取值脚本**误判：设备实际返回
`partition-size:vendor_boot_a: 0x6000000`，脚本按第一个冒号切分得到
`vendor_boot_a: 0x6000000`。该次没有 `FAILED`、没有刷写；修正取值后重新做完整
8 次。以下为修正后的结果。

| # | 墙钟（+08:00） | 变量 | 值 | 结果 |
| --- | --- | --- | --- | --- |
| 1 | 23:01:36.778 | product | `nuwa` | OK |
| 2 | 23:01:36.978 | is-userspace | `no` | OK |
| 3 | 23:01:37.053 | current-slot | `a` | OK |
| 4 | 23:01:37.106 | partition-size:vendor_boot_a | `0x6000000` | OK |
| 5 | 23:01:37.153 | product | `nuwa` | OK |
| 6 | 23:01:37.200 | is-userspace | `no` | OK |
| 7 | 23:01:37.240 | current-slot | `a` | OK |
| 8 | 23:01:37.282 | partition-size:vendor_boot_a | `0x6000000` | OK |

8/8 成功，跨度 0.55 s；无 `FAILED`、`Variable Not found` 或
`unknown command`。

## 产物核对

```text
path   worktree-sb0-wr-20261126/out/R2-package-r8/vendor_boot.img
size   100663296                (期望 100663296)
sha256 e4a8aaf191bba1b4b6c28222a8221bdd8826a5312a9b0183b7391c909933b03d
```

与 reviewer 接受的 r8 逐字一致。

## 唯一一次刷写

```text
fastboot -s <nuwa-serial> flash vendor_boot_a <...>/R2-package-r8/vendor_boot.img
  Sending 'vendor_boot_a' (98304 KB)                 OKAY [  2.300s]
  Writing 'vendor_boot_a'                            OKAY [  0.030s]
  Finished. Total time: 2.365s
```

- **exit 0**，主机计时 2.511 s；无 `FAILED`、无 AVB footer 警告。
- 只刷一次，未重试；未切槽、未刷其他分区、未初始化、未写
  `userdata`/`metadata`。

## 唯一一次 reboot 与 90 秒采样

```text
fastboot -s <nuwa-serial> reboot
  Rebooting                                          OKAY [  0.000s]
  Finished. Total time: 0.000s
```

- 发起/记录 `2026-11-27T23:02:11.781+08:00`，**exit 0**；只执行一次。

| 采样 | 相对 | 墙钟（+08:00） | nuwa 在 fastboot | adb 设备 |
| --- | --- | --- | --- | --- |
| S0 | +0 s | 23:02:11.788 | 否；仅见 `????????????  fastboot` | 无 |
| S1 | +10 s | 23:02:21.794 | 否 | 无 |
| S2 | +20 s | 23:02:31.790 | 否 | 无 |
| S3 | +30 s | 23:02:41.788 | 否 | 无 |
| S4 | +40 s | 23:02:51.794 | 否 | 无 |
| S5 | +50 s | 23:03:01.800 | 否 | 无 |
| S6 | +60 s | 23:03:11.795 | 否 | 无 |
| S7 | +70 s | 23:03:21.789 | 否 | 无 |
| S8 | +80 s | 23:03:31.789 | 否 | 无 |
| S9 | +90 s | 23:03:41.789 | 否 | 无 |

- S0 的 fastboot 行只剩不可读 serial（USB 重枚举），不是 nuwa 稳定态；S1 起
  该行也消失，设备完全离开主机 USB。
- `adb devices -l` 10 点全部无设备；采样窗口 90.10 s，未追加 reboot、未重刷、
  未发 adb 写/挂载命令。

## 判读

- 只证明 bootloader 接收并写入了 `e4a8aaf1…b03d`：`Sending`/`Writing OKAY`、
  exit 0；bootloader 不支持 `fastboot fetch`，无分区字节回读，**不证明盘上
  字节内容**。
- USB 行为与 R1/R2/R3 一致：+0 s 离开稳定 fastboot，+10 s 起完全不在主机
  USB。该现象可重复，但 10 s 粒度不能区分「加载器已切到内核、内核未建 USB」
  与「未进入内核」。
- **R2 停屏结果未取得**：本轮没有照片、读屏或串口，不能报告
  `ANCHOR/HDR/REASON/PAGES`，也不能把 USB 离场当作 R2 回放结论。预期终点是
  R2 停屏，不是进入系统；本轮未进入 adb/用户态。
- 未验证：盘上分区字节、内核是否开始执行、R2 摘要、文件系统挂载、用户态、
  认证（NOT REACHED，本轮不涉及）。

## 边界

- 未刷 `boot_a`、未读 `boot_a`、未切槽、未初始化、未写
  `userdata`/`metadata`；只触碰 `vendor_boot_a`。
- 本轮没有新增写权限；R2 仍是只读诊断，不是生产写入或交互验收。
- 照片/截帧不入 Git；本轮没有照片。
- 原始时间线与命令输出只在本轮主机日志；本文件保留结论与时间戳。
