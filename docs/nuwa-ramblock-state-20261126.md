# nuwa RamBlock Data 视图与拒写修正（2026-11-26）

**主机候选，生产写门关闭。** 使用前一轮 MODE SENSE 的参数；未运行设备命令、未刷写。

## 三项修正

1. `NUWA_DATA_CANDIDATE` / mode 2 明确区分 `seed`（未开窗或空窗未创建）、`ro`（恢复但不可写）、`rw`（已准入可写）、`iso`（视图/介质不可用）。`seedInfo()` 只给 seed 身份与大小；`reportWriteProtection` 和 `doSynchronizeCache()` 不把 seed/ro 报作可持久写。PU1 显示 `v=seed|ro|rw|iso`，保留原因和 LBA；旧模式格式不变。
2. 不可写在读描述符/RMW 前以 `NotWritable` 拒绝，无媒体写、无 state=5。已准入写失败或 UFS 已报告 transport 隔离才锁存 state=5；不具备可恢复元数据仍拒绝开窗（state=4）。单次已归属的读错误返回 I/O 错误，不把该块改读 seed；隔离后不继续访问。非 LUN0、错窗和多块的底层拒绝未消耗读能力。
3. `NativeRamBlock::start()` 在 `online` 与 `registerService()` 之前确定 mode 2 视图；`selectVolumeSeed()` 的兼容 attach 已是幂等操作。UFS `startRoot()` 在发布根块服务前已经设置 `gStoreGeometry`；显式 RamBlock 工厂由 `nuwa_data_mount_prepare()` 启动。真实源码中先 publish，IOStorage/APFS 才能探测该块设备；同一媒体的第一次可读请求不再看到 attach 前的 seed 视图。fixture 使用同一块 seed `0x5e`、恢复页 `0x42`，比较模拟首次探测和 UUID 查找后从驱动读取的字节。真实 APFS 挂载及缓存行为未运行，不宣称闭合。

锁方向静态核对：RamBlock `gate → native_ufs_store_* → gHost.lock`；只读隔离查询只取现有 host 锁、读取软件标志。`retainedReadLocked`/`retainQuarantineLocked`/`blockRetainedHostLocked` 不回调 RamBlock。根 `NativeUfsBlock::doAsyncReadWrite` 的 completion 在 `ufsReadWindow()` 返回、window/host 两锁均释放之后调用；RamBlock 的 completion 也在释放自身 gate 后调用。未更改 UFS 队列、DMA、锁序或写资格。

## 主机 fixture 和时延

```text
PASS blank/no-create: NotWritable before RMW; read remains seed, no submission
PASS read-only recovered view: first probe and post-lookup bytes=0x42, seed=0x5e; reject write/sync
PASS attributed read error preserves overlay view; transport quarantine isolates without seed fallback
PASS non-LUN0, wrong window and multi-block reject before DMA; subsequent read works, in-flight sync rejected
PASS PU1 distinguishes seed/ro/rw/iso within 47 columns
PASS RamBlock state=5: write/sync/reopen refused, extra submissions=0
```

GCC 11.4 `-O2`、ASan/UBSan、WSL、固定一个主机 CPU。五次采样，满环是 512×32 个唯一页；checkpoint 和 steady 都提交 32 页。

| 项目 | 介质模型动作 | p50 | 最大 |
| --- | --- | ---: | ---: |
| 满环恢复 | 验证 16,384 个最新页，恢复零写 | 510.361 ms | 514.857 ms |
| 普通提交 | 33 写、2 barrier | 0.932 ms | 0.972 ms |
| 碰环满的 checkpoint + 提交 | 162 写、4 barrier | 5.041 ms | 5.738 ms |

这是稀疏内存介质计时，不代表 UFS 尾延迟；断电注入与写放大回归仍分别覆盖。

## 复跑

沿用 [MODE SENSE 单核配方](nuwa-ufs-modeprobe-20261126.md#复跑)；打包和 `--audit-only` 均保留 `--ufs-desc`，对比前一轮 FAT 中 `unixnu.toml`。再按 [overlay 自检配方](nuwa-dualbank-spec-20261126.md#自检) 跑含时延的 `test-nuwa-dualbank.cpp`，并运行 `tests/test-nuwa-data-persist.py "$BASE"`。检查最终内核 `_native_ufs_store_write/_sync/_isolated`、RamBlock publish 顺序和 `porting-record.py check`。

最终构建的 staged fixture 62 项、PU1、overlay ASan/UBSan、linked crashcap、反汇编和 outer/FAT 审计均 **self-checked**。反汇编中 write/sync 返回 0，isolated 仅调用既有锁；未链接真实写后端。UniXNU 上游 HEAD 前后 `e7bddb9a7eecdcf81f36da9fa38bd9d4d3f155c2`，未改 pin。

## 产物与未闭合项

`out/nuwa-ramblock-state-20261126-package/vendor_boot.img`（100,663,296 B）。同 MODE SENSE 包回读的 `unixnu.toml` 逐字节一致，args 577 B，seed/trust 不变，重绑实验 CHMH；FAT 余 **11,005,440 B**。

| 产物 | 哈希 |
| --- | --- |
| Kernel SHA-256 | `d1c53987f9459459872d39dbd6ec5886f94bbd086c9251c984ab83c04980aa88` |
| Outer SHA-256 | `f8cc47cf94b945003bd8206b13d76a63d0df7d8431b84d5d5715564b570ef482` |
| CHMH SHA-384 | `b1ed45f1f7a39da801bc4f292a89454b8458d05140329c81f01f03aa0ff475fecab1b7e5ef113dc4581c24f7f3328102` |
| 回读 FAT SHA-256 | `49f31e7f557221d9b3fd000b45507d57aed88ab0498f5c4238af3706a71fe6f3` |
| Seed SHA-256 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

挂载请求的只读策略未变；未在真实 APFS 上观察首探、缓存或挂载结果，也未验证 UFS 的 FUA 持久性与时延。未独立复跑，锁方向与状态修正待 deep review 复核。不主张持久 Data 或认证达成。
