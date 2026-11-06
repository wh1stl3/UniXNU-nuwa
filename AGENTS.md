# AGENTS.md — UniXNU-nuwa

长期规则见共享治理文档：`D:/Code/PortingiOS/docs/governance-2026-11-06.md`（若路径变更以实际为准）。本文件只写 nuwa 专属约定。

## 目标
小米 13 Pro（nuwa / SM8550）通过 UniXNU 运行 iOS 16（donor: iPhone10,3 / 16.7.16 / 20H392，xnu-8796 线）。

## 基线
- UniXNU 基座：`D:/Code/PortingiOS/UniXNU`（最新上游 main，HEAD e2fdae4；gitlink 修正记录 ArmCpu=93a5030、XnuPrelink=f1d80d3）。
- 本仓由旧 UniXNU-nuwa 重建（2026-11-06），board.toml/scripts 自备份恢复；TODO 项按官方流程逐阶段补齐，不照抄 sheng 板值。

## 硬边界
- flash/erase/改槽等设备写入动作：须用户当轮明确授权。
- 唯一 ECID（--unique-chip-id）等设备种子只经命令行传入，不入库（治理 §6）。
- 含 Apple 组件的产物（kernel-prelinked.macho、boot.img 等）只留本地 out/，不上传 GitHub（治理 §7）。
