# v20 复核请求：panic 格式串与 `wfe_timeout_configure` 算术对不上

日期：2026-10-25
包：镜像 `d329e7c4` / 内核 `1f517836` / ADT `7ebce5a6`（`reports/xnu-first-entry/entry-probe-13.json`）
试验记录：`reports/xnu-entry-probe-trial/2026-10-25-12/trial.json`
构建与软件证据：`reports/kernel-entry-probe/2026-10-25-v20/`

请只回答第 3 节的问题；第 1、2 节是已核对过的事实，供你复核，不必重推。

---

## 1. 已核对的事实（全部来自出货内核二进制，不是源码推测）

### 1.1 读数与行位的对应

行位由**三个互相独立的锚点**唯一确定（读数由用户在实机录像/照片上读出，机器解码不可靠）：

| 读数行 | 屏幕行 | 探针读的东西 | 读到的值 |
| --- | --- | --- | --- |
| 4 | 1376 | `_DTRootNode` | `0xfffffff008491000` |
| 5 | 1408 | `_gPESoCBasePhys`（在 `pe_arm_get_soc_base_phys` 入口读） | `0` |
| 6 | 1440 | `PE_state + 0x90` | `0` |
| 7 | 1472 | `PE_state + 0xa0` | `0xfffffff00715c7c0` |
| 8 | 1504 | `gPEClockFrequencyInfo + 0x48`（= `timebase_frequency_hz`） | `0x000000000124f800` |
| 9 | 1536 | `arm64_eventi` | `0x00000000ffffffff` |

锚点：
- `0xfffffff008491000` = 按加载器公式逐位算出的随包 ADT 内核 VA：
  `Kernel.Base=0xfffffff003dc8000`，`Kernel.End=0xfffffff00848f000`，
  `TreeAddress-Address = ALIGN(Kernel.End-Kernel.Base, 16K) = 0x46c8000`，
  `Args->DeviceTree = Kernel.Base + 0x46c8000 + 0x1000 = 0xfffffff008491000`。
- `0xfffffff00715c7c0` 精确命中内核符号 `_const_boot_args`。
- `0x124f800` = 19200000 = 随包 ADT 里 `timebase-frequency` 的值。

### 1.2 `wfe_timeout_configure` 的真实指令序列（出货内核 0xfffffff0073cae08）

```
0x3cae08  b    <probe hook>              ; 探针把这条替换成 branch
0x3cae0c  stp  x20,x19,[sp,#32]
...
0x3cae1c  adrp x0, "wfe_events_sec"
0x3cae24  add  x1, sp, #24
0x3cae28  mov  w2, #8
0x3cae2c  bl   PE_parse_boot_argn
0x3cae30  cbz  w0, 0x3cae5c
0x3cae34  ldr  x8, [sp, #24]
0x3cae38  cbz  x8, 0x3cae68
0x3cae3c  mov  w9, #16960
0x3cae40  movk w9, #15, lsl #16        ; w9 = 0xF4240 = 1000000 = USEC_PER_SEC
0x3cae44  cmp  x8, x9
0x3cae48  b.ls 0x3cae70
0x3cae4c  str  x9, [sp, #24]           ; 钳到 1000000
0x3cae50  mov  w8, #16960
0x3cae54  movk w8, #15, lsl #16        ; w8 = 1000000
0x3cae58  b    0x3cae70
0x3cae5c  mov  w8, #16960              ; 没找到 boot arg
0x3cae60  movk w8, #15, lsl #16        ; w8 = 1000000
0x3cae64  b    0x3cae6c
0x3cae68  mov  w8, #1                  ; 解析出 0
0x3cae6c  str  x8, [sp, #24]
0x3cae70  adrp x9, 0xfffffff007ac0000
0x3cae78  ldr  x9, [x9, #1296]         ; x9 = gPEClockFrequencyInfo.timebase_frequency_hz
                                      ;   0xfffffff007ac0510 = _gPEClockFrequencyInfo+0x48
0x3cae7c  udiv x19, x9, x8             ; ticks_per_event = timebase / events_per_sec
0x3cae80  mov  x0, x19
0x3cae84  bl   flsll
0x3cae88  subs w8, w0, #1              ; bit_index = flsll(ticks) - 1
0x3cae8c  b.vs <ubsan>
0x3cae90  mov  w9, #1
0x3cae94  lsl  w9, w9, w8              ; AArch64 寄存器移位量取低 5 位
0x3cae98  subs w9, w9, #1
0x3cae9c  b.vs <ubsan>
0x3caea0  sxtw x9, w9
0x3caea4  tst  x19, x9
0x3caea8  cinc w8, w8, ne
0x3caeac  subs w8, w8, #1
0x3caeb0  csel w8, wzr, w8, lo         ; 有符号为负 -> 0
0x3caeb4  adrp x9, 0xfffffff00716e000
0x3caeb8  str  w8, [x9, #1528]         ; arm64_eventi = w8
```

`flsll` 实现（`osfmk/arm64/loose_ends.c:699`）：`mask == 0 ? 0 : 64 - __builtin_clzll(mask)`。

### 1.3 `wfe_timeout_init` 的判据（出货内核 0xfffffff0073cadb0）

```
0x3cadb0  b    <probe hook>            ; 探针替换
0x3cadb4  ldr  w8, [x8, #1528]         ; arm64_eventi (0xfffffff00716e5f8 + 0x5f8)
0x3cadb8  cmp  w8, #64
0x3cadbc  b.hs 0x3cadd4               ; -> panic
0x3cadd4  sub  sp, sp, #48
0x3cade0  mov  w9, #2219               ; 源码行号 machine_routines.c:2219
0x3cade4  adrp x10, ...                ; __FUNCTION__
0x3cadec  adrp x11, ...                ; 格式串
0x3caf4   stp  x10, x9, [sp, #16]
0x3caf8   stp  x11, x8, [sp]           ; 构造 va_list
0x3cafc   adrp x0, ...
0x3cb004  bl   panic
```

### 1.4 调用顺序与唯一性

`arm_init` 内（出货内核 0xfffffff007972df0 起）：

```
0x972df8  bl PE_init_platform
0x972dfc  bl configure_timer_apple_regs
0x972e00  bl wfe_timeout_configure
0x972e04  bl wfe_timeout_init
```

- 全镜像 `bl <_wfe_timeout_configure>` **只有一处**（0xfffffff007972e00）。
- `arm64_eventi`（0xfffffff00716e5f8）**只有一处写**（0xfffffff0073caeb8）。
- `PE_init_platform` 内 `pe_identify_machine` 会被调用：`PE_init_platform(boolean_t vm_initialized, void *args)` 的 `vm_initialized` 是**形参**（`arm_init` 传 `FALSE`），`if (!vm_initialized)` 恒真（`pexpert/arm/pe_init.c:419`）。所以 `SecureDTInit(PE_state.deviceTreeHead, PE_state.deviceTreeSize)` 与 `pe_identify_machine(boot_args_ptr)` 都会执行。

### 1.5 随包 ADT 的内容

`scripts/audit-adt-xnu-find-entry.py`（逐字节复刻 `find_entry` 的全局游标语义）确认：`arm-io` 命中、`ranges[1] = 0x17000000`、cpu0 `state="running"`、`timebase-frequency = 19200000`。
**注**：该树没有 `nProperties == 0` 的终止节点，游标会正好走到 blob 末尾（0x3340）—— 这一点待你确认是否影响 `find_entry` 命中 `arm-io` 之前的路径。

---

## 2. 由 1 推出的矛盾

按 1.2 的指令逐条推：

- **时基 = 19200000**（读数行 8 直接测得，且 `wfe_timeout_configure` 读的地址 `0xfffffff007ac0510` 与探针读的 `_gPEClockFrequencyInfo+0x48` **是同一个地址**）：
  `ticks_per_event = 19200000 / events_per_sec`，`events_per_sec ∈ {1, 解析值(≤1000000), 1000000}`
  → `ticks ∈ [19, 19200000]` → `flsll ∈ [5,25]` → `arm64_eventi ∈ [38,59]`，**永远 < 64**。
- **时基 = 0**（我上一轮的主线假设）：
  `ticks = 0` → `flsll(0) = 0` → `subs w8,w0,#1` → `w8 = 0xffffffff`
  → `lsl w9,w9,w8` 取低 5 位 = 31 → `w9 = 0x80000000` → `subs` → `0x7fffffff`
  → `sxtw` → `tst x19,x9`（x19=0）→ 0 → `cinc` 不触发 → `subs w8,w8,#1` → `0xfffffffe`
  → `csel w8,wzr,w8,lo`（有符号负 → 0）→ **`arm64_eventi = 0`**，不是 0xffffffff，也 < 64。

⇒ **两种情况都不会 panic。** 但 v19 在实机上确实读到了格式串 `%s: invalid bit index (%u)`（`25733A20696E7661` / `6C69642062697420`，与该字符串前 16 字节逐字节吻合，且该字符串在出货内核 0x74d37 处存在、全树唯一出处是 `osfmk/arm64/machine_routines.c:2219`）。

⇒ **要么读数行 8/9 的行位对应不对，要么这条 panic 不是从 `wfe_timeout_init` 这条路来的，要么 `flsll`/`csel` 的语义我理解错了。**

---

## 3. 请回答的问题

**Q1（最要紧）**：在 `arm64_eventi` 只有一处写、且 `wfe_timeout_configure` 全镜像只有一个调用点的前提下，`_enable_timebase_event_stream` 里的 `panic("%s: invalid bit index (%u)")` 有没有可能被触发？如果不可能，那么**实机上这条 panic 到底来自哪里**？请给出你在出货内核里找到的、能产生该格式串的其它调用路径（注意 `osfmk/arm64/machine_routines.c:2219` 在**这个内核**里可能与 `tree-8796` 源码不同 —— 实机内核的符号表来自 `nuwa-8796-source` CI 构建，而 `tree-8796` 是另一份 checkout，请以**出货内核二进制**为准）。

**Q2**：读数行 8 = 19200000 这个值，是不是可能来自**另一个**同名/同偏移的全局？出货内核里 `0xfffffff007ac0510` 这个地址被谁写？请列出对该地址（以及它所在的 `gPEClockFrequencyInfo` 结构）的所有写者。

**Q3**：出货内核里 `PE_parse_boot_argn("wfe_events_sec", ...)` 在实机上会返回什么？`wfe_events_sec` 会不会由 `configure_timer_apple_regs()` 或别处注入？`boot_args.CommandLine` 在实机上是什么内容（实机 `boot_a` 是官方 stock 镜像，命令行应该为空）？

**Q4**：v20 探针的读数行从屏幕 1088 行起，与固件自己的 `DiagDraw` 文字（`DarwinBoot.c:359` 的 `Y = Video[4]/4 + Row*Line`，即 1440x3200 屏的第 800 行起）重叠。下一轮是否应该把读数行改到 800 行**以上**（例如 256-768 之间的空档），并给每一行加一个可自识别的常量前缀（例如行首画 4 个固定 nibble 区分行号）？请给一个具体的行位与标记方案。

**Q5**：`scripts/audit-adt-xnu-find-entry.py` 报告 `arm-io` 能命中，但同时报告**树里没有 `nProperties == 0` 的终止节点**。XNU 的 `find_entry` 用 `nodeP->nProperties == 0` 作为"节点列表结束"标志，而 `SecureDTLookupEntry`/`FindChild` 用 `skipTree`。请确认：在**没有**终止节点的情况下，`SecureDTFindEntry("name", "arm-io")` 走到 `arm-io` 之前会不会因为游标跑偏而漏掉 `arm-io`？特别是 `/cpus` 下的 8 个 cpu 节点在树里的位置（`arm-io` 在根的最后一个子节点）。

---

## 6. 附：本轮其他更正（不影响 Q1-Q5，但请一并知悉）

- 我上一轮怀疑 `/cpus/cpu0` 的 `state` 属性 size 含结尾 NUL 会导致 `strncmp(value,"running",size)` 不匹配 —— **不成立**，`strncmp` 遇 NUL 即停，size=8 与 size=7 同样返回 0。
- 我上一轮怀疑加载器 `DARWIN_BOOT_ARGS` 与 XNU `boot_args` 有 11 处偏移不匹配 —— **那是我的脚本漏了 C 自然对齐造成的假象**；加对齐后 `deviceTreeP`/`deviceTreeLength`/`machineType`/`Video` 全部一致，只剩 `bootFlags`/`memSizeActual` 因 CommandLine 长度 608 vs 1024 而不同。
- 模型夹具把 ADT 指针写进 `boot_args` 的 0x58/0x60，**真实偏移是 0x60/0x68** ⇒ D-036 里"补入 ADT 后 UBSan 消失"不能作为实机证据。已修正偏移。
- 探针自身两个缺陷（v19 起）：panic 变参的 KVA 判据要求页对齐（`__FUNCTION__` 是字符串字面量，不会页对齐）⇒ 1088/1248 必为空；`HEXROW_VAL` 内部用 x12 而钩子用 x12 保存变参指针 ⇒ 第二次 `ldr x23,[x12,#8]` 会读地址 0x8（足以让内核死在钩子里，该路径 v19 从未被实机验证）。两处已修，并有 `scripts/test-probe-read-sites.py`（17 项）覆盖。
- 解码表 'E' 的位图抄错（`11111000111110011111` 应为 `11111000111110001111`），会让一个 digit 解成 '?'。已修并加断言。

---

**Q6（探针布局，影响下一轮能否读到数）**：v20 的读数行放在屏幕 1088-1568 行，而固件自己的文字（UEFI console 输出，经 GOP 画到 framebuffer）从**屏幕第 800 行起**（`DarwinBoot.c:359` 的 `Y = Video[4]/4 + Row*Line`，`Video[4]=3200` ⇒ 800）一直往下，占据 800-1920。因此 v20 的数字与固件日志**叠在一起**，用户只能读出其中未被覆盖的部分（可见 9 行，1088/1248/1568 三行没读到）。

现有色带占满 256-1040（步进 32、高 32，**没有间隙**），800 行以下全是固件文字区，0-200 是固件绿条。请给一个可落地的方案，满足：
- 所有读数行落在**固件文字不会覆盖**的区域（屏幕 800 行以上 = 绿条 + 色带区）；
- 每行自带可识别标记（否则下一轮又只能靠肉眼数行位，本轮就是靠三个锚点互锁才定下来）；
- 一轮实机能读到足够多的量（v20 想要 6 个：`_DTInitialized`、`_DTRootNode`、`_gPESoCBasePhys`、`PE_state+0x90`、`PE_state+0xa0`、`timebase_frequency_hz`、`arm64_eventi`，再加 panic 变参的指针与函数名）。

我初步想过：把色带高度从 32 降到 16、步进保持 32，腾出 16 行间隙，再把 hex 字形从 4x4 缩到 3x3（15 行高）放进间隙；每行首部用 4 个固定 nibble 区分行号。请评估这个方案，或给出更好的。

（相关实测：色带行位占用 = 352,384,…,1040 及 1088-1568；绿条在照片里对应屏幕 0-200 行；`DiagDraw` 只在失败路径调用，正常路径那些文字来自 UEFI console，位置不可控。）


> 复核闭环（2026-10-25）：此请求已由v21/v22记录承接；ADRP搬移错误解释了同一panic，LO与时基算术已纠正，屏幕字段已编号，最新实机进入pmap入口。见2026-10-25-v21-probe-transparency.md、2026-10-25-v22-pmap-transition.md及D-038/D-040。本文保留为原始问题清单，不作为当前结论。
