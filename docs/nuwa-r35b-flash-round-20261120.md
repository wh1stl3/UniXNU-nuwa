# r35b 上机前记录 — 2026-11-20

## 审查与绑定

主控转述：**方案 A，deep_reviewer 深审 PASS WITH CONDITIONS**；审查结论绑定以下现物镜像哈希，而非分支名。完成下列上机前三项确认前不执行设备操作。该判词不证明运行时行为或认证通过；认证仍为 NOT REACHED。

现物记录，SHA-256：

| 对象 | 哈希 |
| --- | --- |
| vendor_boot.img | `3c5c2df89ff67341af3fdc4a40eef82467a7360389685f4303f241315ecc9388` |
| payload.img | `de26794988414ec4280fbe6937f86de5b6fd8868a0a69cc3d25c1f5fffb30afd` |
| derived.adt | `22a9e9f4bc13ccb4b3a020c1bc840e75b09c2e078bc15ce2e5323dd115e0cf3c` |
| kernel.macho | `ad7e70f7e615494c6162cec1a72610e119e897414bb89e4e038075244442da2f` |

CHMH（SHA-384）：`9ea4853ca37f2e59310720d6803a30d39c2a74da60d12c30896d168ed80fafbe246969138120f6b1b512a3d6fc3be0be`。完整打包及 audit 记录见 [r35b packaging](nuwa-r35b-packaging-20261120.md)。本轮证据为现物哈希核对加一次构建与 audit，**不是两次干净构建复现**；独立 verifier 最终构建/测试未复跑。

页面 build-tag 仍为 `nuwa-r35`，不能凭页面标签区分 r35 与 r35b；后续观测须关联本次实际写入镜像的哈希和写入记录。

## record.json 勘误

已核对包内 `record.json:112` 的 `exit_observe` 沿用 r35 的旧说明，称入环条件为 `status` 或 `os_reason namespace` 非零。r35b 实际入环条件为 `signal || ns`，其中 `signal = status & 127`；普通 `exit(1)` 的 `status=0x100` 不再仅因 status 非零入环。详见 [exit selection](nuwa-r35-exit-selection-20261120.md)。这是记录文字勘误，不修改已核对包。

## 回滚与限制

首选 r34 `vendor_boot`（100663296 B，SHA-256 `46aa4fd9f575a30824543fed7c128c5013d35af8d62a98715d0312d1752c891e`），路径 `UniXNU-nuwa/out/nuwa-ufs-apfs-root-chmh-20261119-r34/vendor_boot.img`。历史 r34 写入只有 bootloader ACK、无设备镜像回读；当前槽和设备状态本轮未核对。

原厂备份：`boot_a.stock.img`（201326592 B，SHA-256 `d530872b80f9cc44a260411a1a7d1c6357a9d3e562577e803e7a82945226c0d9`）；`vendor_boot_a.stock.img`（100663296 B，SHA-256 `493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`），均在 `UniXNU-nuwa/out/nuwa-boot-payload-write-20261115-01/`。原厂 `boot_a` 是整分区 dump，fastboot 接受该尺寸尚未验证；bootloader 无 `fetch`，回滚写入 ACK 不等于设备镜像回读。回滚启动载荷不恢复 `userdata`，包括无备份、无逆操作的尾窗口写入；详见同目录 `ROLLBACK-r9.md`。

## 上机前三项确认

1. 取得并核对用户当轮授权原文，明确目标与动作；本记录及审查结论不是设备写入授权。
2. 按型号只读识别唯一 nuwa，并只读核对当前槽；未唯一命中或槽不符合目标则停止。所有后续设备命令固定使用确认的 serial，切换模式后重新识别。
3. 确认 r34 回滚镜像现物哈希、可访问性与回滚条件均就绪；回滚设备写入同样需当轮明确授权。

本记录未执行设备命令，未重构建或更改产物；主机结果为 self-checked，设备运行与独立最终验证尚未验证。
