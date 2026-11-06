# UniXNU-nuwa

小米 13 Pro（nuwa / SM8550）的 UniXNU 设备仓。目标：iOS 16（donor iPhone10,3 / 16.7.16 / 20H392，xnu-8796 线）。

## 当前进度（2026-11-06）
- 阶段：**仓库重建完成，未开始开发**（对应官方 porting checklist 第 2 步「建设备仓」刚落地）。
- 已有：board.toml（含 TODO：IPSW url/sha256、kernel/prelink、firmware、bootimg 地址）、scripts（ADT 生成器/审计/录像判读等历史工具）、AGENTS.md。
- 下一步：按官方 S02 补 board.toml TODO（IPSW pin 用 donor-ios16.lock 哈希核对）。

## 约定
规则见 `../docs/governance-2026-11-06.md`（本机共享）与 AGENTS.md。Apple 派生产物不上传本仓（治理 §7）。
