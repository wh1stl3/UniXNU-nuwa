# nuwa IconServices 禁用项后的观察 — 2026-11-25

主控转述用户实机结果及 vision 转录，记录和主机符号化为 **self-checked**；
本次记录没有独立核对原图或重新访问设备。单次采样不证明长期状态；
认证仍 NOT REACHED，持久交互目标未达成。

## 载荷与时序

相对基线唯一 args 变更为追加
`disable-jobs=com.apple.iconservices.iconservicesagent`，args 从 507
增至 561 字符，其余字节不变；主机打包依据见
[`nuwa-icondisabled-20261125.md`](nuwa-icondisabled-20261125.md)。
用户/主控报告 outer
SHA-256 `a2243ee872a11aa34dab3f9d778625e9fa1ec8112cb3637e08ac1ec96ba344fc`
已刷写并重启，重启时刻 **2026-11-25 01:52:21 UTC+08:00**。
本记录未独立复核刷写日志、载荷回读或运行时身份。

### 设备写入前审查留痕

主控转述：`reviewer` 给出 **PASS WITH CONDITIONS（方案 c）**，两项条件
在该次刷写前已核：(a) job 为 system 域，plist 路径为
`/System/Library/LaunchDaemons/`，使用 `disabled.plist` 而非
`disabled.501.plist`；(b) `p_comm` 为 `iconservicesagen`，依据
`MAXCOMLEN=16` 和 `kern_exec.c:917–923`。此处按主控提供的“方案 c”
原文记录，不将其改称方案 B 或声称本次独立复核了审查过程。

## t=374s 转录

```text
PEER icon=- cm=61 lsd=92 SB=26
SHOT lsd n=9 w=8 r=0 ks=00000000 sc=44594000 sb=012f3000
T0 C=fffffff0076e4880 U=206ba5538,1d2119c78,1d210ece0,1d210e8fc f=11!
T0+4 U=1c62a4ea8,1c629e654,1d212c780,1d20fcddc
T0+8 U=1c6280b44,1e8bb8344,000000000
T1 C=fffffff00725dd74 U=206ba5030,206bb6db8,206ba5524,1d20fe308 f=22!
T1+4 U=1d20fe694,2161820ec,1c57a0224,1c5739cb0
T1+8 U=1c57386e0,1c573861c,20d663a8c,20d66652c
T2 C=fffffff007744d68 U=206ba5ad0,1d20fc4a0,1c625b990,1c625b8c4 f=19!
T3 C=fffffff0072c619c U=206ba4fac,1d20fc360,1e0b104bc,1e0b106e8 f=53!
PROC n=120
SC n=10 o=10
LOAD user=27% sys=72%
XR p9 MSUEarlyB
```

另转述 EXIT 三条：`IOMFB_FDR_Loader`、`prng_seedctl`、
`sysstatuscheck`；本次未收到三条 EXIT 的完整原文或退出原因，故不补造。
界面层无变化：未见锁屏或图标。屏幕顶部蓝色横条为常驻，不是本轮新现象。

`icon=-` 是本轮 PID 1–4096 的有界 census 未找到精确 `iconservicesagen`
名称；用户将其判为 agent 未运行、禁用生效。它不能单独证明系统范围内
全时段不存在，也不能证明 launchd 的具体读取或策略提交过程。

## 四线程与结论

完整逐帧符号表、候选缓存 UUID、内核地址与置信边界见
[`nuwa-lsd-stack-20261124-symbols.md` 第四轮](nuwa-lsd-stack-20261124-symbols.md#第四轮禁用-iconservicesagent-后-t374s)；
运行时 cache UUID 未观测。

| 线程 | 候选内核 continuation | 已显示的外层业务路径 |
|---|---|---|
| T0 | `filt_wlwait_continue` | `-[_LSInstallProgressService performJournalRecovery]` ← `__43+[_LSInstallProgressService beginListening]_block_invoke` ← `_LSServerMain` |
| T1 | `ipc_mqueue_receive_continue` | `-[MadGate copyActivationRecord:]` ← `copyActivationRecord`（MobileActivation） |
| T2 | `ulock_wait_continue` | `__LAUNCH_SERVICES_CLIENTS_ARE_WAITING_FOR_THE_DATABASE_TO_FINISH_SEEDING__` ← `-[LSDatabaseBlockingFetchClient getServerStoreBlockingWithCompletionHandler:]` |
| T3 | `semaphore_wait_continue` | libMobileGestalt 内部两个未命名函数 |

前三轮观察 lsd 有 2 线程，显示的 T0 一直在 IconServices 初始化同步
等待；本轮 `n=9 w=8`。**加入禁用项后，观察到显示的 lsd T0 离开此前
IconServices 路径并进入 LS 初始化相关路径。** 没有隔离对照轮，不能将
变化归因于禁用 agent；单次采样不能证明所见等待是短暂还是持续，也不能
据此断言 LS 数据库构建成功或交互已达成。其他线程和未显示帧不在判定范围内。

## 后续与机制

下一步是等待 seeding，在约 `t=600s` 与 `t=900s` 再采样并比较；
任何新设备操作须当轮授权。

供后续排查的机制：`package/nuwa-watchdog/nuwa_watchdog_policy.c` 在
Data 挂载验证成功后、initproc exec 前按 args 重建并 rename
`disabled.plist`；**若策略成功提交**，seed 中同名文件会被覆盖，因此该路径
的禁用项应通过 args 控制。本轮是否成功提交策略未独立观测。
