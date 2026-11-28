# nuwa retained v1 r3：挂接失败传播

**构建时 self-checked；未接设备、未刷写。** 后续终审及单次刷写见 [观察](nuwa-v1-retained-reset-flash-20261128-observation.md)。r3 替代 [被退回的两个 r2 outer](nuwa-v1-retained-20261128.md)。设备工作树基座 `a8ba7129742ae3e16c8c0edd7924ae9929078a9f` 加本轮修改，构建 pin 和模板同 r2；UniXNU 与 nuwa 远端 HEAD 前后未变。

## 修正及证据

`NativeRamBlock::attachStore()` 在既有 gate 内复用 `directFailed`：v1 mode 2 请求在 window 或 Overlay 挂接失败时保留错误，`Kept` 或成功挂接时清除。未尝试挂接和 `Kept` 仍是成功的空同步；挂接失败即使 `direct` 未激活，`doSynchronizeCache()` 与转发的 `doSynchronize()` 也向 online 调用者返回 `kIOReturnIOError`。失败分支在进入 retained 之前返回；没有更改上游算法、reset 顺序、传输、导出或锁。

fixture 将实际 `attachStore()`、`StoreOps`、`doSynchronizeCache()` 和 `doSynchronize()` 编译到主机 shim，连接实际 staged encoder / response parser 与 retained store。故障在模拟完成处注入。补丁前两个定向 case 均在期望 `kIOReturnIOError` 的断言中止（fixture 子进程 `SIGABRT`）；r3 全部 12 case exit `0`。

| 输入 | r3 主机观察 |
| --- | --- |
| 第一次 reset sync 返回 CHECK CONDITION | 64 条 bitmap FUA 写后 `0x35` 失败，不写 header；挂接状态 4、overlay inactive。 |
| 第二次 reset sync 返回 CHECK CONDITION | 64 条 bitmap FUA 写、首次 `0x35` 成功、FUA 写 header、第二次 `0x35` 失败；同样状态 4、overlay inactive。 |
| 首次 sync 超时 / 错 tag | 分别为 `TIMEOUT_ORPHAN` / `FATAL_QUARANTINED`，不写 header。 |
| 上述四种失败之后 | 重调 `attachStore()` 不复挂；两个 IOKit 同步入口均 `kIOReturnIOError`，新增 UFS 提交及 retained host-lock 获取均为 0。 |
| 未挂接 / `Kept` / reset 成功 | 前两种同步仍成功且不进入 UFS；reset 成功后的 IOKit 同步实际提交一条额外 `0x35` 并成功。 |

最终 Mach-O：`doSynchronizeCache` 在 `0xfffffff0079c3314` 读取 `directFailed`，`0xfffffff0079c3318–331c` 装入 `0xe00002ca`，`0xfffffff0079c3320` 跳过 `0xfffffff0079c332c` 的 `_native_ufs_store_sync` 调用。重新核对 `write10` 在 `0xfffffff0079b0788–078c` 写 `0x082a`（LE `2a 08`），`CombinedRead::issue` 在 `0xfffffff0079afcfc–fd00` 写 opcode `0x35`；33 页 `writeRun` 与 root 同锁的主机断言仍通过。

## r3 产物

共用 kernel `out/nuwa-v1-retained-20261128-build-r3/kernel.macho` SHA-256 `9556939f42341590f9fa1a8a7996776f0aa75d8687d5672f6f0e2548ee9e7682`。

| | 日常 `out/nuwa-v1-retained-20261128-daily-r3/` | reset `out/nuwa-v1-retained-20261128-reset-r3/` |
| --- | --- | --- |
| args bytes，不含 NUL | 580 | 599 |
| outer SHA-256 | `25eed03ccca975d6fad9d2cb743a2b3ba47cef45f7c66fecf96457f771f47180` | `213cdf065fe5eab45215f96c2efb12a8c320d51a4efadfcd586dd71140dd942d` |
| FAT SHA-256 | `03b4afc0754f61d3bd5439027b4c7b6f144993543b8aac805e81988a0ee1b9bd` | `7390a39d482ad692906f4a8d6e03b54ec3212036a7f2c4af630465a8a3b5c88f` |
| CHMH（SHA-384 值） | `a91250c1c0f4eb1cea6c00443f8310d1e567ac2a82083600648dfeadf49745717046015d3848998238b606d9fca207bb` | `d5af876369ea4e125acdf59e51859ffc6cd823df62161e70ff75d525c086f8f36513a7e4c377eec5370e716c339e8031` |

日常和 reset 分别对对应 r2 的 `unixnu.toml` 运行 `cmp`，均 exit `0`，重新绑定各自 CHMH。均 `device_release=false`；后续终包审查见上述观察，硬件介质持久性仍未验证。

## verifier 复跑

沿用 [r2 复跑命令](nuwa-v1-retained-20261128.md#复跑)，`b` 换成新的 build 目录，打包循环 `output` 换成新的日常/reset 目录。r3 本轮 rebuild、ASan/UBSan retained 12 case、post-event、双包 build + audit-only + `fsck.fat -vn` 均 exit `0`。另复跑以下两个历史 profile，均 exit `0`：

```sh
$p -B tests/test-nuwa-v1-entry.py "$base" \
  out/nuwa-v1-shape-20261128-build/nuwa-data-provider/{NativeUfs.cpp,CombinedRead.h}
$p -B tests/test-nuwa-retained-entry.py out/nuwa-no-glyph-20261128-build "$base" \
  --disposable --output out/nuwa-v1-retained-sync-r3-disposable-recheck
```
