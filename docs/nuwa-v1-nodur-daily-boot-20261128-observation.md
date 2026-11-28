# nuwa V1-NODUR daily r2 单次刷写与 reboot — 2026-11-28

状态：**device/self-checked；屏幕和运行结果未知**。daily r2 单次刷入
`vendor_boot_a`，Sending/Writing OKAY、exit 0；随后单次 reboot OKAY、exit 0。
完成 120 秒 adb/fastboot 采样；采样后一次只读识别中 adb 为 0 台，唯一
fastboot 设备为 enuma。没有分区回读、屏幕或 Data 运行证据。

## 当轮接受、授权与审查

> 用户本轮明确接受：LU0 `[59491258, 61588475)` 窗口内容可能丢失（无已校验备份），并授权刷入 daily 并重启。

用户同时要求不切槽、不初始化、不额外写 `userdata`。本轮未执行切槽、单独
初始化、reset 包刷写或主机额外 `userdata` 写入。daily 包不带
`sheng-data-reset=1`；启动后包自身是否执行普通 Data 写入未观测，不能据主机
命令推断运行期零写入。

`deep_reviewer` 对 NODUR r2 终审 **PASS WITH CONDITIONS**（会话
`ses_ddec18ea7ffeyB65Dqk9L1P4Im`），要求优先 daily；这是深审，不是“方案 B
审查，未经 deep_reviewer”。审查要求当轮授权、唯一识别、目标槽与回滚备份、
outer 哈希，以及窗口已校验备份或用户当轮接受丢失。本轮采用上面的用户接受，
不声称窗口有备份。终审及源码主机记录见
[V1-NODUR](nuwa-v1-nodur-20261128.md)。该 profile 的 `2a 00` 和零 `0x35`
不构成介质耐久契约；掉电可能丢最近写入或撕裂原地覆写。

刷前核验回滚说明
`UniXNU-nuwa/out/nuwa-boot-payload-write-20261115-01/ROLLBACK-r9.md` 存在；
同目录 `vendor_boot_a.stock.img` 为 100663296 B、SHA-256
`493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`。
它只能用于启动载荷回滚，不是 Data 窗口备份；本轮未回滚。

## 身份、门禁与产物

时间均为主机本地 +08:00，serial 不入库。16:40:32.467 枚举 adb 0 台、
fastboot 2 台，均 exit 0；逐台只读 product 分别为 `enuma`、`nuwa`，选中唯一
nuwa，后续定向命令固定其 serial。

| # | 完成时间 | 字段 | 读数 | exit |
| ---: | --- | --- | --- | ---: |
| 1 | 16:40:32.637 | `product` | `nuwa` | 0 |
| 2 | 16:40:32.688 | `current-slot` | `a` | 0 |
| 3 | 16:40:32.739 | `is-userspace` | `no` | 0 |
| 4 | 16:40:32.793 | `partition-size:vendor_boot_a` | `0x6000000` | 0 |
| 5 | 16:40:32.843 | `product` | `nuwa` | 0 |
| 6 | 16:40:32.896 | `current-slot` | `a` | 0 |
| 7 | 16:40:32.947 | `is-userspace` | `no` | 0 |
| 8 | 16:40:32.999 | `partition-size:vendor_boot_a` | `0x6000000` | 0 |

16:40:33.161 实算 daily
`out/nuwa-v1-nodur-20261128-daily-r2/vendor_boot.img` 长度 100663296 B，
SHA-256 `f38386adf86b45731af251a8ad95d3abceca0f67f6437148821b53345397aba8`。
只读句柄从计算哈希保持到刷写返回，禁止并发修改。reset r2 本轮未刷，也未
重新核算哈希。

## 唯一刷写及 reboot

```text
16:40:33.162 fastboot -s <fixed-nuwa> flash vendor_boot_a <daily-r2>
Sending 'vendor_boot_a' (98304 KB)                 OKAY [  2.265s]
Writing 'vendor_boot_a'                            OKAY [  0.035s]
Finished. Total time: 2.335s
16:40:35.571 exit 0

16:40:35.573 fastboot -s <fixed-nuwa> reboot
Rebooting                                          OKAY [  0.000s]
Finished. Total time: 0.000s
16:40:35.622 exit 0
```

以上回执均来自标准错误，标准输出为空；各执行一次，无重试。未观察到 AVB
footer 警告。bootloader 的 OKAY 不是分区内容回读，也不证明系统已经启动。

## 120 秒采样及身份边界

从 reboot 调用开始，以单调时钟每 10 秒发起一次 adb 与 fastboot 枚举；下表
时间是每组开始时间，采样中的两次枚举顺序执行且 exit 均为 0。设备总数是该
接口上所有设备，不是 nuwa 数。固定 serial 的匹配结果两接口均为 `absent`。

| 计划秒数 | 时间 | 实际秒数 | adb 总数 | fastboot 总数 |
| ---: | --- | ---: | ---: | ---: |
| 0 | 16:40:35.626 | 0.052 | 0 | 2 |
| 10 | 16:40:45.591 | 10.017 | 0 | 1 |
| 20 | 16:40:55.574 | 20.000 | 0 | 1 |
| 30 | 16:41:05.589 | 30.015 | 0 | 1 |
| 40 | 16:41:15.583 | 40.009 | 0 | 1 |
| 50 | 16:41:25.592 | 50.018 | 0 | 1 |
| 60 | 16:41:35.579 | 60.005 | 0 | 1 |
| 70 | 16:41:45.589 | 70.015 | 0 | 1 |
| 80 | 16:41:55.588 | 80.014 | 0 | 1 |
| 90 | 16:42:05.587 | 90.013 | 0 | 1 |
| 100 | 16:42:15.588 | 100.014 | 0 | 1 |
| 110 | 16:42:25.596 | 110.022 | 0 | 1 |
| 120 | 16:42:35.584 | 120.011 | 0 | 1 |

解析器在分割前先 `Trim()`；对含行首空白的模拟行及完整 fixed-serial 比较
做了合成自检。**但 0 秒组仍有两台 fastboot，日志却记固定 serial 缺席；未
保留原始枚举行，无法独立重建这一组或排除 serial 变化，不能用该行确定离开
fastboot 的时刻。** 120 秒采样内的剩余设备没有逐次复核型号。

采样后 16:43:36.084–16:43:36.141 再做一次顺序只读识别：adb 0 台、
fastboot 1 台，唯一 fastboot 设备 `product=enuma`，均 exit 0。因此这些
后续快照中没有看到 nuwa 的 adb/fastboot 设备；这不排除其他 USB 协议、设备
状态变化或系统启动，也不是屏幕结果。

## 证据与未验证项

- 本机脱敏执行日志
  `out/nuwa-v1-nodur-daily-boot-20261128-164032-1d9a5b0d/device-transcript-redacted.log`
  的 SHA-256 为
  `0131f9e056c33c091666ef059816728f3da282d453a9079f37c2432297a8b418`；
  上文记录全部门禁、回执和采样，serial 不入库。
- 分区回读、Data 挂载及写入、`tzinit` 结果、屏幕、交互和掉电耐久均未验证；
  本轮没有认证证据。后续设备操作需要另获授权。
- 设备操作、日志与主机检查均为 self-checked；独立 `verifier` 尚未复跑，不应
  为复核重放刷写或 reboot。
