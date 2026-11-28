# nuwa A 槽恢复后 reset r2 单次 reboot — 2026-11-28

状态：**device/self-checked；屏幕与 reset 结果未知**。A 槽恢复后，四项只读
门禁匹配，单次 reboot 返回 OKAY、exit 0；完成 120 秒 adb/fastboot 采样。
原固定 serial 在首次 fastboot 采样即缺席，但该组另有身份未知的设备；10 秒
起各组 fastboot 列表只含此前识别为 enuma 的设备，adb 均为空。具体离开时刻、
reset 是否执行及系统状态未知。

## 授权与前史

用户要求在 A 槽恢复后对已刷入的非 FUA reset 包执行一次 reboot，并允许 reset
由包自身执行；不刷写、不切槽、不单独初始化。前轮用户已明确接受 LU0
`[59491258, 61588475)` 窗口内容可能丢失，并确认能在第二次启动 reset 前
拦截并回到 fastboot；该包的 reset 参数不会自清除。

[槽恢复记录](nuwa-v1-nodur-slot-reenable-20261128-observation.md)记载
`slot-unbootable:a=yes` 时用户授权单次 `set_active a`，复查为 `no`、当前槽
`a`。[reset 刷写记录](nuwa-v1-nodur-reset-boot-20261128-observation.md)的
目标为 SHA-256
`a7bbfff6f0f858344b945a0e3e291e8859f11f883446d1650c2c257b2158e15d`。
没有分区回读，本轮所启动载荷的身份仍依赖该刷写回执与其后分区未改变的假设。
原包深审为 `deep_reviewer` **PASS WITH CONDITIONS**（会话
`ses_ddec18ea7ffeyB65Dqk9L1P4Im`）；不是“方案 B 审查，未经 deep_reviewer”。

## 重启前身份及门禁

时间为主机本地 +08:00；serial 不入库。17:00:32.488 枚举 adb 0 台、
fastboot 2 台，均 exit 0；逐台只读 product 分别为 `enuma`、`nuwa`。
选中唯一 nuwa，后续定向命令固定其 serial。

| 完成时间 | 字段 | 值 | exit |
| --- | --- | --- | ---: |
| 17:00:32.659 | `product` | `nuwa` | 0 |
| 17:00:32.708 | `current-slot` | `a` | 0 |
| 17:00:32.762 | `is-userspace` | `no` | 0 |
| 17:00:32.812 | `slot-unbootable:a` | `no` | 0 |

这里的门禁是在 reboot 前执行，本轮没有刷写。

## 唯一 reboot

```text
17:00:32.812 fastboot -s <fixed-nuwa> reboot
Rebooting                                          OKAY [  0.000s]
Finished. Total time: 0.000s
17:00:32.859 exit 0
```

回执来自标准错误，标准输出为空。只发送一次，没有重试；本轮未执行刷写、
`set_active`、切槽或独立初始化，也没有额外主机 `userdata` 写入。是否发生包
自身的 reset 写入未观测。

## 120 秒采样与身份边界

从 reboot 调用开始，以单调时钟每 10 秒发起 adb 与 fastboot 枚举；表中本地
时间为每组开始时间，后两列是各接口枚举完成时相对 reboot 的秒数。两项
顺序执行，所有枚举 exit 均为 0。每组 adb 列表均为空，原固定 serial 在每组
fastboot 列表中均未出现。

`dev01`、`dev02`、`dev03` 为本次进程内临时别名，不是 serial。刷前
`dev01` 的 product 为 `enuma`，`dev02` 为固定目标 `nuwa`；`dev03` 型号
未知。解析枚举行前先 `Trim()`，按精确 serial 分配别名。

| 计划秒数 | 组开始时间 | adb 完成秒数 | fastboot 完成秒数 | fastboot 列表 |
| ---: | --- | ---: | ---: | --- |
| 0 | 17:00:32.864 | 0.112 | 0.171 | `dev01`, `dev03` |
| 10 | 17:00:42.824 | 10.075 | 10.117 | `dev01` |
| 20 | 17:00:52.831 | 20.082 | 20.124 | `dev01` |
| 30 | 17:01:02.821 | 30.071 | 30.116 | `dev01` |
| 40 | 17:01:12.817 | 40.067 | 40.110 | `dev01` |
| 50 | 17:01:22.816 | 50.074 | 50.121 | `dev01` |
| 60 | 17:01:32.823 | 60.091 | 60.137 | `dev01` |
| 70 | 17:01:42.816 | 70.075 | 70.119 | `dev01` |
| 80 | 17:01:52.816 | 80.067 | 80.109 | `dev01` |
| 90 | 17:02:02.817 | 90.081 | 90.132 | `dev01` |
| 100 | 17:02:12.831 | 100.083 | 100.133 | `dev01` |
| 110 | 17:02:22.824 | 110.070 | 110.112 | `dev01` |
| 120 | 17:02:32.827 | 120.071 | 120.115 | `dev01` |

0 秒组中的 `dev03` 做了一次只读 `getvar product`，4 秒未完成，包装进程终止
该查询并记 `exit=-1`；这是包装层的超时标记，不是 fastboot 自身退出码。
没有重试，超时原因和该设备型号均未知。因此 0.171 秒只能说固定 serial
缺席，不能排除 nuwa 以不同 serial 出现。10.117 秒起所采 fastboot 快照
只含此前识别为 enuma 的 `dev01`，对应 adb 快照为空；这是离散快照，不证明
其间连续离线、其他 USB 协议状态或精确离开时刻。

## 证据与未验证项

- 本机脱敏日志
  `out/nuwa-v1-nodur-restored-reboot-20261128-170032-ce322252/device-transcript-redacted.log`
  SHA-256 `2fd023504fb512ce27f2170ea0b6ef185b0f5a3e1b62b9db436c7781a9bfa2c1`。
  上文记录全部门禁、reboot 回执和采样；serial 不入库。
- 等待用户照片，记录 `DATA mnt` 和 `DATA hdr`，尤其 `st=3`（Fresh）；未见
  画面前不声称 reset 成功。分区回读、Data 写入与挂载、交互和掉电耐久均未知。
- 设备操作与主机记录均为 self-checked；独立 `verifier` 未复跑，不应为复核
  重放 reboot。
