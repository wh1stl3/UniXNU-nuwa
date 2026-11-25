# nuwa Data v3 接入（2026-11-26）

单核主机候选，**self-checked**。未运行设备命令、未刷写。生产 Data mode 2 仍拒绝开窗，持久 Data 未达成；实验 CHMH 不是认证。

## 接缝与几何

- `NativeRamBlock::attachStore()` 的 `NUWA_DATA_CANDIDATE` / mode 2 使用 `DualBankLogOverlay<>`。固定 2,097,152 页；`overlayBlocks(pages)` 返回 4,195,074 块，其他页数返回 0。`native_ufs_store_open()` 不改：`end = last + 1 - reserve = 61,588,475`，`first = end - blocks = 57,393,401`。staged 实际入口在 host fixture 里断言该区间；只在正例替换硬件准入为模拟介质。mode 1 仍用原窗口。
- `attachStore()` 另配 256 KiB 去重 scratch，`open()` 返回即释放；保留 512 KiB 双 bitmap、两个 4 KiB 工作页及原 128 KiB stage。成功恢复或提交回填 `native_data_persist_present`。磁盘格式见 [v3 规范](nuwa-dualbank-spec-20261126.md)，不迁移旧格式。
- `doAsyncReadWrite()` 在既有 RamBlock gate 内每次暂存最多 32 个连续页，首尾不足 4 KiB 才 RMW；整页覆写不读取旧页。单次 `writeRun()` 成功后才累计该批字节。描述符短读不提交当前批；overlay I/O 失败锁存 `directFailed/state=5`，同句柄后续写和 sync 拒绝，重复 attach 不重开。`doSynchronizeCache()` 在同一把 gate 下读取该状态，不发硬件命令；未改 UFS 锁或锁序。
- `Provider<CandidatePort, false>`、`fuaProvenLocked() == false`、空 cold-start 证据原样。最终紧凑 `kernel.macho` 的 `_native_ufs_store_write` 只解析 args、取/放既有锁后返回 0，`_native_ufs_store_sync` 只解析 args 后返回 0；开窗函数没有硬件提交调用，镜像中无 `RetainedWritePort`/`writePageLocked` 符号，可见 v3 `open` 和 `candidateIO`。

## 主机复跑与结果

用 [单核 crashcap 配方](nuwa-crashcap-20261125.md#reproduction)，构建附加 `--pixsig --data-persist-diag --data-candidate-gpt ../.cache/device-evidence/20261107-recovery/gpt-sda.bin`。打包和独立 `--audit-only` 均附加 `--data-persist-diag`，不加 `--ufs-desc`。选仓内真实 `out/` 下的新 `B`/`P`；打包器不接受解析后位于其他仓的输出或 kernel。基座钉 `693f5d9cae8a408dd18b39f3f9fdc4228c934241`，查得上游 HEAD 构建前后均为 `e7bddb9a7eecdcf81f36da9fa38bd9d4d3f155c2`，未采用。

```sh
"$PY" -B tests/test-nuwa-retained-entry.py "$B" "$BASE"
"$PY" -B tests/test-nuwa-data-persist.py "$BASE"
"$PY" -B tests/test-nuwa-crashcap.py "$B/kernel.macho"
c++ -std=c++17 -Wall -Wextra -Werror -pthread -fsanitize=undefined \
    -fno-sanitize-recover=all tests/test-nuwa-data-write.cpp -o "$B/test-nuwa-data-write"
"$B/test-nuwa-data-write"
llvm-objdump -d --disassemble-symbols=_native_ufs_store_open,_native_ufs_store_write,_native_ufs_store_sync \
    "$B/kernel.macho"
llvm-nm -C "$B/kernel.macho"
fsck.fat -vn "$P/readback-fat.img"
mdir -i "$P/readback-fat.img" ::/EFI/UniXNU/Payloads
```

独立 overlay 九类 ASan/UBSan 用例按 [规范配方](nuwa-dualbank-spec-20261126.md#自检) 复跑；37 项 Data/冷启动回归、PU1 几何和 linked crashcap 均通过。同一 staged retained fixture 其余 42 项也通过；新增输出：

```text
PASS RamBlock first write and full overwrite: bank 0/1, overwrite reads=0
PASS RamBlock 32-page batch: one log, partial edges preserved, one media RMW read
PASS RamBlock state=5: write/sync/reopen refused, extra submissions=0
PASS RamBlock checkpoint recovery: old batch across bitmap-block boundary, present=33
PASS RamBlock 1-page amplification: 2.251953x
PASS RamBlock 32-page amplification: 1.039124x
```

恢复正例在 present/active 两张图的 32,768 页边界两侧设置活动位，checkpoint 后使下一批数据落盘但日志未落盘，再用新实例恢复，逐字节比对旧批数据。

## 包与边界

`out/nuwa-dualbank-20261126-package/vendor_boot.img`（100,663,296 B）。outer/FAT 回读只替换 kernel 和 ADT 中重绑的 CHMH；561 B args、seed、trust 不变，未加 SMP。Python audit 与 `fsck.fat -vn` / `mdir` 同意，FAT 剩余 **11,038,208 B**。

| 产物 | 哈希 |
| --- | --- |
| Kernel SHA-256 | `121f20bf6ae8a979b68f21bb87f9170a491071796092d368bf5a72fdd693b665` |
| Outer SHA-256 | `f3b6c8ccfffbaa2c6f7055b4573fb09ad2cdea8c9e25e0409f6c0f4935090ae7` |
| CHMH SHA-384 | `0165e21b201e2db38ebebd8ff0d525cebf65a506da2d297e3d1be623d2d83ca30372366186739ea96d7396c1807a72ad` |
| 回读 FAT SHA-256 | `54ee847cb9101af68902b55f9e22b4aa5d4003c0300143a2372a0ddbf0149c69` |
| Seed SHA-256 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

未完成：独立 verifier 复跑、RamBlock gate/status 改动的 deep review、真实 UFS 的断电/FUA/冷启动资格及持久交互。包只留本地 `out/`。
