# nuwa V1-NODUR reset r2 单次刷写与 reboot — 2026-11-28

状态：**device/self-checked；reset 运行结果未知**。reset r2 单次刷入
`vendor_boot_a`，Sending/Writing OKAY、exit 0；随后单次 reboot OKAY、exit 0。
10–120 秒采样中，刷前固定 serial 出现在 fastboot 列表。没有分区回读、屏幕或
Data 运行证据，不能据此判断 reset 是否实际执行。

## 当轮授权与审查

> 用户授权：刷入**非 FUA 的 reset 包**并启动一次（该包每次启动都会请求清空窗口，只启动一次）。

用户要求记录窗口内容可丢弃；LU0 `[59491258, 61588475)` 没有已校验备份。
用户授权包自身执行 reset，要求不切槽、不单独初始化、不额外写 `userdata`。
本轮只由主机刷写指定 `vendor_boot_a` 并请求一次 reboot；没有切槽、单独
初始化、刷 daily 或主机额外写 `userdata`。实际包自身是否写入 bitmap/header
未观测。

`deep_reviewer` 对 NODUR r2 终审 **PASS WITH CONDITIONS**（会话
`ses_ddec18ea7ffeyB65Dqk9L1P4Im`）；这是深审，不是“方案 B 审查，未经
deep_reviewer”。审查优先 daily；本轮在
[daily 刷写和启动](nuwa-v1-nodur-daily-boot-20261128-observation.md)之后，
按用户的新授权选择 reset。审查指出 reset 参数不自清除，必须能阻止第二次
启动前回到 bootloader 并换回已审 daily，不能控制自动重启则不使用 reset。
刷前询问用户能否阻止第二次启动并在此前回到 fastboot、具备换回 daily 的条件，
用户答复 **“能，已准备好”**。本轮未刷 daily；后续切换需当轮授权。

`V1-NODUR` 是非耐久契约，不承诺掉电后的 data/bitmap/header 落盘次序或
reset 原子性。终审和主机产物记录见 [V1-NODUR](nuwa-v1-nodur-20261128.md)。
刷前核验回滚说明
`UniXNU-nuwa/out/nuwa-boot-payload-write-20261115-01/ROLLBACK-r9.md` 存在；
同目录 `vendor_boot_a.stock.img` 为 100663296 B、SHA-256
`493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`。
它不是 Data 窗口备份；本轮未回滚。

## 身份、门禁与产物

时间均为主机本地 +08:00，serial 不入库。16:47:09 首次只读预检发现 adb
0 台、fastboot 2 台，product 分别为 `enuma`、`nuwa`；唯一 nuwa 的八项门禁
匹配。取得自动重启拦截准备确认后，16:49:37 在实际刷写的同一进程再次枚举：
adb 0 台、fastboot 2 台，逐台 product 仍为 `enuma`、`nuwa`，均 exit 0。
选中唯一 nuwa，后续定向命令固定其 serial；下表是第二次、刷前最终八项门禁。

| # | 完成时间 | 字段 | 读数 | exit |
| ---: | --- | --- | --- | ---: |
| 1 | 16:49:37.724 | `product` | `nuwa` | 0 |
| 2 | 16:49:37.785 | `current-slot` | `a` | 0 |
| 3 | 16:49:37.838 | `is-userspace` | `no` | 0 |
| 4 | 16:49:37.890 | `partition-size:vendor_boot_a` | `0x6000000` | 0 |
| 5 | 16:49:37.942 | `product` | `nuwa` | 0 |
| 6 | 16:49:37.990 | `current-slot` | `a` | 0 |
| 7 | 16:49:38.052 | `is-userspace` | `no` | 0 |
| 8 | 16:49:38.102 | `partition-size:vendor_boot_a` | `0x6000000` | 0 |

16:49:38.265 实算 reset
`out/nuwa-v1-nodur-20261128-reset-r2/vendor_boot.img` 为 100663296 B，
SHA-256 `a7bbfff6f0f858344b945a0e3e291e8859f11f883446d1650c2c257b2158e15d`；
只读句柄从实算哈希一直保持到刷写返回，禁止并发修改。16:49:38.423 只核
daily SHA-256 `f38386adf86b45731af251a8ad95d3abceca0f67f6437148821b53345397aba8`，
未刷 daily。

## 唯一刷写及 reboot

```text
16:49:38.423 fastboot -s <fixed-nuwa> flash vendor_boot_a <reset-r2>
Sending 'vendor_boot_a' (98304 KB)                 OKAY [  2.265s]
Writing 'vendor_boot_a'                            OKAY [  0.035s]
Finished. Total time: 2.333s
16:49:40.803 exit 0

16:49:40.804 fastboot -s <fixed-nuwa> reboot
Rebooting                                          OKAY [  0.000s]
Finished. Total time: 0.000s
16:49:40.858 exit 0
```

以上回执均来自标准错误，标准输出为空；各执行一次，无重试。未观察到 AVB
footer 警告。bootloader 的 OKAY 不是分区内容回读，也不能证明包已执行。

## 120 秒采样

从 reboot 调用开始，以单调时钟每 10 秒发起 adb 与 fastboot 枚举；表中时间
为每组开始时间，组内两项顺序执行且 exit 均为 0。`dev01`、`dev02`、`dev03`
是本次进程中的临时别名，不是 serial：刷前 `dev01` 的 product 为 `enuma`，
`dev02` 为选中的 `nuwa`；`dev03` 未识别，不能推断其型号或身份。解析前
对枚举行 `Trim()`，每次按精确 serial 映射到别名。

| 计划秒数 | 时间 | 实际秒数 | adb | fastboot 列表 |
| ---: | --- | ---: | --- | --- |
| 0 | 16:49:40.862 | 0.057 | 无 | `dev01`, `dev03` |
| 10 | 16:49:50.819 | 10.014 | 无 | `dev01`, `dev02` |
| 20 | 16:50:00.815 | 20.010 | 无 | `dev01`, `dev02` |
| 30 | 16:50:10.821 | 30.016 | 无 | `dev01`, `dev02` |
| 40 | 16:50:20.820 | 40.014 | 无 | `dev01`, `dev02` |
| 50 | 16:50:30.819 | 50.014 | 无 | `dev01`, `dev02` |
| 60 | 16:50:40.814 | 60.008 | 无 | `dev01`, `dev02` |
| 70 | 16:50:50.817 | 70.012 | 无 | `dev01`, `dev02` |
| 80 | 16:51:00.822 | 80.016 | 无 | `dev01`, `dev02` |
| 90 | 16:51:10.810 | 90.005 | 无 | `dev01`, `dev02` |
| 100 | 16:51:20.820 | 100.015 | 无 | `dev01`, `dev02` |
| 110 | 16:51:30.805 | 110.000 | 无 | `dev01`, `dev02` |
| 120 | 16:51:40.811 | 120.005 | 无 | `dev01`, `dev02` |

0 秒组固定 serial 未出现在 fastboot 列表；10–120 秒组匹配到同一固定 serial。
`dev03` 的型号、0–10 秒的设备行为及返回 fastboot 的原因均未知；fastboot
枚举不区分 bootloader 与 userspace，末次采样也未重新读取 `is-userspace`。
不能据此认定 reset 执行、重启原因或 Data 状态，也不能推断整个期间没有第二次
包自身启动。主机没有再次发送 reboot。

## 证据与未验证项

- 本机脱敏日志
  `out/nuwa-v1-nodur-reset-boot-20261128-164937-286f4511/device-transcript-redacted.log`
  SHA-256 `6e56d0fa30a62d1868c963f9887b2a5172845815b0559b3a3ecc7ed95645fc8b`；
  上文记录全部最终门禁、回执及采样。serial 不入库。
- 等待用户屏幕照片：`DATA mnt`、`DATA hdr`，重点确认是否为 `st=3`（Fresh）；
  若仅显示 fastboot 也应记录。未看到 Fresh 前不声称 reset 成功。
- 分区回读、reset bitmap/header 实际写入、Data 挂载、交互和掉电耐久均未验证；
  本轮没有认证证据。reset 参数不是自清除，后续启动或切换 daily 需要新授权。
- 设备操作与主机检查均为 self-checked；独立 `verifier` 尚未复跑，不应为复核
  重放刷写或 reboot。
