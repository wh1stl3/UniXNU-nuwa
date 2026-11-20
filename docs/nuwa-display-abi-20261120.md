# 20H392 显示 ABI 取证（G1 收尾，2026-11-20）

状态：**self-checked（主机侧、未独立复核）**。输入是本机 20H392 donor kernelcache，无设备操作、无内核构建。

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
