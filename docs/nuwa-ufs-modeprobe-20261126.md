# nuwa 只读 MODE SENSE 与 live GPT 摘要（2026-11-26）

范围：单核、本地候选，未访问设备。生产 Data 的写资格、冷启动证据和 FUA 门均不变。

## 探针与字段

- `nuwa-ufs-desc=1` 的一次性入口沿用 READ_DESC，并增加一次 MODE SENSE(10)。CDB `5a 08 08 00 00 00 00 00 40 00`：DBD=1、当前 Caching Page `0x08`、LUN0、64 B device→host、一个 PRD、slot0。请求、返回缓冲区读取和完成分类共用原 host 锁与 slot；未更改 DMA/IOMMU、锁序或超时后的隔离合同。READ_DESC 已隔离时不提交 MODE SENSE。
- 解析 mode header byte 3 bit 4 `DPOFUA` 和普通 Caching Page byte 2 bit 2 `WCE`。以 UPIU residual 得实际字节数，再验证 mode data length、block descriptor 区及各 mode page 边界；完整头但无普通 caching page 时 `wce=unk`，畸形/短响应只显示 `UFS2 err=<status> sc=<sense>`。已归属的 CHECK CONDITION 和畸形参数不隔离；timeout 才按既有 orphan 合同隔离，无额外提交。DPOFUA 是报告位，不是 FUA 持久性证明。
- `UFS2 dpofua=<0/1|unk> wce=<0/1|unk> gpt=<ok|bad|unk>` 从缓存绘制。GPT 源是现有 `Provider::open()` 主备校验，不用根布局 cache 或本地 GPT pin 代替。验证通过为 `ok`，读到结构/身份错误为 `bad`，未验证或读取未完成为 `unk`。生产 mode 2 因门关闭不进入主备读，所以预期 `gpt=unk`；绘制、探针均不为此补发 GPT I/O。

## 复跑

沿用 [Data v3 单核配方](nuwa-dualbank-integration-20261126.md#主机复跑与结果)。打包与 `--audit-only` 都加 `--ufs-desc`。主机使用实际 staged transport 与模拟介质：

```sh
"$PY" -B tests/test-nuwa-retained-entry.py "$B" "$BASE"
"$PY" -B tests/test-nuwa-crashcap.py "$B/kernel.macho"
llvm-objdump -d --disassemble-symbols=_native_ufs_store_write,_native_ufs_store_sync,_nuwa_ufs_mode_row "$B/kernel.macho"
fsck.fat -vn "$P/readback-fat.img"
mdir -i "$P/readback-fat.img" ::/EFI/UniXNU/Payloads
```

ASan/UBSan staged fixture，默认无 MMIO/无行，显式探测验证 CDB、方向、LUN、PRD 与零写入。输出：

```text
PASS MODE SENSE(10) read-only once: UFS2 dpofua=0 wce=0 gpt=unk
PASS MODE SENSE(10) read-only once: UFS2 dpofua=0 wce=1 gpt=unk
PASS MODE SENSE(10) read-only once: UFS2 dpofua=1 wce=0 gpt=unk
PASS MODE SENSE(10) read-only once: UFS2 dpofua=1 wce=1 gpt=unk
PASS MODE SENSE short header: UFS2 err=6 sc=000000
PASS MODE SENSE short caching page: UFS2 err=6 sc=000000
PASS MODE SENSE CHECK CONDITION: UFS2 err=3 sc=050000
PASS MODE SENSE timeout: UFS2 err=5 sc=000000
PASS live dual GPT from existing open, no extra I/O: UFS2 dpofua=0 wce=0 gpt=bad
PASS live dual GPT from existing open, no extra I/O: UFS2 dpofua=0 wce=0 gpt=ok
PASS UFS2 banner: cached hook, bounded row capacity
```

最终内核反汇编：UFS2 绘制只调用 `snprintf`；写/sync 仍恒返回 0，不链接实际硬件写后端。Linked crashcap、候选 outer/FAT 回读和 `fsck.fat -vn`/`mdir` 均 **self-checked**。UniXNU 上游 HEAD 构建前后 `e7bddb9a7eecdcf81f36da9fa38bd9d4d3f155c2`，未改 pin。

## 产物

`out/nuwa-ufs-modeprobe-20261126-package/vendor_boot.img`（100,663,296 B）。args 561→577 B，只追加 ` nuwa-ufs-desc=1`；仅 kernel、其 ADT CHMH 和配置改变。seed/trust 不变；FAT 剩余 **11,038,208 B**。

| 产物 | 哈希 |
| --- | --- |
| Kernel SHA-256 | `f0299b23cefafea210a7d863f60cc6fc4d31bc294a21b6959ea98c8ddce8646f` |
| Outer SHA-256 | `932c01bd957c6bb8c1b227a672aae32526bc904b2eb8ad7cac4fae954add4fb6` |
| CHMH SHA-384 | `38bd5f70ca87c9633f400c4553eca7347f6bff36c57db6225ec4bbb1fe500fb0fcf9c65e5f559330ccb55cb587967ea6` |
| 回读 FAT SHA-256 | `2f666c4aff5f6a69c26b8804335c5250d607b06ba8b005400e45f4b9c16130ae` |
| Seed SHA-256 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

未独立复跑、未上机。真实设备是否支持该命令及其报告值未测。
