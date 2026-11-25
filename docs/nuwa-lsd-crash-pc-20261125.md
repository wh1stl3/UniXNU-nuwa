# lsd SIGSEGV PC 离线检查 — 2026-11-25

**self-checked，仅主机。** 输入是主控提供的 vision 转录，未独立核对原图。
运行时缓存 UUID 和主映像完整基址未观测；以下符号与段归属分别以候选
缓存匹配运行时、主映像基址为 `0x1009b4000` 为前提。

## 原始现场

```text
CR p92 lsd sig=11 code=1 dr=0
CR+ pc=00000001b9583478 lr=00000001b9588824
CR+ sp=000000016f555290 fp=000000016f5552b0
CR+ fa=0000000100b78c0 k=0000000000000000
SHOT lsd n=8 w=7 r=0 ks=00000000 sc=394c8000 sb=009b4000
```

## 地址与符号

缓存运行时基址 `0x180000000 + 0x394c8000 = 0x1b94c8000`。
缓存相对偏移是 VM 偏移，不是文件偏移。

| 项 | 运行时地址 | 缓存相对偏移 | 去 slide VA | 候选符号 |
|---|---|---|---|---|
| PC | `0x1b9583478` | `0xbb478` | `0x1800bb478` | `/usr/lib/libobjc.A.dylib`：`objc_retain` / `objc_retain_x0` + `0x10` |
| LR | `0x1b9588824` | `0xc0824` | `0x1800c0824` | 同库：`objc_storeStrong` + `0x2c` |

置信级别：**候选缓存内的导出符号上界**；两处 `LC_SYMTAB` 命名
符号起点分别为 `0x1800bb468`、`0x1800c07f8`，均与
`LC_FUNCTION_STARTS` 最近函数边界一致。PC 有同址导出别名，不能从 PC
区分调用时用哪个名字。LR 是记录的返回地址，不能当作正在执行的指令。

候选 `out/dyld-cache-20261124/dyld_shared_cache_arm64` UUID
`8F970452-C9E3-3E88-B114-FEB1864BC9E0`，42 个分片和
`.symbols` UUID 均由现有解析器逐一核对；两个地址位于 `.01` 的
libobjc `__TEXT`。符号文件 UUID 为
`51CCBA45-1FC2-3F19-AED0-47050BDF009A`。运行时 UUID 未取得。

## 故障指令（去 slide VA）

从 `.01` 映射中取原始机器码，以 Capstone 5.0.7 解码；PC 的分片文件偏移
`0x5f478`。以下为故障指令前后各 10 条：

```text
1800bb450  clrex
1800bb454  b       #0x1800e22b8
1800bb458  clrex
1800bb45c  b       #0x1800ce628
1800bb460  clrex
1800bb464  ret
1800bb468  ands    x0, x0, x0
1800bb46c  b.le    #0x1800bb464
1800bb470  ldxr    x16, [x0]
1800bb474  and     x17, x16, #0xffffffff8
1800bb478  ldr     x17, [x17, #0x20]    // PC
1800bb47c  tbz     w17, #2, #0x1800bb424
1800bb480  tbz     w16, #0, #0x1800bb450
1800bb484  lsr     x17, x16, #0x2c
1800bb488  cbz     x17, #0x1800bb460
1800bb48c  mov     x17, #0x200000000000
1800bb490  adds    x17, x16, x17
1800bb494  b.hs    #0x1800bb458
1800bb498  stxr    w16, x17, [x0]
1800bb49c  cbnz    w16, #0x1800bb470
1800bb4a0  ret
```

故障指令是 **64 位 load**，目标寄存器 `x17`，地址为旧 `x17 + 0x20`，
无索引寄存器；并非 store、call 或 ret。前两条通过 `x0` 读取到 `x16`
再掩码形成 `x17`。没有采到这些寄存器，不能直接证明其实际值或对象来源。
若 `fa` 确为该 load 的有效地址，则旧 `x17` 应为 `0x100b78a0`；
这是条件推导，不是观测寄存器值。

## fault 地址与 lsd Mach-O

逐字读取 `fa=0000000100b78c0` 得 `0x100b78c0`，不是
`0x100b78c00` 或 `0x100b78c0` 前补一个 1。按题给主映像假定基址
`0x1009b4000`，差值为 **`-0xf08fc740`**；两者相差一个高位数量级，
不可静默补数字。

只读根卷 `/tmp/nuwa-root-inspect-20261124/os/root/usr/libexec/lsd`
SHA-256 `c46e8e7330ab1c008aa50873d230a44f68eb57d675e3fe0b01e0917f9596b2e1`。
`llvm-objdump --macho --private-headers` 显示以下段，运行时范围仅对
非 PAGEZERO 段按所给基址平移：

| 段 | Mach-O VM 范围（半开） | 假定运行时范围 | 文件偏移 / 大小 |
|---|---|---|---|
| `__PAGEZERO` | `[0, 0x100000000)` | 同左，不平移 | `0 / 0` |
| `__TEXT` | `[0x100000000, 0x100004000)` | `[0x1009b4000, 0x1009b8000)` | `0 / 0x4000` |
| `__DATA_CONST` | `[0x100004000, 0x100008000)` | `[0x1009b8000, 0x1009bc000)` | `0x4000 / 0x4000` |
| `__LINKEDIT` | `[0x100008000, 0x100010000)` | `[0x1009bc000, 0x1009c4000)` | `0x8000 / 0x6050` |

该二进制没有 `__DATA` 段。`fa` 不在上述任何文件支持段，而落入
Mach-O 声明的无权限 `__PAGEZERO` 范围；该段 `fileoff=filesize=0`，
因此没有对应文件偏移或 lsd 符号。段表本身不证明运行时 VM 映射状态；
`llvm-nm -n` 仅列出未定义的 `__LSServerMain` 和
`__mh_execute_header`。

## 综合判断与边界

* 候选代码确定 PC 是通过寄存器间接 **读**；结合所报 SIGSEGV、
  fault 地址及条件推导，支持 retain 路径读取坏的对象/类元数据指针，
  不是当前指令向保护段写入或执行。具体哪个上游指针损坏、实际 fault
  原因和寄存器值尚未证实，不能仅以地址确定根因。
* PC 与 LR 均属 **libobjc Objective-C runtime**，不是 LaunchServices、
  Foundation 或 libsystem 的函数。LR 位于 `objc_storeStrong`，与 retain
  路径相容，但此处未以反汇编证明精确调用关系。
* 之前可见栈中的 `-[ISIconManager _init]` 和
  `__31+[ISIconManager sharedInstance]_block_invoke` 不等于本次
  `objc_retain` / `objc_storeStrong`；本次只有 PC/LR，未给出更外层调用栈，
  不能判定与 IconServices 有关或无关。
* 静态符号、指令、段表和算术为 **self-checked**；设备现场是未经原图
  核对的 vision 转录，运行时缓存及主映像身份为假设，未访问设备、
  未执行构建或提交。
