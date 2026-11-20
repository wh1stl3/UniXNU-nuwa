# 20H392 显示 ABI 取证（G1 收尾，2026-11-20）

状态：**self-checked（主机侧、未独立复核）**。输入是本机 20H392 donor kernelcache，无设备操作、无内核构建。
最新时序取证见 §13；最近一次 host-only 归档复跑见 §12。

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
