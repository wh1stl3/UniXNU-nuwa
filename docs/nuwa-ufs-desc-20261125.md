# nuwa UFS 描述符：传输可行性（2026-11-25）

**历史阶段：按「只发 UIC」的边界不可实现；当前实现见下文。**
UFS device/unit/configuration descriptor 是 UFS device management 数据，
不是 UniPro DME attribute。没有公开、已验证的 UIC `GET_DESCRIPTOR`
opcode；不能把 Query opcode `0x01` 写入 UICCMD，它在那里是 **DME_GET**。

## 静态证据

公开参考为 [Xiaomi fuxi-t-oss `7fad87dc178d09489b74a714e4a525d56f546855`](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/7fad87dc178d09489b74a714e4a525d56f546855/drivers/scsi/ufs)，未移植代码。

| 通道 | 源码依据与边界 |
| --- | --- |
| UIC / DME | `ufshci.h:47–50,122,149–154,254–288`：`UICCMD/ARG1/ARG2/ARG3` 为 `0x90/94/98/9c`，HCS.UCRDY bit 3，IS.UCCS bit 10，结果在 ARG2 低 8 位。`ufshcd.c:2282–2399,3938–4001` 中 DME_GET/PEER_GET 是本地/对端属性访问，GET 值来自 ARG3，并不返回描述符。 |
| UTP Query | `ufs.h:76–86,168–170,395–397`：Query Request/Response 为 `0x16/0x36`；Query `READ_DESC=0x01`、`READ_ATTR=0x03`，device/configuration/unit IDN 分别 `0/1/2`。`ufshcd.c:2583–2654,2992–3027,3246–3305`：`READ_DESC` 走 `DEV_CMD_TYPE_QUERY`，构造 UPIU 后由 `ufshcd_send_command` 提交 transfer slot；`3424–3443` 检查响应 IDN 和描述符长度。 |
| 本地实现 | `ShengUfs@f020bd693c34790c04e97c52720af3cd842336fb/NativeUfs.cpp:1819–1843` 有 `native_ufs_dme_get`，会写 IS.W1C 及 UIC 寄存器。它不是当前候选的入口；其前置裸读 `gHost.ready` 和 UIC timeout/迟到完成处理也不符合 retained 边界，不能直接移入。重新核对的 retained r8 `CombinedRead.h:61–63,117–133,158` 已有通过 UTRL/slot 0 的 `READ_ATTR(CurrentPowerMode)`，但没有 `READ_DESC` 或 UIC sender。 |

## 目标字段

以下为字段来源，不是本机实测；短描述符不得按零处理。

| 字段 | 来源 |
| --- | --- |
| `bNumberLU`、`bBootEnable`、`wManufacturerID` | device descriptor `0x06`、`0x08`、`0x18`（厂商 ID 为 BE16）；`ufs.h:219–235`。 |
| `bLUEnable`、`bWriteProtect`、`bLogicalBlockSize`、`qLogicalBlockCount` | unit descriptor `0x03`、`0x05`、`0x0a`、`0x0b`（块长为 2 的指数，块数 BE64）；`ufs.h:191–199`。`ufshcd.c:3576–3587` 区分一般 LUN 和 RPMB；不能仅按 `bNumberLU` 假定连续的 LUN 索引，也不应触及 well-known LUN。 |
| `cache`、`fua` | 未找到可据 configuration descriptor 确认的位，保持 `unk`。同一 Xiaomi pin 的 `drivers/scsi/sd.c:2687–2816` 从 SCSI MODE SENSE caching page 的 WCE、模式参数头的 DPOFUA 获取声明；是另一条 UTP/SCSI 路，DPOFUA 也不证明掉电持久性。 |

## 锁与启动影响

如果后续允许 UTP，推荐扩展现有只读 Query 路径，而不是新建 UIC
sender。发出 `READ_DESC` 前须持 `gHost.lock`，确认 retained domain、
slot 和 DB 均符合现有 guard；同一把锁覆盖提交至归属验证。它不写介质，
但会改写共享描述符并占用根读的唯一 transfer slot。timeout、fatal 或
无法归属的响应必须保留 DMA、隔离队列；不能保证这种故障之后根读仍继续。
只有确认所有权归还的非致命协议/解析失败才可以仅记诊断码。若必须保证
诊断故障不影响根读，需独立、已资格化的队列/域或外部预采集；现有
retained provider 不具备该保证。

## 只读 UTP 候选（self-checked）

`DescriptorPort::read_descriptor` 只接受 device IDN `0` / index 0 或 unit
IDN `2` / 一般 LUN `0…31`，不用 well-known LUN。持 `gHost.lock`，
经 `CombinedRead::issue` 和既有 ownership guard/DB bit 0 提交 Query
UPIU `0x16`、standard read、opcode `0x01`、selector 0；长度上限 255，
无 PRDT/写 payload。应答 UPIU `0x36` 必须匹配 type/LUN/tag、Query
opcode/IDN/index/selector 和长度；仅在全归属完成、仍持锁时从 response
UPIU offset 32 复制。参考同一 Xiaomi pin 的 `ufshcd.c:2190–2216,2583–2619,3246–3305`
和 `ufs.h:421–430`。没有 UIC 命令或介质写。

设备拒绝且响应归属完整（如 `0xfe`）走已归属命令错误；短而归属明确的
描述符仅记解析码。超时、坏 tag、长度不归属、fatal 或坏 OCS 走已有
隔离，保留 DMA，不重放、不继续根读。UFS 错误行 `err=3` 表示已归属
Query 拒绝（`q` 为结果），`4` 为归属不明，`5` 为 timeout，`6` 为
字段/最小长度不合格，`7` 为未找齐设备声明的活动 LUN。无新 panic。

只在根窗口发布完成后且 `nuwa-ufs-desc=1` 时执行一次；无参数或非 1 的
值不访问硬件。发布完成条件不变，但故障隔离仍会拒绝后续根 I/O。
读取 device 后按升序浏览一般 LUN，直到找到设备声明的活动 LUN 数，
不把 `bNumberLU` 当成连续索引；跳过已归属的 `INVALID_INDEX (0xfc)`。
缓存 `bootEnable`、厂商 ID、每个 LUN 的 enable/WP/块长/块数；横幅只
显示一条摘要：`lu` 为声明的 LUN 数，`bs` 为 LUN0（缺则 `unk`），
`wp` 为 `bWriteProtect != 0` 的**配置** mask，不代表当前生效保护。
`mfr` 为 4 位十六进制厂商 ID；cache/FUA 不输出。渲染器只读 release/acquire
发布的不可变缓存，UFS 摘要/错误行与 PROC 同级，不执行 I/O，≤78 列。

实际 UBSan fixture 输出（候选的 Query->slot 路径，模拟硬件）：

```text
PASS READ_DESC default and invalid opt-in: no MMIO, no row
PASS READ_DESC invalid and well-known LUNs rejected before MMIO
PASS READ_DESC opt-in once: 5 read-only Query UPIUs, UFS lu=2 bs=4096 wp=00000008 mfr=01ce
PASS READ_DESC query result FE: UFS err=3 q=fe, next root=allowed
PASS READ_DESC short descriptor: UFS err=6 q=00, next root=allowed
PASS READ_DESC oversize envelope: UFS err=4 q=00, next root=isolated
PASS READ_DESC wrong tag: UFS err=4 q=00, next root=isolated
PASS READ_DESC timeout: UFS err=5 q=00, next root=isolated
```

42 项入口、37 项 Data/冷启动、12 项 re-init 模型通过；linked crashcap、
反汇编与 outer/FAT audit、`fsck.fat -vn` 均 self-checked。反汇编确认
`read_descriptor` 在 host 锁内调用 `CombinedRead::issue`；缓存行仅
执行格式化，`native_ufs_store_write/sync` 无硬件调用，未链接独立写后端或
UIC sender。真实描述符内容未测。

## 离线候选与复跑

单核 `out/nuwa-ufs-desc-20261125-package/vendor_boot.img`，100663296 B；
args 561→577 B，仅追加 ` nuwa-ufs-desc=1`。仅 kernel、其重绑 ADT
CHMH、FAT `unixnu.toml` 改变；seed/trust 不变，FAT 余 **11042304 B**。
UniXNU 上游 HEAD 构建前后均为 `b04f131da9151182dbb26ce4e638fa8acc2933ac`；
未改本地 pin。未访问设备、未刷写，写门关闭。

| 产物 | 哈希 |
| --- | --- |
| Kernel SHA-256 | `d8ff9cb25ac2591fca38ef5218a676e308a099c5e89573132e3b049ce94a867a` |
| Outer SHA-256 | `434a58a9d35f9d005df28adb4eb9cf26c6c7fb2903e4c1e21f599fc335da2c3c` |
| CHMH SHA-384 | `245366ca44855a0a1bac9a7723ee9b3d4cdd0a0c762caea28d0eb2f9b7bcdac0f31a3010ebc23f8e58d644ea9b0dbae4` |
| 回读 FAT SHA-256 | `51bcd9c0709e6d0cd17c21102778b1e2437cf116d9b2a22b72d0cf7e8ce5ea02` |
| Seed SHA-256 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

沿用 [Data 候选单核配方](nuwa-data-write-design-20261125.md)，用 fresh
`B`/`P`（本轮 build `out/nuwa-ufs-desc-20261125-build`）。build 参数
不变；`package-nuwa-crashcap.py` 打包和 `--audit-only` 都增加
`--ufs-desc`。复跑 `tests/test-nuwa-retained-entry.py "$B" "$BASE"`、
Data/re-init fixture、linked crashcap、反汇编和 FAT 审计。
