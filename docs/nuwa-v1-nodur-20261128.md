# nuwa retained v1：V1-NODUR

**主机 self-checked，未接设备、未刷写。** 主控转述 r3 到 `DATA0 st=4 ro=0` 后 `tzinit` 以 EIO 退出并 panic；缺实际失败 CDB，不能区分 FUA 与 flush。本轮只供界面 bring-up，不是持久化验收。

**NODUR r2 替换初版两包。** deep_reviewer 退回初版日常 `12e3bfd3…2e2be5`、reset `a2dcbd30…d86f43`：`getWriteCacheState` 返回成功并写 `false`，按 `IOStorageFamily-67f9003c/IOBlockStorageDevice.cpp:51–59` 等价于报告缓存已关闭，而当前没有该证据。r2 仅对 retained NODUR 返回 `kIOReturnUnsupported` 且不改输出；disposable 既有 Unsupported 和其他 profile 不变。`StoreOps` 注明上游 FUA/durable 前提不成立，计数仅反映命令完成。

`--data-v1-retained` 沿用同一 retained Slot 0，`WriteVolatile` 提交 `2a 00`，单条最多 32 个 4 KiB 块。同步在原 host lock 内排序并复核已打开窗口、slot/host 健康与归属；不暂存、不新提交，不发 `0x35`。上层 FUA 和 flush 请求照收；store 不健康或 mode-2 挂接失败经两个 IOKit sync 入口返回 `kIOReturnIOError`。未请求挂接及保留不匹配 v1 header 的 `Kept` 仍走原先的空同步。屏幕（含 panic 安全带）和 `audit.json` 标注 `V1-NODUR`。

上游 `PersistOverlay` mode 2 未改，先完成数据命令再置位并写 bitmap；reset 先写 bitmap，再写 header。这只是主机命令次序，**掉电可能丢失最近写入，且已存在页原地覆写可能撕裂**；也不承诺介质上 data/bitmap/header 的相对落盘次序或 reset 原子性。LU0 窗口 `[59491258, 61588475)`、seed、双 GPT、旧格式隔离和失败即停不变；无 ABI、锁实现、DMA/IOMMU、额外提交者变更。复用 `UniXNU/drivers/RamBlock@4be2d7eb05ef5a98126c91e0302c149140c0e3e1`（BSD-2-Clause-Patent），以及本仓已有 disposable `WriteVolatile` / `FullWrite` 和 order 检查模式。

## 产物

目录前缀 `out/nuwa-v1-nodur-20261128-`，两包共用 `build-r2/kernel.macho` SHA-256 `1fec715e6a76d6adf02b8db8ca9e8070542b7c4fd8475930168aba277633f97b`。

| | `daily-r2` | `reset-r2` |
| --- | --- | --- |
| args ASCII 字节，不含 NUL | 577 | 596 |
| `vendor_boot.img` SHA-256 | `f38386adf86b45731af251a8ad95d3abceca0f67f6437148821b53345397aba8` | `a7bbfff6f0f858344b945a0e3e291e8859f11f883446d1650c2c257b2158e15d` |
| `readback-fat.img` SHA-256 | `a87358c3508eabdfd976bbdfd75d9321beaa0048b380fbc486f3746bf42dc9b0` | `1b599bd7a3b85ac633c75023b06206cf9af62a6650487af801080b47acba240c` |
| CHMH（SHA-384 值） | `ff6b45b91dfc19445b1ccf011ad97180fbb926347bedcde4f4d126ed81fc155f90ded1c78db7c403f3052cb4d7308d3f` | `df6c237c93cba7ad0c0c30ecbb49839447a3f5f9d1ab10d20d532962ff56094a66ec9e460a7372458820be0799d0d8b9` |

日常 args（FAT 回读）；reset 仅追加 ` sheng-data-reset=1`，不是自清除，重复启动 reset 包会再次请求清空 overlay。

```text
-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1 build-tag=V1-NODUR boot-progress-scale=3 sheng-data-persist=2 sheng-log-reserve=1024 offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1 offline-legacy-transfer=1 offline-legacy-cpu-present=1 nuwa-lite=1 nuwa-mg-reset=1 nuwa-hid-standin=1 nuwa-sb-stack=900 disable-jobs=com.apple.iconservices.iconservicesagent nuwa-ufs-neon=1
```

模板 pin、seed 与 trust 不变；FAT 仅 kernel、ADT、配置不同。CHMH 分别重绑，不是认证证据；`device_release=false`。主控转述 `deep_reviewer` 对 NODUR r2 的终审为 **PASS WITH CONDITIONS**（会话 `ses_ddec18ea7ffeyB65Dqk9L1P4Im`），要求优先 daily；不是“方案 B 审查，未经 deep_reviewer”。独立 verifier 尚未复跑。

## 主机轨迹与复跑

`out/nuwa-v1-nodur-20261128-build-r2-retained.log`：17 个 ASan/UBSan 情形 exit `0`，录到 199 个 `2a 00`（含故障提交），无 `0x35`。getter 测试从实际源码提取方法并使用真实构建宏，验证 `Unsupported` 且输出初值为 `false` 或 `true` 时均不变。最终 Mach-O 在 `0xfffffff0079c3424`–`0xfffffff0079c342c` 仅执行 `mov w0,#711; movk w0,#57344,lsl #16; ret`（`0xe00002c7`），无内存写入。

```text
writeRun: 2a 00 LBA=59491332 n=32 -> LBA=59491364 n=1 -> LBA=59491259 n=1 (bitmap)
FUA 请求: 2a 00 LBA=59491332 n=1 -> dispatch/completion Success, 4096 B
reset:    2a 00 LBA=59491259..59491322 n=1 -> order -> 2a 00 LBA=59491258 n=1 -> order
```

健康 sync 返回成功，零预备、零提交、tag 不变。故障注入覆盖 root 超时、错误完成 tag 产生隔离、归属寄存器改变、reset 写 CHECK CONDITION、reset 两个排序点归属丢失；各 sync 失败均零新提交。越窗、错包 seed、日常错 v1 header seed、两种旧格式、任一 GPT 错、root/log 重叠均零写。最终 Mach-O 反汇编：`CombinedRead::issue` 在 `0xfffffff0079afcfc` 调用 `write10`，`0xfffffff0079afd00` 清 CDB byte 1 后复制；`native_ufs_store_sync` 在 `0xfffffff0079ab740` 调归属 guard，不走 `issue`。

复跑 [retained r3 命令](nuwa-v1-retained-20261128.md#复跑) 的 build、`test-nuwa-v1-retained.py`、`test-nuwa-postevent.py`、两包 package / audit / `fsck.fat -vn`，更换新输出目录；构建参数和模板不变。NODUR r2 构建、post-event、反汇编、两包 package / audit / FAT 检查、两份配置相对初版的 `cmp` 与 porting-record (`--base origin/main`) 均 exit `0`。初版通过的独立源级 `test-nuwa-data-write.cpp` Gate 回归输入未变。UniXNU build pin `693f5d9cae8a408dd18b39f3f9fdc4228c934241`；UniXNU、nuwa 远端 HEAD 前后分别为 `fdf81eaa832ce5c850d3c53c698407aa722a4653`、`fe6b859367cc7b0641e9ae7dda46d8b5c6fc4fb0`，未合并。设备基座 `1851aa7`。
