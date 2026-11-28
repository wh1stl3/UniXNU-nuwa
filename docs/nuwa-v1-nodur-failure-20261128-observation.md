# nuwa retained v1 与 V1-NODUR 失败观察 — 2026-11-28

状态：**主控转述用户照片及 vision 转录，记录 self-checked**。本次记录工作
无代码修改、无新候选、无设备访问、无设备写入，也未构建。以下此前的刷写、
重启和 `set_active` 与本次记录工作分开；包运行时是否写入窗口仍未知。

## 三次启动的画面

| 版本 | 照片 | 共同结果 |
| --- | --- | --- |
| retained v1 reset r3（FUA 写和真实 `0x35`） | `reset-r3.jpg` | `DATA0 st=4`，`tzinit` exit 5，t=107s panic |
| V1-NODUR daily r2 | `daily1.jpg` | `DATA0 st=4`，`tzinit` exit 5，t=107s panic |
| A 槽恢复后 V1-NODUR reset r2 | `reset-4.jpg` | `DATA0 st=4`，`tzinit` exit 5，t=107s panic |

daily 和 A 槽恢复后的 reset 画面均为：

```text
[V1-NODUR] DATA0 st=4 err=0 ro=0 dev=1000002 seed=1 first-attempt
[V1-NODUR] S p1=RUN sb=never EX=17:tzinit:0/5:pp=1
tzinit[17] exited -- no exit reason available -- (signal 0, exit status 5)
```

三次记录的失败结果一致，reset 未改变上述失败表现。主控据此判断 FUA/flush
不是本次共同失败的原因；这属于对照推断，不是对失败 I/O 的逐项实测归因。
此前 FUA 版的载荷身份依赖刷写回执及之后分区未变的假设；各次刷写均无分区回读。

## 持久层和槽位

主控判断三个版本的持久 overlay 均未挂接。此前另一构建的
[NEON 观察](nuwa-ufs-neon-20261126-observation.md)曾记录 `pres=0 wr=0`；
它不是上述三次的同次计数。三张 panic 照片不显示持久层的 `pres`、`wr`
或 `why=`。`DATA0 st=4` 是首次 APFS Data 挂载流程的成功阶段，
**不是**持久 overlay 的状态码；不能单凭它证明持久层未挂接。

“overlay 未挂接 → 写入被拒 → APFS EIO → tzinit exit 5 → panic”与主控判断
和画面一致，但中间各环节及挂接失败的具体原因尚未逐项证实，缺少 `why=`。
窗口当前真实内容，以及 reset 是否真正写过 bitmap/header，均未验证。

主控转述：每次 panic 后 A 槽被标记 `slot-unbootable:a=yes`，需通过
`set_active a` 恢复。现有[槽位操作记录](nuwa-v1-nodur-slot-reenable-20261128-observation.md)
直接记载的是 daily 启动及 reset 首次 reboot 请求后的单次查询和恢复：
`slot-unbootable:a=yes`、`slot-retry-count:a=0`；一次 `set_active a`
返回 OKAY，复查为 `slot-unbootable:a=no`、`current-slot=a`。这是 A 槽恢复后
reset 再次启动之前的读数；本次没有最后一次 panic 后的独立槽位查询，也没有
逐次恢复的完整日志。

## 照片与 SHA-256

照片只留本地 `nuwa/media/`，不入 Git；SHA-256 由本次记录工作对文件实算。

| 照片 | SHA-256 |
| --- | --- |
| `reset-r3.jpg` | `e2b0d2fb110ecd11d83631efbfdb27b7a6e32df8acbeaf29688277ec1fdef1cc` |
| `daily1.jpg` | `0566559cf3a7c533cac2259437b020826686cd4d58ce720a8d795e5c1b18b7c5` |
| `reset-4.jpg` | `b2e0bc23123478879bc855eb623707183b9aef8ed2195e586b11f4bb953a7767` |

相关先前操作记录：[retained v1 reset reboot](nuwa-v1-retained-reset-reboot-20261128-observation.md)、
[daily](nuwa-v1-nodur-daily-boot-20261128-observation.md)、
[reset 刷写与 reboot](nuwa-v1-nodur-reset-boot-20261128-observation.md)、
[槽恢复后 reboot](nuwa-v1-nodur-reset-slot-restored-reboot-20261128-observation.md)。
