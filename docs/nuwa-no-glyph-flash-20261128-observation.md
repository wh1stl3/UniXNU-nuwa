# nuwa 无字形示例 FUA 包刷写及重启 — 2026-11-28

状态：**device/self-checked**。单次 `vendor_boot_a` 刷写及单次 reboot 均获
bootloader OKAY；90 秒内未再枚举出原 nuwa serial。尚无本包的屏幕、Data 挂载或
运行时写入证据，不能将 USB 枚举结果当作启动成功或失败。

## 授权、审查与条件

- 用户当轮授权识别唯一 nuwa、仅刷一次 `vendor_boot_a`、单次 reboot 及 90 秒
  adb/fastboot 采样；不切槽、不初始化、不刷其他分区，也不由主机直接写
  `userdata`。经明确补充确认，**允许本次 FUA 包启动后向既有 userdata Data
  overlay 窗口自动写入**；这不是只读启动授权。
- 最终增量由普通 `reviewer` **PASS WITH CONDITIONS**，会话
  `ses_de229b371ffeLyDZjum1Eg4tZw`；方案 A 普通审查，本增量未使用
  `deep_reviewer`。判词针对完整 outer
  `8d77f769bbc23ce7eb4c93957fe6bd2bb47ee22509dd5cc59c3d8beecb1fcca7`
  与 banner r2 比较，未发现字形示例移除之外的渲染、存储、写门或 panic 行为改动；
  仍保留原有条件性绘制和运行时限制。继承的 FUA 写路径另有早前
  `deep_reviewer` 审查，见 [FUA 观察](nuwa-fua-trial-20261127-observation.md)。
- 审查要求修正参数长度口径：现有参数 **602 B 正文**；追加 merlinx 对照五项
  后是 **709 B 正文、710 B 含 NUL**，官方指南原样五项则是 **715 B 正文、
  716 B 含 NUL**。均超出 `CommandLine[608]` 的 607 B 正文上限。本包未追加
  这些参数，修正仅涉及文档，见 [构建记录](nuwa-no-glyph-examples-20261128.md)。
- 审查还要求刷前确认回滚备份可用。**执行者漏做了刷前核验**；刷后才实算确认
  `UniXNU-nuwa/out/nuwa-boot-payload-write-20261115-01/` 下的
  `boot_a.stock.img`（201326592 B，SHA-256
  `d530872b80f9cc44a260411a1a7d1c6357a9d3e562577e803e7a82945226c0d9`）、
  `vendor_boot_a.stock.img`（100663296 B，SHA-256
  `493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`）
  和 `ROLLBACK-r9.md` 在位。刷后核验不能补成刷前已核验；回滚未执行，备份也
  不恢复 Data overlay 内容。

## 设备门禁与产物

首次只读预检于 00:33:42–00:33:43 完成；为厘清上述自动写入授权而暂停后，
于 00:35:44 在一个主机进程内重新识别并执行以下门禁。`adb devices -l` 无设备；
`fastboot devices` 两台，逐台只读 product 为 `enuma` 和 `nuwa`，唯一 nuwa
被选中，后续目标命令固定同一 serial。另一台仅作型号确认；serial 不入库。

| # | 时间 +08:00 | 字段 | 读数 |
| --- | --- | --- | --- |
| 1 | 00:35:44.427 | product | `nuwa` |
| 2 | 00:35:44.474 | is-userspace | `no` |
| 3 | 00:35:44.515 | current-slot | `a` |
| 4 | 00:35:44.554 | partition-size:vendor_boot_a | `0x6000000` |
| 5 | 00:35:44.593 | product | `nuwa` |
| 6 | 00:35:44.631 | is-userspace | `no` |
| 7 | 00:35:44.672 | current-slot | `a` |
| 8 | 00:35:44.716 | partition-size:vendor_boot_a | `0x6000000` |

八项均 exit 0、无失败或重试。00:35:44.760 `slot-unbootable:a=no`、
00:35:44.802 `slot-retry-count:a=5`，均 exit 0；是刷前读数，重启后未复查。
00:35:44.997 实算
`out/nuwa-no-glyph-20261128-package/vendor_boot.img`：100663296 B，SHA-256
`8d77f769bbc23ce7eb4c93957fe6bd2bb47ee22509dd5cc59c3d8beecb1fcca7`。

## 唯一刷写与唯一 reboot

```text
00:35:44.999  fastboot -s <nuwa-serial> flash vendor_boot_a <reviewed outer>
Sending 'vendor_boot_a' (98304 KB)                 OKAY [  2.264s]
Writing 'vendor_boot_a'                            OKAY [  0.035s]
Finished. Total time: 2.333s
00:35:47.378  exit 0

00:35:47.379  fastboot -s <nuwa-serial> reboot
Rebooting                                          OKAY [  0.000s]
Finished. Total time: 0.000s
00:35:47.417  exit 0
```

无重试、无 AVB footer 警告；未切槽，未刷其他分区，未由主机初始化或直接写
`userdata`。bootloader 回执不是设备分区字节回读。

## 90 秒 USB 采样

相对时间从 reboot 命令返回后计；十次 `fastboot devices` 与 `adb devices -l`
均 exit 0，总采样用时 90.087 s。

| 采样 | 相对 | 时间 +08:00 | fastboot 行数 | 原 nuwa serial | 不可读行 | adb 行数 |
| --- | --- | --- | ---: | --- | ---: | ---: |
| S0 | +0.003 s | 00:35:47.421 | 2 | 否 | 1 | 0 |
| S1 | +10.008 s | 00:35:57.427 | 1 | 否 | 0 | 0 |
| S2 | +20.004 s | 00:36:07.422 | 1 | 否 | 0 | 0 |
| S3 | +30.008 s | 00:36:17.426 | 1 | 否 | 0 | 0 |
| S4 | +40.019 s | 00:36:27.438 | 1 | 否 | 0 | 0 |
| S5 | +50.011 s | 00:36:37.430 | 1 | 否 | 0 | 0 |
| S6 | +60.014 s | 00:36:47.433 | 1 | 否 | 0 | 0 |
| S7 | +70.020 s | 00:36:57.439 | 1 | 否 | 0 | 0 |
| S8 | +80.013 s | 00:37:07.432 | 1 | 否 | 0 | 0 |
| S9 | +90.004 s | 00:37:17.423 | 1 | 否 | 0 | 0 |

S0 不可读行未归属；其余 fastboot 行未重新按型号识别，不能排除目标以其他
serial 重枚举。脱敏操作日志仅留本地
`out/nuwa-no-glyph-flash-20261128/device.log`。

## 待观察及边界

已提示用户拍摄 `DATA mnt` 与 `DATA hdr … COUNT=` 两组完整字段；照片及转录尚未
取得。本包允许的自动 Data 写是否发生、挂载、UI、文件级持久及断电耐久均未证。
FUA 位在实验路径被接受但未转为介质 FUA，flush 返回成功不构成介质耐久证明；
认证仍 **NOT REACHED**。构建测试为 self-checked，独立 verifier 未复跑。
