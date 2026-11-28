# nuwa post-event diagnostic outer — 2026-11-27 flash observation

状态：设备写入已执行，主机侧 self-checked；刷写轮**未重启、未启动**。后续单独授权的
一次 reboot 观测已执行（见文末），两路 USB 传输在 150 s 内未重现，仍无屏幕或运行时
证据。刷写轮只验证身份、产物哈希与 `vendor_boot_a` 刷写，不构成候选启动验收、
文件系统挂载或认证证据。

## 授权与审查

- 用户当轮明确授权：刷入诊断 outer，**不重启**，刷后留在 fastboot。
- `deep_reviewer` 终审 **PASS WITH CONDITIONS**
  （session `ses_de6f88826ffePVthCKXnVOioO2`）。
- 上一组 `ec230dff…` / `8dfe35fa…` 已被 deep review 退回，不作刷写候选；本轮使用
  修复后的 `b9103e97…` outer。

## 设备身份

- 唯一 nuwa 处于 fastboot；另一台 enuma 未操作。
- `product=nuwa`、`is-userspace=no`、`current-slot=a`、`slot-count=2`、
  `unlocked=yes`。
- `partition-size:vendor_boot_a=0x6000000` = 100,663,296 B，满足候选长度。

## 产物哈希

| 产物 | 字节 | SHA-256 / SHA-384 |
| --- | --- | --- |
| outer `vendor_boot.img` | 100,663,296 | `b9103e97409e83b1a70d058391e260b320500e016ece828fb1dacf02e74497b8` |
| kernel `kernel.macho` | 52,207,616 | `4e02af6228d363907d7d3fbe68776d80e649bb4516cd272343f89e4e38818398` |
| FAT `readback-fat.img` | 67,108,864 | `29f24dc5888b4965921e4c1a0630afe19b2b1ca53ee6fb0692d3571c507715af` |
| CHMH (experimental) | — | SHA-384 `d5f1299efaf7a672919b517eb9a27e62f8337da5ef8795991a624c5d264b3b22ebd67e3d04cd7443ef3501c185f314a5` |
| ADT `kernel.macho.adt` | 13,680 | `e87e638ee2a85a1cb57b06bad953782e6b789175d755cebee7683d08a16ea5f1` |

宿主 `audit.json` 另记录：seed `3c81135b…` 与 trust `eb1475f6…` 未变，args 602 B，
FAT free 11,021,312 B，`device_release=false`。CHMH 为实验身份，非认证。

## 刷写

输入路径：
`out/nuwa-postevent-20261127-package-r6/vendor_boot.img`。

```text
fastboot -s <nuwa-serial> flash vendor_boot_a <...>/vendor_boot.img
  Sending 'vendor_boot_a' (98304 KB)  OKAY [2.266s]
  Writing 'vendor_boot_a'             OKAY [0.035s]
  Finished. Total time: 2.334s
```

exit 0，只写一次 `vendor_boot_a`。未执行 `reboot`，未切槽，未刷其他分区，未初始化，
未写 `userdata`/`metadata`。

刷后再次 `fastboot devices`：nuwa 与 enuma 仍在 fastboot；nuwa 未离开 fastboot。

## 边界

- 本轮没有启动候选，因此不能报告 DATA0、PID1、SpringBoard、panic 行或任何屏幕
  结果；候选的 panic-safe 行 7/8 设计仍未在实机显示。
- 刷写成功只证明 bootloader 接收了镜像，不证明镜像可启动、屏幕可见或运行时正确。
- SB0/disposable 写门、认证与文件系统挂载状态均未改变；认证仍 **NOT REACHED**。
- 下一次启动需要单独授权；刷写轮不提供快速重启或冷启动证据。
- 原始命令输出只留在 `out/nuwa-postevent-flash-20261127/`（Git 忽略，序列号已脱敏）。

## 2026-11-27 重启观测（后续单独授权）

- 授权：用户当轮明确授权执行**一次** `fastboot reboot` 作启动观测；不刷分区、不切槽、
  不初始化、不写 `userdata`/`metadata`，观察期间不发送任何 adb 写命令或挂载命令。
- 重启前身份复核：唯一 nuwa、serial 不入库；`product=nuwa`、
  `current-slot=a`、`is-userspace=no`、`slot-count=2`。身份或槽位不符即停止的约定未触发。
- 重启命令与 exit：

```text
fastboot -s <nuwa-serial> reboot
  Rebooting                                          OKAY [  0.000s]
  Finished. Total time: 0.000s
exit 0
```

- 发起时间 `2026-11-27T12:06:47.667+08:00`，命令返回 `12:06:47.850`。
- 观察：自 `12:06:53` 起每 10 s 采样一次 `adb devices` / `fastboot devices`，共 15 次至
  `12:09:22`（相对 reboot 发起约 +15 s 至 +155 s），两路传输均未出现设备：

| 采样 | 墙钟 (+08:00) | adb | fastboot |
| --- | --- | --- | --- |
| +10 s | 12:07:03 | 无 | 无 |
| +20 s | 12:07:13 | 无 | 无 |
| +30 s | 12:07:22 | 无 | 无 |
| +40 s | 12:07:32 | 无 | 无 |
| +50 s | 12:07:42 | 无 | 无 |
| +60 s | 12:07:53 | 无 | 无 |
| +70 s | 12:08:02 | 无 | 无 |
| +80 s | 12:08:12 | 无 | 无 |
| +90 s | 12:08:23 | 无 | 无 |
| +100 s | 12:08:32 | 无 | 无 |
| +110 s | 12:08:43 | 无 | 无 |
| +120 s | 12:08:53 | 无 | 无 |
| +130 s | 12:09:03 | 无 | 无 |
| +140 s | 12:09:12 | 无 | 无 |
| +150 s | 12:09:22 | 无 | 无 |

- 边界：`fastboot` 接受 `reboot` 只证明 bootloader 收到命令；150 s 内两路 USB 传输都未
  重新枚举，既不能区分「已进入无 USB 服务的系统/UEFI」与「未上电或未启动」，也不证明
  启动到任何阶段。屏幕内容由用户拍照，本轮不判定画面，不报告 DATA0、PID1、
  SpringBoard、panic 行或任何屏幕结论。
- 本轮未重新核对 `vendor_boot_a` 已刷 outer 与 `boot_a` r4 loader 的盘上内容（无读取、
  无写入）；除上述一次 reboot 外未执行其他设备动作。
