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
