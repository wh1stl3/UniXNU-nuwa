# nuwa 受限 Data 写设计（2026-11-25）

**单核候选已链接 provider 骨架和双槽 overlay；Data 写门禁关闭。**
此包不验证可写性或持久化，未接触设备。保留 PU why。

## r3：retained 响应分类收紧（self-checked）

当前候选只将 **`CHECK CONDITION (0x02)` + 合法 autosense** 认作可归属命令错误：
必须匹配响应类型/LUN/tag，UPIU response code 为 0，sense 段长度正确且满足
固定/描述符 sense 格式；只允许无残量或 underflow 位与非零、未超界残量一致。
`GOOD (0x00)` 必须无 sense、无残量（原 REQUEST SENSE 短传输例外仍保留）。
拒绝 `CONDITION MET 04`、`BUSY 08`、`INTERMEDIATE 10`、
`INTERMEDIATE-CONDITION MET 14`、`RESERVATION CONFLICT 18`、
`COMMAND TERMINATED 22`、`TASK SET FULL 28`、`ACA ACTIVE 30`、
`TASK ABORTED 40` 和所有其余/保留值（含 `ff`）。任何异常响应、捕获到的外槽 DB
位或完成 OCS 非零都不归属；OCS `0xf` 是尚未完成的初值，若持续到期限则保持
timeout orphan 而不认作完成。这些路径全部拒绝新 I/O，并保留 DMA 与映射。

沿用下文单核构建/打包配方，用 fresh `B`/`P`（本轮
`out/nuwa-ufs-recovery-candidate-20261125-build-r3` /
`out/nuwa-ufs-recovery-candidate-20261125-package-r3`）。新 fixture 从候选
stage 的 `CombinedRead::issue` 经实际 `response()` 驱动 `retainedSlot` 和
`CandidatePort`，只替换硬件/内核胶水，不注入预先分类的 Evidence：

```sh
S=out/nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/source
c++ -std=c++17 -Wall -Wextra -Werror -Wno-unused-function -fsanitize=undefined \
  -I "$B/nuwa-data-provider" -I "$S" tests/test-nuwa-retained-response.cpp \
  -o "$B/test-retained-response"
"$B/test-retained-response"
```

```text
PASS CHECK CONDITION + valid sense  next root=allowed Data write/sync=denied
PASS CHECK CONDITION + underflow    next root=allowed Data write/sync=denied
PASS reserved status ff             next root=denied Data write/sync=denied
PASS unsupported BUSY status        next root=denied Data write/sync=denied
PASS CHECK CONDITION without sense  next root=denied Data write/sync=denied
PASS invalid sense                  next root=denied Data write/sync=denied
PASS wrong tag                      next root=denied Data write/sync=denied
PASS contradictory residual         next root=denied Data write/sync=denied
PASS oversized residual             next root=denied Data write/sync=denied
PASS foreign DB bit then clear      next root=denied Data write/sync=denied
PASS nonzero OCS                    next root=denied Data write/sync=denied
PASS wrong UPIU type                next root=denied Data write/sync=denied
PASS wrong LUN                      next root=denied Data write/sync=denied
PASS oversized UPIU length          next root=denied Data write/sync=denied
```

32 项 Data/回收模型、linked crashcap、反汇编写拒绝检查、outer/FAT audit 与
`fsck.fat -vn` 同轮 self-checked。561 B args、seed 与 trust 不变，只换
kernel 与重绑的 ADT CHMH；outer 100663296 B，FAT 余 **11042304 B**。
UniXNU 上游 HEAD 前后为 `b04f131da9151182dbb26ce4e638fa8acc2933ac`，未改 pin。

| 产物 | 哈希 |
| --- | --- |
| Kernel SHA-256 | `b84af43d0327b7bd83d26197d4a54935f36b9152cc9fee63fd1806abede63590` |
| Outer SHA-256 | `1ad194532b20ac5ea270ce14d1d07233dc2b1a9e8e7e3305657a266a250e1f0b` |
| CHMH SHA-384 | `4929d19e406071f06a9b4654751b541e2aace5aeba43b96ed432a0aa6d272220a606a0313adef3805ba0a07d35e781ae` |
| 回读 FAT SHA-256 | `1c6b41819d86bf4210a0e745715da62ab3373751c848055837b5e79a7fe02adc` |
| Seed SHA-256 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

## 单 slot DMA 回收候选（self-checked）

主机模型可恢复根读，候选内核没有硬件恢复后端；写门禁关闭。本节 r2 产物与下文旧 Data v2 产物均为基线。

### 寄存器与调用链

`retained/` 指构建 pin 内的 `out/nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/source/`。
寄存器定义参考本地 [mu_basecore@cfb93724 的 `UfsHci.h`](https://github.com/microsoft/mu_basecore/blob/cfb93724a06ff86ff5ba971413368a7809ee42a5/MdePkg/Include/IndustryStandard/UfsHci.h)（BSD-2-Clause-Patent，引用 UFSHCI 2.0）。

| 路径 | 寄存器 / 证据 |
| --- | --- |
| 两列表 | UTRL BA/U `0x50/54`、DB `0x58`（slot bitmap）、CLR `0x5c`、RSR `0x60` bit 0；UTMR BA/U `0x70/74`、DB `0x78`、CLR `0x7c`（DB/CLR `[7:0]`）、RSR `0x80` bit 0；两 BA 低寄存器 `[31:10]`，1 KiB 对齐（`UfsHci.h:295–363`）。`retained/PreservedNop.h:68–128` 只在接管时确认两 DB 空、屏蔽 IE、停两列表、换 UTRL BA/U、重启 UTRL；不改 UTMR BA/U、不重启 UTMR、不用 CLR。 |
| 控制器与 IRQ | HCE `0x34` bit 0；HCS `0x30` bits 0/1/2/3 = DP/UTRLRDY/UTMRLRDY/UCRDY；IS/IE `0x20/24`，`UfsHci.h:152–229`。`retained/TransferPoll.h:8–26` 使用 fatal mask `0x71880`（bits 7/11/12/16/17/18；2.0 参考不定义 bit 18 的错误语义）。`CombinedRead.h:122–141` 每次复查 HCE/HCS、SMMU/domain、队列与 BA。 |
| 提交与归属 | `retained/CombinedRead.h:39–70,92–153`：slot 0，DB bit 0，UPIU byte 3 的 tag 在 `1…255` 循环，不能当作隔离代号。连续 DMA 147456 B：UTRD `0`（OCS `+8`，初值 `0xf`）、UCD `4096`、response `4608`、PRDT `5120`、data `16384`。`NativeUfs.cpp:295–352` cache/barrier、poll IS/DB/OCS、1 s 单调期限。DB 全清、OCS=0、无 fatal、UPIU 类型/LUN/tag/长度吻合及 residual 合法后才归属；候选额外拒绝看见过外槽 DB 的完成。 |
| CRYPTODMA / 厂商 UTRL 配置 | `retained/GccUfs.h:9–26` 仅有 GCC PHY ICE core clock `0x77074`、公用 clock enable bit 0；不是 CRYPTODMA idle/reset。板上 CRYPTODMA/ICE 和厂商 UTRL 配置寄存器地址、位义及 reset 持久性 **unknown**，候选不读写。 |
| abort/TM 与 reset/link | retained 和 [ShengUfs@f020bd69](https://github.com/UniXNU/ShengUfs/tree/f020bd693c34790c04e97c52720af3cd842336fb) 未见 Abort Task 或 TM submit。上游 `NativeUfs.cpp:234–238,481–490` 接管不切 HCE/链路；`:1833` 的 UIC `0x90` 是 DME_GET。本地 `UfsPassThruHci.c:1853–1929,1945–1990,2001–2157,2176–2224` 有 HCE disable/enable/readback、两列表重建、controller stop、LINK_STARTUP（`0x90` opcode `0x16`，参数 `0x94/98/9c`，`UfsHci.h:59–62,395–406`），未找到发 Abort Task 的路径。这是通用初始化参考，不是 SM8550 DMA drain 证据。Linux v6.12 `include/ufs/ufshci.h` 请求 HTTP 429，未重试。 |
| 上游与 retained domain | 上游 `RootCommands.h:5–63,150–195,268–334,554–610` 用 slot→entry/DB bit、SCSI tag=entry、`gOutstanding/gSlotGen` 跟踪；超时保持 DMA、poison，不取消/重放。`retained/PreservedNop.h:27–71,80–128` 沿用 OEM link/HCE/clock、SID `0x60` 的 SMR/S2CR 与 CBAR/CBA2R/SCTLR；`NativeUfs.cpp:248–315,810–828` 保持 HC/SMMU MMIO 映射与自有 DMA，软件 claim 防二次接管。**Reset 后各寄存器、SID 映射、UTM/UTR 归属和 link 有效性都未证**；CPU pin 不是 DMA 排空。 |

### 状态与接入

- `IDLE → SUBMITTED → COMPLETED_OK`；归属明确的命令错误进入 `COMPLETED_CMDERR`，允许根读，Data 写和 sync 本会话不再允许。
- `TIMEOUT_ORPHAN` / `FATAL_QUARANTINED` 拒绝新请求，保留 DMA 与映射，不因迟到完成解禁，不重放。
- 显式 `tryRecover` 进入 `RECOVERING`，拒绝普通 I/O。先证明任务终止或 controller 停止、排除迟到完成、slot 与 DMA 归还，才可重建队列；随后验证 LUN/布局/GPT 和已知 LBA 整块内容。失败不缓存证明，再超时重新 orphan。六项全部成立才进入 `RECOVERY_PROVEN`，只恢复根读。
- `RetainedRead.inc` 在现有 `hostRead4k` 锁内跟踪根读，与 Data 共用 `Slot`。`Provider<CandidatePort, false>` 强制关闭写入；`KernelPort.inc` 的硬件回收/FUA 门禁恒假。TODO：取得 SM8550 task/HC stop、总线/SMMU drain 与 stale completion exclusion 的证据，再资格化队列、LUN/GPT、预期根块。DB=0、abort/reset 返回、软件换 tag 均不是独立证明。

32 项 host 断言组通过（原 23 + 新 9）：共享锁等待时根读先超时、迟到完成/abort 失败、DB=0 但 DMA 未归还、fatal、外槽/残余、重建/identity 失败、reset 后根块错误、恢复再超时、六步完成后只恢复根读。检查 DMA 字节、mapping ID 和写次数。

```sh
c++ -std=c++17 -Wall -Wextra -Werror -pthread -fsanitize=undefined \
  tests/test-nuwa-data-write.cpp -o out/nuwa-ufs-recovery-fixture-20261125
./out/nuwa-ufs-recovery-fixture-20261125
```

### 候选与复跑

沿用下文 Data v2 构建/打包配方，换 fresh `B`/`P`：本轮为
`out/nuwa-ufs-recovery-candidate-20261125-build-r2` /
`out/nuwa-ufs-recovery-candidate-20261125-package`。UniXNU 上游 HEAD
前后均为 `b04f131da9151182dbb26ce4e638fa8acc2933ac`，未改本地 pin。
linked crashcap、outer/FAT audit 与 `fsck.fat -vn` 均 self-checked。
Outer 100663296 B，FAT 剩余 **11042304 B**；只有 kernel 与 ADT CHMH
改变，561 B args、seed、trust 保持不变。

用 `llvm-objdump -d --disassemble-symbols=… "$B/native.macho"` 核对：
`native_ufs_store_write/sync` 只调用 boot 参数解析、锁获取/释放并返回 0；
log write/sync/panic、export write 直接返回 0。`retainedReadLocked` 进入
`CombinedRead::issue`，READ CDB `0x28` 向 UTRL DB 写 `1`，不是介质写；
无 linked `hostWrite4k`/`hostScsi*` 发送路径或硬件恢复后端。

| 产物 | 哈希 |
| --- | --- |
| Kernel SHA-256 | `d8ffa51d4bef97d944422c54d8a4bf5274981e280b9bc9088ef954a63176157c` |
| Outer SHA-256 | `e2beeeb6b81e4fdf5a66d85306f9670d971d0eef6c3868242f1ed664b58732e6` |
| CHMH SHA-384 | `70254221750d328e3cce1d5c3da7cf9ad91bc68ebcbc6e244866c9475933e4c441933a173fda786507ca3b71c4d29c83` |
| 回读 FAT SHA-256 | `6286169bbef0310ae760584ebc789da0a8bf0193fcbcbcb61b13e6937c1a58d7` |
| Seed SHA-256 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

## 复用设计

| 来源 | 采用方式 |
| --- | --- |
| [`UniXNU/ShengUfs@f020bd693c34790c04e97c52720af3cd842336fb`, `RootCommands.h`](https://github.com/UniXNU/ShengUfs/blob/f020bd693c34790c04e97c52720af3cd842336fb/RootCommands.h)（BSD-2-Clause） | `package/nuwa-data-write/Gate.h` 在 `Window::contains` 使用减法边界判定，在 `write10` 只编码单个 4 KiB LBA 和强制 FUA。不采用多 slot、重试、log 窗口或全 LUN `0x35`。原许可见同目录 `LICENSE`。 |
| [`Liquidation0619/hakios-thyme-mi10s@4bb1a4ee`, `src/userland/var_store.c`](https://github.com/Liquidation0619/hakios-thyme-mi10s/blob/4bb1a4ee/src/userland/var_store.c)（MIT；设计参考，无代码移植） | 保留两代提交根、发布前验证校验、先数据后 header。其 `load()` 会在校验最新候选失败时验证另一槽；nuwa 只接受完整的同 seed 旧代或新代，不采用另一 seed，也不在无完好世代时回落到 seed。 |
| [`Liquidation0619/hakios-thyme-mi10s@4bb1a4ee`, `src/kernel/bsd/dev/thyme_ufs.c`](https://github.com/Liquidation0619/hakios-thyme-mi10s/blob/4bb1a4ee/src/kernel/bsd/dev/thyme_ufs.c)（APSL-2.0；设计参考，无代码移植） | 只参考「证明队列所有权后才交给另一个生产者」的原则。thyme 暂时切出 native 队列，经驻留 loader 写，再尝试恢复 native。nuwa retained slot 没有该 loader 接口或已证明的切换协议，不能借它清 poison 或恢复根读。 |

**映射到 `PersistOverlay`：** `Overlay.h` 替代候选内的 mode 2 单槽，
不改变 mode 1 或只读基座。两个可独立校验的
header 是提交点；header 包含版本、seed 标识、非回绕世代、映射校验。
选定当前完整世代后，先作废非当前提交槽；修改的页即使已落过盘也必须
写到当前完整世代未引用的位置，不能原位覆盖。写入新页并确认 FUA，
写可独立验证的下一代 bitmap/映射（包含引用的页位置及数据校验），
再最后 FUA 写下一代 header。只有全部成功且 Data 屏障通过才在内存
切换可见映射。保留旧版映射及其引用的所有页，直到不再需要回读旧提交；
沿用单 bitmap 加固定页原地覆盖**不能**实现双槽语义。

恢复时从两个 header 中选最高且 header、映射、引用页校验全部匹配的同
seed 世代，不跨世代拼页；两个不可判定或 I/O 结果不明时报错。禁止 reset
有效 overlay，包括同 seed；新建只接受经明确证实为空的窗口，不能把
「没有认识的 header」当成空。页、bitmap 或 header 失败时停止靠 overlay
服务 I/O，不能发布未提交位，也不能静默退回 seed。

## Provider 不变量及接线边界

- `gpt` 独立检查 LUN 0 / 4 KiB、主备头签名、版本、已记录的 92 字节
  头长、实际读取位置和互指 LBA、usable 范围、预期磁盘 GUID、条目数组
  位置/32 条 ×128 B、双 CRC、两数组逐字节一致、`sda32` 的名称/类型/
  分区 GUID/范围、不与其它条目重叠。fixture GUID 是合成值，不入库
  实机 GUID。实际只读主 GPT 留在机型本地历史 `.cache`，接线时身份
  必须从独立本地输入绑定；备 GPT 必须在 open 当下实读。
- `placement` 证明根镜像向上取整后留 1024 块 guard，Data 结尾恰好
  留出非零 tail reserve。`Window::contains` 单独限制 WRITE(10)
  可寻址范围和每次块范围，不通过加法检查末尾。
- 当前 `RootCommands.h:261–282` 的根读拿 `gHost.lock` 后走
  `RootReadSession::read` / `CombinedRead::issue`。`hostWrite4k` 只是
  stub，不能改成走旧 `hostScsiDir`：两条路径必须共用 retained
  `CombinedRead` 的 ownership、descriptor、completion 和锁合约。
  `KernelPort.inc` 在生成的 `NativeUfs.cpp` 把 mode 2
  `native_ufs_store_{open,read,write,sync}` 接到 `Provider.h`。骨架
  用同一把 host 锁、ready/poison 和 retained guard；出错即保留隔离。
  log/export/panic 保持原拒绝路径，不转调 Data 写。私有 GPT 标识由
  已保存的本地 capture 校验生成，只留构建目录、不入库。
- `Slot` 的 `IDLE → SUBMITTED` 由 ready + slot 所有权授权；
  `SUBMITTED → COMPLETED_OK` 需归属正确且无残余的 FUA 成功；
  `→ COMPLETED_CMDERR` 只接受已确认归还的、可归属的命令错误；
  `→ TIMEOUT_ORPHAN` 不复用原映射/区、不重放；
  `→ FATAL_QUARANTINED` 处理 fatal、无法归属和所有权不明。
  `RECOVERY_PROVEN` 有独立状态，无入边。`tryRecover()` 无条件失败；
  DB=0、迟到响应和 abort 尝试均不证明原映射已回收。
- Data `sync` 在同一 host 锁内检查 FUA 持久性已证、host ready、
  无在途且无粘滞错误；没有 `0x35`。候选没有 `NUWA_DATA_WRITE_OPT_IN`，
  也没改变 args 添加 `nuwa-data-write=1`。内核的 FUA 和回收证明接口
  均返回 false，且无硬件写后端；fixture 的 `Evidence` 不是硬件证据。

每槽为 `[header, bitmap, 固定位置的 pages]`。完整校验覆盖 header、
带填充的 bitmap、按序排列的所有存在页。写时复制另一槽仍需的旧页，
原子边界是最后一个 header 的 FUA 与完成屏障；失败时当前会话停止
overlay 读写，不切 seed。现有单槽 v1 header 位于新窗口第二槽的
header 位置，识别为外来而不覆盖。诊断实现验证双槽完整性时扫描存在页，
建空槽前扫全窗口，并为每次提交复制当前存在页；这不是性能合格
的运行方案。真实设备不得在未评估成本、未实现 retained 写回收和
未证明 FUA 持久性时开启。

## 主机 fixture（self-checked）

```sh
c++ -std=c++17 -Wall -Wextra -Werror -fsanitize=undefined \
  tests/test-nuwa-data-write.cpp -o out/nuwa-data-write-fixture-20261125
./out/nuwa-data-write-fixture-20261125
```

```text
PASS GPT valid nuwa geometry with synthetic GUIDs
PASS GPT wrong LUN/block size rejected
PASS GPT CRC-correct wrong userdata unique GUID rejected
PASS GPT CRC-correct disagreeing entry arrays and reciprocal LBA rejected
PASS GPT bad header CRC and bad entry CRC rejected
PASS placement guard/tail, one-block overrun and integer wrap rejected
PASS CDB encodes one WRITE(10) FUA page
PASS sync rejects SUBMITTED and accepts attributed FUA completion
PASS attributed command error is sticky for Data
PASS orphan rejects late completion, recovery, root and Data
PASS unowned before/after submission quarantines slot
PASS default provider gate and log/export/panic deny every write
PASS opt-in mock uses one FUA per page, stops on orphan without replay
PASS power cut 1 preserves both old pages; unpublished bitmap invisible
PASS power cut 2 preserves both old pages; unpublished bitmap invisible
PASS power cut 3 preserves both old pages; unpublished bitmap invisible
PASS power cut 4 preserves both old pages; unpublished bitmap invisible
PASS power cut 5 preserves both old pages; unpublished bitmap invisible
PASS slot flip and partial update survive reboot without reset
PASS data checksum failure falls back read-only
PASS one damaged header falls back read-only; two fail closed
PASS foreign header and nonempty blank-header window not overwritten
PASS no writes without proven FUA barrier
```

断电模型依次打断非活动 header 作废、页 0、页 1、bitmap、最后 header。
未测真实断电、锁竞争、DMA 归还或真实响应归属/残余。

## 候选包与复跑（self-checked）

`out/nuwa-data-write-candidate-20261125-package/vendor_boot.img` 为
100,663,296 B。纯 Python outer/FAT 回读及 `fsck.fat -vn` 同意：
FAT 剩余 **11,042,304 B**，只变更 kernel 和 ADT 的 CHMH；561 字节 args
和 seed 不变。链接图含 v2 `Overlay::{open,scan,writeRun}`；
`native.macho` 中 `_native_ufs_store_write` 与 `_native_ufs_store_sync`
均返回 0（可取锁，不发介质命令）。linked crashcap fixture 通过。

| 项 | 散列 |
| --- | --- |
| Kernel SHA-256 | `8603e6f1c61a452c8b1db188376635e27591b1c3aadca7d8087d1cfee3a21aa4` |
| Outer SHA-256 | `33dfcfd76bb00f1a2ee6f9eaee55c4f828781b7899f699955227f189a0b1527f` |
| CHMH SHA-384 | `49deb1dd413c15248be32c710c906c5158c9eadcef2b3a031121b919d92ad9c6ba860724155ad36d627bda948b5ffd6d` |
| 回读 FAT SHA-256 | `8762e1829ecce959f1d7c7dcb0ecb226f469ce0422a2e5fe2ba44ebd4c750b30` |
| Seed SHA-256 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

复跑用 [Data PU why 配方](nuwa-data-persist-fix-20261125.md#diagnostic-and-self-check)，
在构建命令追加 `--data-candidate-gpt ../.cache/device-evidence/20261107-recovery/gpt-sda.bin`，
`B`/`P` 用新目录；复跑 `tests/test-nuwa-data-write.cpp` 与 `tests/test-nuwa-crashcap.py "$B/kernel.macho"`。
构建前后上游 HEAD 均为 `8542980d02b4d2cc5c32ee3542de1760b2562aac`，未采用。
提交级记录检查用 `/home/wh1stl3/.local/bin/python3.11`。未运行独立 verifier。
