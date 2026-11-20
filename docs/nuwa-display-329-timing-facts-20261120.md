# 20H392 slot 329 TimingEnable：消费事实表

状态：self-checked，静态反汇编，未运行设备或独立 verifier。输入为
`UniXNU/out/ipsw/20H392/kernelcache.decompressed`，SHA256
`2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221`；
`Image` 初始化实际核验此哈希。地址省略 `0xfffffff000000000`。

## 结论及边界

329 的返回值是虚调用返回 `w0` 的 bit 0；timeout 日志格式确实名为
`TimingEnable`，且另两个消费点用它决定是否进入各自的状态处理路径。
**不是“启用超时取消”开关**：超时路径调用 329 只将 bit 0 放进日志，
并未据此分支；此后能到达 `5c11a6c` 时，无论 329 true/false 都调用
330。中间 `iomfb_rack_debug` 检查触发的 panic 路径可能不返回，不可
说 330 一定执行。

329 是 Legacy 纯虚槽；当前检查未识别具体 subclass 的实现、状态位位置、
写入者或 nuwa 上有效的状态转换。`DPLink` 日志读取的 `self+0x1524`
不是 329 返回值；无法把它的写入者当成 TimingEnable 的写入者。
因此不足以决定 nuwa 329 恒真或恒假，也不足以放行运行；330 请求生命周期
仍另待闭合。

## 逐项对照

`self` 为入口 `x0` 保存值；表中调用的虚表偏移不是 self 字段。
`bit0=1/0` 只描述调用实际消费的位，非断言其他位。

| 地址 | 指令 / self 偏移 | 分支目标与结论 |
|---|---|---|
| 5c10d44–5c10d58 | 保存入口 x0 到 `[sp,#0x18]` | 后续 x0 为 self。 |
| 5c10e0c–5c10e18 | `ldrb` self+0x1528；`tbnz #0` | bit0=1 → 5c10f04；否则继续。字段语义未定。 |
| 5c10e20–5c10e30 | `ldr w8,[self,#0x147c]`；零检测 | 零 → 5c10f04；非零继续。日志将其称 PowerStates-Cntr，不推断其所有状态语义。 |
| 5c10e38–5c10e48 | `ldr x8,[self]`; `ldr x8,[x8,#0xa48]`; `blr x8`; `tbz w0,#0` | 329 bit0=0 → 5c10f04；1 → 5c10e50，调用虚表 `+0xa18`，参数 w1=7、x2=0；返回非零亦 → 5c10f04，返回零再调用 5c11160。 |
| 5c10f04–5c10f38 | 读 self+0x1656，条件调用虚表 `+0x9f8`；随后从 self+0x13c0 传参至 5c10924 | 此处不是函数返回；之后仍可能进入第二个 329 消费点。字段和调用语义未定。 |
| 5c10f48–5c10f6c | 读 self+0x1528 bit0 和 self+0x147c | 前者为 1 或后者为零 → 5c11014；否则继续。 |
| 5c10f74–5c10f84 | `ldr x8,[self]`; `ldr x8,[x8,#0xa48]`; `blr x8`; `tbz w0,#0` | 329 bit0=0 → 5c11014；1 → 5c10f8c，调用虚表 `+0xa18`，参数 w1=6、x2=0；返回非零 → 5c11014，零再调用 5c11160。 |
| 5c11014–5c11020 | self, w1=1；`bl 5c11c04` | 两条分支汇合后调用；该函数的完整效果未定。 |
| 5c11884–5c118e4 | 5000；对 self+0x13b0 指针作虚调用 `+0x110`；返回值比较零 | 非零进入 5c118ec → 超时日志；零 → 5c11abc；单凭此处不定义所有返回码。 |
| 5c11928–5c11930 | 日志字符串 `4f66199` | 字面含 “CommandWake didn't happen even after 5 seconds ... cancelling swaps”。 |
| 5c11968–5c11978 | `ldrb` self+0x1524，保存到栈 | 位随后入日志 DPLink；不写 self。 |
| 5c1197c–5c11984 | 虚表 `+0xa48`；`blr` | 329 返回值；没有 self 字段直接读写。 |
| 5c119a4–5c119ac | `ldr` self+0x147c、self+0x1480 | 送日志 PowerStates-Cntr、Display；不写 self。 |
| 5c119d0–5c119e0 | `and x11,x11,#1`、栈偏移 0x28；随后 `mov x11,x0; and x11,x11,#1; str x11,[sp,#0x30]` | 前者为 DPLink，后者为 329 的 TimingEnable；未发现基于 329 返回值的条件分支。 |
| 5c119ec–5c119f4 | `bl 5c26cec`，格式串 `4f66224` | 输出 `HPD, DPLink, TimingEnable, PowerStates-Cntr, Display`；HPD 的输入来自更早局部变量，写入者未定。 |
| 5c119f8–5c11a40 | 查询 `iomfb_rack_debug`、检查返回值与栈局部值 | 任一检查为零 → 5c11a6c；均非零 → 5c11a48 的 5c274f0（panic 字符串）。这两项不是 329。 |
| 5c11a6c–5c11a78 | self 的虚表 `+0xa50`；`blr` | 槽 330；到达此处不依赖 329 值，330 行为和生命周期不在本次闭合范围。 |

上表内所见 self 偏移均为读，无对应 self 字段写入；栈上的 329 日志
bit 由 `5c119dc–5c119e0` 写入。未穷举动态别名或其他模块的写入，
不能据此断言任何状态字段没有写入者。

## 复跑

在 WSL 的 `UniXNU-nuwa` 根目录执行下列只读命令；依赖 Python 3、
capstone 与基座 `kits/XnuPrelink`。最后打印全部指定区间，输出中的
地址保留完整前缀。需逐指令对照，不创建生成文件。

```sh
python3 - <<'PY'
import importlib.util
from pathlib import Path
import capstone
s = importlib.util.spec_from_file_location('derive', 'scripts/derive-nuwa-display-abi.py')
d = importlib.util.module_from_spec(s)
s.loader.exec_module(d)
base = Path('/mnt/d/Code/PortingiOS/UniXNU')
i = d.Image(base, base / 'out/ipsw/20H392/kernelcache.decompressed')
cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
for lo, hi in [(0x5c10d44,0x5c11034), (0x5c1187c,0x5c11a7c)]:
    start = d.va(format(lo, 'x'))
    for ins in cs.disasm(i.read(start, hi-lo), start):
        print(f'{ins.address:x}: {ins.mnemonic} {ins.op_str}')
for a in ('4f66199','4f66224','4f662b8','4f614d2'):
    print(a, i.read(d.va(a), 200).split(b'\0')[0].decode())
PY
```

完整区间以复跑输出为准；下方记录本次 `5c11928–5c11a74` 连续指令。

```asm
5c11928: adrp x0, #0xfffffff004f66000
5c1192c: add x0, x0, #0x199
5c11930: bl #0xfffffff005c26cec
5c11934: ldur x0, [x29, #-0xb8]
5c11938: ldur w9, [x29, #-0x2c]
5c1193c: mov x8, x9
5c11940: str x8, [sp, #0x50]
5c11944: ldur w9, [x29, #-0x30]
5c11948: mov x8, x9
5c1194c: str x8, [sp, #0x58]
5c11950: ldur w9, [x29, #-0x4c]
5c11954: mov x8, x9
5c11958: str x8, [sp, #0x60]
5c1195c: ldur w9, [x29, #-0xa4]
5c11960: mov x8, x9
5c11964: str x8, [sp, #0x68]
5c11968: mov x9, #0x1524
5c1196c: mov x8, x0
5c11970: add x8, x8, x9
5c11974: ldrb w8, [x8]
5c11978: str w8, [sp, #0x74]
5c1197c: ldr x8, [x0]
5c11980: ldr x8, [x8, #0xa48]
5c11984: blr x8
5c11988: ldur x8, [x29, #-0xb8]
5c1198c: ldr x16, [sp, #0x48]
5c11990: ldr x15, [sp, #0x50]
5c11994: ldr x14, [sp, #0x58]
5c11998: ldr x13, [sp, #0x60]
5c1199c: ldr x12, [sp, #0x68]
5c119a0: ldr w11, [sp, #0x74]
5c119a4: ldr w9, [x8, #0x147c]
5c119a8: mov x10, x9
5c119ac: ldr w9, [x8, #0x1480]
5c119b0: mov x8, x9
5c119b4: mov x9, sp
5c119b8: str x9, [sp, #0x78]
5c119bc: str x16, [x9]
5c119c0: str x15, [x9, #8]
5c119c4: str x14, [x9, #0x10]
5c119c8: str x13, [x9, #0x18]
5c119cc: str x12, [x9, #0x20]
5c119d0: and x11, x11, #1
5c119d4: str x11, [x9, #0x28]
5c119d8: mov x11, x0
5c119dc: and x11, x11, #1
5c119e0: str x11, [x9, #0x30]
5c119e4: str x10, [x9, #0x38]
5c119e8: str x8, [x9, #0x40]
5c119ec: adrp x0, #0xfffffff004f66000
5c119f0: add x0, x0, #0x224
5c119f4: bl #0xfffffff005c26cec
5c119f8: ldr x1, [sp, #0x80]
5c119fc: mov w8, #0xaa
5c11a00: sturb w8, [x29, #-0xa9]
5c11a04: adrp x0, #0xfffffff004f61000
5c11a08: add x0, x0, #0x4d2
5c11a0c: mov w2, #4
5c11a10: bl #0xfffffff005bf761c
5c11a14: subs w8, w0, #0
5c11a18: cset w8, ne
5c11a1c: mov w9, #1
5c11a20: and w8, w8, w9
5c11a24: sturb w8, [x29, #-0xa9]
5c11a28: ldurb w8, [x29, #-0xa9]
5c11a2c: tbz w8, #0, #0xfffffff005c11a6c
5c11a30: b #0xfffffff005c11a34
5c11a34: ldur w8, [x29, #-0xa8]
5c11a38: subs w8, w8, #0
5c11a3c: cset w8, eq
5c11a40: tbnz w8, #0, #0xfffffff005c11a6c
5c11a44: b #0xfffffff005c11a48
5c11a48: mov x9, sp
5c11a4c: adrp x8, #0xfffffff004f65000
5c11a50: add x8, x8, #0x96d
5c11a54: str x8, [x9]
5c11a58: mov x8, #0x81b
5c11a5c: str x8, [x9, #8]
5c11a60: adrp x0, #0xfffffff004f66000
5c11a64: add x0, x0, #0x2b8
5c11a68: bl #0xfffffff005c274f0
5c11a6c: ldur x0, [x29, #-0xb8]
5c11a70: ldr x8, [x0]
5c11a74: ldr x8, [x8, #0xa50]
```
