# nuwa UFS NEON 2026-11-26 操作记录

- 用户本轮授权：先刷指定 `vendor_boot_a`，暂不重启；不写其他分区或 Data。
- 最终候选 `out/nuwa-ufs-neon-20261126-package/vendor_boot.img`，指定 SHA256 `18fa4941696667d1813442022ea71fc48e4c414b1abadb1caf73774fcc76202a`。
- 主控转述 reviewer `ses_dea4ac134ffeukgJojpK2eehP1` 对最终 diff 及上述 outer 的结论：PASS WITH CONDITIONS，仅静态；方案 B 审查，未经 deep_reviewer。
- 门禁：实算镜像哈希、唯一 fastboot product nuwa、当前槽 a；不满足即停止，不进 bootloader、不切槽、不重试、不重启。刷写结果不等于回读。

## 本轮结果（self-checked）

- `Get-FileHash -Algorithm SHA256`：`18fa4941696667d1813442022ea71fc48e4c414b1abadb1caf73774fcc76202a`，与指定值一致。
- `fastboot devices` exit 0，2 台；逐台固定 serial 执行 `getvar product`，exit 均为 0，分别为 `enuma` 和 `nuwa`，nuwa 唯一。序列号脱敏不入库。
- nuwa 固定 serial 执行 `getvar current-slot`，exit 0，输出 `current-slot: a`。
- nuwa 固定 serial 单次执行 `fastboot -s <serial> flash vendor_boot_a out/nuwa-ufs-neon-20261126-package/vendor_boot.img`，输出：

```text
Sending 'vendor_boot_a' (98304 KB)                 OKAY [  2.265s]
Writing 'vendor_boot_a'                            OKAY [  0.036s]
Finished. Total time: 2.335s
FLASH_EXIT=0
```

- 未执行回读，Writing OKAY 不证明分区内容回读一致；未切槽、未重启、未写其他分区或 Data。运行效果尚未验证。

## 后续画面（主控转述 vision，非独立 verifier）

主控提供 vision 会话 `ses_de9f9f5aeffetgOZpKgGq114t` 的转录：
`media/微信图片_20261126120125_559_25.jpg`（t340）和
`media/微信图片_20261126120206_560_25.jpg`（t405）；媒体不入 Git。
两帧标题均为 `nuwa-r35 crashes=0 exits=5`，六行一致：

```text
NEON build=ufs-neon-20261126 cid=N261126A s=4 old=? rsr=?
NEON HC 3587031f/00000001/0000010f/00000000/00000000/00000400
NEON DEV len=59 lu=06 boot=01 mfr=0198
NEON LU 01/00/0c n=0000000003afc400 rc=3afc400/1000 ok
NEON MS 1/1 e=0:000000 GPT p/b/id=ok/ok/ok
NEON PL=ok A=4/4 nz=0 M(part)=10/10 nz=0
```

两帧均有 `PU1 DATA st=4 h=9 g=0/ff why=window l=0`，
`PU2 pres=0 ld=0 wr=0 sy=0 er=0`（左首字符裁切）。
UFS 行从 `L r=2244 rd=6939ms T r=121109 rd=337kms` 变化为
`L r=1182 rd=2451ms T r=141161 rd=388kms`。

画面 cid 与候选标签一致，但不是每次启动的 nonce，刷写无分区回读，
不能单凭它证明镜像级关联。`old`、`rsr` 未知；HC 快照不证明旧 DMA
终止或所有权。四个锚点及 768 个 map/ring 页中的 10 个采样为零，
不证明其余页为空或 overlay 可初始化；MODE SENSE 位不证明持久性。
写入和 sync 仍关闭，交互与重启持久性均未验收。本次记录者未访问设备。
