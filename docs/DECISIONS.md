# D-001 · 物理内存窗口按 boot_args 单窗口声明，首选主 bank（0x8c0000000 / 9216 MiB）

- 状态：**accepted**（宿主依据代码与实测定，2026-10-22 02:55）
- 否决的原提案：`NEED-REVIEW.md` R-001 的 A / B / C 三选一（那份题面把问题问错了）
- 证据基线：`docs/inherited/nuwa-observed.json`、`docs/inherited/meminfo.txt`
- 代码基线：`D:\Code\PortingiOS\common\sources\xnu-ios16-full`（只读）

## 1. 结论

1. **窗口只能是一个连续区间** —— 不是策略选择，是内核代码写死的。
2. 因此 **C（全 14 段）在当前 pmap 下不可实现**，直接排除；它不是「改动量大」，是需要重做 physmap。
3. **首选 B**：`gPhysBase = 0x8c0000000`、`memSize = 9216 MiB`。这不需要改 pmap 一行代码，改的是 loader 填的 `boot_args`。
4. **A 按提案原文是错的**：低 4 GiB 区间并不连续，`0x80000000` 起 2 GiB 这个区间根本不存在（见 §3）。若 B 的装载位置验证不通过，退路是 **A′ = 0xa4a81000 起 768 MiB**（低区最大连续块），代价是只能跑到内核起来，用户态必然 OOM。

## 2. 代码证据：单窗口是硬约束

`osfmk/arm64/arm_vm_init.c`

```
1832:  gPhysBase = args->physBase;
1834:  real_phys_size = args->memSize + (shadow_ptop - shadow_pbase);
1836:  real_phys_size = args->memSize;
1961:  real_avail_end = gPhysBase + real_phys_size;
```

```
378:  if (__improbable((pa < gPhysBase) || ((pa - gPhysBase) >= real_phys_size))) {
380:      panic(...pa, gPhysBase, real_phys_size);
382:  return pa - gPhysBase + gVirtBase;
```

- `gPhysBase` / `real_phys_size` 全部来自 **`boot_args`**，所以选哪个窗口是 **loader 的事**，不是 pmap 的事。
- `pa < gPhysBase` 也会 panic：**内核自身、boot_args、ramdisk 必须都落在窗口内**。这一条决定了 B 能不能用（见 §4）。
- physmap 只有 `[gPhysBase, gPhysBase + real_phys_size)` 一个区间，落在窗口外的 DRAM 段无法进入 physmap。多段 DRAM 需要重写 physmap，不是加个字段。

## 3. 实测：低 4 GiB 是碎片，不存在 2 GiB 连续块

`nuwa-observed.json` 的 14 段里，4 GiB 以下共 11 段，最大的单块是：

| 区间 | 大小 |
| --- | --- |
| `0xa4a81000 – 0xd4cfffff` | 768 MiB ← 低区最大连续块 |
| `0xe7cb0000 – 0xff7fffff` | ≈379 MiB |
| `0x82800000 – 0x8a7fffff` | 640 MiB |
| 其余 8 段 | 均 < 130 MiB |

`0x811d0000` 是 DRAM 起点，不是 `0x80000000`；`0x811d0000` 到 `0xffffffff` 之间被 bootloader 保留区切成 11 段。
所以 A 的「0x80000000 起 2 GiB 连续窗口」既起点错、也不连续 —— 按它声明会让 physmap 把保留区当普通 RAM 用。

能给出「够大且连续」的只有一段：`0x8c0000000 – 0xaffffefff` = **9216 MiB**。

## 4. PA 位宽不是障碍（R-001 高估了这个风险）

`osfmk/arm64/proc_reg.h`

```
972:  #define TCR_IPS_VALUE TCR_IPS_42BITS     // __ARM_42BIT_PA_SPACE__
974:  #define TCR_IPS_VALUE TCR_IPS_40BITS     // 默认
```

40 位 PA = 1 TiB 寻址。`0x8c0000000` 是 36 位地址、`0xaffffefff` 是 36 位顶端，**离 40 位上限还有 4 位余量**。
`gPhysBase` / `pa` 在代码里是 `unsigned long long`，无 32 位截断点。
→ 「基址在 35 GiB 需要改 pmap」这个担心不成立；要改的是 loader 侧的装载地址与 `boot_args`。

## 5. B 的真实门槛（这是下一步唯一要验证的事）

B 成立的前提是：**loader 能把 kernel + boot_args + ramdisk 全部放到 ≥ `0x8c0000000`**，否则 §2 第 378 行的 `pa < gPhysBase` 立刻 panic。

验证方法（离线可做，不需设备）：
1. 查 boot image header 的 `kernel_offset` / `ramdisk_offset` / `tags_offset` 是否支持 64 位地址、能否被设到 `0x8c000000+`；
2. 查 ABL 是否限制 payload 装载窗口（在 `docs/inherited/iomem.txt` 之外，看 UniXNU 的 loader 代码与 nuwa 的 dtbo/boot 配置）；
3. 若两者都允许，写 B；若任一不允许，退 **A′（768 MiB）** 并把「用户态内存不足」记为已知限制，不要为了凑容量去改 pmap。

## 6. 对 R-001 的处置

- R-001 由本决策**结案**，`NEED-REVIEW.md` 里标 `answered by D-001`。
- 不再向用户问 A/B/C。若 §5 的验证结论与本文冲突（例如 header 只支持 32 位 offset），按 §5 退 A′，并在 `DECISIONS.md` 追加 `D-002` 说明推翻理由 —— 这是技术事实更新，不是重新征询意见。
