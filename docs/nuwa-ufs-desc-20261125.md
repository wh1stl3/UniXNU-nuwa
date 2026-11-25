# nuwa UFS 描述符：传输可行性（2026-11-25）

**按「只发 UIC」的边界不可实现，未改 provider 或候选。**
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

**状态：仅静态审查。** 未添加 boot arg、横幅、fixture 或候选包；没有
新五哈希/FAT 数值。未访问设备，未刷写，写门无变更。
