# nuwa retained v1 reset r3 单次 reboot — 2026-11-28

状态：**device/self-checked；reboot 已请求，reset 运行结果未知**。唯一 nuwa 的
八项只读门禁满足；bootloader 不支持分区 fetch，随后一次 reboot 返回 OKAY、
exit 0。完成 120 秒 adb/fastboot 采样，但 serial 匹配存在下述缺陷，不能据此
确认目标何时离开 fastboot 或是否仍在 fastboot。未观察屏幕或 Data 状态。

## 授权、前史和边界

- 本轮用户称已断电复位并重新进入 fastboot，明确同意「reset 包启动时自行写入
  userdata 内的 bitmap 与 header（即执行 reset）」。这是本轮启动和包自身
  reset 写入的授权；不含主机额外写 userdata、刷写、切槽或单独初始化。
  断电复位本身为用户转述，主机没有独立测量。
- 已刷镜像的目标为
  `213cdf065fe5eab45215f96c2efb12a8c320d51a4efadfcd586dd71140dd942d`；
  [前次刷写记录](nuwa-v1-retained-reset-flash-20261128-observation.md)
  记载单次 `vendor_boot_a` Sending/Writing OKAY、exit 0，及
  `deep_reviewer` 终审 **PASS WITH CONDITIONS**（会话
  `ses_de05c0974ffeUCPfM5MRsnAzb5`；不是「方案 B 审查，未经
  deep_reviewer」）。此前无分区回读；本轮也无法回读，镜像驻留身份仍依赖
  前次刷写回执和其后状态未变的假设。
- 既有深审条件中，当前启动域 retained 队列交接和旧 DMA 排除仍无独立证据。
  前次用户接受缺少这些证据的刷写残余风险和未备份 Data 窗口丢失风险；本轮
  授权 reset 不证明队列交接、旧 DMA 排空或持久性。reset 参数不是自清除标志，
  禁止自动再次启动；结果未明时停止，不自动重试。

## 设备识别和门禁

主机时间均为 +08:00；serial 不入库。16:05:25.447–16:05:25.656
`adb devices -l` exit 0、0 台，`fastboot devices` exit 0、2 台；
逐台 `getvar product` 均 exit 0，分别为 `enuma` 和 `nuwa`。选中唯一
`nuwa`，后续所有定向设备命令使用该固定 serial。

以下八次由同一个 PowerShell 主控进程按序发起；表中时间为各查询完成时间。
每次结果均来自 fastboot 标准错误，标准输出为空，exit 均为 0：

| # | 时间 | 字段 | 读数 | exit |
| ---: | --- | --- | --- | ---: |
| 1 | 16:05:25.825 | `product` | `nuwa` | 0 |
| 2 | 16:05:25.878 | `current-slot` | `a` | 0 |
| 3 | 16:05:25.930 | `is-userspace` | `no` | 0 |
| 4 | 16:05:25.982 | `partition-size:vendor_boot_a` | `0x6000000` | 0 |
| 5 | 16:05:26.038 | `product` | `nuwa` | 0 |
| 6 | 16:05:26.089 | `current-slot` | `a` | 0 |
| 7 | 16:05:26.142 | `is-userspace` | `no` | 0 |
| 8 | 16:05:26.199 | `partition-size:vendor_boot_a` | `0x6000000` | 0 |

## 只读回读尝试与唯一 reboot

16:05:26.202–16:05:26.265 对固定 serial 执行一次只读
`fastboot fetch vendor_boot_a <out 内文件>`，exit 1，标准错误：

```text
fastboot: error: Unable to get max-fetch-size. Device does not support fetch command.
```

因此**无法回读**，没有重刷；工具在 `out/` 留下 0 B 输出文件，不是分区
回读结果。

```text
16:05:26.274 fastboot -s <fixed-nuwa> reboot
Rebooting                                          OKAY [  0.000s]
Finished. Total time: 0.000s
16:05:26.320 exit 0
```

以上回执来自标准错误，标准输出为空；只请求一次，没有重试。没有执行
flash、切槽、独立初始化或主机 userdata 写入；是否发生包自身的 reset 写入
未观测。

## 120 秒采样及身份限制

以 reboot 调用开始的单调时钟为基准，0–120 s 每 10 s 发起
`adb devices -l` 和 `fastboot devices`。下表为每组开始时间；两项枚举
exit 均为 0。设备总数是各接口全部设备数，不是 nuwa 数。

| 计划秒数 | 时间 | 实际秒数 | adb 总数 | fastboot 总数 | 日志中的固定 serial 匹配 |
| ---: | --- | ---: | ---: | ---: | --- |
| 0 | 16:05:26.327 | 0.050 | 0 | 2 | adb 否，fastboot 否 |
| 10 | 16:05:36.293 | 10.019 | 0 | 1 | adb 否，fastboot 否 |
| 20 | 16:05:46.289 | 20.015 | 0 | 1 | adb 否，fastboot 否 |
| 30 | 16:05:56.284 | 30.010 | 0 | 1 | adb 否，fastboot 否 |
| 40 | 16:06:06.280 | 40.006 | 0 | 1 | adb 否，fastboot 否 |
| 50 | 16:06:16.278 | 50.004 | 0 | 1 | adb 否，fastboot 否 |
| 60 | 16:06:26.288 | 60.013 | 0 | 1 | adb 否，fastboot 否 |
| 70 | 16:06:36.283 | 70.009 | 0 | 1 | adb 否，fastboot 否 |
| 80 | 16:06:46.278 | 80.004 | 0 | 1 | adb 否，fastboot 否 |
| 90 | 16:06:56.290 | 90.016 | 0 | 1 | adb 否，fastboot 否 |
| 100 | 16:07:06.285 | 100.011 | 0 | 1 | adb 否，fastboot 否 |
| 110 | 16:07:16.294 | 110.020 | 0 | 1 | adb 否，fastboot 否 |
| 120 | 16:07:26.288 | 120.014 | 0 | 1 | adb 否，fastboot 否 |

**匹配限制**：采样代码用 `($_ -split '\s+')[0]` 取 serial，没有先去除
行首空白；行首有空白时会错误地取到空字符串。合成文本自检中无行首空白
可匹配、有行首空白不能匹配。采样日志未保留原始枚举行，无法排除该情况。
因此上表仅照录日志的匹配结果；日志中的 `first_fastboot_absent_s=0.05`
及 `first_both_absent_s=0.05` **不能作为目标离开接口的证据**。首组仍有
2 台 fastboot，10 秒起为 1 台，但剩余设备身份未在采样中重新核对。设备
是否离开、何时离开均未知；不能推断 USB 完全离线或系统已启动。

## 证据与未验证项

- 脱敏原始执行日志仅在本机
  `out/nuwa-v1-reset-reboot-20261128-160525-9ea08987/device-transcript-redacted.log`，
  SHA-256 `ac0974bc7a3180616303876a94e44d009a0229165008b9893c27c4c98a84b306`。
  本文保留全部门禁、回执和采样结果；serial、照片和镜像不入库。
- Fresh（state 3）、bitmap/header 实际写入、Data 挂载、FUA 耐久、屏幕、
  后续 daily Resumed 以及持久交互均未验证；认证仍 NOT REACHED。
- 本轮设备与日志为 self-checked，独立 `verifier` 未复跑；不重放 reboot
  或 reset 作为验证。
