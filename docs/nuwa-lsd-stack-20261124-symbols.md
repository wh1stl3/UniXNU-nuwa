# lsd stackshot address check — 2026-11-24

## 第四轮（禁用 iconservicesagent 后 t=374s）

仅主机 **self-checked**。输入为用户提供的 vision 转录，未独立核对原图；
“禁用后”是本轮条件，不单凭栈证明禁用生效。运行时 cache UUID 未观察，
以下用户态归属均以候选 arm64 缓存 UUID
`8F970452-C9E3-3E88-B114-FEB1864BC9E0` 与运行时一致为前提。
`sc=0x44594000`，运行时基址 `0x1c4594000`。表中偏移为观察 PC 减此基址，
非文件偏移。总计 30 个非零用户值；T0 的 `f=11` 实际给出 **11 个**
用户值，其中 U10 是记录的零，不是 12 个非零帧，也不能仅凭零断言栈结束。

### 内核 continuation

用候选 kernel `out/nuwa-peer-probe-20261125-build/kernel.macho`，
SHA-256 `44158f0fea54fc54b48c243aed864ec7567e5c566bafb4bdaeaad1e11184cc94`，
执行 `llvm-nm -n`，下列地址均**恰为符号起点**；`ks=0` 只反映显示的低
32 位，未用它证明完整 slide。候选 kernel 与本轮运行内核一致仍依赖载荷身份。

| C | 候选内核符号 | 对应本轮可见用户态陷入 |
|---|---|---|
| `fffffff0076e4880` | `filt_wlwait_continue` | `kevent_id` |
| `fffffff0072c619c` | `semaphore_wait_continue` | `semaphore_wait_trap` |
| `fffffff00725dd74` | `ipc_mqueue_receive_continue` | `mach_msg2_trap` |
| `fffffff007744d68` | `ulock_wait_continue` | `__ulock_wait` |
| `fffffff0076c099c` | `workq_unpark_continue` | 前轮用户帧为 `__workq_kernreturn` |

因此前面把后三个 **C 值本身**称为 `mach_msg2_trap`、`__ulock_wait`、
`__workq_kernreturn` 不准确：这些是用户态陷入函数，C 是对应内核 continuation。

### 用户帧

置信级别 `S`：`.symbols` 本地 nlist 起点与 `LC_FUNCTION_STARTS` 一致；
`E`：映像 `LC_SYMTAB` 导出符号起点与函数边界一致（符号上界）；
`F`：仅有函数边界，没有该函数的可用名称。去掉一个 Mach-O nlist 前缀
下划线；ObjC 方法保持原名。

| 线程/帧 | 观察 PC | 相对偏移 | 库 | 函数 + 偏移 | 级别 |
|---|---|---|---|---|---|
| T0 U0 | `206ba5538` | `42611538` | libsystem_kernel | `kevent_id + 0x8` | E |
| T0 U1 | `1d2119c78` | `0db85c78` | libdispatch | `_dispatch_event_loop_wait_for_ownership$VARIANT$armv81 + 0x1b0` | S |
| T0 U2 | `1d210ece0` | `0db7ace0` | libdispatch | `__DISPATCH_WAIT_FOR_QUEUE__ + 0x138` | S |
| T0 U3 | `1d210e8fc` | `0db7a8fc` | libdispatch | `_dispatch_sync_f_slow + 0x8c` | S |
| T0 U4 | `1c62a4ea8` | `01d10ea8` | CoreServices | `-[_LSInstallProgressService performJournalRecovery] + 0x58` | S |
| T0 U5 | `1c629e654` | `01d0a654` | CoreServices | `__43+[_LSInstallProgressService beginListening]_block_invoke + 0x28` | S |
| T0 U6 | `1d212c780` | `0db98780` | libdispatch | `_dispatch_client_callout + 0x10` | S |
| T0 U7 | `1d20fcddc` | `0db68ddc` | libdispatch | `_dispatch_once_callout + 0x1c` | S |
| T0 U8 | `1c6280b44` | `01cecb44` | CoreServices | `_LSServerMain + 0x7d8` | E |
| T0 U9 | `1e8bb8344` | `24624344` | dyld | `start + 0x744` | S |
| T0 U10 | `000000000` | — | — | 记录的零，无符号 | — |
| T1 U0 | `206ba5030` | `42611030` | libsystem_kernel | `mach_msg2_trap + 0x8` | E |
| T1 U1 | `206bb6db8` | `42622db8` | libsystem_kernel | `mach_msg_overwrite + 0x1e4` | E |
| T1 U2 | `206ba5524` | `42611524` | libsystem_kernel | `mach_msg + 0x14` | E |
| T1 U3 | `1d20fe308` | `0db6a308` | libdispatch | `_dispatch_mach_send_and_wait_for_reply + 0x214` | S |
| T1 U4 | `1d20fe694` | `0db6a694` | libdispatch | `dispatch_mach_send_with_result_and_wait_for_reply$VARIANT$armv81 + 0x38` | S |
| T1 U5 | `2161820ec` | `51bee0ec` | libxpc | `xpc_connection_send_message_with_reply_sync + 0xec` | E |
| T1 U6 | `1c57a0224` | `0120c224` | Foundation | `__NSXPCCONNECTION_IS_WAITING_FOR_A_SYNCHRONOUS_REPLY__ + 0xc` | S |
| T1 U7 | `1c5739cb0` | `011a5cb0` | Foundation | `-[NSXPCConnection _sendInvocation:orArguments:count:methodSignature:selector:withProxy:] + 0x7e8` | S |
| T1 U8 | `1c57386e0` | `011a46e0` | Foundation | `-[NSXPCConnection _sendSelector:withProxy:arg1:] + 0x70` | S |
| T1 U9 | `1c573861c` | `011a461c` | Foundation | `_NSXPCDistantObjectSimpleMessageSend1 + 0x38` | S |
| T1 U10 | `20d663a8c` | `490cfa8c` | MobileActivation | `-[MadGate copyActivationRecord:] + 0xf0` | S |
| T1 U11 | `20d66652c` | `490d252c` | MobileActivation | `copyActivationRecord + 0x28` | S |
| T2 U0 | `206ba5ad0` | `42611ad0` | libsystem_kernel | `__ulock_wait + 0x8` | E |
| T2 U1 | `1d20fc4a0` | `0db684a0` | libdispatch | `_dispatch_group_wait_slow + 0x34` | S |
| T2 U2 | `1c625b990` | `01cc7990` | CoreServices | `__LAUNCH_SERVICES_CLIENTS_ARE_WAITING_FOR_THE_DATABASE_TO_FINISH_SEEDING__ + 0x20` | S |
| T2 U3 | `1c625b8c4` | `01cc78c4` | CoreServices | `-[LSDatabaseBlockingFetchClient getServerStoreBlockingWithCompletionHandler:] + 0x30` | S |
| T3 U0 | `206ba4fac` | `42610fac` | libsystem_kernel | `semaphore_wait_trap + 0x8` | E |
| T3 U1 | `1d20fc360` | `0db68360` | libdispatch | `_dispatch_semaphore_wait_slow + 0x80` | S |
| T3 U2 | `1e0b104bc` | `1c57c4bc` | libMobileGestalt | 未命名函数 `0x19c57c430 + 0x8c` | F |
| T3 U3 | `1e0b106e8` | `1c57c6e8` | libMobileGestalt | 未命名函数 `0x19c57c644 + 0xa4` | F |

T0 U8 的最近本地符号跨越函数边界，不采用；`_LSServerMain` 的
LC_SYMTAB 起点与最近 `LC_FUNCTION_STARTS` 边界一致。T3 的 MobileGestalt
映像在此 `.symbols` 集中无本地符号；最近导出符号跨越多处函数边界，
故只报告函数边界，不猜函数名。

### 判读与边界

* **T0**：`kevent_id` → dispatch event-loop ownership/queue sync →
  `performJournalRecovery` → `beginListening` block → dispatch once →
  `_LSServerMain` → dyld `start`。显示其在 LS 安装进度 journal recovery
  路径等待队列所有权，不证明已经读取某文件或完成数据库构建。
* **T1**：Mach message → dispatch 同步等待 → libxpc → Foundation NSXPC
  → `-[MadGate copyActivationRecord:]` → `copyActivationRecord`；
  MobileActivation activation-record 同步请求，具体对端及 selector 未证。
* **T2**：`__ulock_wait` → dispatch group wait → LS 数据库 seeding
  等待标识 → `LSDatabaseBlockingFetchClient`；显示在等数据库 seeding
  完成，不证明 seeding 工作线程或造成等待的原因。
* **T3**：semaphore wait → libdispatch → 两个未命名 MobileGestalt 函数；
  显示等待信号量，无法从已命名帧确认具体操作。

相对前三轮 T0 的 IconServices 初始化等待，本轮 **T0 已不在所显示的
IconServices 栈上**，且观察线程总数从 2 增至 9；这支持可见执行路径发生
变化，但不证明禁用导致变化、数据库正常推进或该进程整体已脱离所有
IconServices 路径。`n=9 w=8` 仅展示四个等待线程、每线程最多 12 帧，
其他线程与截断帧不可据此推断。单次采样不能区分短暂等待与长期卡住。

复用 `out/lsd-symbolize-20261124.py`，内存替换目标和缓存路径，并断言
映射含执行权限。42 个分片 UUID、`.symbols` UUID、映射边界、Mach-O
`__TEXT` 及函数边界检查对全部 30 个非零 PC 完成；它们均落在候选缓存
可执行映像中，**无非缓存非零帧**。零不是缓存或非缓存帧。
`sb=012f3000` 仅为低 32 位，不能单独恢复主映像完整地址区间。
本轮未修改除本记录以外的文件，未提交、未访问设备。

## 第三轮（禁用后 t=374s）

主机符号化 **self-checked**；输入为用户提供的 vision 转录，未独立核对图像。
“禁用后”仅指使用了禁用候选载荷，不证明禁用生效。候选根卷 arm64 缓存
UUID `8F970452-C9E3-3E88-B114-FEB1864BC9E0`；运行时 UUID 未观测，
所以符号归属以运行时缓存与候选缓存一致为前提。

本轮 `sc=0x2f5f0000`，缓存运行时基址
`0x180000000 + 0x2f5f0000 = 0x1af5f0000`。表内偏移是观察 PC 减该
**运行时基址**；不是 PC 减 slide 后得到的 unslid VA，也不是文件偏移。

| 帧 | 观察 PC | 缓存相对偏移 | 库 | 函数 + 偏移 | 置信级别 |
|---|---|---|---|---|---|
| U0 | `0x1f1c01030` | `0x42611030` | libsystem_kernel | `mach_msg2_trap + 0x8` | 导出符号上界 |
| U1 | `0x1f1c12db8` | `0x42622db8` | libsystem_kernel | `mach_msg_overwrite + 0x1e4` | 导出符号上界 |
| U2 | `0x1f1c01524` | `0x42611524` | libsystem_kernel | `mach_msg + 0x14` | 导出符号上界 |
| U3 | `0x1bd15a308` | `0x0db6a308` | libdispatch | `_dispatch_mach_send_and_wait_for_reply + 0x214` | `.symbols` 精确 |
| U4 | `0x1bd15a694` | `0x0db6a694` | libdispatch | `dispatch_mach_send_with_result_and_wait_for_reply$VARIANT$armv81 + 0x38` | `.symbols` 精确 |
| U5 | `0x2011de0ec` | `0x51bee0ec` | libxpc | `xpc_connection_send_message_with_reply_sync + 0xec` | 导出符号上界 |
| U6 | `0x1b07fc224` | `0x0120c224` | Foundation | `__NSXPCCONNECTION_IS_WAITING_FOR_A_SYNCHRONOUS_REPLY__ + 0xc` | `.symbols` 精确 |
| U7 | `0x1b0795cb0` | `0x011a5cb0` | Foundation | `-[NSXPCConnection _sendInvocation:orArguments:count:methodSignature:selector:withProxy:] + 0x7e8` | `.symbols` 精确 |
| U8 | `0x1b07946e0` | `0x011a46e0` | Foundation | `-[NSXPCConnection _sendSelector:withProxy:arg1:] + 0x70` | `.symbols` 精确 |
| U9 | `0x1b079461c` | `0x011a461c` | Foundation | `_NSXPCDistantObjectSimpleMessageSend1 + 0x38` | `.symbols` 精确 |
| U10 | `0x1d713b36c` | `0x27b4b36c` | IconServices | `-[ISIconManager _init] + 0x1b8` | `.symbols` 精确 |
| U11 | `0x1d713fdd4` | `0x27b4fdd4` | IconServices | `__31+[ISIconManager sharedInstance]_block_invoke + 0x18` | `.symbols` 精确 |

**12 帧偏移与上面的 t=384s 版本逐项完全一致**，不只前五帧一致；
初轮只显示四帧，其 U0–U3 也完全一致。观察 PC 不同是因为 slide
不同，不能由此认定外层路径变化。本轮 U5 的 unslid VA 为
`0x1d1bee0ec`，U10 为 `0x1a7b4b36c`，U11 为 `0x1a7b4fdd4`。

在候选缓存匹配假设下，内→外顺序为：
`mach_msg2_trap` → `mach_msg_overwrite` → `mach_msg` →
`_dispatch_mach_send_and_wait_for_reply` →
`dispatch_mach_send_with_result_and_wait_for_reply$VARIANT$armv81` →
`xpc_connection_send_message_with_reply_sync` →
`__NSXPCCONNECTION_IS_WAITING_FOR_A_SYNCHRONOUS_REPLY__` →
`-[NSXPCConnection _sendInvocation:orArguments:count:methodSignature:selector:withProxy:]`
→ `-[NSXPCConnection _sendSelector:withProxy:arg1:]` →
`_NSXPCDistantObjectSimpleMessageSend1` → `-[ISIconManager _init]` →
`__31+[ISIconManager sharedInstance]_block_invoke`。这是仍在
IconServices `sharedInstance` block 内初始化并走同步 NSXPC 等待路径；
不以这些栈帧断言服务名、对端或每对帧直接调用，U11 之外的调用者亦未显示。

复用 `out/lsd-symbolize-20261124.py`，在内存替换缓存路径与 12 个目标，
另加 mapping 当前保护包含 `VM_PROT_EXECUTE`（bit 4）的断言；42 个分片
UUID、`.symbols` UUID、映像 `__TEXT`、可执行映射和 `LC_FUNCTION_STARTS`
断言均完成。12 帧都落在候选映像的可执行 `__TEXT`，**没有非缓存帧**；
不是仅凭正偏移作此判断。`sb=0044e000` 仅提供低 32 位，不用于推定主映像。
本节只做主机分析，无设备访问或 Git 提交。

Host arithmetic and source inspection: **self-checked**. Input is a vision
transcription, not independently checked against the image. No build, device
access, flash, or Git commit.

## Input

```text
SHOT lsd n=2 w=2 r=0 ks=00000000 sc=08a28000 sb=006b2000
T0 C=fffffff00725dd74 U=1cb039030,1cb04adb8,1cb039524,196592308 f=35!
T1 C=fffffff0076c099c U=000000000 f=1
```

## Address arithmetic

With the requested cache base convention, `0x180000000 + 0x08a28000 =
0x188a28000`. Cache-relative offsets are VM offsets, not cache file offsets.
The unslid VA is the observed address minus `sc`.

| Row | Observed user value | Cache-relative offset | Unslid VA |
| --- | --- | --- | --- |
| T0 U0 | `0x1cb039030` | `0x42611030` | `0x1c2611030` |
| T0 U1 | `0x1cb04adb8` | `0x42622db8` | `0x1c2622db8` |
| T0 U2 | `0x1cb039524` | `0x42611524` | `0x1c2611524` |
| T0 U3 | `0x196592308` | `0x0db6a308` | `0x18db6a308` |
| T1 U0 | `0x000000000` | `-0x188a28000` | not applicable |

`196592308` is nine hexadecimal digits and represents address
`0x196592308`, equivalently `0x0000000196592308`; nine digits are exactly
the formatter's width, not evidence of a missing displayed character. It is
four-byte aligned. The transcription itself is not independently verified.
The zero in T1 is a recorded zero, not a missing frame.

`sb=006b2000` shows only the low 32 bits of the first load address; under the
given `0x1006b2000` interpretation no nonzero displayed PC is near that base.
The full base and upper end of the main image require the `SHOT2` and mapping
information; the displayed low bits alone do not establish the interval.
Positive cache offsets alone do not establish executable cache membership:
actual matching cache image mappings are required.

## Symbols and conclusions

### 12 帧版本 — t=384s（self-checked）

输入为主控提供的 vision 转录，未独立核对图像；仅主机分析，无设备访问。
`sc=0x05d4c000`，运行时缓存基址 `0x185d4c000`，表内偏移为
PC 减该基址。候选缓存 UUID `8F970452-C9E3-3E88-B114-FEB1864BC9E0`；
运行时 UUID 未观测，故归属以候选缓存匹配为前提。SystemOS 窗口以
`apfs-fuse -o ro -s 5637144576` 挂载并检查 `findmnt` 为 ro；缓存主文件、
42 分片和 `.symbols` 复制至 `out/dyld-cache-20261124/`。复用本文件所述
解析器，内存中替换路径和目标地址；42 分片 UUID、符号文件 UUID、映射
边界及各目标的 Mach-O `__TEXT` 均通过解析器断言。

| 帧 | 观察 PC | 缓存内偏移 | 库 | 函数 + 偏移 | 置信级别 |
|---|---|---|---|---|---|
| T0 U0 | `0x1c835d030` | `0x42611030` | libsystem_kernel | `mach_msg2_trap + 0x8` | 导出符号上界 |
| T0 U1 | `0x1c836edb8` | `0x42622db8` | libsystem_kernel | `mach_msg_overwrite + 0x1e4` | 导出符号上界 |
| T0 U2 | `0x1c835d524` | `0x42611524` | libsystem_kernel | `mach_msg + 0x14` | 导出符号上界 |
| T0 U3 | `0x1938b6308` | `0x0db6a308` | libdispatch | `_dispatch_mach_send_and_wait_for_reply + 0x214` | `.symbols` 精确 |
| T0 U4 | `0x1938b6694` | `0x0db6a694` | libdispatch | `dispatch_mach_send_with_result_and_wait_for_reply$VARIANT$armv81 + 0x38` | `.symbols` 精确 |
| T0 U5 | `0x1d793a0ec` | `0x51bee0ec` | libxpc | `xpc_connection_send_message_with_reply_sync + 0xec` | 导出符号上界 |
| T0 U6 | `0x186f58224` | `0x0120c224` | Foundation | `__NSXPCCONNECTION_IS_WAITING_FOR_A_SYNCHRONOUS_REPLY__ + 0xc` | `.symbols` 精确 |
| T0 U7 | `0x186ef1cb0` | `0x011a5cb0` | Foundation | `-[NSXPCConnection _sendInvocation:orArguments:count:methodSignature:selector:withProxy:] + 0x7e8` | `.symbols` 精确 |
| T0 U8 | `0x186ef06e0` | `0x011a46e0` | Foundation | `-[NSXPCConnection _sendSelector:withProxy:arg1:] + 0x70` | `.symbols` 精确 |
| T0 U9 | `0x186ef061c` | `0x011a461c` | Foundation | `_NSXPCDistantObjectSimpleMessageSend1 + 0x38` | `.symbols` 精确 |
| T0 U10 | `0x1ad89736c` | `0x27b4b36c` | IconServices | `-[ISIconManager _init] + 0x1b8` | `.symbols` 精确 |
| T0 U11 | `0x1ad89bdd4` | `0x27b4fdd4` | IconServices | `__31+[ISIconManager sharedInstance]_block_invoke + 0x18` | `.symbols` 精确 |
| T1 U0 | `0x1c835d4f0` | `0x426114f0` | libsystem_kernel | `__workq_kernreturn + 0x8` | 导出符号上界 |
| T1 U1 | `0x1d78e6720` | `0x51b9a720` | libsystem_pthread | `start_wqthread + 0x8` | 导出符号上界 |

函数名去除一个 Mach-O nlist 外部名前缀下划线；Objective-C 方法名按
原样显示。`.symbols` 精确表示本地 nlist 符号起点与
`LC_FUNCTION_STARTS` 最近起点一致；导出符号上界来自 `LC_SYMTAB`
命名外部符号，起点也与最近函数边界一致，不声称已解析 export trie。
所有 14 帧均落在候选缓存映像的可执行 `__TEXT`，无非缓存帧。
T0 前四个偏移与上一轮 `0x42611030`、`0x42622db8`、
`0x42611524`、`0x0db6a308` **完全一致**。

按采样栈内到外（不以此证明每对帧一定直接调用）：
`mach_msg2_trap`（libsystem_kernel）→ `mach_msg_overwrite`
（libsystem_kernel）→ `mach_msg`（libsystem_kernel）→
`_dispatch_mach_send_and_wait_for_reply`（libdispatch）→
`dispatch_mach_send_with_result_and_wait_for_reply$VARIANT$armv81`
（libdispatch）→ `xpc_connection_send_message_with_reply_sync`（libxpc）→
`__NSXPCCONNECTION_IS_WAITING_FOR_A_SYNCHRONOUS_REPLY__`（Foundation）→
`-[NSXPCConnection _sendInvocation:orArguments:count:methodSignature:selector:withProxy:]`
（Foundation）→ `-[NSXPCConnection _sendSelector:withProxy:arg1:]`
（Foundation）→ `_NSXPCDistantObjectSimpleMessageSend1`（Foundation）→
`-[ISIconManager _init]`（IconServices）→
`__31+[ISIconManager sharedInstance]_block_invoke`（IconServices）。

- 可见的业务层发起者是 **IconServices 的 `ISIconManager` 初始化**，而不是
  仅能归到通用 xpc；Foundation 和 libxpc 是同步代理消息传输层。不能由
  这些帧断言 LaunchServices、CoreServices 或 container 客户端发起。
- 最外层可见 U11 属于 **IconServices 系统私有框架**，不是 lsd 主二进制：
  去 slide 后 `0x1a7b4fdd4` 落在候选 IconServices `__TEXT`
  `[0x1a7b41000, 0x1a7b8f000)`。所有其他帧亦有候选缓存映射；
  `sb=00e7c000` 只有低 32 位，无法单独恢复 lsd 主映像完整区间，
  因而不以它推定任意主二进制映射。
- **到此为止**：新增帧揭示了 IconServices 初始化经 NSXPC 同步请求，
  但没有给出具体 selector、连接服务名或远端进程，也没有显示 U11
  以外调用者；不可凭 `serviceName` 邻近符号猜对端。需要连接/消息或
  selector 与服务端身份证据，以及更外层栈，才能回答具体谁向谁请求。
  `f=35!` 所代表的未显示帧不在本次表内。

### arm64 缓存符号化结果 — 2026-11-24（self-checked）

本节取代下面历史节中“须 arm64e”的假设和“无法定位”的当时结论；输入
进程与根卷缓存均为 arm64，见 `nuwa-root-arch-20261124.md`。本节仅为候选
根卷缓存的离线解析；运行时缓存 UUID 未观测，故尚不能独立证明与运行时一致。

缓存主文件（WSL）
`/tmp/nuwa-root-inspect-20261124/systemos/root/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64`，
magic `dyld_v1   arm64`，UUID `8F970452-C9E3-3E88-B114-FEB1864BC9E0`，
shared-region base `0x180000000`。主头列出的 42 个分片均打开、UUID
逐一匹配，含 `.28.dyldlinkedit` 和 `.42.dyldlinkedit`；`.symbols` UUID
`51CCBA45-1FC2-3F19-AED0-47050BDF009A` 匹配主头的 symbolFileUUID。
映射按每个分片自身的 VM mapping 处理，没有拼接文件。

| 帧 / 缓存偏移 | 映像与分片 | 函数 + 偏移 | 置信级别 |
|---|---|---|---|
| U0 `0x42611030` | `/usr/lib/system/libsystem_kernel.dylib` / `.19` | `mach_msg2_trap + 0x8` | 导出符号上界 |
| U1 `0x42622db8` | 同上 | `mach_msg_overwrite + 0x1e4` | 导出符号上界 |
| U2 `0x42611524` | 同上 | `mach_msg + 0x14` | 导出符号上界 |
| U3 `0x0db6a308` | `/usr/lib/system/libdispatch.dylib` / `.03` | `_dispatch_mach_send_and_wait_for_reply + 0x214` | 精确（.symbols 命中） |

表中 C 名去掉 Mach-O 外部名前缀下划线；对应原始 nlist 分别为
`_mach_msg2_trap`、`_mach_msg_overwrite`、`_mach_msg`、
`__dispatch_mach_send_and_wait_for_reply`。前三个来自映像 `LC_SYMTAB`
的命名符号，不是 `.symbols` 中最近的本地符号；这三个起始地址均与
`LC_FUNCTION_STARTS` 最近边界一致。U3 的 `.symbols` 命中地址
`0x18db6a0f4` 亦与最近函数边界一致。由此避免把跨度更大的最近本地符号
误当作前三帧的函数；前三帧的“导出符号上界”指符号表上界，不是声称
已经解析导出 trie。

- U3 是 **libdispatch 通用 IPC 包装层**，不是 LaunchServices/CoreServices
  专用代码；其函数名显示同步发送并等待应答路径。
- U0 是 Mach 消息陷入，U1 是 `mach_msg_overwrite`，U2 是 `mach_msg`：
  三者是通用 Mach 消息/等待代码，单独不能证明请求或应答一方。结合 U3
  只能判断本线程处于发送并等待应答的调用路径，不能据此断言对端身份或
  消息当前处于发送还是接收阶段。
- 与上一轮所述 `LaunchServices::Database::Context::_get`、
  `_LSContextInitWithOptions`、`_LSContextInitCommon` **不是同一组函数**：
  四个显示帧属于 libsystem_kernel/libdispatch，符号均不一致；这不排除
  未显示的其余调用帧中存在 LaunchServices。若上一轮对同一四个归一化
  偏移声称这些 LS 符号，则两种符号化存在冲突，不能在缺运行时 UUID 和
  上轮原始符号化输入时认定原因。

工具为本地 Python 3 辅助解析器
`worktree-display-dsp/out/lsd-symbolize-20261124.py`；结构参照 Apple
`dyld/include/mach-o/dyld_cache_format.h`（Apple OSS dyld，main，APSL 2.0；
本次读取，未 pin commit）。逐分片校验 UUID、mapping 文件边界、目标所属
Mach-O `__TEXT`，然后分别读 `.symbols` 本地 nlist、经 `__LINKEDIT`
VM 映射读 `LC_SYMTAB` 和 `LC_FUNCTION_STARTS`。命令原文：

```sh
wsl -e python3 /mnt/d/Code/PortingiOS/nuwa/worktree-display-dsp/out/lsd-symbolize-20261124.py
wsl -e bash -lc 'python3 /mnt/d/Code/PortingiOS/nuwa/worktree-display-dsp/out/lsd-symbolize-20261124.py | tail -45'
```

### 2026-11-24 source-image recheck — self-checked

The earlier search below is historical and its claim that the DMG was absent
is superseded: the source exists at
`UniXNU-nuwa/out/root-inputs-20261113/ipsw/20H392/087-86593-047.dmg`
(2,743,074,816 bytes). Mounted using
`sgan81/apfs-fuse@66b86bd525e8cb90f9012543be89b1f092b75cf3` with
`-o ro`; `findmnt` reported `fuse` and `ro`. Its actual cache path is
`/root/System/Library/Caches/com.apple.dyld/` relative to this mount.
Historical volume identity is `SydneyUpdate20H392.D22D221SystemCryptex`,
iPhone OS 16.7.16 / 20H392; this recheck did not independently verify the
volume name or OS version.

The directory contains **only arm64**, not arm64e: the main
`dyld_shared_cache_arm64` is 393,216 bytes, magic
`dyld_v1   arm64`, UUID `8F970452-C9E3-3E88-B114-FEB1864BC9E0`;
there are 42 arm64 subcaches and `dyld_shared_cache_arm64.symbols`.
The full directory listing with individual byte sizes is saved in
`UniXNU-nuwa/out/dyld-20H392-20261124/cache-list.txt`. No arm64e
main cache, subcache, or symbols file exists in this directory, so none was
copied. This arm64 cache is not evidence of the requested arm64e identity and
was not used for attribution.

| Cache-relative offset | Library / function | Confidence |
| --- | --- | --- |
| `0x42611030` | unavailable | cannot locate |
| `0x42622db8` | unavailable | cannot locate |
| `0x42611524` | unavailable | cannot locate |
| `0x0db6a308` | unavailable | cannot locate |

Consequently U3 cannot be classified as LaunchServices/CoreServices versus
generic IPC, and U0–U2 cannot be classified as synchronous XPC initiator
versus response or generic wait. An arm64e cache matching the observed
runtime UUID is required; the runtime UUID remains unobserved. No device
access, build, flash, or Git commit was performed.

### Earlier search (historical)

**Stop: no matching cache located**, so cache path, size and UUID are unknown;
the intended donor version is iPhone10,3 iOS 16.7.16 / 20H392, not a
verified identity for any cache in this search. The target root's actual
cache architecture and UUID also require evidence; do not substitute a
different build or architecture.

Searches, host-only and read-only:

* Searched names recursively under `D:/Code/PortingiOS/nuwa/`, including
  `out/` and `.cache/`, for `*dyld_shared_cache*`, `*.symbols`,
  `*symbolized*`, `*lscontext*`, and `*.ipsw`; no candidate found.
* `D:/Code/PortingiOS/UniXNU/out/ipsw/20H392/` contains trust caches,
  device trees and a kernelcache, but not the donor IPSW or OS DMG.
* Searched WSL `/root`, `/home`, the above donor directory and nuwa
  `out/` and `.cache/` for the same names; no cache or IPSW found. No
  `ipsw`, `jtool2`, or `dyld_shared_cache_util` was found on Windows PATH
  or in WSL PATH.
* Earlier `nuwa-display-abi-20261120.md` §14 records a SystemOS DMG
  `087-86593-047.dmg` and split caches, but that DMG is absent from the
  donor directory now. `nuwa-userspace-20261119-observation.md` describes
  an `arm64` cache in the SystemOS cryptex; that historical observation
  does not establish this run's cache UUID or justify using `arm64e`.
  No image was remounted and no device was accessed.

| Frame | Cache offset | Library + function + function offset | Direction |
| --- | --- | --- | --- |
| T0 C | — | `mach_msg2_trap`, prior-round supplied identification only | kernel continuation |
| T0 U0 | `0x42611030` | unknown + unknown + unknown | innermost displayed user frame |
| T0 U1 | `0x42622db8` | unknown + unknown + unknown | recorded after U0 |
| T0 U2 | `0x42611524` | unknown + unknown + unknown | recorded after U1 |
| T0 U3 | `0x0db6a308` | unknown + unknown + unknown | outermost displayed user frame |
| T1 C | — | `__workq_kernreturn`, prior-round supplied identification only | continuation |
| T1 U0 | — | zero; no symbol | recorded value |

The supplied prior-round SpringBoard T1 values normalize to the same four
offsets according to the task input; this search did not independently
recheck that observation. Assuming the producer's frame array is ordered
inner to outer, the tentative caller-to-callee order is U3 → U2 → U1 → U0;
address magnitude does **not** determine call direction, and exact direct
calls are not established.

U3 cannot be classified as LaunchServices/CoreServices-specific versus
libdispatch/libxpc/generic IPC without the matching mapping and symbols.
Likewise U0–U2 cannot be classified as synchronous XPC initiator, responder,
or generic wait. The prior `mach_msg2_trap` identification alone does not
prove a specific XPC role or peer. The 35 recorded entries include callers
not shown here.

**Offline attribution stops here**, not at a proven generic IPC layer: no
user frame has been symbolized. To continue, supply the exact root-volume
cache and its split files including linkedit/symbols, with build/architecture
and runtime cache UUID evidence linking it to the observed process, or an
equivalently UUID-bound symbolization artifact. Further callers require the
remaining captured user frames. No build, flash, device access or commit.

## `f=35!` source

`scripts/generate_r35_display_diag.py` collects the array count (lines 239–249):

```c
      } else if (in_thread && (type == BP_SHOT_USER_STACKFRAME64 || type == BP_SHOT_USER_STACKLR64 ||
                               type == BP_SHOT_KERN_STACKLR64)) {
        unsigned stride = type == BP_SHOT_USER_STACKFRAME64 ? 16 : 8;
        if (!bp_shot_elements(item, stride, &count)) return BP_SHOT_INTEGRITY;
        if (type != BP_SHOT_KERN_STACKLR64) thread.have_user = 1;
        unsigned *used = type == BP_SHOT_KERN_STACKLR64 ? &thread.kerns : &thread.users;
        unsigned limit = type == BP_SHOT_KERN_STACKLR64 ? BP_SHOT_KERN_PCS : BP_SHOT_USER_PCS;
        uint64_t *pc = type == BP_SHOT_KERN_STACKLR64 ? thread.kern : thread.user;
        for (unsigned i = 0; i < count && *used + i < limit; ++i)
          pc[*used + i] = bp_shot_word(data + i * stride);
        *used += count;
```

The relevant output code (lines 298–307) is:

```c
    // iOS arm64 user VA fits in 36 bits. K uses the low 40 of a canonical kernel VA.
    for (unsigned j = 0; j < t->users && j < BP_SHOT_USER_PCS; ++j) {
      bp_shot_hex(k, 1, t->user[j], 9);
      memcpy(pcs + 10 * j, k, 10);
      if (j) pcs[10 * j - 1] = ',';
    }
    char frames[12] = "-";
    if (t->have_user) snprintf(frames, sizeof(frames), "%u", t->users);
    snprintf(row, 120, "T%u %s U=%s f=%s%s", i, top, pcs, frames,
      t->users > BP_SHOT_USER_PCS || t->truncated ? "!" : "");
```

Thus `35` is the decimal count of recorded synchronous user frame entries,
not the four displayed addresses and not proof of the complete true stack
depth. `!` is set for more than four entries or the producer's user-truncated
flag. Here 35 exceeds four, so `!` follows even if the producer flag is clear;
it does not tell us whether producer truncation also happened. The flag is
copied from `snap->ss_flags` at line 237.
