# nuwa disposable Data 日志环滚动设计（2026-11-28）

状态：**设计，未实现；仅静态审查**。本方案让同一运行会话在第 512
条记录之后继续写，不把命令完成当作介质持久。当前 disposable 后端没有
足以证明断电后已确认写入仍存在的屏障；因此，**未知的冷重开必须拒绝挂载**。
离线故障模型中的可恢复结论不等于真实 UFS 的断电保证。

## 1. 基线与当前格式

源码基准为本工作树 `ba02fc006e47432a8186396fb25cbedecfaec959`：
`package/nuwa-data-write/DualBankLogOverlay.h`（overlay）、
`DisposableData.h`（实例/窗口）、`DisposablePort.inc`（实际 I/O），以及
`package/nuwa-ramblock/NativeRamBlock.cpp`（请求和 open 接线）。
复用同文件中既有的双 bitmap、双数据银行、checkpoint 与 CRC 思路；生产
checkpoint 需要 `ops.sync()` 的不同合同，不能直接拿来给 disposable 使用。

所有位置是相对窗口的 **4096 B 块**，窗口绝对范围为 LU0
`[57393401, 61588475)`。`Pages=2097152`，即 8 GiB 的逻辑页：

| 区域 | 相对块范围 | 含义 |
| --- | --- | --- |
| SB0、SB1 | `0`、`1` | 两个 checkpoint superblock |
| map 组 0、组 1 | `[2,130)`、`[130,258)` | 每组 128 页：前 64 页 present bitmap，后 64 页 active-bank bitmap；每一 bit 对应一个逻辑页 |
| ring | `[258,770)` | 512 个单页记录槽，`physical=(head+i)%512` |
| data bank 0、1 | `[770,2097922)`、`[2097922,4195074)` | 各 2097152 页，逻辑页 `p` 的两个固定位置分别为 `Data0+p` 和 `Data1+p` |

`present=0` 表示从不可变 seed 取页；`present=1` 时 `active=0/1` 选择银行。
`active` 不能在 `present=0` 的页上置位。运行时新写目标由
`target(p) = present(p) && !active(p)` 给出：不存在时先写 bank 0；
已存在时写当前银行的另一份。CPU 侧 `Workspace` 含两张当前 bitmap；
`present_` 是置位页数，不是 ring 记录数。

### 1.1 SB 与 ring 格式（现有 v3，不是新提案）

所有整数小端；CRC 是 `Gate.h:138–145` 的 CRC-32/IEEE，计算某 CRC
字段时将该 4 字节视为零。两个 SB 在块尾均有 generation（偏移 4080，
8 B）、槽号（4088，4 B）与整块 CRC（4092，4 B）。

| SB 字段 | 字节偏移 / 长度 |
| --- | --- |
| magic / 版本 / SB 槽号 | `0/8`、`8/4`、`12/4`；disposable 为 `NUWAXSB3` / `3` |
| 页数 / checkpoint generation | `16/8`、`24/8` |
| seed identity | `32/32` |
| 每张 bitmap 页数 / ring 槽数 | `64/4`、`68/4` |
| head / 保留零 / present count | `72/4`、`76/4`、`80/8` |
| 两张 bitmap 拼接后的 CRC / SB 头 CRC | `88/4`、`92/4`；头 CRC 覆盖 96 B |

ring 数据记录是 `NUWAXLOG`，版本 3，每块至多 `MaxRun=250` 个 entry：

| 字段 | 字节偏移 / 长度与检查 |
| --- | --- |
| magic、版本、physical | `0/8`、`8/4`、`12/4` |
| generation、checkpoint epoch | `16/8`、`24/8` |
| seed、entry 数 | `32/32`、`64/4`；数目 `1..250` |
| 保留零、头 CRC、保留零 | `68/4`、`72/4`、`76/4`；头 CRC 覆盖 80 B |
| 每个 entry | 从 `80` 起，每项 16 B：逻辑页 `u64`、整 4096 B 数据 CRC `u32`、bank `u8`、3 B 零；页号不越界、同记录不重复、bank 只能为 0/1 |
| 未用 entry、尾部 | 未用 entry 全零；`4080/8` generation、`4088/4` physical、`4092/4` 整块 CRC |

头 CRC 只覆盖头；整块 CRC 覆盖记录和尾部，数据 CRC 单独覆盖引用的
4096 B 数据页。CRC 不是认证。普通 v3 SB 的 map CRC 只覆盖 bitmap，
**不覆盖 checkpoint 所引用的数据页**；日志回放中的数据 CRC 才校验最新
日志版本。map 中的 `present count` 必须等于 present bitmap 的置位数。

### 1.2 generation、head 与回放（现有实现）

- 通用非 disposable 模式选合法 SB 中 generation 最大者；两个合法 SB 同代、
  foreign SB、最新 SB 的 map CRC/count/active 不符均失败，不能从已封存
  的新 checkpoint 静默回退。checkpoint 写另一组 128 页 map、`sync`、
  写对应 SB、`sync`；然后 `epoch=gen`、`head=(旧 head+used)%512`、
  `used=0`。首次建锚的特别路径见源码 `checkpoint()`。
- **disposable 例外**：仅接受外部初始化的 `NUWAXSB3` SB0、全零 SB1，
  SB0 的 generation、head、present count 均为 0，且其 map 校验通过；
  不能在内核 create 或 checkpoint。其 `epoch=0`、`head=0` 始终不变。
  空白窗口也不是 `Open::Empty`，而是 `Open::Failed`；有效初始 SB0 的
  `open()` 返回 `Resumed`、generation 0。
- 每次成功 `writeRun` 写一条记录：数据页写完 → `ops.sync()` → 日志页
  写完 → `ops.sync()` → 在 RAM 应用 bitmap，`gen++`、`used++`。
  disposable 的 `ops.sync()` 实际是 `native_ufs_store_order()`，只检查
  前面命令已完成及当前会话/所有权，**不是 flush**。第 512 条提交后
  `writable=false`；重开回放满环也是 `Resumed` 但只读。
- 回放先从 SB 的 map/epoch/head 出发，按 ring 顺序验证记录结构、种子、
  `gen-epoch=i+1`，旧 epoch 仅在不跨越当前 epoch 时跳过；当前 epoch
  必须是无空洞的连续前缀、generation 每条加 1，每个 entry 的 bank 必须
  等于该时刻的 `target(page)`。依序 `apply`，后写覆盖同页先写。
  随后反向扫描该前缀，用 `seen` 只读并检查**每个页最新 entry**的数据 CRC；
  被后写取代的旧数据页不验。disposable 对任意坏 CRC ring 块拒绝；
  非 disposable 对紧邻前沿的 corrupt 块有专门例外。
- `NativeRamBlock::candidateIO()` 每次 staging 最多 32 页，支持局部页先读
  再改；单 run 成功才计其字节。调用者已有 RamBlock gate 序列化，UFS
  共用既有 host 锁和 Slot0。`DisposablePort.inc:75–80` 只允许写一个块，
  且相对位置必须 `>=Log`；**运行时不能写 SB0/SB1 或两组固定 map**。

## 2. 滚动方案：在银行空闲页 checkpoint，而非放宽写门

选择**先固化整个当前 map**，不要求被覆盖记录的页恰好被新记录再次
引用。仅把最旧记录删掉或假定它已被后续记录覆盖是不正确的：它可能是
某个仍活跃逻辑页的唯一映射。直接调用现有 `checkpoint()` 同样不行：
既要写禁止区域，也假定 `sync` 的合同强于 disposable 的 `order`。

新格式称 **R4（提案）**：窗口、SB、固定 map、512 个 ring 槽和两数据银行
的位置与上述完全相同。初始化器必须另行准备 R4 的空 SB0、零 SB1、
零 map 和零 ring；运行时仍不初始化、不写固定 SB/map。R4 在需要
checkpoint 时，将两张当前 map 的 128 个块写入数据银行中**没有被当前
map 引用的 128 个不同物理页**，再用一个 ring 槽发布 checkpoint 描述符。
此后每个 checkpoint 占用一个 ring 槽，因此其后的数据记录容量是 511，
不是声称额外增加了 ring 空间；第一次滚动之前仍可写满 512 条数据记录。

### 2.1 必须成立的不变量

1. 每个 present 页恰有一个当前 active 银行；未 present 的页由 seed 服务。
   当前活页的物理位置绝不能用于 checkpoint 页，也不能被下一笔数据原位写。
2. 新 checkpoint 的 128 个物理页各不相同、都在两数据银行内，且均不等于
   任一当前 active 页；不覆盖当前 checkpoint 正在引用的 128 个页，也不
   占用待写 run 的目标页。新 checkpoint 描述符完成并经 `order` 后才可
   释放旧 checkpoint 页。描述符和其地图一旦选为最新，不回退到旧描述符。
3. 活跃 checkpoint 的 128 页必须一直被 pin。若用户写的 `target(p)` 命中
   其中任何一页，**先制作并发布一个新的完整 checkpoint**，选其他空闲
   页，然后才能按原规则写该用户数据。读 map 不会把 checkpoint 页当
   用户数据。回放须拒绝当前 epoch 的数据记录引用已 pin 的 checkpoint 页。
4. 选择 128 页可确定为：按逻辑页升序枚举每页当前 `target(p)`，跳过
   已 pin 的页及本 run 的目标页，取前 128 个。每个逻辑页贡献一个不同
   的非 active 位置；即使排除旧 checkpoint 的 128 页和最大 run 的
   250 页，`2097152-128-250 > 128`，仍有足够位置。此计数依赖当前
   双银行和固定几何，不是额外窗口或额外硬件资源。
5. checkpoint 是当时**完整**的 present/active map，而非只拷贝最老
   记录的页。只有它及其引用页通过校验后，才可视它所覆盖的所有旧
   记录为 stale；此后遇到新 checkpoint 坏或依赖缺失，返回未知，不回落
   旧世代或 seed。
6. generation 只随成功的数据记录增加，不能回绕；checkpoint 不增加
   generation，另有单调、不回绕的 `checkpoint_seq`，初始为 0，同一
   generation 可以有多个 checkpoint。任一计数将溢出时停止写入。
   旧 checkpoint 的 generation 相同并不表示冲突，以严格递增的 seq
   区分；相同 seq 的不同描述符是未知。

### 2.2 R4 编码与完整性

以下是提案，不是现有 magic、字段或 API。用 `NUWAXS04`、`NUWAXC04`、
`NUWAXL04` 分别标识 R4 初始 SB、checkpoint 和数据记录，版本字段均为 4，
旧 v3 不能被当作 R4。固定初始 SB 承载相同几何、seed、空 map CRC 和
初始 `generation=0`；除 magic/版本外沿用上表的 96 B SB 布局与 CRC，
槽号、head、count 均为 0，初始 root 隐含为 32 个零字节；SB1 必须为零。
新格式依然只允许同一个逻辑 seed。

为保留 `MaxRun=250` 而在日志中携带全状态校验，R4 数据 entry 由 16 B
改为 8 B：**3 B 小端页号**（必须 `<2097152`）、4 B 小端数据 CRC、
1 B bank。记录头长度 152 B：沿用 v3 的 magic、version、physical、
generation、epoch、seed、entry 数及 `68/4`、`76/4` 的零字段；
`72/4` 为对 152 B 头计算的头 CRC；新增 `80/8` checkpoint seq、
`88/32` 前状态摘要和 `120/32` 后状态摘要。250 个 entry 从 `152` 起，
未用 entry 到尾部 `4080` 的所有字节为零；尾部 generation、physical
和整块 CRC 的位置与 v3 相同。页号重复、非法 bank、保留位非零、
字段/尾部/CRC 不符均为未知。

checkpoint 是单个 ring 页：`0/8` magic、`8/4` version、`12/4`
physical、`16/8` generation、`24/8` checkpoint seq、`32/32` seed、
`64/8` present count、`72/4` 下一 head、`76/4` 两张 map 拼接的 CRC、
`80/4` 描述符头 CRC、`84/4` 零、`88/32` 状态摘要、`120/512`
按 map 页顺序排列的 128 个 `u32` 窗口相对物理页号。头 CRC 覆盖
`[0,632)` 且将 `80/4` 清零；`[632,4080)` 必须为零；尾部及整块 CRC
与上述相同。head 必须是 `(physical+1)%512`；目录必须无重复、全在
data bank、符合不变量 2–3，map 的 count/active/CRC 必须成立。

仅有 bitmap CRC 无法在清理旧日志后验证 checkpoint 活页，因此 R4 还定义
状态摘要（完整性检查，不是认证）：

```text
item(p,b,data) = SHA256("NUWA-R4-page" || LE64(p) || u8(b) || data[4096])
root = XOR(item(p,active(p),data(p)) for each present p)
```

空集为 32 个零字节。每次写先读旧 active 页计算旧 `item`（未 present
时省略），再用新数据计算新 `item`，在局部变量中按 XOR 删除旧项、加入
新项；成功的 R4 日志保存前/后 root。checkpoint 发布前，扫描全部当前
present 页重新计算 root，必须等于内存 root，然后把它写进描述符；任意
读错或不符即停止，不释放旧引用。重开时先按日志重建**最终** map，
再扫描所有最终 active 页并比较最终 root；这允许 checkpoint 之后同一页
的旧银行已被后续写复用。仍对每个最终最新日志 entry 验它的数据 CRC。
root/CRC 用于发现损坏，不提供抗恶意篡改，也不能以 CRC 或哈希成功证明
已确认写入没有被整个丢失。全量扫描最坏需读 8 GiB；这是本方案的明确
开销，不宣称启动性能达标。

### 2.3 写入与回放算法

单会话内沿用现有调用者串行化。下一数据写若 ring 有空且目标未碰 pin，
仍按数据页 → order → 数据记录 → order → 发布 map/root/generation。
日志头里的前 root 必须等于当前 root，后 root 是本 run 结果。

当首次满 512 条时，或当前 checkpoint 后已有 511 条数据记录时：

1. 锁定当前完整 map、generation 和 root；按 2.1 选址、核验 root。
   将两张 map 顺序写入 128 个空闲银行页，再 `order`。
2. 写 checkpoint 描述符：首次满环覆盖槽 0 的最旧数据记录；已有
   checkpoint 时覆盖其后的最旧数据记录，保留当前 checkpoint 槽。
   精确选槽：未满时为 `(head+used)%512`；满时为 `head`，即当前最旧
   数据记录的位置。首次尚无 checkpoint 时容量为 512，此后为 511；
   若为避免 pin 冲突而提前 checkpoint，使用上述未满分支。不得覆盖
   当前 checkpoint 槽。`seq++`、`epoch=当前 generation`、
   `head=(描述符槽+1)%512`。描述符写完再 `order`。
3. 两次 order 均成功后在 RAM 发布新 checkpoint、head 和 pin 集，释放旧
   pin；原 epoch 记录成为 stale。此时原来只存在于最旧记录的活页已被
   新 map 引用。再执行触发该 checkpoint 的用户写。checkpoint 本身
   不计为用户数据提交。

重开时，先验证 R4 初始 SB 和所有 512 槽的格式/CRC；空槽可为零，
损坏或不明槽不当成空槽。选择 `checkpoint_seq` 最大的合法 checkpoint；
没有 checkpoint 时使用初始空 map、epoch/seq/head 均为 0。选中后读取
128 页并校验 map 与目录，以其记录的 root 为日志链起点；不能在重放前
要求当前数据仍匹配 checkpoint root，因为之后的日志可能已复用旧银行。
发现更新的不可判定描述符、重复 seq、新 map 损坏或依赖不完整，不回退
旧 checkpoint。按选中 head 顺序重放
当前 seq 的连续数据前缀，要求 epoch 等于 checkpoint generation、
generation 逐条加一、bank 按当时 map 的 `target` 翻转、前 root 与
上一 root 相等、不能命中 pin；先前 seq 的合法记录只有在 generation
不超过 checkpoint generation 时才能当作 stale。当前 seq 出现空洞后
再出现记录、未来 seq、错代、超范围、重复页、根摘要或最新数据 CRC
不符，均为未知。完成后全量核验最终 root，才可发布可服务的 map。

## 3. 第 513 条、掉电与未知

设最初 512 条均成功，逻辑页 A 只出现于第 1 条，下一 run 改写 B。
首次滚动的命令序列是：

```text
读/验证所有活页和 root
写 128 个未引用银行页的 map → order
在 ring[0] 写 checkpoint(seq=1, gen=512, head=1) → order
发布 checkpoint/pin
将 B 的新数据写至原 map 选择的另一银行 → order
在 ring[1] 写数据记录(seq=1, gen=513, epoch=512) → order
发布 B 的 map 和 root；gen=513；确认该 run
```

ring[0] 原第 1 条被 checkpoint 取代、ring[1] 原第 2 条被新记录取代；
A 的映射已在 128 页 checkpoint 中，不要求新记录再写 A。多页 run 的所有
数据页均在第一个数据 `order` 之前，记录及内存发布仍以 run 为单位。

### 3.1 可恢复性：明确模型

下面的旧/新状态结论只适用于离线模型 **M**：每次成功的 `order` 被
fixture 建模成一个**真正的有序持久屏障**，其前完成的写均进入持久快照；
两次屏障之间的写可缺失、完整或按扇区撕裂；块 CRC/状态摘要碰撞不在
检测能力内。实际 `disposableOrder()` 只代表命令完成次序，**不满足也
未证实满足 M**，不因复用 `order` 名称改变 FUA/flush 语义。

| 故障点 | M 下重新读取并完整验证后的判据 |
| --- | --- |
| 写 checkpoint 的 128 页之前、中间、之后至首个屏障 | 旧活页和旧 pin 不被改；旧记录完整则恢复 gen 512；新地图可能是垃圾，未发布不能采用。 |
| checkpoint 描述符写入之前、撕裂、完整、第二个屏障前后 | 原记录完整且未发生不可判定损坏时恢复旧 gen 512；描述符完整且其地图/root 完整时恢复新 checkpoint gen 512；撕裂或新依赖不完整为未知。不得从疑似新 checkpoint 回退。 |
| 发布 checkpoint 后，写第 513 run 的部分数据或到数据屏障前后 | 新数据只写非 active 且非 pin 页；没有完整新记录时恢复 checkpoint 的 gen 512，B 和 A 均为旧值。 |
| 新日志写入之前、撕裂、完整、第二次数据屏障前后 | 旧槽仍完整时为 gen 512；完整新记录且所有新数据/root/CRC 验证成功时为 gen 513；撕裂、错代、缺页或不符为未知。多页 run 不允许只发布其中一部分。 |
| 最终 order 后、内存发布前；内存发布后/确认前后 | M 下介质记录完整且 root 匹配，均可恢复 gen 513；用户是否看到返回值不改变日志的提交判定。 |

必须另测 checkpoint 提前触发、pin 冲突搬迁、第二次环绕、任一数据页与
128 页 map 的各写入/屏障故障，以及多个成功 run 后的同页反复翻转。
I/O 返回失败、超时、无法归属、目录越界/重复、非法代数、完整新记录
但引用页或 root 校验失败，均停止会话并判未知；不重试写、不重新初始化、
不静默切 seed。

### 3.2 实际后端的不可判定性

仅凭当前非持久 `order`，第 513 条返回后，缓存可能连同新地图、新
checkpoint、数据和新记录一起丢失，介质恰好与“第 512 条后从未发第
513 条”逐字节相同。即使全部 CRC/摘要正确，两个历史也不可区分；在
同一不可靠介质上再写一个 dirty/commit 标记也可能一起丢失。因此：

- 同一仍活跃的运行会话可以使用完成顺序写至 513 及更远；成功只表示
  当前 disposable 请求的非持久完成，不表示断电耐久。
- 可在保留独立 RAM 会话凭据的同次会话中重开：凭据至少绑定同一窗口、
  seed、最近已发布的 generation、checkpoint seq/head 和 root；与回放
  结果不一致即未知。该凭据是设计上的验证条件，不宣称现有 API 已提供。
- 冷重开或掉电后，**缺独立的已确认前沿/持久顺序证据时返回未知并拒绝
  挂载**，不能仅因读到合法旧前缀就声称已确认的最后写入存在。将来若
  另行证明实际介质提供 M 所需的屏障合同，或取得可信且绑定本窗口、
  前沿及 root 的独立凭据，才可按所证明的合同考虑恢复；本设计不发明
  该证据或启用新屏障。离线模型测试不构成设备资格。

## 4. `open()` 判定与兼容性

保留生产路径现有 `Empty / Resumed / Failed` 含义；R4 disposable 的
提案 verdict 另区分 `LegacyUnsupported`、`Unknown` 和明确的 `Failed`
（I/O/参数失败可并入失败，但不得被视为空白）。实际接线必须把
`LegacyUnsupported`、`Unknown` 和 `Failed` 全部当作不 ready、不 writable、
不挂载，且不能沿用当前只检查 `result == Failed` 的简化判断。

| 输入 | R4 提案 verdict / 行为 |
| --- | --- |
| 全零窗口、未提交的初始化、foreign seed/几何 | `Failed` 或 `Unknown`；不 create、不自动清理，绝不返回可写 `Empty` |
| 有效 R4 初始锚和空 ring | 保留旧 disposable 的“有效初始锚是 `Resumed`、generation 0”约定；须有当前初始化/会话的独立资格，不能把任意旧空前缀当冷启动无丢写证明 |
| 完整 R4 回放，且同会话凭据相符或已具备经证明的独立恢复合同 | `Resumed`；符合写门后可写，非持久性不变 |
| 旧 `NUWAXSB3` / `NUWAXLOG` 窗口 | `LegacyUnsupported`，包括未满环；不自动迁移或覆盖。完整满环可进一步标记为 legacy-full，但不是 R4 |
| 撕裂、混合版本、疑似更新 checkpoint、无法确定恢复前沿 | `Unknown`，拒绝挂载，不回退到旧 map 或 seed |

尤其要识别旧满环：有效 v3 SB0（gen/head/count 均 0、SB1 零）后，
512 槽是同 seed、epoch 0、physical 为各自槽号、generation 依次
`1..512` 的合法 `NUWAXLOG`；旧 map 与最终活页 CRC 校验也须通过，
才能诊断为完整 legacy-full。其 SB0 看起来仍为空 map，不能仅靠 SB0
把它误当新空窗口。无法完整分类的损坏旧窗口仍拒绝，不能标为空或重置。
R4 magic 变化也使旧实现拒绝 R4，而不是把 R4 当旧格式继续写。
迁移、丢弃或重初始化旧窗口均不属于本设计，需另行授权和方案。

## 5. 最小离线验收矩阵（待实现；本轮未运行）

使用 512 槽真实几何验证边界；可另用小环加速组合，但不能以小环替代
真实第 513 条。mock 需要分别模拟 M 与“不保证持久/任意丢失及重排”，
并记录每块写、order、返回值和对禁写区域的访问。

| 用例 | 判据 |
| --- | --- |
| 第 513 条成功 | 先写满 512 条再写第 513 条，返回成功、gen=513；先写满 128 页 map、order、checkpoint、order，再数据、order、日志、order；无 SB/固定 map 写；原生两银行、窗口边界不变。 |
| 最旧记录唯一活页 | 第 1 条写 A，第 2–512 条不写 A，第 513 条写 B；跨环后 A 的 has、bank 和逐字节数据均与第 512 条后相同，B 为新数据，present count 正确。 |
| 覆盖后重开 | 无断电同会话，提供匹配的独立 RAM 前沿凭据；新对象返回 `Resumed`，重建的每个受测页、gen、seq、head、root 和 count 与重开前一致，之后可再写。凭据不符必须 `Unknown`。 |
| 后续环绕与 pin 冲突 | 写至少到第二次 checkpoint，主动写命中 map 页所在的目标银行；先完整搬迁并发布新 checkpoint，再写用户数据；所有 checkpoint 前仅出现一次的活页仍逐字节正确；验证 seq 同 gen 的提前 checkpoint。 |
| 第 513 条每个掉电点 | M 下枚举 128 次 map 写、两个 checkpoint order/描述符、run 的每个数据页、数据 order、ring 写/order、内存发布及返回前后的 before/after；对块写另枚举 prefix/suffix/mixed 撕裂。结果只允许表 3.1 的完整 gen 512、完整 gen 513 或 `Unknown`，不能混合 run、丢 A、静默回退。 |
| 非持久丢写反例 | 已确认 gen 513 后，让所有新增介质写丢失，重开看到与 gen 512 相同字节；无独立证据必须 `Unknown` 且拒绝挂载；还要覆盖后写先落、map/描述符/数据各自缺失或撕裂。 |
| 兼容与校验负例 | 完整 v3 空/部分/满环均 `LegacyUnsupported`，满环不当空；混合 R4/v3、错 seed、坏 map/目录、重复地址、损坏描述符、错 seq/gen/head、洞后有记录、pin 命中、活页损坏及摘要/CRC 不符均拒绝；无写入和 seed-only fallback。 |
| 不回绕和不越界 | generation/seq 到上限时停止，无回绕；随机/边界 run 的 map 页、数据页和 ring 写均在既有允许范围，run 数上限和重复页检查有效。 |

## 6. 不做与实施边界

- 不改变生产 `Provider<CandidatePort, false>`、冷启动资格、编译/boot
  opt-in、GPT/seed/窗口身份、单块写与 `rel>=Log` 的门禁，或共用锁、
  Slot0、错误隔离及 DMA/所有权合同。不接设备，不对任何设备写授权。
- 不把 `order` 改称 flush，不新增 FUA 保证；默认仍拒绝 FUA/同步请求。
  已有 `NUWA_DISPOSABLE_FUA_PERMISSIVE` 诊断选项仍仅把 FUA/flush 当
  非持久实验请求，不能声称其提供持久性。
- 不改变原窗口、逻辑页数、seed fallback 对**未映射页**的含义、每 run
  原子发布及 bank 交替；R4 的 checkpoint 暂用的是未引用银行页，不新增
  分区、外部存储或用户可见容量。绝不把 overlay 打开失败当作 seed-only。
- 不修改旧 v3 数据，不做自动升级、reset、迁移、恢复写或静默格式化；
  不把本设计的 host fixture 视为实际介质断电、冷启动、APFS 持久性或
  设备可交互的证据。
- 后续落地涉及存储元数据及写路径，须针对最终改动与故障模型独立审查；
  本文不改变代码、不构建，独立 verifier 和真实硬件资格均未完成。
