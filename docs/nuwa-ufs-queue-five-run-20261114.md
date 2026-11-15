# UFS queue-five 运行记录（2026-11-14）

## 身份与观察

- Run：`ufs-queue-five-20261114-01`；outer SHA256 `44205ea9c123afd1a13109c98329f2c8c0d96e9c2a1021ff9b82cc3920248dc9`；kernel SHA256 `eff66a33a097568e3c44f84fb1a7f3365889613cdcb629583944f2c99022012b`。
- 主控转述用户两照片读数：`QUEUE_ONLY_DONE attempt5 completed5 hc_read5`，`HCE=1 UTRLDBR=0 UTRLRSR=1 UTRLBA=0xc5f01000 UTRLBAU=0`。无独立 vision 或录像时序验收，不推断持续时长或重启行为。
- 主控转述最终 binary reviewer：panic call `007992b0c`、返回 `007992b10` 吻合；加载合同从 r4 到 B 载荷和产物绑定，画面/栈一致。这是关联证据，非认证。
- 旧队列地址是 DMA 地址；`UTRLRSR=1` 未停，`UTRLDBR=0` 仅瞬时，不能证明 ownership 或 producer exclusion，也不证明 DMA、transport 或 root 已闭合。

## 恢复证据

独立 host verifier 的 `out/queue-five-restore-verifier-20261114/summary.json` 为 18/18 PASS。B 备份及恢复回读均为 100663296 字节，SHA256 `493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`；事件 `0000–0126` 连续，恢复从 `0063` 开始，记录含 A、Android、root、`_a` 事件。两处 writer-closed 存在，active lock 不存在。

三个持久 host wrapper 日志记录 run、profile、script SHA 和 `process_exit=0`；stdout 已脱敏，serial 未重新硬件关联，A 无镜像级回读。以上不表示当前 live 或长期稳定。

## 下一步与边界

host 有界 SID `0x60` 域只读候选已启动；单次 NOP 前仍须闭合 ownership、producer exclusion 和 SMMU 域。TPL 支线 deferred；下一设备操作未授权。照片和录像不入 Git，serial 与 private key 不记录。
