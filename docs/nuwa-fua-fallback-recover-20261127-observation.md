# FUA outer 回落 fastboot 复核与诊断 outer 恢复尝试 — 2026-11-27 observation

状态：前两次 `vendor_boot_a` 写入尝试均在 download 阶段被拒绝（0 B 写入）；用户
彻底断电复位后，第三次写入**成功**（`Sending`/`Writing OKAY`，exit 0），随后单次
`reboot` OKAY、exit 0。60 s 采样内设备在 +0 s 离开 fastboot 稳定态（serial 显示
`????????????`），+10 s 回到 fastboot 并持续到 +60 s，`adb` 全程无设备。主机侧
**self-checked**。无屏幕、启动阶段或用户态证据。

## 背景

- FUA 实验 outer `b5d1b9f1…` 已单次刷入 `vendor_boot_a`，刷写轮未启动；刷写输出与
  刷后状态见 `docs/nuwa-fua-trial-20261127-observation.md`。
- 2026-11-27 18:09:40 的授权单次 `fastboot reboot` 与 200 s 只读采样已记在同一文件
  「2026-11-27 18:09:40 授权重启与 200 秒在场采样（追加）」：重启瞬间 USB 重新枚举，
  10 s 内 nuwa 回到 fastboot 并持续到 200 s，`adb devices` 全程无设备。
- 本轮用户观测（主控转述）：FUA 包刷入后，`fastboot reboot` 与长按电源两次启动都只
  回到 fastboot，未出现字符界面。长按电源的时刻未记录；屏幕内容由用户观察，本记录
  不补充画面判读，也不据此判定启动阶段。

## 本轮授权与门禁

- 授权：识别唯一 nuwa；只刷一次 `vendor_boot_a`，写入诊断 outer
  `out/nuwa-postevent-20261127-package-r6/vendor_boot.img`；只执行一次
  `fastboot reboot`；随后 60 s 采样。异常即停。
- `fastboot devices` 两台：一台 `product=enuma`（未操作），一台唯一 nuwa（serial
  不入库，本轮固定使用）。
- nuwa 门禁复核（刷前）：`product=nuwa`、`current-slot=a`、`is-userspace=no`、
  `partition-size:vendor_boot_a=0x6000000` = 100,663,296 B，满足 ≥ 100,663,296 B。
  `slot-count=2` 见前轮记录，本轮未复读。
- 产物复核：`vendor_boot.img` 100,663,296 B，SHA-256
  `b9103e97409e83b1a70d058391e260b320500e016ece828fb1dacf02e74497b8`，与授权值及
  `docs/nuwa-postevent-20261127-observation.md` 的记录一致。

## 第一次刷写尝试：无后缀 `vendor_boot`（失败，未写入）

命令（目标名未带槽位后缀，与既往成功记录的 `flash vendor_boot_a` 不同）：

```text
fastboot -s <nuwa-serial> flash vendor_boot <...>/vendor_boot.img
```

实际输出：

```text
Warning: skip copying vendor_boot image avb footer (vendor_boot partition size: 0, vendor_boot image size: 100663296).
Sending 'vendor_boot' (98304 KB)                    FAILED (remote: 'Requested download size is more than max allowed
')
fastboot: error: Command failed
```

- 开始 `2026-11-27T18:17:24.088+08:00`，结束 `18:17:24.296`，**exit 1**。
- 输出没有 `Writing` 行；bootloader 在 download 阶段拒绝，未进入写入，判定本轮
  **0 B 写入**。
- 无重试。

### 第一次尝试的原因线索（被第二次尝试修正）

- 同一客户端对无后缀名查询失败：`getvar partition-size:vendor_boot` 返回
  `FAILED (remote: 'GetVar Variable Not found')`；带后缀的
  `partition-size:vendor_boot_a` 返回 `0x6000000`。客户端因此在 AVB footer 提示中
  显示 `partition size: 0`，并按整包 100,663,296 B 发送。
- 同一镜像、同一尺寸此前用显式 `flash vendor_boot_a` 成功（`Sending 'vendor_boot_a'
  (98304 KB) OKAY`、`Writing OKAY`，见 `docs/nuwa-postevent-20261127-observation.md`
  「刷写」节）。所以本次更像是目标名/AVB footer 处理差异导致发送尺寸超过 bootloader
  上限，而不是镜像或分区容量问题。
- bootloader 的上限没有读出：`getvar max-download-size` 同样返回
  `GetVar Variable Not found`。失败的确切额度未证；上述因果未验证。
- 客户端：platform-tools `fastboot version 37.0.1-15733141`。
- 第二次尝试（显式 `vendor_boot_a`）在同一错误处复现，见文末「第二次尝试」：目标名
  只是触发条件，决定性条件是刷写会话能否读到分区大小。

## 停止点与只读复核

- 按 brief「异常即停」：未重试刷写；**未执行**本轮授权的一次 `fastboot reboot`，
  也未做 60 s 采样——这两步以恢复成功为前提，本轮恢复未发生。
- 失败后只读复核（约 `18:17:50`，与客户端版本查询同批）：`fastboot devices` 两台仍
  在，nuwa serial 正常；`partition-type:vendor_boot_a: raw`；`adb devices` 无设备。
  `getvar max-download-size` 与无后缀 `partition-size:vendor_boot` 均返回
  `GetVar Variable Not found`。该批**没有复读** `product`/`current-slot`/
  `partition-size:vendor_boot_a`；它们到下一轮刷前门禁（18:20 起）复读时才暴露出
  不稳定。
- 未执行 `fastboot fetch` 或分区回读；未切槽，未刷其他分区，未初始化，未写
  `userdata`/`metadata`，未发任何 adb 写/挂载命令。

## 第二次尝试：显式 `vendor_boot_a`（2026-11-27 18:25，失败，未写入）

- 授权：主控确认第一次失败后，明确要求用显式 `vendor_boot_a` 重试**一次**；若再次
  失败即停，不重试、不再改目标名。
- 刷前复核（18:20:47–18:24:42）：`fastboot devices` 两台，enuma 未操作；nuwa serial
  与上轮相同（不入库）。镜像复算 100,663,296 B、SHA-256 `b9103e97…97b8`，与授权值
  一致。四个门禁值均至少成功读回一次：`product=nuwa`、`current-slot=a`、
  `is-userspace=no`、`partition-size:vendor_boot_a=0x6000000`。
- 同一时段 nuwa 的 `getvar` 出现随机 `GetVar Variable Not found` / `unknown command`：
  同一变量时好时坏（`partition-size:vendor_boot_a` 单独查询 6 次中前 3 次失败、后 3 次
  返回 `0x6000000`；链式 4 条查询的第 4 条稳定失败；18:26:42 四个门禁查询全部失败）。
  同批 enuma 的 `product` 查询稳定。该现象出现在第一次失败的 96 MiB download 之后；
  18:16–18:17:24 的同类查询全部正常。

唯一一次重试的实际输出：

```text
fastboot -s <nuwa-serial> flash vendor_boot_a <...>/vendor_boot.img
Warning: skip copying vendor_boot_a image avb footer (vendor_boot_a partition size: 0, vendor_boot_a image size: 100663296).
Sending 'vendor_boot_a' (98304 KB)                 FAILED (remote: 'Requested download size is more than max allowed
')
fastboot: error: Command failed
```

- 开始 `2026-11-27T18:25:21.646+08:00`，结束 `18:25:21.866`，**exit 1**。
- 无 `Writing` 行，0 B 写入；按指令停止，未重试、未改目标名、未 `reboot`、未做
  60 s 采样（采样以刷写成功为前提）。

### 判读（修正第一次尝试的假设）

- 显式 `_a` 复现同一错误，且警告显示**刷写会话内部**拿到的
  `vendor_boot_a partition size: 0`：客户端的分区大小 getvar 也遇到
  `Variable Not found`。因此“目标名缺 `_a`”只是第一次失败的触发条件，不是充分原因；
  决定性条件是刷写会话能否读到分区大小。
- 历史成功记录（同镜像同尺寸，`Sending` 后 `Writing OKAY`）说明 bootloader 能接受
  该镜像；本次整包 100,663,296 B 被拒。推断客户端读到分区大小时会去掉 AVB footer
  （略小于 0x6000000）再发送，读不到时按整包发送即超过 download 上限。上限数值与
  截断字节数**未验证**。
- 该 getvar 不稳定出现在第一次 download 被拒之后，enuma 同时段稳定；更像 nuwa
  bootloader 在该次失败 download 后的会话/解析状态异常，而非镜像或分区问题。
  需要一次 bootloader 复位（断电或重启）后复测；本轮未授权该动作。

## 第三次尝试：断电复位后显式 `vendor_boot_a`（2026-11-27 18:29，成功）

- 用户已彻底断电复位并重新进入 fastboot；本轮刷前状态全部重新读取，不沿用复位前
  判断。
- 身份：`fastboot devices` 两台，一台为 enuma（未操作）；nuwa serial 与前两轮
  相同（不入库），固定使用。
- 稳定性门禁（18:29:0x–18:29:37）：`product`、`current-slot`、`is-userspace`、
  `partition-size:vendor_boot_a` 各连查 3 次，共 12 次**全部成功、exit 0**，值分别为
  `nuwa` / `a` / `no` / `0x6000000`，无 `Variable Not found` 或 `unknown command`。
  与断电复位前的不稳定状态相反，会话已恢复稳定。
- 镜像复算（18:29:42）：100,663,296 B，SHA-256 `b9103e97…97b8`，一致。
- 唯一一次刷写：

```text
fastboot -s <nuwa-serial> flash vendor_boot_a <...>/vendor_boot.img
  Sending 'vendor_boot_a' (98304 KB)  OKAY [  2.269s]
  Writing 'vendor_boot_a'             OKAY [  0.035s]
  Finished. Total time: 2.337s
```

- 开始 `2026-11-27T18:29:45.837+08:00`，结束 `18:29:48.321`，**exit 0**。
- 本次输出**没有** `partition-size: 0` / AVB footer 警告，与「分区大小可读时客户端
  截断 AVB footer 后再发送」的判读一致。
- 未切槽、未刷其他分区、未初始化、未写 `userdata`/`metadata`。

### 唯一一次重启与 60 s 采样

```text
fastboot -s <nuwa-serial> reboot
  Rebooting                                          OKAY [  0.000s]
  Finished. Total time: 0.000s
```

- 发起 `18:30:04.089`，命令返回 `18:30:04.250`，**exit 0**；只执行一次。
- 采样：自 reboot 返回起每 10 s 一次 `fastboot devices` / `adb devices -l`，共 7 点
  （+0…+60 s）：

| 采样 | 相对 | 墙钟（+08:00） | nuwa 在 fastboot | adb |
| --- | --- | --- | --- | --- |
| S0 | +0 s | 18:30:04.254 | 否，行显示 `????????????` | 无 |
| S1 | +10 s | 18:30:14.263 | 是 | 无 |
| S2 | +20 s | 18:30:24.258 | 是 | 无 |
| S3 | +30 s | 18:30:34.254 | 是 | 无 |
| S4 | +40 s | 18:30:44.268 | 是 | 无 |
| S5 | +50 s | 18:30:54.253 | 是 | 无 |
| S6 | +60 s | 18:31:04.257 | 是 | 无 |

- 时间线：reboot 瞬间 nuwa 的 fastboot 稳定态被打断（serial 不可读）；+10 s 内重新
  列出并持续到 +60 s；`adb` 全程无设备。60 s 内没有观察到设备停在没有 USB 服务的
  状态。
- 刷后只读复核（18:31:21，exit 0）：`product=nuwa`、`current-slot=a`、
  `is-userspace=no`、`partition-size:vendor_boot_a=0x6000000`。

## 边界

- 第三次刷写成功只证明 bootloader 接收了 `b9103e97…` outer；无 `fastboot fetch` 或
  分区回读，不证明盘上字节内容。
- +0 s 的 `????????????` 只证明 USB 重新枚举、fastboot 稳定态被打断；10 s 采样粒度
  不能区分「仅 USB 复位后留在 fastboot」与「尝试启动后回落」，也不给出确切离开时长。
  +10…+60 s 设备在 fastboot，说明本窗口内没有进入可被 adb 看到的用户态。
- 本记录不报告字符界面、DATA0、panic 行、PID1 或任何未看到的屏幕内容；候选内核是否
  开始执行、卡在哪一步，本轮无证据。
- 2026-11-27 12:06 对同一 r6 outer 的 reboot 观测是 150 s 内两路 USB 均未出现；本次
  60 s 窗口内 +10 s 回到 fastboot，两者不矛盾也不互证，需屏幕/串口证据区分。
- 恢复目标只达到「诊断 outer 写回 `vendor_boot_a` 且 bootloader 确认」；设备仍回落
  fastboot，交互与启动均未验证。下一次设备动作需单独授权。
