# nuwa 受限 Data 写设计（2026-11-25）

**单核候选已链接 provider 骨架和双槽 overlay；Data 写门禁关闭。**
此包不验证可写性或持久化，未接触设备。保留 PU why。

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
