# nuwa retained v1 reset r3 启动门禁 — 2026-11-28

状态：**device/self-checked；门禁未通过，未重启**。本轮只做设备枚举和只读
`getvar`；`current-slot` 返回远端失败，无法确认槽位 `a`。因此没有执行
`fastboot reboot`，也没有开始重启后的 120 秒采样。屏幕内容未观察。

## 授权和边界

用户授权启动已刷入的 reset r3，指定 `vendor_boot_a` 的镜像 SHA-256 为
`213cdf065fe5eab45215f96c2efb12a8c320d51a4efadfcd586dd71140dd942d`；
要求先确认唯一 nuwa、`product=nuwa`、`current-slot=a`、
`is-userspace=no`，只执行一次 reboot，再每 10 秒采样 120 秒；同时要求不
刷写、不切槽、不初始化、不写 `userdata`。本轮未回读分区，镜像身份来自
[前次刷写记录](nuwa-v1-retained-reset-flash-20261128-observation.md)，
不是本轮对设备分区的哈希验证。

另有待明确的授权冲突：reset 包带 `sheng-data-reset=1`。根据
[实现记录](nuwa-v1-retained-20261128.md#轨迹与边界)，符合运行门禁后它会重建
retained Data 并写 bitmap、header；窗口位于 `userdata`
（[布局记录](nuwa-disposable-data-20261126.md#admission-and-result)）。
这与“不初始化、不写 userdata”的字面约束冲突，不能仅凭 reboot 指令推定
获准包自身写入。旧轮用户接受 Data 窗口丢失风险的记录，不改变本轮这一限制。

## 只读门禁

时间为主机本地时间 +08:00；serial 不入库。15:58:49.082 开始报告以下同次
枚举和顺序查询结果（标准输出、标准错误合并捕获）：

```text
adb devices -l: exit 0, 0 devices
fastboot devices: exit 0, 1 device
fastboot -s <fixed-nuwa> getvar product:
product: nuwa
Finished. Total time: 0.004s
exit 0

fastboot -s <fixed-nuwa> getvar current-slot:
getvar:current-slot                                FAILED (remote: 'unknown command')
Finished. Total time: 0.000s
exit 0

fastboot -s <fixed-nuwa> getvar is-userspace:
is-userspace: no
Finished. Total time: 0.005s
exit 0
```

唯一 fastboot 设备报告 product 为 nuwa，且 `is-userspace=no`。尽管
`current-slot` 进程 exit 0，远端响应明确为 `FAILED`，不是 `current-slot: a`。
`is-userspace` 查询因批次顺序在该失败后执行；未重试槽位查询，也未尝试替代
设备命令。

## 未执行和未验证

- reboot：未执行，故无 reboot 输出、exit 或重启时刻。
- 120 秒 adb/fastboot 时间线：未开始；上面是重启前单次只读门禁，不是采样
  时间线。
- 未执行刷写、切槽、初始化或主机 `userdata` 写入。
- 本轮未启动本包；Fresh、Data 挂载、介质耐久及屏幕结果均未验证。是否允许包自身
  初始化并写 `userdata` 需用户明确；槽位 `a` 仍需可靠只读证据。
