# nuwa userdata 交接 — 2026-11-14

本次只落盘交接；后续由新会话开展。先读 `D:/Code/PortingiOS/docs/context-brief.md`、`nuwa/AGENTS.md` 和本仓规则。以下哈希及审查结果是主控交接的既有记录，本次未重算大文件、未操作设备。

## 当前产物与边界

- 真实 UFS 持久交互及断电重启验收尚未达成。NOP 曾实机成功并恢复，不是新一次上机，也不是当前 live 状态。
- r5 只读 root kernel：`out/nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/kernel.macho`，55545856 B，SHA256 `809587d53fef9b0b3e9b2054a9e06c649d3c66cd45be3fafbe632ac575cb0acc`。root 链 deep 条件通过；visibility 普通 review 和独立 verifier 通过。920 host 读、9 失败、12 出口；marker 12 是 Unicorn 真实 ARM64 指令加硬件适配，不是面板实测。
- r2 包：`out/nuwa-ufs-apfs-root-chmh-20261114-r2/vendor_boot.img`，100663296 B，SHA256 `72a4e8eaa420e6bff6713518126452d60a13329905833ef5a9b41dd1d0b279a9`；profile `ufs-apfs-root-20261114-r2`。执行器 `scripts/run-pmap-ret-once.py` SHA256 `d6f923c3ab346e01b93fd17adfbf990c7312ee4d7af64f04274e36f8c77d1dda`。包独立验证通过：`out/nuwa-ufs-apfs-root-chmh-verifier-20261114-r2/VERIFIER-REPORT.md`。
- CHMH-only 是实验身份，认证未证；候选拒绝所有介质写。data DMA、APFS 和 launchd 未实测；published 不等于 mounted。

## userdata 授权与实际状态

- 用户已将原“先备份”改为“不再备份 直接开始推送”，授权无备份安装 userdata 前 `8446279680` B，镜像 SHA256 `da429da64b4d91a08b8adb1d3162f8348b37b358509ab1bd5d8bf09abdbf68d7`。不含 root 启动或启动分区写；不要自动 root 启动。
- 失败的备份空目录 `out/nuwa-userdata-prefix-backup-20261114-01` 保留；无有效备份，**无回滚**。所有实际尝试均在写之前停止，本轮 userdata 写入 0 字节。最近一次检查 write claim 不存在；新会话须重新只读核对，不能声称当前 live。
- 曾出现两台 ADB 设备，已按规则处理；新会话重新按型号识别唯一 nuwa，所有目标命令显式指定 serial，不记录 serial 入库。

## inspect 修复与验证状态

- 真实 inspect 失败于 identity-snapshot completion；后续只读捕获确证原始输出 146 B、SHA256 `c9450e5d55799e6d1ec14cfc24117f07ae343112d12a488188b617f81b073142`，13 个 CRLF，末尾为 CRLF `NUWA_OK` CRLF。证据 `out/nuwa-userdata-identity-host-20261114/original-capture-01/{identity.json,run.json}`。
- 修复仅对 shell 文本副本做 CRLF→LF，二进制 exec-out 不变。最新 `scripts/nuwa-userdata-install.py` SHA256 `3296157043120afcc7bd844b8c1f8d76f5fab9adf5a6ebff52daa39f6f2f5393`；`scripts/test-nuwa-userdata-install.py` SHA256 `509372820c5da9f828e37e85a982e4dc2d5a21b650f8880e20fe11b0b74e96f7`。
- `out/nuwa-userdata-crlf-host-20261114/REPORT.md`、diff 和 10 项定向测试为 **self-checked**。前一 `ba7c09fc` 版本的 34 项测试独立 PASS，见 `out/nuwa-userdata-no-backup-verifier-20261114/`，且 review 条件通过；不能转称最新版独立通过。最后执行 agent 因最终 CRLF 受影响测试尚未独立复跑而停止；实际尚未复跑。

## 新会话步骤

1. 按最新版成本和验证规则裁定并完成最终版本受影响验证；若需要复跑，只跑 10 项受影响测试，不重跑全矩阵。保持旧版与新版验证状态分开。
2. 重新只读核对同一 pin、write claim 和唯一 nuwa 目标；在 WSL 运行以支持目录 fsync，重新 inspect，包括 `/dev` tmpfs 容量。Windows `adb.exe` 绝对路径已支持通过 `wslpath` 转换本地 push 路径。`/home/wh1stl3/.local/bin/python3.11` 已由 verifier 实际运行，之前 scout 的有限 find 声称其不存在是错误；`/usr/bin/python3` 3.10 也已测。
3. inspect 和所有门禁通过后，按既有授权一次执行 `write --without-backup`，核全授权、manifest pin 和源 hash；126 窗，末窗 55 MiB，逐窗及最终完整回读。失败保留 claim，不重试、不放宽 guard。同一授权无需再问；环境变化或超范围新设备操作另取授权。没有强制发起新设备操作。

## 工作区保留

本仓已有大量未提交变更、未跟踪脚本与文档；`out/` 被忽略，不代表资产已提交。保留全部历史日志及工作区，不盲目 stage，不自动 commit/push，禁止 `rm -rf` 和 force push。此前 scout 越界删除了 `scripts/__pycache__` 历史 pyc，源码未变，记录此一次偏差，不追改。
