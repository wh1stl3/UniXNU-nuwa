# nuwa A 槽状态与单次 set_active — 2026-11-28

状态：**device/self-checked**。A 槽操作前状态查询为
`slot-unbootable:a=yes`、`slot-retry-count:a=0`；按用户授权执行一次
`set_active a`，返回 OKAY、exit 0。随后只读复查
`slot-unbootable:a=no`、`current-slot=a`。本轮未刷写、未 reboot。

## 授权与身份

用户要求先确认唯一 nuwa，读取当前槽、A/B 的 unbootable 与 retry count、
`is-userspace`；仅当 A 的 unbootable 为 `yes` 时执行一次 `set_active a`，
然后复查 A 的 unbootable 和当前槽。不授权刷写或 reboot。

16:55:36.967 +08:00 枚举 adb 0 台、fastboot 2 台，均 exit 0；逐台
`getvar product` 分别为 `enuma`、`nuwa`。选中唯一 nuwa，以下所有定向
设备命令使用同一固定 serial；serial 不入库。

## 操作前七项只读结果

以下时间为主机本地 +08:00。`product` 在身份识别时读取，其余项按表中顺序
读取；各命令标准输出为空，标准错误返回所列字段及 `Finished`，exit 均为 0。

| 完成时间 | 字段 | 实际值 | exit |
| --- | --- | --- | ---: |
| 16:55:37.081 | `product` | `nuwa` | 0 |
| 16:55:37.140 | `current-slot` | `a` | 0 |
| 16:55:37.193 | `slot-unbootable:a` | `yes` | 0 |
| 16:55:37.252 | `slot-retry-count:a` | `0` | 0 |
| 16:55:37.301 | `slot-unbootable:b` | `no` | 0 |
| 16:55:37.350 | `slot-retry-count:b` | `7` | 0 |
| 16:55:37.398 | `is-userspace` | `no` | 0 |

## 单次 set_active 与复查

```text
16:55:37.398 fastboot -s <fixed-nuwa> set_active a
Setting current slot to 'a'                        OKAY [  0.006s]
Finished. Total time: 0.011s
16:55:37.454 exit 0

16:55:37.505 slot-unbootable:a: no    exit 0
16:55:37.554 current-slot: a           exit 0
```

回执和复查字段均来自标准错误，标准输出为空。只发送一次 `set_active a`，
没有重试，没有执行刷写或 reboot；复查后最后一次设备响应来自同一固定
serial 的 fastboot。A/B 的 retry count 及 B 的 unbootable 只在操作前读取，
操作后未复查。

## 限制与证据

- 前轮最后一次刷写的目标是非自清除的 reset r2
  `a7bbfff6f0f858344b945a0e3e291e8859f11f883446d1650c2c257b2158e15d`；
  没有分区回读。见
  [reset 刷写与 reboot](nuwa-v1-nodur-reset-boot-20261128-observation.md)。
  后续若启动该包，可能再次请求清空窗口，须另获授权。
- `slot-unbootable:a` 从 `yes` 变为 `no` 只证明本次 fastboot 读取到的槽标志
  变化，不证明 reset 已执行、系统能启动、Data 挂载或掉电耐久。
- 本机脱敏日志
  `out/nuwa-v1-nodur-slot-check-20261128-165536-c6ec72ed/device-transcript-redacted.log`
  SHA-256 `99fa0877c65b8c058808b0ee52d1024d51bf659d4af7d5ed1c436bc3c6f438ec`。
  本文保留全部字段与回执；设备序列号不入库。
- 设备操作与记录均为 self-checked；独立 `verifier` 尚未复核，不应为复核重放
  `set_active`。
