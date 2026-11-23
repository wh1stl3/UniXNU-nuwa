# SpringBoard 停滞记录（2026-11-23）

- 载荷：outer SHA256 `c8abfda3…5b2a`（截断值；`nuwa-sb-restart=400`）。
- 分支与范围：`display/20h392-dsp-diag`，本轮相关已有提交 `569dbcb..caf50cc`；实机 one-shot 探针为 `03dffd0`，后续 `74f5597` 和 `caf50cc` 尚未上机，不把它们归入该实机载荷。
- 证据分级：实机读数来自**用户观测、主控转述**，本记录未独立核验原始影像；主机静态分析与审查结论亦为主控转述，非本次独立复核。已有主机构建为 self-checked；本次仅整理记录。

## 已证（限主控转述的用户实机观测）

- 约 `t=400s` 触发 `psignal(SIGKILL)`，横幅 `K=1`；出现 `EXIT p26 SpringBoard status=9 sig=9 ns=2 sub=9` 和 `XR p26 SpringBoa f2681ad0 sig=9`。SB 被杀并退出，当时并非不可打断的内核等待。
- launchd 重新拉起实例，`PROC SB=` 从 25 变为 170；新实例稳定存活、不崩溃。
- `t=760s` 和 `t=870s` 两次 `SC` 均为 10，`SC +0`：新实例同样没有提交帧。

## 已推翻

- 「SpringBoard 只是启动太早、来不及等 backboardd」：系统就绪后重起的 pid 170 仍不出帧，单靠该解释不成立。
- 「卡在内核不可打断等待」：SIGKILL 生效并正常退出，排除本次被杀实例处于此状态。

## 未证

- **阻塞而非慢跑**：`LOAD idle=0%` 时，PC 采样器未抽到 SB 不能区分阻塞与可运行但被饿死；此前视为已证的说法撤回。
- **显示链路已打通**：只证 backboardd 经 CPU 拷贝递交 Apple logo（`SC n=10~12`）；SB → CARenderServer → swap 的真实提交路径从未检验。
- **ABBA 死锁**：主控转述主机静态分析显示 20H392 有同一代码模式：`+[AWAttentionAwarenessConfiguration initialize]` 尾调用 `+[AWClientPreferences initializePreferences]`，后者为单条 `ret`；`dyld_shared_cache_arm64.13` 偏移 `0x1cd5a9c`，原字节 `684a19d0004d47f9`。没有线程等待栈，不能确诊。
- **SIGKILL 的 PC 来源**：SIGKILL 递给进程，处理线程未定，`f2681ad0` 可能来自任意线程；PC 每次不同不能推出 SB 在跑。

## 新线索：未解释

`EXIT p154 xpcproxy status=4e00 sig=0 exit=78` 中 78 为 `EX_CONFIG`，有服务因配置未启动，但服务名未确认。主控转述离线差集：12 条缺失路径中 9 条属于运行时挂载的 `/System/Cryptexes/*`，不能当作根卷缺失；唯一确定缺失的 `/usr/sbin/sntpd` 为 `RunAtLoad=true` 的时间同步服务，不是 SB 前置。

## 已排除的旁支

- **App Cryptex**：`/private/preboot/Cryptexes` 为空、本地无 AppOS 输入；依赖它的 8 个任务均 `RunAtLoad=false`。sheng iPadOS 17 配置也只提供 OS + SystemOS 两窗口；不是 SB 首帧前置。
- **锁状态**：AKS `native_aks_lock_state()` 固定返回 0（unlocked），selector 7 返回 4（unlocked since boot）；nuwa 未实现 `aks-sls` 参数，不是阻塞原因。
- **服务缺失**：`SVC 3f` 采样确认 `runningboardd`、`distnoted`、`cfprefsd`、`notifyd`、`securityd`、`mobileactivationd` 在场，不证明其他服务均已就绪。

## 已尝试但被阻断

runtime text fixup 拟将 `+[AWAttentionAwarenessConfiguration initialize]` 入口改为 `ret`；上游 UniXNU 的 sheng iPadOS 17 配置启用签名验证后原地改字节的机制。主控转述 deep_reviewer 判断该机制在 8796 上不自洽：验证后修改 vnode 源页却沿用已验证状态，`vm_fourk_pager` 的区间 `cs_validate_range` 是具体反例，wire 不消除问题。两次 DeepSeek `coder_hard` 和一次 `openai/gpt-6.2-astra` 均以不改写已验证代码为由拒绝实施。此路线目前无执行路径，除非有真实签名制品或源码级修复。

## 待办（已有构建，尚未上机）

- `74f5597`：`nuwa-sb-restart-every=180` 最多杀 SB 四次，用于比对多次 PC；PC 来源限制仍适用。
- `caf50cc`：既有诊断行优先于动态堆栈，并恢复宽度上限。reviewer 注：`LOAD`、`UFS`、`SCHED` 无保底席位；scale 3 下屏幕实际为 80 列，恢复上限不改变可见列数。
- 线程转储三次尝试均卡在 `task_threads` 端口/线程引用合同与 `thread_get_state` 暂停语义，尚未实现。

本记录未构建、未操作设备；持久交互和断电重启验收尚未完成。
