# nuwa Data 双 Bank 日志 overlay（v3，2026-11-26）

范围：独立格式与主机模型，**self-checked**；未接内核、未打包、未访问设备。复用本仓 `Gate.h` 的小端读取、窗口判定和 IEEE CRC32，以及 `Provider.h` 的相对块 `read/write/sync` 接口；没有引入外部代码。调用者负责介质资格、FUA 和串行化。

## 布局与线格式

块 4096 B，逻辑页数 2,097,152，两个 bitmap 各 64 块，日志 512 块。窗口绝对 LBA `[57393401, 61588475)`。相对区间：

| 区域 | 块区间 |
| --- | --- |
| SB0 / SB1 | `[0,1)` / `[1,2)` |
| BMP0 / BMP1 | `[2,130)` / `[130,258)` |
| LOG | `[258,770)` |
| DATA0 / DATA1 | `[770,2097922)` / `[2097922,4195074)` |

- SB `NUWADSB3`：小端字段从偏移 `8/12/16/24/32/64/68/72/76/80/88/92` 起，依次为 version、slot、pages、ckpt_gen、seed hash、每张 bitmap 块数、环块数、log_head、flags、present_count、bitmap CRC、header CRC。pages、ckpt_gen、present_count 为 u64，其余数值为 u32。头 CRC 覆盖前 96 B；`[96,4080)` 保留字节为零。
- LOG `NUWADLOG`：80 B 头；version/slot 为 u32，gen/ckpt_gen 为 u64，seed hash 32 B；偏移 `64/68/72/76` 的 u32 为 entry_count/flags/header CRC/reserved。每条 16 B：u64 页号、u32 页 CRC、u8 bank、u8 flags、u16 reserved。未用条目与保留位清零。写接口提交连续 1–250 页；读回格式要求页号在范围内且单块内不重复。
- SB/LOG 尾从 4080 起，分别为 u64 代次、u32 槽与 u32 块 CRC；计算各自 CRC 时将对应的四字节字段视为零。bitmap CRC 覆盖整个 `present || active` 区。两张图本身没有超尾位（页数恰等于位容量）；未 present 页的 active 位必须为零。

## 执行与恢复

- `open()` 不写介质。双空 SB 检查整个元数据区和历史位置 640、2097857（640 已含于正式元数据区）。首次允许写的 `writeRun()` 先 FUA 写 `SB0`（代次 0）并 sync；`BMP0` 已经验证全零，不重写。这样即使第一次在历史探针所在数据块撕裂，重开仍可回 seed。首个 SB 自身撕裂且无完整锚点时拒绝恢复；没有自动清除或重建。
- 数据首次写入 bank 0，后续写入对侧。数据 FUA → sync → LOG FUA → sync，才更新内存。环满时先写下一套 128 块 bitmap、sync、下一 SB、sync，再切换。I/O 失败使当前句柄停写；必须重新 `open()` 才能取得新的状态。
- 恢复从最新完整 SB 开始；身份不符、同代 SB 或最新 bitmap 校验失败均拒绝，不回退到较旧 bitmap。写一半的备用 SB 不阻止有效锚点恢复。日志先查连续代次及 bank 转换，一个 CRC 损坏块只允许出现在首个缺口的位置；其后接受空块或合法旧 epoch 记录，拒绝第二个损坏块、同 epoch 续块和未来 epoch。逆向按页去重，仅校验最新生效日志引用的数据页；未被本 epoch 更新的 checkpoint 页面没有独立持久 CRC。
- 任务简报之外明确的格式决定是初始空锚点、字段宽度及头 CRC 覆盖范围，以及损坏槽必须在首个缺口。工作树未找到独立的 Neon 规范正文；以派发的几何、字段及九类判据为准，未比对外部黄金镜像。

## 自检

WSL Ubuntu 22.04，GCC 11.4；从设备仓根目录复跑（`OUT` 为主机临时目录）：

```sh
g++ -std=c++17 -Wall -Wextra -Werror -O2 -g \
    -fsanitize=undefined,address -fno-sanitize-recover=all \
    -fno-omit-frame-pointer -no-pie tests/test-nuwa-dualbank.cpp \
    -o "$OUT/test-nuwa-dualbank"
"$OUT/test-nuwa-dualbank"
```

```text
PASS layout and boundaries
PASS bank alternation
PASS torn data (first write and overwrite)
PASS torn log (prefix, suffix, mixed; empty and stale targets)
PASS multi-page run power cuts
PASS checkpoint power cuts (bootstrap, L=4 and L=512)
PASS ring wrap
PASS fail-closed matrix
   1 page/run: 1153/512 = 2.251953x
  32 page/run: 17025/16384 = 1.039124x
PASS write amplification
```

断电注入包括 32 页 run 的每个数据、日志、sync 边界；checkpoint 的所有 128 个 bitmap 写和 SB/sync/下一次单页提交的前后边界，另含首个 present/active bitmap 块与 SB 的扇区混合撕裂。每次 `open()` 断言零写、零 sync；Fail 矩阵还断言失败后写调用不会触碰介质。写放大按稳定周期（512 个 run、一个 checkpoint）计块，不计首次空 SB 或底层介质内部放大。

未覆盖：真实 UFS 断电/FUA 行为、内核接线/并发和 checkpoint 后未被日志覆盖的数据介质损坏。未独立复跑。
