# nuwa post-event diagnostic outer — 2026-11-27 flash observation

状态：设备写入已执行，主机侧 self-checked；**未重启、未启动**，因此没有屏幕或
运行时证据。本轮只验证身份、产物哈希与 `vendor_boot_a` 刷写，不构成候选启动验收、
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
- 下一次启动需要单独授权；本轮不提供快速重启或冷启动证据。
- 原始命令输出只留在 `out/nuwa-postevent-flash-20261127/`（Git 忽略，序列号已脱敏）。
