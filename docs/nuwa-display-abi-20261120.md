# 20H392 显示 ABI 取证（G1 收尾，2026-11-20）

状态：**self-checked（主机侧、未独立复核）**。输入是本机 20H392 donor kernelcache，无设备操作、无内核构建。
最新 A2（CPU-only / no-software-vsync）完整链接与 strict emit 见 §23；两条运行路线的放行判据见 §16，formatter 与 teardown 夹具见 §15。

## 0. 结论

1. **338 槽与 9 个纯虚槽复算一致**：`[211,212,242,243,292,293,321,322,329]`，vtable
   `0xfffffff006def8e0`，与 `out/nuwa-display-20261115-r1/REPORT.md` 逐项相同。
2. **7 个限定槽全部定位到具体槽**（246 / 274 / 276 / 281 / 282 / 287 / 336），每条都有本机指令或调用点锚点。
3. **9 个实例字段、6 个请求字段有锚点**；实例大小 `0x1660`（5728 B）。
4. 已生成 `package/OriginalLegacyFramebufferABI.h` 与 `package/original-bindings.S`。
   **但它们还不是可构建件**：绑定只覆盖 7 个 Legacy 入口，驱动需要的 9 个 IOSurface/vsync
   胶水符号仍未派生，设备侧 builder 也还没有。
5. 每个数字都能用第 6 节的生成器复算；生成器在写文件前逐条断言锚点，任一不符即失败。

## 1. 输入与既有材料

| 输入 | 值 |
| --- | --- |
| donor kernelcache | `UniXNU/out/ipsw/20H392/kernelcache.decompressed`，50,937,856 B，SHA256 `2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221` |
| family | `com.apple.iokit.IOMobileGraphicsFamily` v343.0.0，load `0xfffffff004f60400`，可执行 `0x8378` |
| 既有推导 | `out/nuwa-display-20261115-r1/derive-display-abi.py`、`display-abi.json`、`REPORT.md` |
| vtable 解码参考 | `UniXNU/scripts/audit-mobile-graphics-legacy.py`（同一形状判定法） |
| 逐槽对照方法 | enuma `build-enuma-gop-legacy.py` / `LegacyABI.in.h`；**只用写法与 stub 序列，不取任何数值** |

`out/nuwa-display-20261115-r1/derive-display-abi.py` 已重跑，输出：
`legacy vtable {"vptr": "0xfffffff006def8e0", "slots": 338, "abstract_slots":
[211,212,242,243,292,293,321,322,329], "prefix_overrides":
[0,1,7,14,21,44,79,85,86,87,111,141,155]}`，与 REPORT §2.1 一致。

## 2. REPORT.md 关键结论转写（`out/` 被 gitignore，故入库）

- 20H392 是 **338 槽**、9 个纯虚；enuma/iPadOS 17 那条线是 **358 槽**、纯虚
  `[211,213,245,246,306,307,337,338,345]`。前 168 槽覆盖集两边完全一致
  `[0,1,7,14,21,44,79,85,86,87,111,141,155]`，168 槽之后短 20 槽。
- 因此 enuma 生成的头（358 项、`sizeof==0x18a0`、限定槽 249/288/290/295/296/301/354）
  **不能复用**；本文件就是 nuwa 专用重定。
- 20H392 的 7 个限定槽在旧 REPORT 里是“未定”；本轮全部落到具体槽（第 3 节）。
- 实例字段与请求字段在旧 REPORT 里是“未定”，且用 enuma 那组偏移做机械反查是负结果；
  本轮从本镜像的队列/尺寸/状态指令重新量出（第 4、5 节）。
- family 不在 r9 现役内核里；要跑显示必须重新 prelink，且 roots 缺
  `com.apple.iokit.IOAVFamily`、`com.apple.iokit.IOMobileGraphicsFamily`、`com.apple.kec.Libm`
  三条。Libm 的 20H392 字面量池指纹仍未取证（G3），是 prelink 前的硬阻塞。
- 两个 hook 补丁在基座 `profiles/arch/arm64/patches/xnu/series`；nuwa 的 `patch_series`
  只有 `device:` 一个源，所以当前没打进 8796 树。dry-run 能打（`bsd_init.c` fuzz 1）。
- 启动参数以基座 pin `e47c1b8` 为准，仍带 `sheng-` 前缀；CPU 拷贝最小组合见 REPORT §3.4。
- 用户态 swap 契约（`0x728/0x750`、IOSurface 字段）仍未复算：`reports/` 已剪除（G2）。
  Data 卷缺失是 launchd 之后的另一条独立缺口（G6）。

## 3. 7 个限定槽（全部已定）

地址均为 donor VA；槽号是 338 槽表中的下标。

| 槽 | 名字与签名 | 抽象 | 锚点 |
| --- | --- | --- | --- |
| 246 | `void getDisplayDimensions(uint32_t *, uint32_t *)` | 否 | 方法 `0xfffffff005c247ac`；`0x5c247dc` `ldr w8,[x8,#5208]` → `0x5c247e4` `str w8,[x9]`，`0x5c24804` `ldr w8,[x8,#5212]` → `0x5c2480c` `str w8,[x9]`；对 x1/x2 判空。 |
| 274 | `bool startHardware()` | 否 | 方法 `0xfffffff005c17e44`（`mov w8,#0` / `and w0,w8,#1`）；`start()` 在 `0x5c0d5d8` 用 `ldr x8,[x8,#2192]` 调用并检查 w0，失败即返回 false。 |
| 276 | `void kickSwapQueue()` | 否 | 方法 `0xfffffff005c192b8`（空 body，仅保存 x0 后 ret）；6 处调用点使用 vtable 偏移 2208，例如 `0x5c0c22c`、`0x5c0daa4`、`0x5c0fb90`、`0x5c17000`、`0x5c1b188`、`0x5c25814`。 |
| 281 | `void completeCurrentSwap()` | 否 | 方法 `0xfffffff005c1ace4`：`mov w8,#1` → `and w1,w8,#1` → `bl 0x5c1012c`；被调方读当前请求字段 `[self+4872]`，处理队首并以抽象钩子 `vtable+2568`（槽 321）收尾。 |
| 282 | `bool validateSwap(const OriginalLegacySwapRequest *)` | 否 | 方法 `0xfffffff005c1ad10`：保存 x1、`mov w8,#0` / `and w0,w8,#1`；调用点 `0x5c165b4` 用 `ldr x8,[x8,#2256]` 传请求指针并检查返回值。 |
| 287 | `bool getRefreshAttributes(uint64_t *, bool)` | 否 | 方法 `0xfffffff005c234b4`：`0x5c234c0` `mov x8,#0x4444` + `0x5c234c4` `movk x8,#0x444,lsl16` = `0x4444444` = `2^32/60`；写 words[0]/[2]/[4]，再经 `vtable+2168`（槽 271）做换算。 |
| 336 | `int applyStateRequest(OriginalLegacyStateRequest *, bool)` | 否 | 方法 `0xfffffff005c1c1d8`：`0x5c1c20c` `ldrb w8,[x8,#16]`（changed）；读请求 `+0/+4/+8/+12`；`0x5c1c240` 读 `[self+5236]`、`0x5c1c260` 写回、`0x5c1c294` 读 `[self+5240]`；changed 时调 `vtable+2272`（槽 284）。 |

7 个槽的抽象位都不是抽象（不与第 0 节的 9 个纯虚重叠）。

**定位方法**：先用 168 槽之后的 stub 形状序列做逐槽对照（enuma 的写法，不取数值），得到候选；
再用本镜像的调用点/参数/返回值独立确认。274/282/287/336 有直接调用点或结构常量，
281 有 `true` 转发与当前请求消费，276 有 6 处 vtable 偏移 2208 调用。以上均为静态锚点，
**未做运行时验证**。

## 4. 实例字段（9 个）

实例大小 **5728 B（0x1660）**：metadata 构造器 `0xfffffff005c0bc74` 内
`0x5c0bca4` `mov w3,#0x1660`，类名字符串在 `0xfffffff004f6564a`（`0x5c0bc98` ADRP+ADD）。

| 偏移 | 角色 | 锚点 |
| --- | --- | --- |
| 4872 | 当前请求指针 | `0x5c0fe9c` `ldr x8,[x8,#4872]`；`0x5c0fed0` 写回；`0x5c10038` 作为完成路径的请求参数。 |
| 4880 | pending 队首 | `0x5c0feb4` 和 `0x5c0fecc` 读取；后者读出的值由 `0x5c0fed0` 写到 self+4872。 |
| 4888 | pending 队尾 | `0x5c0fe50` 读、`0x5c0fe70` 写；入队时新节点的 prev 取旧队尾。 |
| 4992 | vsync 客户端队列头 | `0x5c10060`、`0x5c1b948` 读；在 vsync 发送路径前取该字段。角色由使用位置推定，未运行时验证。 |
| 5064 | vsync 相关保留对象 | `0x5c0c5e8` 初始化为 0；`0x5c196ec` 取指针、`0x5c19700` release 后清零。角色由 retain/release 形状推定。 |
| 5208 | 宽（u32） | `getDisplayDimensions` 与 `installBootDimensions` 对应字段 |
| 5212 | 高（u32） | 同上 |
| 5236 | 请求状态 requested（u32） | `applyStateRequest`：读 `[self+5236]` 与请求 +4 比较，变化则写回 |
| 5240 | 电源状态 powered（u32） | `applyStateRequest`：读 `[self+5240]` 与请求 +12 比较，变化则写回 |

## 5. 请求字段（6 个）

| 偏移 | 角色 | 锚点 |
| --- | --- | --- |
| 2184 | surfaces（4 个对象指针） | `0x5c161f0`、`0x5c0eed4` `add x8,x8,#0x888`，随后按 `lsl #3` 取 4 项；校验路径循环 4 次。 |
| 792 | 掩码块起点（3 个字） | `0x5c14c18` `str w9,[x10,#792]`；`0x5c14ca8` 写 800（来自 userclient +268）；`0x5c167b8` 读 792、`0x5c167c4` 读 796；日志 `swap_submit enabled/completed` 打印 792/796。 |
| 17 | rect0 数组（4×16 B） | `0x5c16264` `add x10,x8,#0x11`，`ldr q0` × 4；附近字符串为 `srcRect.*`。 |
| 81 | rect1 数组（4×16 B） | `0x5c16284` `add x10,x8,#0x51`，同样 4 次 qword 拷贝。 |
| 804 | options 块起点（3 个字） | `0x5c14cb8` `str w8,[x10,#804]`（来自 userclient 参数 +272）；同块尾字 812 在 `0x5c167d0` 被读；日志标为 `dummy`。中间 808 未单独命中。 |
| 816 | 目标尺寸（宽/高） | `0x5c14cd4` 写 816、`0x5c14ce0` 写 820，值来自 `[self+5208]/[self+5212]`。 |

队列节点（辅助/非 6 项）：请求基址 +2408 = next、+2416 = previous；队首/队尾/当前分别存
request 基址（不是节点地址），`0x5c0fe50`、`0x5c0fe70`、`0x5c10010` 为锚点。
请求总分配大小未取证，头文件因此不写 `static_assert(sizeof(OriginalLegacySwapRequest))`。

## 6. 生成器与复算

生成器：`scripts/derive-nuwa-display-abi.py`（本提交新增）。

产物：

- `package/OriginalLegacyFramebufferABI.h`：338 槽类声明，170 个 168+ 虚函数按槽序生成，
  9 个纯虚 `= 0`，7 个限定槽具名；实例大小 `static_assert == 5728`；
  `OriginalLegacySwapRequest` / `OriginalLegacyStateRequest` 与请求/实例偏移常量。
- `package/original-bindings.S`：`__ZTV25IOMobileFramebufferLegacy` + 7 个 Legacy 入口的绝对绑定。
- 生成器同时写 `package/nuwa-display-abi.json`（本机摘要，已随本分支入库）。

复算（WSL，cwd = `UniXNU-nuwa`）：

```sh
PY=/home/wh1stl3/.local/bin/python3.11
$PY -B scripts/derive-nuwa-display-abi.py \
  --base /mnt/d/Code/PortingiOS/UniXNU \
  --kernelcache /mnt/d/Code/PortingiOS/UniXNU/out/ipsw/20H392/kernelcache.decompressed \
  --out package
$PY -B out/nuwa-display-20261115-r1/derive-display-abi.py   # 旧的槽数/纯虚复算
```

生成器在写文件前逐条断言：vtable 地址/槽数/纯虚集、实例大小指令、7 个槽地址、
槽语义调用点、9 个字段指令、6 个请求字段指令。任一不符即非零退出。

头文件的独立语法/尺寸检查：`out/nuwa-display-abi-20261120/header-test.cpp` 用假 `IOService`
编译通过（`sizeof(IOMobileFramebufferLegacy)==5728`、swap 节点偏移 2408/2416 断言成立）。

## 7. 已定 / 未决

**已定（有锚点）**：338 槽、9 纯虚、vtable/方法区间；7 个限定槽的槽号/签名/抽象位；
实例大小 5728；实例字段 9 个（其中 4992/5064 的角色为结构推定）；请求字段 6 个；
swap 节点链接 2408/2416。

**未决 / 不在本轮**：

- 9 个胶水符号仍未派生：`native_legacy_surface_{descriptor,width,height,stride,allocation,format,planes}`、
  `native_legacy_set_refresh_properties`、`native_legacy_vsync_notify`。`original-bindings.S`
  因此不完整，`libNativeLegacyDisplay.late.a` 还不能链接。
- 请求总分配大小、options 中间字 808、`OriginalLegacyStateRequest` 尾部填充大小只有下界/形状依据。
- 170 个非具名槽的返回类型/参数仍是 opaque `void`（与 enuma 生成器同法），未逐槽签名化。
- 所有结论是静态指令锚点，未运行、未上机；`startHardware`/`kickSwapQueue` 等的真实调用时机未验证。
- 旧的 G2/G3/G4/G5/G6 缺口不变（用户态 swap 契约、Libm 池、设备侧 builder、内核重链接、Data 卷）。

## 8. 消费端合同补充（未闭合）

- `0x5c10240` 的 `ldr x8,[x8,#2568]` 是完成路径对槽 321 的调用；该槽在 donor 是纯虚。生成声明采用基座消费者 `NativeLegacyDisplay.cpp:779` 的签名，并从 opaque leaf 宏移除 321，保留原槽位置与纯虚属性。精确最终子类 vtable 尚未生成或验证。
- `kLegacyVsyncClients` 使用已记录的 4992 偏移；`0x5c0fecc` 是读 self+4880，`0x5c0fed0` 是写 self+4872，不是写 pending head。
- 使用 `/root/nuwa-pmap-ret-native-20261111/.../IOPMGR.cpo.json` 的真实 8796 编译选项和头，将输入换为基座 `drivers/GopFramebuffer/NativeLegacyDisplay.cpp`、加本设备 package include 和 `-DNATIVE_LEGACY_CANCEL_SWAPS=1`，编译失败：首个错误 `NativeLegacyDisplay.cpp:533`，`isMainDisplay()` 标为 override 但当前生成基类没有对应虚函数。未生成对象；最终子类槽 321 无二进制证据。编译命令重建脚本位于本机临时路径 `C:/Users/Administrator/AppData/Local/Temp/opencode/nuwa-abi-compile.py`，不作为持久证据。
- `isMainDisplay`、`getDotPitch`、`supportedFrameInfo`、`cancelSwapsAfterTimeout` 的 donor 槽位尚未限定；不以其他系统或编译成功推断槽位。其余九项 surface/vsync glue、设备 builder、用户态 swap 合同和 prelink 仍未闭合。已有基座 GopFramebuffer 翻译单元可复用，需独立派生本 donor 的链接入口与构建步骤；本轮未实现 builder 或九项胶水。
- 此修正仅为 host 静态合同，未完成实际编译、链接、运行、设备或独立 verifier；需要 deep review 复核 ABI。

## 9. 20H392 消费端复查（self-checked，仍未闭合）

基座 `693f5d9cae8a408dd18b39f3f9fdc4228c934241`，消费者 `GopFramebuffer@e47c1b8de169cd2bd0b885c7d85e433010e3cdf2`，donor 仍为第 1 节的哈希。下列 donor 地址省略 `0xfffffff000000000` 前缀。

| 消费者 override | 20H392 证据与处理 |
| --- | --- |
| `bool isMainDisplay()` | **184，具体虚函数** `0x5c12264`。dispatch 表 `0x6decb58` 的 selector 18 行 `0x6decd08` 指向 `0x5c00658`（单标量输出）；经 `0x5c00688` 调用包装器，`0x5bfe52c` 从 framebuffer 取 `vptr+1472`，只读返回值的第 0 位并输出 0/1。函数体读 `self+0x1522` 和 `self+0x152b`，在 `0x5c122b0` 返回布尔值；与基座 `:533` 的无参数布尔 override 一致。 |
| `IOReturn getDotPitch(uint32_t *)` | **188，具体虚函数** `0x5c1d128`。`0x5c1d184/188` 引用 `"dot-pitch"`，`0x5c1d24c` 向保存的 x1 指针写 32 位，`0x5c1d250` 返回 IOReturn；`0x5bfe818` 从 framebuffer 取 `vptr+1504` 并转发该输出。与基座 `:842` 一致。 |
| `supportedFrameInfo` | selector 74 的 `0x6ded248` 行指向 `0x5c00c04`（1 标量入、1 标量出、64 B 结构出），再到 `0x5bfec14`。`0x5bfec58` 从 `vptr+1696` 调用纯虚槽 **212**，w1 为索引，x2 为本地 32 位计数输出，x3 为 key 缓冲区，w0 为状态。该调用**不设置 x4**；基座 `:853` 要求并写第四个 `uint32_t *mask`。缺同签名的 20H392 调用锚，不能把该四参 override 装进 212。 |
| `cancelSwapsAfterTimeout` | `0x5c11928/2c` 引用五秒超时日志；之后 `0x5c11980` 的布尔调用是纯虚槽 **329**，其返回值在 `0x5c119dc/e0` 入日志的 `TimingEnable` 位（格式串 `0x4f66224`）。`0x5c10e40` 和 `0x5c10f7c` 也把这个布尔值用于状态分支。实际清队列路径另经 `0x5c11a74` 的槽 **330**，目标 `0x5c0fbe8` 从 `self+4872` 读当前请求，调用者不消费返回值。两者均不构成基座 `:770` 所需的独立布尔取消回调锚。 |

生成器只具名替换原 184、188 两项并断言 donor 锚点；338 槽、九个纯虚位和直接绑定不变。不改基座 override。

复跑第 8 节的真实 8796 translation unit（`-DNATIVE_LEGACY_CANCEL_SWAPS=1`）：clang 退出 1，**首错 `NativeLegacyDisplay.cpp:770:36`**，`cancelSwapsAfterTimeout()` 拒绝 `override`，没有可匹配的基类虚函数。无目标对象，未检查最终子类槽 321。复跑时用该 `IOPMGR.cpo.json` 的 `directory` 和 `arguments`：把 `file` 替换为基座 `drivers/GopFramebuffer/NativeLegacyDisplay.cpp`，`-o` 指到临时对象，移除 `-W*`（连带其 `-Xclang` 包装），追加 `-I<设备仓>/package`、`-I<同一构建树>/.cache/xnu-work/osfmk`、上述宏和 `-ferror-limit=1`。

未链接、未上机；ABI 待方案 A 的 `deep_reviewer` 审查及独立 verifier 复跑。

## 10. 方案 A：20H392 host TU 适配（self-checked）

按主控转述的本轮深审结论实施。第 8–9 节的编译失败是历史结果；本轮使用基座
`693f5d9cae8a408dd18b39f3f9fdc4228c934241`、`GopFramebuffer@e47c1b8de169cd2bd0b885c7d85e433010e3cdf2`
的完整 TU，仅在设备仓 `out/` 副本中适配。槽 212 仍为九个原始纯虚位之一，从
guard 列表改由三参 `supportedFrameInfo(uint32_t, uint32_t *, char *)` 覆盖；有效输出写
`count=0`、清 64 B key 并返回 `kIOReturnUnsupported`，无 mask 参数或访问。生成器断言
selector 74 的 dispatch 行、转发指令、槽 212 调用和结果转发，以及 321/329/330 的调用锚。
donor 338 槽、九个纯虚位置和 `original-bindings.S` 均不变。

真实 xnu-8796 构建的 `IOPMGR.cpo.json` 提供 cwd 和参数。保留其架构、代码生成、
defines 和生成头；替换输入/输出，去掉原 TU 的 `-W*`（含 `-Xclang` 包装），追加
基座驱动 quote include、设备 `package` 和构建树 `osfmk` include、
`-DNATIVE_LEGACY_CANCEL_SWAPS=0 -ferror-limit=1`。Clang 24
`58c46bae21181fb4240cf964461bea738d96d50e` 退出 0（17 条指定初始化警告）。
完整 cwd/argv 与输入校验信息保留在本地 `out/nuwa-display-host-abi-20261120/compile.json`，
SHA256 `9b5786db627f6dd40d56d6ebccd7e29e24eeb4d1cea1bf732b856585bd853ba8`；
原 CPO SHA256 `d390eb4440c6854e0243d041f0cd329be419a10ef78facf9a90102f3822e0c70`。

实际 ARM64 Mach-O `NativeLegacyDisplay.o`：388400 B，
SHA256 `13759effe67bd68ec1db3316fd0e4847deecd2e37aaeaf31bd5515070d335ffe`。
从 `__ZTV19NativeLegacyDisplay` 的 section/value 锚定 `__const` 内重定位，六项均是
无 addend 的 8 字节 `ARM64_RELOC_UNSIGNED`；另用 `llvm-readobj --relocations` 交叉核对：

| 槽 | section offset | 目标 |
| --- | --- | --- |
| 184 | `0x5e0` | `NativeLegacyDisplay::isMainDisplay` |
| 188 | `0x600` | `NativeLegacyDisplay::getDotPitch` |
| 212 | `0x6c0` | `NativeLegacyDisplay::supportedFrameInfo`（三参） |
| 321 | `0xa28` | `NativeLegacyDisplay::collectCompletionReports` |
| 329 | `0xa68` | `NativeLegacyDisplay::opaque329`（guard） |
| 330 | `0xa70` | `IOMobileFramebufferLegacy::opaque330`（继承，未增加直接绑定） |

**禁止以该对象运行。** 槽 329 的 TimingEnable 合同仍未实现；关闭取消回调只隔离
host 编译，未证明 donor 取消后 `validated`、GPU 请求和 fence 的生命周期正确。
两项都需独立合格证据才能解除运行门禁。本轮未链接、未上机，未进行独立 verifier。

复跑（WSL，cwd = `UniXNU-nuwa`；输出目录须不存在）：

```sh
PY=/home/wh1stl3/.local/bin/python3.11
BASE=/mnt/d/Code/PortingiOS/UniXNU
TREE=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree
CPO=$TREE/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json
$PY -B scripts/derive-nuwa-display-abi.py \
  --base "$BASE" --kernelcache "$BASE/out/ipsw/20H392/kernelcache.decompressed" --out package
$PY -B scripts/verify-nuwa-display-host-abi.py \
  --base "$BASE" --cpo "$CPO" --out out/nuwa-display-host-abi-verifier
llvm-readobj --relocations out/nuwa-display-host-abi-verifier/NativeLegacyDisplay.o
```

复跑输出路径不同且保留 `-g`，对象哈希只标识各自的对象，不替代槽位核验。

## 11. 方案 A：七个 IOSurface 读取器与 host-only 归档（self-checked）

生成器钉住第 1 节的 20H392 donor SHA256。下表地址省略 `0xfffffff000000000`；
每行独立校验 family 的三条跳板指令、GOT 指针、IOSurface 的完整 `ldr; ret` 及语义锚点。
`original-bindings.S` 只新增下列七个读取器；338 槽的头与此前的 Legacy 绑定不变。

| 读取器 | family 跳板 → IOSurface leaf | load | 独立语义锚点 |
| --- | --- | --- | --- |
| descriptor | `5c2737c → 5a4e724` | `x0`, +56 | `5c0f050–5c0f06c` 从 swap 的 surface 数组取对象，返回值立即作为对象调用。leaf 不 retain，返回借用指针；调用方须持有活 surface，不能因调用而 release descriptor。 |
| width | `5c2740c → 5a4e7f4` | `w0`, +144 | `5c159d0` 比较 `srcRect.x + width`，失败日志 `4f6672e` 明示 Buffer width。 |
| height | `5c27418 → 5a4e7fc` | `w0`, +148 | `5c15b18` 比较 `srcRect.y + height`，失败日志 `4f66791` 明示 Buffer height。 |
| stride | `5c272f8 → 5a4e80c` | `w0`, +152 | `5c1d6cc` 返回值关联 `src_stride`；`5c1d67c` 非零 plane 分支另读 plane 0。新 getter 不把 plane stride 当普通 stride。 |
| allocation | `5c27298 → 5a4e834` | `w0`, +172 | `5a4b2cc–5a4b2fc` 读取 `IOSurfaceAllocSize`，拒绝非零高 32 位，随后在 `5a4b3b4` 存到 +172。不是相邻 +160。 |
| format | `5c27304 → 5a4e7e4` | `w0`, +164 | `5c1d7dc` 返回值作为 `format` 属性的值。 |
| planes | `5c272d4 → 5a4e82c` | `w0`, +176 | `5a47894–5a478cc` 从 `IOSurfacePlaneInfo` 数组取计数写到 +176；不是 +180。 |

在 AArch64，写 `w0` 将 `x0` 高 32 位清零，故 width/height/stride/allocation
适配驱动的 `uint64_t` 返回无需读取相邻字段。format/planes 保留 `uint32_t`。
读取器无分配、引用计数或锁操作；没有改变请求所有权。

**两个未绑定的计时入口：**

- Refresh：`5c23610` 调用 slot 287，发布 `IOMFBDisplayRefresh`，以 `w0 & 1` 返回。
  AppleMobileDispH10P 的 `start_hardware_boot()` 在 `5ccfc5c–5ccfc74` 通过自己的 late-init 成功判断，
  再经 `5ce1650 → [6dfb618]` 调用。nuwa 消费点在 `NativeLegacyDisplay.cpp:530` 的
  `registerService()`，不能用这条 donor 硬件就绪条件证明其等价。保留未解析，不造返回值。
- Vsync：`5c0dc28–5c0dc34` 从对象读三条 64 位计时值传给 `5c1b838`；发送体直接遍历
  +4992 链表，报 `dropped VBL message`。`5c10894` 是另一处调用。不能从四寄存器匹配
  证明 nuwa 的定时器 (`NativeLegacyDisplay.cpp:417`) 与注册、移除及 teardown 在同一序列化域，
  也未确认三项计时的语义与每条路径等价。保留未解析，不引入空 sender。

**归档复算。** 沿用 §10 的 `PY`/`BASE`/`CPO`，并用 LLVM 14 `llvm-objcopy`、
`llvm-ar`。`GopFramebuffer@e47c1b8` (BSD-2-Clause-Patent) 是唯一驱动源码，基座只读。
真实 CPO 保留原目标（`arm64-apple-ios17.0.0`，这是该 8796 CPO 的编译目标，不是 donor 版本）
及内核编译选项；去掉 CPO 的 warning 和依赖记录输出，取消回调仍只在 host TU 关闭。
板级 provider 也用同一 CPO 编译。CPU 路径不用 `NativeGOPPresenter`，不把 GPU presenter
归档进来。构造器策略复用基座 `scripts/build-adreno740-accelerator.py`（UniXNU
`693f5d9c`，BSD-2-Clause-Patent）的 manual-only 做法；本机 LLVM 的 Mach-O objcopy
不支持 `--globalize-symbol`，改由 TU 副本中的 `.globl` 交给 Clang 汇编器，objcopy 只去
`__mod_init_func`。校验 raw init 指针重定位到该入口、三个归档成员无自动 init/term section、
唯一全局手动入口由板级 TU 引用、六槽重定位仍与 §10 相同。未实际调用初始化器。

```sh
GEN=out/nuwa-display-abi-verifier
HOST=out/nuwa-display-host-archive-verifier
$PY -B scripts/derive-nuwa-display-abi.py \
  --base "$BASE" --kernelcache "$BASE/out/ipsw/20H392/kernelcache.decompressed" --out "$GEN"
for f in OriginalLegacyFramebufferABI.h original-bindings.S nuwa-display-abi.json; do
  cmp "$GEN/$f" "package/$f" || exit 1
done
$PY -B scripts/verify-nuwa-display-host-abi.py --base "$BASE" --cpo "$CPO" --out "$HOST"
llvm-nm --format=posix "$HOST/HOST-ONLY-incomplete-display.a"
llvm-readobj --relocations "$HOST/NativeLegacyDisplay.manual.o"
```

实际三成员归档 `HOST-ONLY-incomplete-display.a` 为 612752 B，本次 SHA256
`2c808e4c037859f593f9cfbb074ff7e07aec18a6558fa60f0e1467f053b0e5ee`（对象含调试路径）。
从实际归档取出成员校对其字节及七个 getter，按外部定义消去归档内部引用后还有 381 个
未解析符号，含 160 个 Legacy 类符号及 6 个仅弱引用符号。`archive.json` 列出每项来源及弱引用位；
固定 CPO 的完整清单指纹 `18c7dc556bb9a3c27a2338e960bd13ebff9b98edb51cc568e9793a8d285e915d`。
这是未解析清单校验而非链接通过。两个计时入口仍未解析，Legacy 剩余外部解析需另证。
运行仍禁用：329 TimingEnable 和 330 超时后的请求/队列生命周期未闭合。没有改 hook、
内核档案列表、Libm 或 prelink；没有做最终链接、上机候选或设备操作。

## 12. 方案 A：refresh 注册阶段与 vsync 串行域（self-checked）

输入同 §11：20H392 donor SHA256 `2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221`，
设备基线 `f0a85a2`、基座 `693f5d9c`、驱动 `e47c1b8`。以下 donor VA 省略 `0xfffffff000000000`；
以 Mach-O 段映射、ARM64 反汇编、vtable/GOT 和内核符号表交叉核对。只记录证据，不加绑定。

**Refresh 在硬件启动成功路径、首次服务注册之前发布。**

- H10P vptr `6e06980` 的 slot 86 为 `5ccff04`，`5ccff70` 经 `[6dfba78]` 调用 Legacy
  `start`（`5c0c8cc`）。该函数在 `5c0d5dc` 调 slot 274，返回假即跳到失败返回，不到
  `5c0d77c` 的 slot 84 (`registerService(0)`；`6e06c20 → IOService::registerService`)。
- H10P slot 274 `5cd0238` 在 `5cd0280` 同步取 gated action 的结果；wrapper vptr
  `6dec2b0` slot 13 `5bfac78` 在 `5bfad6c` 调 gate `runAction`。action `5cdd558`
  → `5cd0298` → `5cd03f8` → `start_hardware_boot` `5ccfb0c`。late-init 成功才到
  `5ccfc74 → 5ce1650 → [6dfb618] → 5c23610`；helper 返回假沿 `5cd03fc` 退出，
  不进入注册。`5c237b8` 的属性写入本身不检查返回值，不能把 helper 为真当作 IORegistry 回读。
- nuwa `NativeLegacyDisplay.cpp:862–888` 确实在同一个 slot 274 验证 GOP 映射并设置
  子类 `primary`；`:524–531` 的发布也在 `IOService::registerService` 前。因此**阶段已对齐**，
  但不能直绑：donor `5c23698–5c236b8` 读 `self+5410` 的位作为 slot 287 的 `fixed`
  输入，不走子类 `isMainDisplay()`；Legacy `5c0d3dc` 清该字节，GOP `primary` 写的是
  子类成员。`:539–547` 用 `fixed` 决定是否改最大间隔，而 `:530` 不消费发布函数返回值。
  最小下一步：用不启动内核的用例核对六个属性值（32.32 秒／mach ticks，含固定／非固定）、
  GOP 模式对应的显式速率策略及发布失败行为，再决定设备侧 formatter；不写 donor 私有状态来凑输入。

**vsync 注册／移除与定时发送锚定同一个 workloop；不是整个发送／停机链都已证明串行。**

| donor 路径 | 锚点与结论 |
| --- | --- |
| 注册／移除 | selector 72/73 行 `6ded218/230` → `5c00b44/bac` → 用户客户端 framebuffer 的 vslots 208/209（`5bfead8/5bfeb68`）。`5c1b00c/5c1b2a0` 都从 `self+5040` 调 `IOCommandGate::runAction`（gate vptr `715cce0` slot 29 → `777a24c`）。gated bodies `5c1b01c/5c1b2b0` 插入／摘链，从 `self+4912+16*index` 取队列；index 5 正是 sender 的 `+4992`。 |
| 定时发送 | `5c0c4e8 → 5c26e90 → [6deaf68]` 创建 +5040 gate，`5c0c59c` 挂到 +5048 loop。donor 的 **fake benchmark** timer `5c0d138` 的 action 是 `5c0daec`，`5c0d19c` 把 timer 挂到 slot 111 所返的同一个 +5048 loop（`5c122bc`）。`5c1b838` 本身不进 gate；在 `5c1b948` 读头、`5c1b980` 发送、`5c1b9b4` 走 next。 |
| 直接发送／停机 | `5c10084` 在 Legacy slot 330 `5c0fbe8` 内；经 `5c1082c` 的非 benchmark 分支到 `5c10894`，无自身 gate，不能由定时器锚点推导所有调用者已持 gate。Legacy slot 87 `5c0dff4` 的 `5c0e24c/254` 释放并清 timer 成员，`5c0e2d4` 在同一 loop 上移除 command gate；没有包住整个 stop 的 `runAction` 锚点。nuwa `:423–442` 同样把 timer 挂到 `getWorkLoop()`，但 `stop/free` 改状态、cancel/remove/release 没有整体 gated action。真实 8796 的 `IOTimerEventSource.cpp:149–156,176–184` 在回调前关 loop gate；不等于证明 teardown 全段持 gate，也不等于观测到竞态。 |

即使串行域补齐，现有 `NativeLegacyDisplay.cpp:417` 也不能绑定该 sender：`5c0dbbc–5c0dbc8`
把本次时标与递增计数分别写到 +5680/+5672，`5c0db88–5c0dbb4` 生成相邻时标间隔
（首帧用配置间隔），`5c0dc28–34` 依次传**计数、时标、间隔**，并非 nuwa 的
`absoluteTime、continuousTime、interval`。直接路径另从 +176/+184/+192 取值（`5c10078–84`）。
最小下一步：只读追这三个直接路径字段的写者和 slot 330 的 caller gate，再用 host-only
测试固定消息六字的顺序与单位，覆盖注册→tick→移除、tick 已排队→stop 后无发送／重挂。
没有通过上述检查前，不改 timer／gate，不加空 sender。

**CPU-only 范围。** `package/NuwaLegacyDisplay.cpp:200` 拒绝 GPU offer；若同时保持
`startDirect` 条件不成立（驱动 `:268–270`），GPU completion 请求、direct latch 和 fence
分支不可达，但 `validated`、`transferred` 仍非空操作（`:600,718,743–763`）。
例如未设置两个退休选项时，CPU copy 已结束而 `retireSwap(...,false)` 不完成请求，
`transferred` 留置。donor 5 秒 wait 并不以 GPU/direct scanout 为前提（`5c11884/5c118d8`）；
超时支线的 slot 329/330 调用（`5c11984/5c11a78`）不能以 CPU-only 判为不可达，
也不能以禁用 C++ cancel override 判为已实现。没有执行此支线，guard 保持。

**复跑。** WSL root 按 §11 的命令，`GEN=out/nuwa-display-timing-donor-recheck` 重派生，
三个生成文件逐字节一致；真实 CPO 使用新 `HOST=out/nuwa-display-host-timing-recheck`。
归档 612752 B，SHA256 `a8fc69395ebe0e314d1f9ec1ef13bf1931aae1359ff7691a9ce7ae904dd5bf1a`；
归档三成员、手动初始化、六个槽和 381 项未解析指纹同 §11，`runtime_eligible=false`。
两个负例：复用新 `compile.json` 的 `directory`/`arguments` 仅把取消宏置 1、改 `-o` 到新对象，
clang 在 `NativeLegacyDisplay.cpp:770:36` 拒绝 `override`（exit 1，无对象）；§11 的
derive 命令改用 1 字节零输入和新输出目录，拒绝非固定 donor（exit 1，无输出目录）。
未链接、未改 Libm／guard、无可运行候选、无设备操作，未独立复跑。

## 13. 方案 A：20H392 refresh 生产合同与 vsync 写者（self-checked）

设备基线 `a50714c`，基座和驱动 pin 同 §12。重新核对 50,937,856 B donor 的完整
SHA256（§1），按 Mach-O 映射反汇编、用 vtable/GOT 和符号表确认下列地址。地址省略
`0xfffffff000000000` 前缀。

### Refresh：六个键已定，消费合同未闭合

`5c23610` 调 slot 287 填六个 u64，再将下表字典挂为 `IOMFBDisplayRefresh`
（`4f67d52`，`5c237b8`）。表中的数值来自 **Legacy fallback** `5c234b4`，
不等于 H10P 的硬件返回值。`ticks(ns)` 是 slot 271 换算：Legacy
`5c24a58 → 5c25b54 → [6deb498] → _nanoseconds_to_absolutetime`。

| word | 字典键（字符串地址／插入调用） | `fixed=1` | `fixed=0` |
| --- | --- | --- | --- |
| 0 | `displayMinRefreshInterval` (`4f67cac` / `5c23710`) | `0x04444444` | 同左 |
| 1 | `displayMinRefreshIntervalMachTime` (`4f67cc6` / `5c2372c`) | `ticks(16666666)` | 同左 |
| 2 | `displayMaxRefreshInterval` (`4f67ce8` / `5c23748`) | `0x04444444` | `0x0aaaaaaa` |
| 3 | `displayMaxRefreshIntervalMachTime` (`4f67d02` / `5c23764`) | `ticks(16666666)` | `ticks(41666666)` |
| 4 | `displayRefreshStep` (`4f67d24` / `5c23780`) | `0` | `0` |
| 5 | `displayRefreshStepMachTime` (`4f67d37` / `5c2379c`) | `0` | `0` |

偶数字是 32.32 秒；min/max 转换先截断 `word * 10^9 / 2^32`。
**字典实际不是无条件保留 64 位数值**：`5c1d818/828` 以 `w2` 存／取，
零扩展到 `x0` 后调用 `OSNumber::withNumber(unsigned long long, unsigned int)`
（`5c270e8 → [6deb130]`）；位宽参数仍是 64。不能由此推断消费者要求截断，
也不能把高 32 位非零的输入视为 donor 会原样发布。

- **状态写者**：Legacy `5c0d3dc` 先清 `self+5410`。H10P gated hardware
  start `5cd0298` 经 `5cd02d0 → 5ccf7ac` 读取 provider 的 `external`
  （`4f8c1b0`，要求 4 字节数据）。`5cd03d0–3d8` 对存于 `self+5416`
  的非零布尔值取反，再写 `self+5236+174`（即 +5410）。无有效属性时该
  分支不更新 +5416；`5cd03d8` 仍从其当前值计算 +5410。`5c236b4`
  取 +5410 的低位，不读 nuwa 的 `primary` 或 `sheng-vsync-fixed`。
  H10P slot 287 `5ccf498` 在该位为真时优先调用 `self+7208` 对象的
  `vptr+1456`；返回假或该位为零才回落 Legacy。已有一个独立内核消费点
  `5c221a0–5c221e0`：成功才以 `words[1]` 的两倍作 swap 时间比较；
  它直接调用 slot 287，**不读取该字典**。
- **失败分流**：`OSDictionary::withCapacity(1)` 返回空时，`5c23678–90`
  直接返回假；slot 287 返回假时 `5c236bc–f0` 记录
  `get_timing_attributes_gated failed` 后返回假，该分支未走字典 release。
  两者均不发布，沿 §12 的 H10P boot/start 返回链阻止注册。进入六键路径后，
  `5c1d848` 遇 OSNumber 分配失败跳过该键，`5c1d864` 不消费插入结果；
  `5c237b8` 也不消费 `setProperty` 的返回值，release 后仍返回真。
  这不是“六键齐全且注册表写入成功”的保证。nuwa `NativeLegacyDisplay.cpp:530`
  则不消费整个 helper 的返回值。
- **首个缺口**：缺同版渲染端读取 `IOMFBDisplayRefresh` 的调用点，无法证明
  它用哪一对单位、怎样处理缺键或发布失败。`NativeLegacyDisplay.cpp:527–547`
  的其它轮次注释和 slot 287 的内核比较都不能代替该证据。GOP 的映射大小也不是
  刷新率证据。保留 refresh import 未解析，不实现 formatter、不写私有状态。

### Vsync：定位写者；不改 gate

- fake timer 的 +5672/+5680/+5688 在 `5c0d08c–94` 清零；
  `5c0dbb4–c8` 分别填间隔、时标、递增序号。Legacy 取时 slot 239
  `5c2475c → 5c17770 → 5c17784 → [6deb478]` 是 `_mach_continuous_time`；
  首间隔用 +5696 的纳秒配置经 slot 271 转换，否则用相邻时标差。
- 直接路径的 +176/+184/+192 在 `5c0d520/5c0dce4/5c0dce8` 清零；
  `5c1b744` 中 `5c1b78c` 递增序号，`5c1b810` 保存 slot 239 时标，
  `5c1b7c8/7f8` 写时标差或首帧由纳秒参数换算的间隔。
  Legacy slot 330 的 `5c10078–84 → 5c1082c → 5c10894` 从这些字段发消息；
  `5c1b90c–944` 依次拆为序号、时标、间隔各自的低／高 32 位，共六个标量。
- 已证的 timeout 入口之一：`5c121ac–5c12214` 以 +5040 `runAction`
  执行 `5c10d44 → 5c10e90/5c10fcc → 5c11160`；其 `5c118d8` 是
  同一 gate 的 `commandSleep`，返回后才可能调用 slot 330（`5c11a78/af0`）。
  这不是 sender 自身进 gate，也不能把 H10P slot 330（`5cd16e0`）当成
  同一个 Legacy 函数。stop 的 `5c0e24c/254` 清 timer，`5c0e2d4` 才移除
  +5040 gate，没有包住这段的显式 `runAction`。
- **首个串行缺口**：缺 `NativeLegacyDisplay.cpp:456 → stopVsync()` 进入
  `cancelTimeout/removeEventSource/release` 前已持与 tick 相同 workloop gate
  的调用链证据；局部 `removeEventSource` 不覆盖整段。未接 sender，也未改 timer。

复算：沿用 §11 的 `PY`／`BASE` 与 derive + 三文件 `cmp`（新输出目录）；
按上表和 writer VA 用 donor 段映射复核指令，`0x04444444` 与 `0x0aaaaaaa`
分别乘 `10^9` 右移 32 位复算纳秒值。无适配，故本轮未重编 8796 归档，
不把 §12 的归档复跑计作本轮结果。未链接、未上机、未独立复跑。

## 14. 方案 A：20H392 用户态读者与 stop 边界（self-checked）

设备仓 `06e4f11`，基座 `693f5d9c`、驱动 `e47c1b8`。只读挂载
`out/root-inputs-20261113/os-window.raw`（SHA256 `6e87bfca…8906`）与
`ipsw/20H392/087-86593-047.dmg`（`9cd738f3…6849`），使用本地
`sgan81/apfs-fuse@66b86bd525e8cb90f9012543be89b1f092b75cf3` 的 `apfs-fuse -o ro`；
两卷 `SystemVersion.plist` 都报 iPhone OS 16.7.16 / 20H392。递归遍历两个 `root/`，
在 Mach-O/fat magic 或 `dyld_v1` 的常规文件中找 `IOMFBDisplayRefresh` 及 §13 六个
以 NUL 结尾的键。OS 计 2,769 文件 / 1,091,890,394 B（含 `backboardd` 和
`SpringBoard.app/SpringBoard`，无 cache 文件），零命中；SystemOS 计 61 文件 /
3,341,336,528 B，含 46 个 cache 文件（主 cache、`.01`–`.40` 各片、`.41.dylddata`、
`.42.dyldlinkedit`、`.symbols` 和两个 DriverKit cache 文件）；两卷均无读取错误。
字面量仅主 cache `.03/.07` 命中；这不是对动态拼键或间接消费者的排除。

以 cache mapping 将文件偏移还原为未 slide 的用户 VA；以 Mach-O `LC_ID_DYLIB`
及各节边界确认归属，在 `.27.dylddata` 取相应 `__cfstring` 对象，在 `__text` 找
`ADRP/ADD` xref，沿 branch island 解出实际入口并以 `.42.dyldlinkedit` 的
`LC_SYMTAB` 复核符号。以下用户 VA 不使用 §13 的内核地址前缀。

- **QuartzCore / WindowServer：** `.03:0x17eed25`（VA `0x18857ad25`）
  → CFString `0x1d5b4d280` → `0x1883adf54–60`。`copy_display_property`
  (`0x1883ac314`) 先通过 `AppleDisplay+0x318` 的连接调用
  `IOMobileFramebufferCopyProperty`；取不到才以 `+0x310` 的 registry entry
  在 `IOService` plane 调 `IORegistryEntrySearchCFProperty`（选项 0）。
  结果必须是 CFDictionary，否则释放并当作缺字典。
  `0x1883adf74/94` 分别取 `displayMinRefreshInterval` 和 `displayRefreshStepMachTime`；
  非空时 `CA_CFIntValue` 以 `kCFNumberIntType` 取值（另接受 CFBoolean），随后
  `sxtw`。min 存 `+0xaf0`；step 经 `CATimeWithHostTime`（`mach_timebase_info` 的
  `numer/denom * 10^-9`）变成秒存 `+0xaf8`，另受功能条件控制可被清零。
  字典不存在时跳过两次写入，前面 `0x1883ad700/704` 已清零；单键不存在也按零。
  在没有已缓存周期或 `CA_HEARTBEAT_RATE` 覆盖时，
  `0x1882dc360–3a4` 优先非零 step，其次非零 min 乘 `2^-32`（`+0x220` bit 4
  置位时减半），否则取 `0x18855caa0` 的 `1/60` 秒。该读点不取 max 或 min/max MachTime。
- **MediaToolbox：** `.07:0xdee43c`（VA `0x19572e43c`）→ CFString
  `0x1d6a4a528` → `FPSupport_GetDisplayRefreshInformation` (`0x1951ce2d8`) 内的
  `0x1951ce58c–594`。`IOMobileFramebufferCreateDisplayList` →
  找到条目中 `+8 == 0` 的显示 → `IOMobileFramebufferOpenByName` →
  `IOMobileFramebufferCopyProperty`，再检查 CFDictionary。该 CopyProperty
  (`0x1af2236d4`) 分派到连接 `+0x6b0`，常规实现 `0x1af224aac` 用连接 `+0x10`
  的 registry entry 在 `IOService` plane 调 `IORegistryEntrySearchCFProperty`；
  另一实现 `0x1af22be40` 先查本地字典再走后端，不能把所有连接都视作直接查 registry。
  `0x1951ce66c/6c0/714` 经 `FigCFDictionaryGetInt64IfPresent` 分别取
  `displayMaxRefreshInterval`、`displayMinRefreshInterval`、`displayRefreshStep`；
  仅 helper 返回真且有符号值 `>=1` 时单独覆盖对应输出。max/min 用
  `CMTimeMake(1, round(2^32/v))`，step 用
  `CMTimeMake(1, round(10^9/v))`（`0x195765800` 是 double `10^9`，不能按 32.32
  套用）。默认分别为 `1/60`、`1/60`、`kCMTimeInvalid`；缺字典或类型错走
  `0x1951ce76c` 的 `FigSignalErrorAt` 再到公共输出路径，保留三个默认值。
  缺单键、非 CFNumber 或非正值仅保留该项默认。该读者不用 `*MachTime`。

这两条闭合了各自实际读取的格式和缺键分流，不意味着 GOP 物理速率已知；
§13 donor 的两个 step 字都为零，也不是设备侧可以从当前模式推导非零 step 的证据。
`displayRefreshStep` 和 `displayRefreshStepMachTime` 不能用同一整数互换。

### 8796 gate 和取消边界

- 固定 feed `xnu-c465a9f8` 检出 `1b191cb5`；`IOService.cpp`、`IOWorkLoop.cpp`、
  `IOTimerEventSource.cpp` 与 nuwa 8796 实际构建树副本逐字节一致。
  `IOService.cpp:3274–3275` 的 finalize 路径用 **victim** 的 loop；
  `:3087 → :3387` 确有在该路线上直接调用虚 `stop(provider)` 的分支。
  但 phase-3 stop (`:3323–3324 → :3106`) 以 **provider** 为 `_workLoopAction`
  的目标，`:2476–2482` 取目标的 loop，有 loop 才 `runAction`，否则直接调用。
  本板 provider 是挂在 IOResources 下的 `IOPlatformDevice`（`package/NuwaLegacyDisplay.cpp:113–145`），
  其继承的取 loop 路线是 `IOService.cpp:1347–1355,7066–7075` 的 provider /
  platform loop；显示对象则用 donor `getWorkLoop` slot 111 (`5c122bc`，`self+5048`)。
  没有同一性保证，不能把 phase-3 stop 或 `free()` 当成已持显示 gate。
- `NativeLegacyDisplay.cpp:423–436` 把 timer 加到显示 loop；首次 arm 用 `runAction`，
  但 `vsyncTimer` 和速率字段先在 gate 外发布。默认两参工厂是 KernelHigh，
  即 passive `timeoutAndRelease`：`IOTimerEventSource.cpp:359–363,259–262,291–302`。
  `wakeAtTime` 保存 loop、递增 generation、为排队调用保留 timer/loop (`:546–575`)；
  到期先关同一 loop gate，再比较 generation，才会调用 owner (`:174–193`)。
  `IOEventSource.cpp:158–169` 的 owner 只是裸指针，不能把 timer retention 当成 owner retention。
- 同一个 donor gate 串行化 client 链表：selector 72/73 落在 §12 的两个
  `runAction`，index 5 插入后走跳表 `5c1b200 → 5c1b168 → 5c1b18c`，
  后者 `vptr+0x8a0` 是 **slot 276** (`kickSwapQueue`)，不是驱动注释里的 slot 290。
  移除在 gate 内摘链（例如 `5c1b41c/440` 更新相邻节点／队尾），不是取消 timer。
  `NativeLegacyDisplay.cpp:412–421` 的 tick 读队头、发送并 rearm；若最后一个
  client 已被移除且未重新注册，下一 tick 在 `:415` 退出，不发送或重挂。
  但 `kickSwapQueue → armVsync` (`:555–556`) 本身不进 gate；注册这一个 caller
  持 gate，不能推到所有调用路径（如 `gpuComplete:452` 明有无 loop 的 fallback）。
- `stopVsync:438–442` 先在外层 gate 未证时 `cancelTimeout()`；默认 passive
  的实现只递增 generation 并撤队，不等待已在途回调
  (`IOTimerEventSource.cpp:356,386–396`；`thread_call.c:1387–1401`)。
  `removeEventSource` 才通过同一 loop 的 control gate 摘链、`setWorkLoop(NULL)`
  （会 `disable`，再次使 generation 失效）并释放 loop 对 event source 的引用
  (`IOWorkLoop.cpp:313–315,623–670`；`IOEventSource.cpp:279–285`)。
  成功移除不是 callout 线程 join，也不覆盖移除前的 cancel 和移除后的成员清零。
  具体未排除的交错：tick 已通过 generation 检查并持 gate → 外线程 cancel →
  该 tick 仍可 send/rearm → 外线程等到 gate 才 remove。未观测到实机竞态，
  不能把上述交错说成 remove 成功后仍会调用 owner。

**可复用方案，未实现：** 复用 `IOWorkLoop::runAction`（8796 `IOWorkLoop.cpp:565–576`
同步、可递归），以 timer 注册时所用且在调用窗口内保活的 **显示 loop** 为唯一串行域。
将 timer 发布、首次 arm、所有 kick 的 vsync 部分、tick 的队列读/发送/rearm、stop
的状态撤销和 `cancel → remove → release` 放在这个域；不把整个 swap 或
`IOMobileFramebufferLegacy::stop` 移入新 action。不得在取 gate 前读 timer 成员
决定是否清理；在 gate 内先使 vsync 不再 active、清成员和 armed，再对保留的局部
timer cancel/remove，只在成功摘链后释放驱动持有的 timer 引用。摘链失败不得当作已停止，
更不能带着活动 timer 走 owner free。`free` 应依赖正常/失败 unwind 已清理的同一
不变量，不从已拆掉的父类 loop 猜取一个新 loop。外层若已经持 provider gate，需先证
两者的锁序或选无外层 gate 的显式清理点。递归 gate 也不是禁止重入：若 sender
有同线程 stop 重入或会让 gate，须分别验证中途不再继续发送以及返回后按原 source /
active 状态拒绝 rearm。timer action 应在第一次改状态前确认 source 仍是 active
timer；不得在持 gate 时等待需要同 gate 的 passive callout。

**解除判据：** 在实际 8796 IOKit 验证中区分显示/注册 gate 和 provider gate；
覆盖已排队未入 gate 的 tick、正在发送且马上 rearm 的 tick、最后 client remove 在
tick 前/后、stop 后 kick、重复 stop/free、start 失败回滚及 sender 重入。判据是
停机 action 撤销后无 owner 回调发送、无新 wake；过期 callout 可退场且引用平衡，
成功摘链、无双释放、无 gate 自等或锁序逆转。消息字序仍按 §13 的计数／时标／间隔，
不复用现有三参数语义。属性侧可先用已定位的两个 reader 建离线 CF 输入夹具：
整字典缺失/错型、逐键缺失、零值、替换一个单位而保持其它键固定；断言 Quartz
fallback 和 MediaToolbox 三个独立输出，再用 20H392 真实 TU 检查获批 formatter /
拒绝路径。夹具不代替真实 reader 或实际 IOKit 调度测试。
本轮未改变 import、timer、Libm 或设备构建输入，故未跑适配 TU/拒绝测试、未上机、
未独立复跑。

## 24. 保留已审 GOT 序列及 Libm 路线边界（self-checked）

基线 `f1ad000757bb59e2b6e457f9ff639b85398efb0a`。本机 ld 二进制含
`-ignore_optimization_hints`；仅对 CPU-only 显示组链接传入该选项，r35 控制组
参数不变。真实 r35 控制组仍除 UUID/map 首行外一致，显示组 ld 成功；现有
`audit_linked_metaclass` 的 ADRP/LDR、GOT 段和实际指针检查以及
`audit_linked_originals` 均运行到完成，随后原样 strict emit 停于
`emit_prelink.py:111`，Libm `0xfffffff005b8c1cc`。
native SHA256 `c690783526424828e23aae3e279f0db0b0141bb60af21a98233c13162b9a7c1c`。
这是禁用该次显示组链接的所有 linker optimization hints，不是对单一指令的优化；
不修改审计或 scanner。原有 metaclass 夹具重跑，错误 GOT 指针、initializer 及
getter 各拒绝；不代表最终 prelink 或运行时通过。

复跑 §23 命令，将 `--out` 换为新目录；本次输出目录为
`out/nuwa-display-ignore-loh-02`，链接后由构建脚本直接调用 strict emit，
未保存 emit 输出。首次执行时 shell 意外展开变量造成 CPO 路径为
`/iokit/DEVELOPMENT/IOPMGR.cpo.json`，未到链接；第二次使用完整绝对路径。

Libm 有界核对：研究分支 `6bfaa2f` 的
`docs/nuwa-20h392-libm-boundary-20261120.md` 未证数据边界或所有间接入边，
不能据此排除候选区间。固定的 XnuPrelink `f1d80d3` 的普通路径在
`emit_prelink.py:74–114` 扫描被选模块全部可执行段并拒绝外部 PC 相对编码；
`README.md:9–25` 的分段重定位布局是 MH_FILESET 路径，不是该传统 prelink
donor 的可直接替换选项。所查本地上游工具未发现无需排除未证区间的受支持
传统布局/重定位路线。最小下一步是取得可证明的代码/数据边界和完整相关入边证据，
或取得针对该传统 donor 的上游支持路径；当前缺此证据，strict emit 阻断不变。
未变更认证、329/330 或设备；无独立 verifier。

## 23. 方案 A2：无 GOP 软件 vsync 的真实 r35 完整链接（self-checked）

基线 `d6aad0c02e7e1203f73e4aab5f437a97e21817b6`，沿用 §22 的基座、驱动
和固定输入。新增 `--no-software-vsync`（必须与 `--cpu-only` 同用）只剪裁输出目录
中的 GOP 驱动副本：删除 timer 状态、client 队首读取、创建/挂载/首次 arm、发送、
重挂和 stop/free 的取消/摘除/释放；`kickSwapQueue` 只删 `armVsync()`，仍按原
条件 re-kick。板级 TU 不生成原空 vsync observer，不添加 sender、空回调或弱占位。
`startHardware` 的 fallible 固定 60 Hz 属性发布、slot 287 的非诊断逻辑、CPU copy、
退休条件与通用观测不变。不改 donor 自己的计时/slot 330 路径。

真实 8796 CPO：五成员归档 749384 B，SHA256
`e271ed7c33228b1b52c187725980091b2f9073eeb7707f11089bc6656ba1a629`；
`NativeLegacyDisplay.manual.o` 326771 B，SHA256
`fc75c81c00ebf7b2fb2ff8a9be3c668806e92b09b86b3d04e82caf9c6813220e`。
对原始对象和归档成员检查 Mach-O 符号和外部重定位，并用 `llvm-nm` / `llvm-objdump`
复核：无 GOP timer/sender/observer，仍有 refresh formatter、scanout、cache flush、
`finishTransfer`、validation/transfer/copy-timing/retirement 的 BR26 引用；
六槽重定位继续匹配（329 为 guard，330 为 donor）。归档 213 → 210：仅减
`IOTimerEventSource::timerEventSource`、`_mach_continuous_time`、`_native_legacy_vsync_notify`
三项外部依赖；只用 `--cpu-only` 的对照仍为 213。两入口单传新选项均拒绝（exit 2）；
refresh、上游 request-state 和 teardown 十个模型用例通过，均不代替运行时。

完整 r35 控制组仍只差 UUID/map 首行，显示组 **ld exit 0**，沿用原 r35 renderer、
完整 object filelist 和原链接参数；实际 `HOST-ONLY-display-native.unstripped`
17718344 B，SHA256 `f03ae8488c97c26bf6467ec1b960b965bae81cda7bda4beaa83e52e5d70356cf`，
`native-link.log` SHA256 `7abd1a1453b842efc37352087d1a77a760ca2904ef2858fea66626b516895387`。
构建脚本的首错是 `build-nuwa-display-native.py:188`：链接器把
`NativeLegacyDisplay::MetaClass::MetaClass()` (`0xfffffff0079bc704`) 的
`ADRP/LDR x2` 化成 +0x10 的 `NOP` 与 +0x14 的 `LDR x2, literal`，
旧审计只接受前一种形式，未改。单独解码确认后者仍从 `__got` 的
`0xfffffff0079e0008` 取 `0xfffffff006a45540`，与 `superClass` 指针和 ABI pin 一致；
这不是最终 prelink 绑定或生命周期验证。

按要求对**实际显示 native**直接运行未修改的严格 `emit()`（不是控制组）。
XnuPrelink `f1d80d37528a33e24643583787123c652b70a268`，两个 Python 输入同 HEAD
（仅工作树 CRLF）。29 roots、slide `-0x1000000`，exit 1；首错
`emit_prelink.py:111` / `instruction_inventory`：
`External PC-relative encoding at 0xfffffff005b8c1cc; no instruction rewrite supported`，
位于 Libm。`strict-emit.log` SHA256
`0c28811ab60077bdea40c5499f169580b090e8102d8ed6d4a25f3e55a6371e98`。

复跑（WSL root，设备仓 cwd）：沿用 §20 命令，追加 `--cpu-only --no-software-vsync`
并设置 `--out "$out"` 为新的 `out/` 子目录。保留链接后的文件；即使外层因旧
metaclass 指令形状检查退出，也不要放宽检查或改 scanner。仅作离线 strict 诊断：

```sh
"$python" -B - ../../UniXNU "$out" > "$out/strict-emit.log" 2>&1 <<'PY'
import hashlib, json, sys, tomllib
from pathlib import Path
base, out = map(Path, sys.argv[1:])
sys.path.insert(0, str(base / 'kits/XnuPrelink'))
from emit_prelink import emit
native = (out / 'HOST-ONLY-display-native.unstripped').read_bytes()
donor = (base / 'out/ipsw/20H392/kernelcache.decompressed').read_bytes()
slide = json.loads((out / 'derived/nuwa-display-abi.json').read_text())['metaclass']['collection_slide']
roots = tomllib.loads(Path('board.toml').read_text())['os_overrides']['ios-16.7.16-20H392']['kernel']['prelink']['roots']
roots = list(dict.fromkeys([*roots, 'com.apple.iokit.IOMobileGraphicsFamily']))
print(f'native sha256={hashlib.sha256(native).hexdigest()} slide={slide:#x} roots={len(roots)}', flush=True)
emit(native, donor, roots, slide)
print('strict emit accepted; bytes discarded, runtime still ineligible')
PY
```

无 GOP VBL 软件发送是 A2 的取舍，不是用户态已选 `CADisplayTimer` 的证据：实际
同进程选路/回调与首帧、329/330 超时请求生命周期、Libm 严格门均**未闭合**。
若实际选择依赖 GOP VBL，则须另证 sender 消息契约及 teardown 串行化方能恢复。
未启 hooks，未保存 prelink 输出、未打包运行候选、无设备操作、未独立复跑。

## 22. 方案 A：CPU-only 8796 TU 与 r35 完整重链（self-checked）

基线 `9791cef`。复用 `UniXNU/GopFramebuffer@e47c1b8de169cd2bd0b885c7d85e433010e3cdf2`
（BSD-2-Clause-Patent）；基座 `693f5d9c` 不写入。两次只读检查的上游 HEAD 一致：
UniXNU `8542980d`、GopFramebuffer `b0d812d5`。`--cpu-only` 仅用于主机；基座驱动
暂存于输出下的 `archive/base/drivers/GopFramebuffer`，只改副本。历史路径仍可复跑。

四项弱导入使 `-static` 失败。版适配在编译前去掉 `note()` 的 GPU trace/fence 采样，
以及 `startDirect → gpuWrote → DPU flip` 和 `kickOnce → gpu_offer → gpu_complete`
两条完整路径（包括 latch/fence timer、异步回调、提前 retire、专用诊断和板级拒绝桩）。
不能只把 `gpuWrote()` 改成成功：那会留下 `sheng-dpu-scanout=2` 下可达的硬件翻页。
`kickOnce()` 回到原 CPU 分支：仍需验证请求、放行 scanout、映射并维护缓存、执行
blank/half/plain/diff 写入及 store barrier，再走原 retire 条件；没有伪造 fence 或完成。
保留 `noteSurface`、通用 ring/stat 和 transfer/copy/validation/retirement 日志；
ring 中 GPU outstanding 位为零。原 r35 renderer 归档（含校验与日志）逐字节复用，
不再需要局部化两项 early GPU counter 的旧观察 alias。代价是无 GPU offload、
direct scanout 或对应诊断；只有真实 GPU/DPU provider、同步与生命周期经审查后才恢复。

真实 8796 CPO：五成员归档 762000 B，SHA256
`48aaf8c8b96d99f5b57163e8711d4d7c218cfba1ded8c36a4a9bbf81625e6e03`。
`llvm-nm` 与 Mach-O relocation 双检确认四项 GPU、两个 DPU 导入及 GPU 回调无定义、
无引用；`llvm-objdump --macho --reloc` 同时确认 copy timing、cache flush、validation
和 transfer 调用仍在。归档未解析 221 → 213，无新增；除四 GPU、两 DPU 外，去掉
direct 专用 `_IOFreeData` 和 `___ubsan_handle_add_overflow_minimal`；`IODeviceMemory::withRange`
仍由板级 TU 引用。329 仍为 native guard，330 仍为 donor relocation；两者不放行，
源级比较确认 `vsyncWanted` 至 `stopVsync`、CPU copy 段、retire/validate 及 fallible start
未变。上游 `Test/request-state.c`、refresh fixture、teardown 10 例均 self-checked。

独立复跑：设 `out` 为 `out/` 下的新路径，用 §20 的 WSL 命令，附加 `--cpu-only`
并改用 `--out "$out"`；另用新输出路径
执行 §20 的两个 fixture。可直接对 `archive/NativeLegacyDisplay.manual.o` 执行
`llvm-nm -Pa` 与 `llvm-objdump --macho --reloc`。上游布局/复制 fixture：
`cc -std=c11 -O2 -Wall -Wextra -Werror "$out/archive/base/drivers/GopFramebuffer/Test/request-state.c" -o "$out/request-state" && "$out/request-state"`。

实跑 `out/nuwa-display-r35-cpu-01`：控制组除 UUID/路径外与固定 r35 一致，
显示组完整 ld **退出 1，唯一未定义为 `_native_legacy_vsync_notify`**：
生成的 `NativeLegacyDisplay.cpp:187`（固定上游 :417）在 `vsyncTick()` 调用 sender，
编译后由 `vsyncFired` 引用（`__text+0x2290`，BR26）；r35 没有 provider。
`native-link.log` SHA256 `4d593c89ac21d42f2beafa687ea29e58d9ff98004833abe14ceee222db1709ed`。
未生成显示 native，Libm strict emit 未到且未改；无打包、无设备操作、未独立复跑。

## 21. 方案 A：refresh 接入 start 后的 r35 完整重链（self-checked）

基线 `0ad2e64`，基座 `693f5d9c`、实际编译的驱动 `e47c1b8` 不变。只读查得
UniXNU HEAD `8542980d`、GopFramebuffer HEAD `b0d812d5`。固定版与 HEAD 都在
普通 swap 的 `note()` 取 trace/fence，而非只在 GPU offer 成功时调用；
`gpuWrote()` 也保留两个 fence 查询。未找到可复用的 CPU-only 条件编译路径。
真实 8796 Mach-O 的四项都带 `N_WEAK_REF`，但原 r35 `-static` 链接拒绝无
provider 的弱引用。基座 `build-fileset-release-reference.py` 的私有比较桩
不是可复用的弱引用实现。本轮不更改四处链接合同，不加假定义。

复用本仓 §15 六键 formatter 和真实 8796 `RegistryBackend`。只在生成 TU 的
`startHardware` 末尾、GOP 映射校验通过且 `primary` 为真时接入：
`sheng-vsync` 缺省/0 或显式 60 接受固定 60 Hz **软件回退**（不声称面板速率），
其他值拒绝；任何 formatter 失败均返回 `false`，并清除 `primary`、释放
`bootMapping`。Legacy `start` 在 slot 274 返回假时不进入 slot 84（§12）；
板级 late probe 的失败分支也不注册。移除 `void registerService` 的旧发布调用，
保留注册 guard、slot 287 和原 donor 绑定。未找到经深审支持、真正编译移除
软件 sender 调用的路径，vsync 保持未解析，timer 与 teardown 不改。

实际 8796 对象：`startHardware`（`__text+0x13e8`）在 `__text+0x15cc` 有唯一
formatter `BR26`，紧随 `tbz w0,#0` 进入失败分支。五成员归档审计确认 formatter
是唯一强定义、驱动是唯一强引用、旧 refresh 导入消失，自动 init 为 0、六个槽
重定位不变。归档 812048 B，SHA256
`a005b77b4fc01e1111078a2888e1e826ddb4713e2af028c2b84e88f61b63af08`。
归档外部导入净数仍为 221：旧 refresh 导入换成 `OSSymbol::withCString`，
后者由实际 r35 内核提供；完整未解析指纹
`c2b547267d51f69a79995ecceab0c6bd12b315b358e8720849b8f29795c12862`。

按 §20 复跑完整链接，仅改用新 `--out out/nuwa-display-r35-refresh-01`，两条
fixture 命令同样替换输出路径。控制组除 UUID/路径外仍一致；刷新 fixture（含
速率与失败分流）和 teardown 10 例通过。显示组 ld 退出 1，**首错仍是
`NativeLegacyDisplay.cpp:193` 的 `note()` 引用无提供者的 `_native_adreno_fences`**。
与 §20 的六项相比只消去旧 refresh；四项弱 GPU 和一个强 vsync 仍未定义。
`native-link.log` SHA256
`0a8d8cf488be86c172e75db068232042d979274dfccc70dd18b01df81760ff68`。
再用新控制组 native、§17 的 29 项 roots 和 `-0x1000000` 复跑不改动的 strict
`emit`，在 `emit_prelink.py:111` 拒绝 Libm `0xfffffff005b8c1cc`，无写出。
显示组未生成 native，未到其 strict emit；329/330 门保留。未验证运行时注册，
未产运行候选，无设备操作，未独立复跑。

## 20. 方案 A：r35 完整输入重链（self-checked）

基线 `1352727`。`--r35-dir` 复用已成功的 r35 `native-link` argv/cwd 和工具环境；
不执行旧 builder、不用隔离 XNU archive 替代对象列表、不接新的 Adreno/GPU 或 timing 实现。
入口校验 r35 命令记录、961 行 `link.filelist`、原 map（990 个输入条目，含 linker
synthesized）、native、renderer archive、CPO、startup record、ld 与 donor 的 pin；
显示归档沿用基座和 driver 的 revision/ABI 门。控制组重链仅重定向输出及 map：
Mach-O 除 `LC_UUID` 的 16 字节字段外逐字节相同，map 除首行输出路径外逐字节相同。

显示组保留 r35 对象、`lastkernelconstructor.o` 与原 archive 次序，末尾 force-load
原有四成员手动初始化显示归档（自动 init 为 0，不装 hook）。r35 renderer `BootProgress.o`
原字节复用，`_boot_progress_prepare_scanout` 单定义。与显示归档仅有两个同名外部定义：
`_native_legacy_early_failures` 和 `_native_legacy_early_retires`。用同工具链 `nmedit -R`
在输出目录局部化旧 companion 中这两个绝对零占位，归档同位置、同成员顺序；
`llvm-nm` 核对两个重名各有且仅有一个新的外部提供者，其余 companion 外部符号不变，
`llvm-objdump -s -r` 核对其段内容与重定位不变。没有新增 stub 或修改任何既有产物。

§19 的 131 项经 map、`llvm-nm` 和实际 ld 对照：45 个由 r35 的真实输入供给
（renderer 15、UFS archive 14、RamBlock archive 13、`vm_user.o` 2、`vm_map.o` 1），
80 个是 r35 已有的 renderer 观测绝对零占位；这 80 个都不在显示归档导入表，不算显示 ABI
实现。实际完整重链退出 **1**，仅剩以下六项，没有新增未定义；首错是
`GopFramebuffer/NativeLegacyDisplay.cpp:193` 的 `NativeLegacyDisplay::note` 引用
`_native_adreno_fences`，该完整静态链接未提供它：

| 对象导入 | 剩余符号 |
| --- | --- |
| 弱（本静态链接仍拒绝） | `_native_adreno_fences`, `_native_adreno_fences_detail`, `_native_gpu_trace_enabled`, `_native_gpu_trace_record` |
| 强（timing 未闭合） | `_native_legacy_set_refresh_properties`, `_native_legacy_vsync_notify` |

WSL root，设备仓 cwd，独立复跑用新 `--out`：

```sh
obj=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837
python=/home/wh1stl3/.local/bin/python3.11
"$python" -B scripts/build-nuwa-display-native.py --base ../../UniXNU \
  --cpo "$obj/iokit/DEVELOPMENT/IOPMGR.cpo.json" \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 --out out/nuwa-display-r35-full-02
c++ -std=c++17 -Wall -Wextra -Werror scripts/host/test-nuwa-display-refresh.cpp \
  -o out/nuwa-display-r35-full-02/refresh-fixture
out/nuwa-display-r35-full-02/refresh-fixture
"$python" -B scripts/test-nuwa-display-teardown.py
```

完整 ld 日志 `out/nuwa-display-r35-full-02/native-link.log` SHA256
`06c68fe56c48ed98bbd427823d6c19cacb5528df438a6b37b24f839b8b74555a`。
旧隔离入口按 §19 复跑，退出 1，131 项及顺序不变。refresh 夹具和 teardown 10 例通过。
用控制组 native 按 §17 相同 roots/slide 调严格
`emit`，仍在 `emit_prelink.py:111` 拒绝 Libm `0xfffffff005b8c1cc`（无写出）。
完整显示 native/map 均未生成，其 strict emit 未到达；329/330、refresh/vsync 及扫描
规则均未改。归档、控制组和中间文件不是设备候选；未上机、未独立复跑。

## 19. 真实 renderer 接入及剩余链接项（self-checked）

基线 `3f42e8ea760c524d539c05e7c96e659bcf8e11cc`。复用本仓
`scripts/build-boot-progress-nuwa.py` 构建的真实 `BootProgress.o`，来源
`UniXNU/UniXNU-sheng@998d0cc5023d4eff54a1ef40cce6ec89dc10083c`（MIT），
不接同 archive 的 stub 成员。对象 SHA256
`acbbf9f569961f4e58947020cd297a16682cddaa096bb6f0e353447ca3b77224`；
构建时 startup 编译记录 SHA256
`8e85399e601ece0259f6e53889adb65fc862d91b638d986dbde06c4cffe8694e`，
与链接树同一记录逐字节一致；构建器检查这两个 pin。在原有 XNU 与 display
force-load 之后、原始 linkarchives 之前加入对象；未改基座或扫描规则。

复跑 §17 命令，追加
`--renderer out/nuwa-bootprogress-20261115-r1/BootProgress.o`，
`--out out/nuwa-display-native-renderer-01`。显示归档 SHA256
`960cb19d1d448cd59076dd2c407793698b096617877cdf573f73b1effcecc0d4`。
实际 ld 退出 1：原 `_boot_progress_prepare_scanout` 已不在错误表，首错是
`package/boot-progress/BootProgress.c:1311` 引用的 `_boot_diag_scan`，
真实 renderer 带入额外依赖；不以 stub 补齐。以下为 ld 报出的全部 131 项，
包括原来的另外 11 项（各行均为 Mach-O 符号）：

```text
_boot_diag_scan _boot_diag_stream _boot_log_tick _boot_process_attempts
_boot_process_busy _boot_process_capture _boot_process_passes _boot_process_rows
_boot_process_seen _boot_process_snapshot _boot_progress_exit_fault
_boot_progress_exit_reason _boot_progress_throw_text _boot_ui_trace_index
_boot_ui_trace_label _boot_ui_trace_phase _boot_ui_trace_ready
_boot_ui_trace_role_rows _boot_ui_trace_rows _boot_ui_trace_snapshot
_mach_vm_allocate _mach_vm_remap _native_adreno_audit_attr
_native_adreno_audit_ticks _native_adreno_cache_stats _native_adreno_coherence
_native_adreno_fences _native_adreno_fences_detail _native_adreno_reassert_ticks
_native_adreno_wc_audit _native_adreno_wc_distrusted _native_cpufreq_row
_native_cpufreq_stage _native_data_persist_errors _native_data_persist_first_lba
_native_data_persist_gpt _native_data_persist_gpt_after _native_data_persist_header
_native_data_persist_loaded _native_data_persist_present _native_data_persist_state
_native_data_persist_syncs _native_data_persist_writes _native_gop_gpu_abandoned
_native_gop_gpu_completions _native_gop_gpu_failures _native_gop_gpu_offers
_native_gpu_trace_enabled _native_gpu_trace_record _native_hid_input_events
_native_hid_input_results _native_legacy_client_calls _native_legacy_client_class
_native_legacy_client_pid _native_legacy_client_status _native_legacy_client_type
_native_legacy_copy_bytes_last _native_legacy_copy_bytes_sum _native_legacy_copy_last
_native_legacy_copy_max _native_legacy_copy_n _native_legacy_copy_sum
_native_legacy_frame_color_counts _native_legacy_frame_color_other
_native_legacy_frame_colors _native_legacy_frame_count _native_legacy_frame_kind
_native_legacy_frame_stats _native_legacy_frame_time _native_legacy_gop_bytes
_native_legacy_gop_physical _native_legacy_gop_virtual _native_legacy_gpu_fallbacks
_native_legacy_gpu_last_status _native_legacy_guard_slot _native_legacy_pm_callbacks
_native_legacy_pm_calls _native_legacy_pm_stage _native_legacy_prepare_attempts
_native_legacy_prepare_calls _native_legacy_prepare_reason _native_legacy_rej_class
_native_legacy_rej_reason _native_legacy_rej_size _native_legacy_rej_state
_native_legacy_rej_surface _native_legacy_rej_surfaces _native_legacy_retirement_calls
_native_legacy_set_refresh_properties _native_legacy_stage
_native_legacy_swap_accepted_count _native_legacy_swap_rejected_count
_native_legacy_swap_validation_calls _native_legacy_swap_validation_reason
_native_legacy_swap_validation_result _native_legacy_transfer_bytes
_native_legacy_transfer_calls _native_legacy_transfer_status _native_legacy_vsync_notify
_native_owner_root_accepted _native_ram_block_bytes _native_ram_block_resident_bytes
_native_ram_block_sparse _native_touch_count _native_touch_rows _native_touch_seq
_native_touch_stage_req _native_touch_xs _native_touch_ys _native_ufs_block_failures
_native_ufs_block_reads _native_ufs_blocks_published _native_ufs_dpu_map
_native_ufs_dpu_state _native_ufs_integrity_failures _native_ufs_matched
_native_ufs_probe_calls _native_ufs_progress_text _native_ufs_read_ticks
_native_ufs_root_failure _native_ufs_root_step _native_ufs_verified_blocks
_native_ufs_verify_ticks _native_virtio_read_failures _native_virtio_read_requests
_native_virtio_ready _native_virtio_verified_blocks _native_wi_count _native_wi_log
_sheng_cpufreq_poll _vm_map_create
```

完整链接日志（含引用者）仅在 `out/nuwa-display-native-renderer-01/link.log`，
SHA256 `dc4596ce0f9daed429a602b430842c67fc0ed0eb8386b5304ac9d483c9059783`。
原 Adreno 实现位于 `drivers/Adreno740/NativeAdrenoPublish.cpp`，DPU map 属于
存储/SMMU；没有本批可证明兼容且无额外硬件/并发合同的现成对象，因此未强接。
`mach_vm_*` / `vm_map_create` 是原 XNU archive 中 vm_tests 的引用，未伪造导出。
未产生 native，strict emit 未到达；329/330、refresh/vsync 未改，非上机候选。

## 15. 方案 A：独立 refresh formatter 与 teardown 夹具（self-checked）

设备基线 `d5f3fe4`，基座 `693f5d9c`，驱动 `e47c1b8`，donor 与 §1 相同。
`scripts/host/NuwaDisplayRefresh.*` 只格式化 §13 的 **Legacy fallback**：调用方必须
显式给 `Fixed`／`NonFixed`，不从 primary、boot-arg、GOP 模式或面板推导。min/max
分别以 32.32 秒和先截断纳秒再换算的 Mach ticks 表示；两个 step 保持零。
对超出 donor `w2` 表示范围或变成零的周期 ticks 返回错误，不做截断包装。
6 个 `OSNumber` 位宽都是 64。只在整个临时字典成功后尝试一次 `setProperty`；
依次区分字典／键／数字分配、插入及属性写入失败。直接使用 8796 的 OSSymbol
重载；`IORegistryEntry.cpp:873–879` 的 C 字符串重载不检查临时 symbol 是否为空。
这是 host-only 编译物，不替换导入符号，也不决定服务注册遇失败后是继续还是拒绝。

同一 formatter 用 typed-input 夹具执行：两种正例、两类读者的缺／错型字典、
六个单键的缺失／零／错型、独立变更时制并检查另一读者不变；注入每个键
（含属性名）、每个数字、每次插入、字典、转换和属性写入失败，检查零遗留引用、
不尝试发布半成品且保留原属性。不是运行 QuartzCore、MediaToolbox 或 IORegistry。
首轮夹具错误在旧 `test-nuwa-display-refresh.cpp:108` 的 MediaToolbox step 断言：
重置输入后 step 仍为 20,000,000 ns，末例错期望了前一个用例的 40（应为 50）；已改期望，
未改单位换算。

**同步清理点取证。** `IOService.cpp:3274–3275` 的 `actionFinalize(victim)` 是一条
可在显示 gate 下同步完成清理的候选：`_workLoopAction:2476–2482` 持该 loop 引用
运行，Legacy slot 95 `6defbd8 → 7745520` 继承 `IOService::finalize`。但它只从
finalize 队列调度；phase-3 `actionStop(provider, client)` 是独立队列，仍以 provider
为目标；`willTerminate`／`didTerminate` 作为 client 回调时还可由父 victim loop 调用
（`:2943–2965,2982–2997,3218–3247`），不能无条件作为入口。板级
`native_legacy_display_late_probe` 的同步失败清理在 `package/NuwaLegacyDisplay.cpp:165–177`，
由基座 `offline-legacy-start.patch` 的 `bsd_autoconf` 在 `IOKitBSDInit` 后调用；它只负责
未成功 start 路径（`NativeLegacyDisplay.cpp:473–476` 在失败返回前不会启动该 timer）。
成功分支保留两个初始引用，不存在对应的显式板级 stop 调用。因此没找到覆盖所有
成功启动后 teardown 的无 provider gate 调用点；不新增回调或改变锁序。

**sender 寿命。** `5c1b948` 借用链首，`5c1b96c/980` 把节点内 `+0x18` 的 reference
和栈上六个 scalar 交给 `5bfe258 → 5c26e54 → [6deaf38] → 77b19a8`
（`IOUserClient::sendAsyncResult64WithOptions`），选项是 1。8796 对照源
`IOUserClient.cpp:2168–2254` 将引用和标量复制进同步 Mach 消息，使用 `COPY_SEND`，
`CanDrop` 分支用零超时发送；错误还可写回 reference[0]。返回后 donor 在
`5c1b9b4` 从**同一借用节点**读 next；这段没有节点或 owner retain，也没有中途重验
active。只能确认此发送路径不是异步保留节点指针；缺全部调用域、摘链/端口寿命以及
重入或让 gate 时借用仍有效的证据。零超时不等价于对这些生命周期的证明。

`scripts/test-nuwa-display-teardown.py` 的确定性双 gate 与引用账本分别建模 driver、
链表、排队／在途、保存 loop、同步 action 与 sender 的 owner 租约。覆盖排队撤销、
脱队但等待 gate、已在发送、同线程 stop 重入、sender 让 gate、摘链失败后重试、
反向锁序、重复 stop、最后 client 摘链、错误 source 和 start 失败回滚。
sender 租约及逐次发送检查是模型要求，不是 donor 已实现的行为；无真实 IOKit 调度。

**复跑**（WSL root，在设备仓，沿用 §10 的 `PY`／`BASE`／`CPO`；`GEN`、`HOST` 必须不存在）：

```sh
set -e
GEN=out/nuwa-display-refresh-donor-verifier
HOST=out/nuwa-display-host-refresh-verifier
$PY -B scripts/derive-nuwa-display-abi.py --base "$BASE" \
  --kernelcache "$BASE/out/ipsw/20H392/kernelcache.decompressed" --out "$GEN"
for f in OriginalLegacyFramebufferABI.h original-bindings.S nuwa-display-abi.json; do
  cmp "$GEN/$f" "package/$f"
done
$PY -B scripts/verify-nuwa-display-host-abi.py --base "$BASE" --cpo "$CPO" --out "$HOST"
$PY -B - "$HOST" <<'PY'
import json, subprocess, sys
from pathlib import Path
host = Path(sys.argv[1]).resolve()
r = json.loads((host / 'compile.json').read_text())
a = r['arguments'][:]
a[a.index(str(host / 'NativeLegacyDisplay.cpp'))] = str(Path('scripts/host/NuwaDisplayRefresh.cpp').resolve())
a[a.index('-o') + 1] = str(host / 'NuwaDisplayRefresh.o')
subprocess.run(a, cwd=r['directory'], check=True)
a = r['arguments'][:]
a[a.index('-DNATIVE_LEGACY_CANCEL_SWAPS=0')] = '-DNATIVE_LEGACY_CANCEL_SWAPS=1'
o = host / 'cancel-rejection.o'
a[a.index('-o') + 1] = str(o)
p = subprocess.run(a, cwd=r['directory'], text=True, stderr=subprocess.PIPE)
first = next(line for line in p.stderr.splitlines() if 'error:' in line)
print(first)
assert p.returncode == 1 and not o.exists() and '770:36: error:' in first
PY
llvm-nm --format=posix "$HOST/NuwaDisplayRefresh.o"
c++ -std=c++17 -Wall -Wextra -Werror scripts/host/test-nuwa-display-refresh.cpp -o "$HOST/refresh-fixture"
"$HOST/refresh-fixture"
$PY -B scripts/test-nuwa-display-teardown.py
```

真实 CPO 的完整 8796 显示 TU、板级 TU 和独立 formatter 均编译成功；donor 三文件逐字节
一致，归档六槽及 381 项未解析指纹不变，两项 timing glue 仍未解析。取消负例的首错仍是
`NativeLegacyDisplay.cpp:770:36`：20H392 没有匹配的 `cancelSwapsAfterTimeout` 虚函数。
本次独立 formatter 对象 SHA256 `6676fe31a3897d8e55160a10842c40e131540a54e3e6493c512d18f959cfa771`，
归档 SHA256 `43ed9c5de0cfe1fb141d9e0649e8b03f6c213287e2df85ac11b7413e40f5a89c`；
含调试路径，新输出目录不要求对象同哈希。夹具通过，未独立复跑；
无实际发布、运行路径、最终链接、Libm／guard 改动或设备操作。
## 15A. nuwa 的 QuartzCore timer 选择证据（self-checked）

**判定：undetermined。** 尚缺 compositor 进程中 MobileGestalt
`MGGetSInt64Answer("ChipID", 0)` 的返回值、其 `CA_FORCE_TIMER`、
`CA_BENCHMARK` / `LK_BENCHMARK` 环境值；不能把启动 ADT 的种子当成查询值，
也不能把条件路径存在当成已选择或 selector 5 已执行。

* 已写入 r34 的输入记录为 `out/nuwa-ufs-apfs-root-chmh-20261119-r34/record.json`；
  本地同轮 `derived.adt` SHA256
  `dd1734b3dcddef1b7b49b64cea2adf4c68bcd7e09da9d860fef77682879c326a`，
  解析 `/chosen/chip-id` 得四字节 `db b8 ca 4a`，小端 `0x4acab8db`。
  `board.toml:159–163` 明确这是软件身份种子；`scripts/make-nuwa-adt.py:244–245`
  将其写到 chosen。它不是 donor profile 的 `0x8015`，也不是用户态查询的实测返回。
  记录中的 kernel args 没有这些 CA/LK 名称，但 kernel args 不等于进程环境；
  r34 的设备运行与载荷身份沿用已有主控转述，未作设备回读。
* 同版 SystemOS cache `.03` 映射基址 `0x186d8c000`，`0x18836d0ec–100`
  读取 `CA_FORCE_TIMER` 并调用 `atoi`；非零跳到 `0x18836d11c` 设置 1。
  否则 `0x18836d104–110` 以 `ChipID`、默认参数 0 调查询入口
  `0x18dbcc7a8`；跳板指向 `0x19c5570c8`，`.42.dyldlinkedit`
  的 nlist 值与字符串表标识该入口为 `_MGGetSInt64Answer`。
  该函数 `0x19c5570d8–10c` 在查询失败时返回调用者提供的默认值 0；
  本批未闭合 MobileGestalt 的 `ChipID` 后端 provider 到 ADT 或其他来源，
  也没有证明查询失败，因此不能断言返回 0 或 `0x4acab8db`。
* 非覆盖查询结果仅当等于 §16 列出的八个值时产生 1；其他值（包括默认 0
  和假设返回的 `0x4acab8db`）产生 0。构造函数 `0x1883da1c0–1d4`
  将此结果放进 server `+0x30d` bit 1。`0x1882d9f10–28` 先检查该位，
  位清才再检查 benchmark；`0x1882cf1a4–1c8` 依序读取 `CA_BENCHMARK`
  与 `LK_BENCHMARK` 并解析数值。只有位清且 benchmark 检查为零才进入
  §16 的用户 Mach timer 候选路径；位设置或 benchmark 非零都不能据此称选中该路径。
  缺实际进程环境，不能据 kernel args 推出这些环境变量缺省。
* 即便选择 timer，§16 的 callback→render→`SwapEnd`→selector 5 是静态可达链，
  不证明进程已启动、实际提交或返回成功。此次只读 SystemOS 与输入记录，
  没有运行候选、构建或操作设备；未独立 verifier。

## 16. 方案 A：保留软件 vsync 与无软件 vsync 首帧（self-checked）

设备基线 `790e4669fe7a20b3d5610a3cec5e9275c9bf3f39`，基座只读 `693f5d9c`。
一次上游检查：UniXNU HEAD `8542980d02b4d2cc5c32ee3542de1760b2562aac`；
`UniXNU/GopFramebuffer@b0d812d578efa2acb005b66f73168891719af09a`（BSD-2-Clause-Patent）
的 `NativeLegacyDisplay.cpp` 仍是 `startVsync` 创建 workloop timer、`stopVsync` 从
`stop/free` 直接 cancel/remove/release、tick 调原 sender；上游允许零或不传 `vsync`
来不分配软件 timer，但没有可直接复用的 teardown 契约。设备继续钉 `e47c1b8`，不迁移参数名。
另查本机正式 8796 feed `1b191cb58250d0705d8a51287127505aa4bc0789`（§14 的实际构建输入）。
不引入第三方实现。

### A1：保留软件 vsync — 首阻断是清理入口的锁序

`NativeLegacyDisplay.cpp:456 → stopVsync:438–442` 不能直接包一次显示 `runAction`：
8796 `IOService.cpp:2914–2924` 能由 `didTerminate` 独立排 `scheduleStop`（`:2863–2865`）；
phase 3 的 `:3302–3324` 只在 **client inactive** 的分支等待 `finalize`，
其它已排队、仍连接的 client 可直接走 provider `_workLoopAction` (`:2476–2482`) →
`actionStop:3106`。因此不能把 `finalize:3387` 或 `terminateWorker:3274–3275` 的
victim loop 当成所有 stop 的前置清理点；也不能把 `removeEventSource` 当成无取锁的操作。
板级 `package/NuwaLegacyDisplay.cpp:121–145` 的 provider 和 donor `self+5048` 的
显示 loop 没有同一性保证。这是**不能证明新 provider→display 边成立**，不是实测死锁。
`thread_call_cancel_wait` 也不能放进 provider/display gate 内等待一个需要该 gate 的工作；
仅排异步清理又不能证明它先于 Legacy stop 拆队列／拆 loop。

sender 也不能因 `CanDrop` 就视为安全：§15 的 `5c1b948 → 5c1b980 → 5c1b9b4`
在 send 后仍解引用同一借用节点。8796 的 `IOUserClient.cpp:2244` →
`ipc_mig.c:121–127,139–164` → `ipc_kmsg.c:2964–2977,3020–3021` 表明，
普通用户端口走队列，队列满且零超时在 `ipc_mqueue.c:425–427` 返回；
对内核空间目的端口则**可同步调用** `ipc_kobject_server`。这不表示正常 compositor
使用内核端口；它排除了用零超时为任意目的端口证明不重入。消息复制/`COPY_SEND`
也不保活原链节点，不等价于在回到 `5c1b9b4` 前禁止摘链。

**下一可测判据：** 在实际 8796 IOKit 路径标记两把 gate 的身份与持有者，
分别触发 programmatic finalize、provider phase-3 stop，并让 tick 已入 gate。
先证可清理于 provider gate 外、且在父类拆队列/loop 之前（或证无反向边及全路径同一性）；
然后对实际 type-5 注册/发送/摘链核对端口来源以及节点从 `5c1b948` 到
`5c1b9b4` 的寿命。在 sender 返回、最后一个 client 摘链和 stop 的交错中，清理后
不能有 send/rearm，过期 callout 可退场。未证该入口前不把 sender 接到真实 TU。

### A2：无软件 vsync 的 CPU 首帧 — 同版存在提交路径，首阻断仍是请求生命周期

复查 §14 的只读 SystemOS cache；用户 VA 不加内核前缀。QuartzCore 的默认路径不是
“等内核 VBL，否则不能 submit”，选择项也**不是** GOP timer 是否启用：

1. `0x1883da1b0–d4/0x1883da908` 的构造路径把 `CADeviceUseVBL` 结果置入
   server `+0x30d` bit 1。`0x18836d0e4–164` 查询 `ChipID`；无有效环境覆盖时，
   只对 `0x7000,0x7001,0x8000,0x8003,0x8001,0x8002,0x8004,0x8010` 置位，
   不含 donor `0x8015`。这不是实际 nuwa 用户态读到的 `ChipID` 证据。虽有
   `CA_FORCE_TIMER` 字面量，`getenv → atoi` 非零在该构建反而跳到置位分支；
   不把它作为强制 timer 的旋钮，也不改用户态。
2. bit 1 清时，`IOMFBServer::add_vsync_source` 的 `0x1882d9f10–90` 在非 benchmark
   路线上创建 `CADisplayTimer`；`0x18837bd24–64` 启用 timing reference 后挂 runloop，
   不是 `0x18837bd6c–7c` 的 IOMFB VSync 通知注册。该用户 timer 的
   `0x18832fb5c → _mk_timer_create` 建 Mach timer，`0x18832fb80–98` 建 CF source；
   `0x1882badf0` 执行 timer 的 callback。timing reference 取不到时
   `0x1882bc450–458` 返回零参考，不是 return-without-render 的等候条件。
3. 正常计时分支 `timer_callback:0x188350c60` 直接调用本地 `vsync_callback`
   （此处是函数名，不是等收到内核消息），后者 `0x1882ba434` 调
   `Server::render_for_time`。该函数在 `0x1884f6030–44` 调 display `vptr+0x180`；
   `AppleCLCDDisplay` vtable 项 `0x1d5b38918` 对应
   `IOMFBDisplay::finish_update`，在 `0x1882d3008` 调 `SwapEnd`。跳板
   `0x18dbcc3f4 → 0x1af223fa8` 经连接分派；普通 kernel backend
   `_kern_SwapEnd:0x1af223544–55c` 用 `IOConnectCallStructMethod` 提交 selector **5**、
   输入 **0x46c** B；donor dispatch 行 `6decbd0 → 5bff998` 的结构尺寸也为 `0x46c`。
   两端是同版真实提交链，不等于证明 nuwa 已选这条分支或提交成功。

首帧候选只复用基座“零速率不建软件 timer”的边界；预期代价是不提供 GOP 合成的
VBL 通知，不宣称连续呈现或物理刷新率。这可从**新增软件 timer 链**移除
provider→display 清理取锁与借用 sender，不会移除 donor 自身的通知/状态路径。
**首阻断：** `package/OriginalLegacyFramebufferABI.h:236` 的 slot 329 仍是纯虚，
host TU 的 `opaque329` 是 guard；donor `5c10e40/5c10f7c` 的状态分支和
`5c11980` 的 timeout 路径读它，均不测试 nuwa 软件 timer 是否存在；
`5c11a74/af0` 的 slot 330 处理请求时也不会为 CPU-only 免除请求所有权。
不能用“禁 vsync”或“禁 host cancel override”移除 guard / 推定 `validated`、
`transferred` 与 donor current/pending 已对账。

**下一可测判据：** 先在同版调用链判明 329 的真实状态输入/转移，及 330 对
CPU copy 已结束但未退休请求的释放和 completion 顺序，要求成功和 timeout 都
使子类及 donor 对同一请求只完成/释放一次。另独立核对 Libm 后，若获准构建并在
真实 20H392 环境验证，须同时捕获：QuartzCore 选择 timer 分支、无 nuwa 软件 timer
或 type-5 tick、首个正常 selector 5 返回成功、同一 swap ID 恰一次退休并在 GOP
出现该帧。仅有 60 Hz fallback 或 `present_surface` 的独立接口不计合格。

### 独立 Libm 门禁及复核输入

donor `__PRELINK_INFO` 直接给出 `IOMobileGraphicsFamily → IOAVFamily → Libm`，
与是否启用软件 timer 无关。对 §1 的未修改 kernelcache，使用
`XnuPrelink@f1d80d37528a33e24643583787123c652b70a268` 原样
`instruction_inventory(data, parent, {"com.apple.kec.Libm": module})`，
其中 `parent = macho(data)["segments"]`，`module = macho(data, backed_offset(parent,
entry["_PrelinkExecutableLoadAddr"], 32, len(data)))`。**首错** `emit_prelink.py:111`：
`External PC-relative encoding at 0xfffffff005b8c07c; no instruction rewrite supported`。
该处的四字节 `55 73 cc 37` 被解成出段分支；不是对数据区分类的充分证据。
`scripts/audit-target-libm-inline-data.py` 是基座已有的鉴证方法，但钉另一 donor；
不能移植它的池偏移或 hash。后续只接受 20H392 本身的完整范围/指纹、真实 literal
指向、边界和反例在原扫描下复算；本轮不改 scanner、profiles 或 security gates。

复核：按 §14 只读挂载同一 SystemOS，主 cache SHA256 `76874e8375252ee643011ff8063f0cce12355f05cf5f9897a34e5679667a65aa`；
QuartzCore `.03`、IOMobileFramebuffer `.13`、vtable `.27.dylddata` 及符号
`.42.dyldlinkedit/.symbols` 用 cache mappings、`LC_ID_DYLIB`、符号表和 ARM64
指令逐项对照上述 VA。8796 核对上述 `IOService`/IPC 行号，Libm 用上段原函数复跑，
预期同一拒绝。没有新增 DUT/模型用例、未改真实 TU 或构建/链接输入；没有运行
新编译、上机或独立 verifier。显示仍 `planned`；优先取证 A2，不宣称首帧已运行。

## 17. Legacy 静态 `gMetaClass`：20H392 主机链接

方法复用：`UniXNU/UniXNU-sheng@c8f92b208068eeaa4cd2b0f592671f04ee70076e`
（BSD-2-Clause-Patent，见该提交 `LICENSE`），
`scripts/build-gop-legacy-display-27.py` 的 data import「donor VA + collection slide，
`.globl` / `.set`」及 `scripts/check-legacy27-binds.py` 的构造函数 `x2` GOT
读回。未移植 sheng 的地址、arm64e 签名、函数 thunks 或任何板值。

- **初始化表 → x0。** 锁定 §1 的 20H392 kernelcache。`IOMobileGraphicsFamily`
  `__DATA_CONST,__mod_init_func` 起始 `0xfffffff006deb4d8`，10 项；
  第 10 项 `0xfffffff006deb520` 指向 `0xfffffff005c25b94`，其 `+8` 的 BL
  调 `0xfffffff005c0bb40`。`0xfffffff005c0bb48/4c` 的 `ADRP x0` / `ADD x0`
  得 `0xfffffff007a45540`；`0xfffffff005c0bb50` 调
  `0xfffffff005c0bb5c`，wrapper 保存并恢复同一 `x0`，在
  `0xfffffff005c0bb74` 调锚点 `0xfffffff005c0bc6c`。锚点给 base ctor
  传 `x1="IOMobileFramebufferLegacy"`（`0xfffffff004f6564a`）和 `w3=0x1660`，
  随后在 `0xfffffff005c0bcb4` 给对象首字写入 metaclass vptr。
- **独立 getter。** 原类 vptr `0xfffffff006def8e0` 的 slot 7
  （`0xfffffff006def918`）指向 `0xfffffff005c0bc54`；函数在 `+8/+12`
  用另一组 `ADRP/ADD` 返回 `0xfffffff007a45540`，没有经过上述 init/caller。
  目标为原 family 可写 `__DATA,__common` 中的静态对象，首 qword 初始为零，
  相对 `__DATA` 起点偏移 `0x7280`，并非 `__TEXT_EXEC,__text` 的构造函数。
- **放置合同。** `XnuPrelink@f1d80d37528a33e24643583787123c652b70a268`
  对选中的 family 保持其 coalesced 段内偏移；`-0x1000000` 时其
  `__DATA` 变为 `[0xfffffff006a3e2c0, 0xfffffff006a5d588)`，
  位于 RW `__PRELINK_DATA` `[0xfffffff006a08000, 0xfffffff006bbc000)`；
  对象是 `0xfffffff006a45540`，构造入口则是 RX `0xfffffff004c0bc6c`。
  同一页对齐 slide 保留 family 内 `ADRP/ADD` 相对位移。donor
  `_PrelinkLinkKASLROffsets` 包含 init 表项和 getter 槽，不包含对象的初始零字。
  原生端为唯一 `N_ABS` 导入绑定，不分配对象内存，也不把 native GOT 交给 donor
  指针表修补。若真实 emit 成功，构建器再核查 family 数据段及 getter 槽、以及原生
  GOT 是否仍指向同一个静态对象；这里是合同，不是本轮已有最终 kernel 的证据。

**自检（WSL root，基线 `6372657` + 本节变更）。** 实际 8796 CPO 编译的对象
在 `__text+0x44/0x260/0x4fc0` 有三组 `GOT_LOAD_PAGE21/PAGEOFF12`，
全为 `ADRP/LDR x2`；另有一个 `__const` 的 8 字节 `superClass` 指针重定位。
独立同工具链的最小静态链接探针（不是驱动链接替代）使用真实生成的
`original-bindings.o`，在 GOT `0xfffffff007008000` 和 `superClass` 均读到
`0xfffffff006a45540`。将 GOT 改回未 slide 的对象地址会被拒绝；将 donor init 表项
或 getter 槽单独替换为构造入口也各自被拒绝。探针和 `check.py` 仅留在本地
`out/nuwa-display-native-metaclass-04/`。生成头文件与旧版逐字节一致。

```sh
obj=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837
python=/home/wh1stl3/.local/bin/python3.11
"$python" -B scripts/build-nuwa-display-native.py --base ../../UniXNU \
  --cpo "$obj/iokit/DEVELOPMENT/IOPMGR.cpo.json" \
  --link-dir "$obj/mach.development.bcm2837.link" \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --out out/nuwa-display-native-metaclass-04
```

复跑须换新 `--out`。实际 `-new_linker -static` native 重链退出 1，首错为
`__ZN25IOMobileFramebufferLegacy13setPropertiesEP8OSObject` 未定义，由
`NativeLegacyDisplay.manual.o` 的 `__ZTV19NativeLegacyDisplay` 引用。
archive SHA256 `41f0c34dbd6ebab7be24e6b39beca5992da3372ee18a490daf78c7fe1ce398c7`；
380 个未解导入相对上轮仅少 `gMetaClass`，引用归属和弱引用位均不变。
剩余 **159 个原类 imports**：

- `setProperties(OSObject*)`、`systemWillShutdown(unsigned)`、`init(OSDictionary*)`、
  `probe(IOService*, int*)`、`getWorkLoop() const`、基类 `C2(OSMetaClass const*)` 和 `D2()`。
- 152 个 `opaque<N>()`：168–183、185–187、189–210、213–241、244–245、247–273、
  275、277–280、283–286、288–291、294–320、323–328、330–335、337。

真实 native 产物及 strict emit 未到达，不以 §16 的独立 Libm 拒绝当成本轮首错。
既有函数/vtable 绑定的最终落位不在这一项数据导入的资格声明内。未造剩余定义、
未改扫描/329/330 门禁、未启用 runtime 或触碰设备；尚无独立 verifier。

## 18. 方案 A：固定 20H392 原类 import 集合（self-checked）

基线 `a304d2d9b5d36a298c546d4f2ca180e6e681719e`；基座 `693f5d9c`、驱动 `e47c1b8`、
donor 同 §1。复用 `UniXNU/UniXNU-sheng@c8f92b208068eeaa4cd2b0f592671f04ee70076e`
（BSD-2-Clause-Patent）`build-gop-legacy-display-27.py` 的精确 import 集合、独立
绝对目标对象与本地跳板，以及 `check-legacy27-binds.py` 的链接后逐槽追踪。
nuwa 为非 arm64e，只有一条 `B` 的跳板，不移植 sheng 的地址、BTI 或签名合同。

| 具名 import | 20H392 目标（省略 `0xfffffff000000000`） | 独立证据 |
| --- | --- | --- |
| `init(OSDictionary*)` | 槽 21 / `5c0c404` | `__ZTV9IOService` 第 21 槽按符号表解析为 `IOService::init(OSDictionary*)`；`5c0c454–46c` 转发 x1 调用父槽并掩取布尔返回。 |
| `setProperties(OSObject*)` | 槽 44 / `5c17abc` | `IOService[44]` 独立解析为 `IORegistryEntry::setProperties(OSObject*)`；`5c17b00–10 → 5c26efc` 以 x1 入参作 `safeMetaCast`，GOT 符号为 `OSDictionary::metaClass` 与 `OSMetaClassBase::safeMetaCast`；转换失败字符串 `4f668c1`，返回状态 `5c17e1c`。 |
| `systemWillShutdown(unsigned)` | 槽 79 / `5c108a8` | `IOService[79]` 符号同名；`5c1090c–14` 经父槽转发 `w1`。 |
| `probe(IOService*, int*)` | 槽 85 / `5c0c644` | `IOService[85]` 符号同名；`5c0c670–84` 经父槽转发 x1/x2、返回 x0。 |
| `getWorkLoop() const` | 槽 111 / `5c122bc` | `IOService[111]` 符号同名；完整 getter 返回 `self+5048` 指针。 |
| `C2(OSMetaClass const*)` | `5c0bbbc` | H10P `5cce4e4/e8 → 5ce16c8 → [6dfb668]` 先传 metaclass、调用后装 H10P vptr；Legacy `5c0bbe8–bf8` 传同参数给父构造再装 Legacy vptr。 |
| `D2()` | `5c0bc08` | H10P teardown `5cce3bc–cc → 5ce16d4 → [6dfb670]` 恢复实参并尾调；目标只调用父析构、不释放存储，不是槽 0/1 的 trap。 |

实编 TU 的 164 个原类 imports：新增 159（7 具名 + 152 opaque）及原有 5
（3 具名入口、vtable、gMetaClass）。以前声明的另 4 个有名原入口在该 TU
没有 import，不再额外导出；声明及对应槽不移除。opaque 精确集合沿用 §17；
每个函数目标都在家族 `__TEXT_EXEC,__text`，由 `__PLK_TEXT_EXEC` RX 文件区承载；
虚函数在 donor 原表按同槽取目标，并有 `_PrelinkLinkKASLROffsets` 站点。原 vtable
位于家族 `__DATA_CONST,__const` / `__PLK_DATA_CONST`（RO）；gMetaClass 仍在
§17 RW 段。`-0x1000000` 只加一次；未改 `XnuPrelink`。未改的 `plan` 对照验证
162 个可执行目标处在选中家族范围，160 个原槽修正均精确等于 `donor VA + slide`。

实际归档中每个 opaque 只有同号 `__ZTV19NativeLegacyDisplay` 的一条零 addend
外部 8 B 指针重定位，没有代码重定位或其它引用；C++ 声明标为 `unavailable`，
直接写 `p->opaque330()` 的真实 CPO 负例被编译器拒绝。没有按占位签名调用，
没有绑定纯虚或重复目标；329 仍是 native guard，330 仍是 donor 槽，未证明其超时合同。
独立小链接仅投影真实归档的 160 条原类槽重定位，使用相同 ld 和真实 veneer /
N_ABS 对象，无完整 TU、内核或 donor 代码。其全部 160 个实际链接槽逐一指到各自
跳板，再跳 `donor VA + slide`；全部 162 个跳板均解码检查。投影中 330 为
`0xfffffff00722f50c → 0xfffffff004c0fbe8`；这不是完整 native 槽审计。
错误 donor、单字节篡改、纯虚目标、并槽、数据段作代码、移位的 opaque 重定位、
投影槽错指相邻跳板、跳板未 slide 各被拒绝。局部投影及篡改检查命令：
`$python -B out/nuwa-display-native-imports-01/check.py`（需本轮 `out/`，不提交夹具产物）。

**真实重跑：** §17 同一命令，仅把 `--out` 换成
`out/nuwa-display-native-imports-01`（独立复跑须用新目录）。真实 8796 CPO 生成四成员
归档 665144 B，SHA256 `c8623a89cc1a213ddc4b0caa0abb3356bf92d29ff0ba5d6b882cc1263f1d9d8f`；
未解析清单 SHA256 `62e4fc66cb6d0acf4f9e9bddcba145911e13572871cb0847e0f15defd6fe5c8f`，
从 380 到 221，仅移除这 159 项（原类剩 0，其他项与 owner/weak 位不变）。
局部投影 SHA256 `5d251af55e603f470357b524a7c70c7c167f33b2e125e26081defa735afaec40`。

真实 `-new_linker -static` 链接退出 1，首错为
`package/NuwaLegacyDisplay.cpp:197` (`_native_legacy_prepare_scanout`) 所引用的
`_boot_progress_prepare_scanout` 在该链接输入中无定义。链接器共报 12 个未定义项；
其余为 `_mach_vm_allocate`、`_mach_vm_remap`、`_vm_map_create`、
`_native_adreno_fences`、`_native_adreno_fences_detail`、`_native_gpu_trace_enabled`、
`_native_gpu_trace_record`、`_native_legacy_set_refresh_properties`、
`_native_legacy_vsync_notify`、`_native_ufs_dpu_map`、`_native_ufs_dpu_state`。
无完整 native、无其最终槽哈希或其 strict emit 结果。
另用同一 `--link-dir` 的同级未改 `mach.development.bcm2837.unstripped`（SHA256
`4a5bf5cc4f6920409b09fdf11eea21389b52b490e247515ab07ffdd38a7f8aa2`）作控制：
调用原样 `emit_prelink.emit(native, donor, roots, -0x1000000)`，`roots` 为
`board.toml` 的 `os_overrides.ios-16.7.16-20H392.kernel.prelink.roots` 加 `IOMobileGraphicsFamily`
去重（29 项）。该控制的首错是 `emit_prelink.py:111`，Libm `0xfffffff005b8c1cc` 的
`48 5f 9d f0` 被解码成覆盖范围外的 PC 相对编码；未发射。不同于 §16 的仅 Libm
inventory 控制；不放宽扫描、不改变 329/330 门禁、无上机候选、无设备操作，
未独立复跑。
