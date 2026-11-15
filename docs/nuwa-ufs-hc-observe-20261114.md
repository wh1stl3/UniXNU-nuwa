# UFS HC observation and restore — 2026-11-14

## 观察与边界

- Run `ufs-hc-observe-20261114-01`，r7 kernel SHA256 `134d1a24ca32b91d3f41cfdf2d95831abdd4ec4c5be827e291970723d14ba0f5`，outer SHA256 `6e150640b3780bcd2bc890d007619eecce2ce2fa6e511a451803556c01c54227`。最终 binary reviewer PASS WITH CONDITIONS（主控转述）。
- vision 实际序列：四读完成，`VER=400 CAP=3587031f HCS=10f HCE=1`；随后是预设 inspect panic，不是 mapping 错误。准确栈第六地址 `0078c43c4`。约 2.5–13.27 秒终止画面无重启；原媒体仅本地 `../media/hc-observe-20261114/`（相对设备仓根目录），不入 Git。
- UFSHCI 4.0、32 transfer/8 task 仅描述该瞬时 HC 状态，不证明 DMA、transport 或 root 成功。复用路线下一步为 host 单次 NOP，先处理 ownership、producer exclusion、SMMU 域；下一设备操作未授权。

## 恢复证据

独立 verifier 报告 `out/ufs-hc-restore-verifier-20261114/verifier-report.md`，机器结果同目录 `verifier-result.json` 和 `verifier-result-restore-exit.json`：备份及 restore-readback 均 100663296 B，SHA256 `493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`，恢复检查 PASS。事件 `0000–0126` 完整、restore 自 `0063` 起；writer 已关闭且无 active lock。A slot 读回与 Android `boot_completed=1`、root `uid=0`、`_a` 事件关联；没有 A 镜像级回读。

verifier 独立读到 restore 原 shell 日志的 exit 0；原文件随后被清理，仅留同目录转写和原 SHA256 `1574a183bb1d2810f78451e64d705fa36911af6c32ed63fbfb6162716f40bf15`。日志无 runid，关联为推断。prepare/boot 整体 exit 0 仅执行 agent 转述，事件 rc 仍有原记录；整体进程 exit 未全部独立验证。不将本轮恢复证据称为当前 live 或长期稳定。
