# nuwa mobileactivationd migration observation — 2026-11-22 evening

- **Evidence identity:** parent-relayed device readings for outer SHA-256 `bf705663…6dd5`, kernel SHA-256 `22af086c…ddc1`; only abbreviated hashes were supplied. Newer six-slot payload `e7a2214b` is separately identified by its supplied prefix; its full hash and kernel binding were not supplied.
- **Branch and revision range:** `display/20h392-dsp-diag`; diagnostics `066e67b..88b2d58` inclusive (scanout, process census, old six-digit XR); record base `37fec8f876418ae1c1953108cc29fde519da556d`. This is source history, not a claim that all artifacts share one revision. The four XR readings are from `88b2d58`; `37fec8f` widened XR.
- **Sources:** hardware readings and Apple logo attribution relayed by parent from user observations; host static analysis supplied by parent, self-checked, not independently rerun here. No build or device operation for this record; no independent verifier reran these conclusions.

## 已证：实机读数

- **已达 — 进程在场：** `PROC n=116..128 SB=26 bb=54 lsd=92 ld=1 lk=69 cm=61` 多次一致，SpringBoard、backboardd、lsd、launchd、lockdownd、containermanagerd 六进程在采样期间稳定在场；较新 `e7a2214b` 六槽版同值。采样不证明初始化完成或之后永久存活。
- **已达 — 显示桥计数：** `SC n=12 r=0 o=12`，其后 `SC +0 in 10s`；累计 12 次调用全成功，接下来 10 秒空闲。按用户/主控提供的帧归属，12 帧由 backboardd 提交并显示 Apple logo；SpringBoard 未提交帧的结论限于本轮观测范围。
- **已达 — 退出读数：** `crashes` / `exits` 持续增长，崩溃进程在 mobileactivationd、lsd、suggestd 间轮换；mobileactivationd 持续反复出现，`status=5 sig=5 ns=2 sub=5`，约每 20 秒一次，PID 每次更换。
- **已达 — XR 低位：** 旧 6 位版 `88b2d58` 的四次 mobileactivationd 崩溃低 24 位为 `dca3bc`、`b3e3bc`、`8e93bc`、`a283bc`；低 12 位恒为 `0x3bc`，位 12–23 不同。分别减 `0x1bf3bc` 得 `0xC0B000`、`0x982000`、`0x72A000`、`0x869000`，均为 4 KiB 整数倍；这是低位匹配而非完整 PC/slide 证明。
- **已达 — 安全属性：** `/chosen` 的 `certificate-production-status`、`effective-production-status-ap`、`certificate-security-mode`、`effective-security-mode-sep` 分别为 `0/0/1/1`；20 个历史包一致。

## 静态结论 — 主机分析，self-checked

- **已达 — 镜像结构：** `/usr/libexec/mobileactivationd` 是独立 Mach-O 而非共享缓存镜像；PIE，`__TEXT` vmaddr `0x100000000`。
- **已达 — 静态失败路径：** `main` 调用 `0x10001ab98`，其中 `dispatch_once` 执行带 `PerformMigration` signpost 的 block；返回值 bit0 为 0 时调用 `0x1001bf35c`，该函数引用 `"main"` 与 `"Migration failed."`，调用 `_os_crash` 后执行 `brk #1`。
- **已达 — 候选指令：** 此 100 字节函数内 `0x1001bf3bc` 的 `brk #1` 是 `__TEXT,__text` 中唯一低 12 位为 `0x3bc` 的非填充候选；另三处同类指令在 `__objc_stubs` 填充区。
- **未确定 — 实机精确 PC：** `_os_crash` 先于 `brk` 调用，实机 PC 严格来说也可能位于 `os_crash` 内部；低 24 位随进程基址变化指向本可执行文件内的解释，但完整 PC/slide 尚未直接取得，候选位置未直接验证。

## 已排除：不要重复假设

- **已排除** `/chosen` 四项安全属性缺失或回归：上述 20 包一致。
- **已排除** lockdownd 未运行：`lk=69`。
- **已排除** containermanagerd 未运行：`cm=61`。
- **已排除** UFS 单槽轮询本身是本轮瓶颈的假设：固定上游 `UniXNU/ShengUfs@99d8bcd3` 本身单槽轮询且屏蔽中断，同类设备用同一驱动可到桌面；页面 `blk` / `req` 分别是验证块计数与成功拷贝计数，不是 UFS 命令数。这不排除其他存储问题。
- **已排除** SpringBoard 未启动：`SB=26`。早前交接前 PC 采样未见 SpringBoard 是 IRQ 采样盲区，不是进程缺席的证据。

## 未证 / 待查

- **未确定** migration block 内具体哪一步返回 false；静态解析进行中。
- **未确定** SpringBoard 卡住与 migration 失败是否有因果关系：时间吻合不足以证明因果。
- **未确定** 修复方向，包括数据层补容器或其他方案；等待失败条件分析完成。
- **未达** 可持续交互及断电重启后回到同系统并交互；认证仍 NOT REACHED。
