# r35b 上机前记录 — 2026-11-20

## 审查与绑定

主控转述：**方案 A，deep_reviewer 对瘦身 r35b 的最终 diff 深审 PASS WITH CONDITIONS**；判词限以下候选及所列条件，绑定现物哈希而非分支名。按成本口径，本轮**未独立验证，放行基于方案 A 深审 + self-checked**，不得表述为独立 verifier 已复跑通过。完成下列上机前三项确认前不执行设备操作；该判词不证明运行时行为或认证通过，认证仍为 NOT REACHED。

现物记录，SHA-256：

| 对象 | 哈希 |
| --- | --- |
| vendor_boot.img | `56e78d27d48e6368cd3f96fa2993bfcba44bea8684d9a6dbc87355dcfd198dbd` |
| payload.img | `95fedd1001f9ee3a275f2decbb47cdc60d9c7301a335b5cc1ef99f6f0e1719c6` |
| derived.adt | `c8c769acdd0877616a697d582b72cb92aed5303c4c3f1e6096c7be53670c093d` |
| kernel.macho | `6262a25ab2211c8010a105d9456cdf46d38832c5edf3667f2b09a8262639deb8` |

CHMH（SHA-384）：`ca463c3f4ba9168203323e4350255d2b0c5f53e4033211dcf2f3124291c63ea7104b5d6fac7da9a3b859dafaefe58528`。修正后 FAT 真实空闲 **12,070,400 B**，高于不变的 8 MiB 门槛 3,681,792 B；构建和 audit 见 [瘦身记录](nuwa-r35b-compact-20261120-observation.md)。本轮不是两次干净构建复现，独立 verifier 最终构建/测试未复跑。

旧 r35b `vendor_boot` SHA-256 `3c5c2df89ff67341af3fdc4a40eef82467a7360389685f4303f241315ecc9388` 真实空闲 8,355,328 B，低于门槛，**禁用**。旧 r35 `vendor_boot` SHA-256 `c6e64820cc46c1a54e65d3640994ad7acf0e7aa807dfd3765eac82f483a4a7ed` 的真实空闲也不足 8 MiB，不作为满足门槛的回退。

瘦身前后最终内核并非所有非 LINKEDIT 字节相同：`__PRELINK_INFO` 段移位，其中仅 `_PrelinkKCID` 约 22 B 不同。native 映射内容、非 STAB 符号和 prelink 绑定的比较边界见瘦身记录，不能把它扩大为最终内核全部非 LINKEDIT 字节相同。

页面 build-tag 仍为 `nuwa-r35`，不能凭页面标签区分 r35 与 r35b；后续观测须关联本次实际写入镜像的哈希和写入记录。

## record.json 勘误

旧 r35b 包内 `record.json:112` 的 `exit_observe` 沿用 r35 旧说明，称入环条件为 `status` 或 `os_reason namespace` 非零。r35b 实际入环条件为 `signal || ns`，其中 `signal = status & 127`；普通 `exit(1)` 的 `status=0x100` 不再仅因 status 非零入环。瘦身候选的打包记录已修正该文字；详见 [exit selection](nuwa-r35-exit-selection-20261120.md)。

## 回滚与限制

首选 r34 `vendor_boot`（100663296 B，SHA-256 `46aa4fd9f575a30824543fed7c128c5013d35af8d62a98715d0312d1752c891e`），路径 `UniXNU-nuwa/out/nuwa-ufs-apfs-root-chmh-20261119-r34/vendor_boot.img`。历史 r34 写入只有 bootloader ACK、无设备镜像回读；当前槽和设备状态本轮未核对。

原厂备份：`boot_a.stock.img`（201326592 B，SHA-256 `d530872b80f9cc44a260411a1a7d1c6357a9d3e562577e803e7a82945226c0d9`）；`vendor_boot_a.stock.img`（100663296 B，SHA-256 `493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`），均在 `UniXNU-nuwa/out/nuwa-boot-payload-write-20261115-01/`。原厂 `boot_a` 是整分区 dump，fastboot 接受该尺寸尚未验证；bootloader 无 `fetch`，回滚写入 ACK 不等于设备镜像回读。回滚启动载荷不恢复 `userdata`，包括无备份、无逆操作的尾窗口写入；详见同目录 `ROLLBACK-r9.md`。

## 上机前三项确认

1. 取得并核对用户当轮授权原文，明确目标与动作；本记录及审查结论不是设备写入授权。
2. 按型号只读识别唯一 nuwa，并只读核对当前槽；未唯一命中或槽不符合目标则停止。所有后续设备命令固定使用确认的 serial，切换模式后重新识别。
3. 确认 r34 回滚镜像现物哈希、可访问性与回滚条件均就绪；回滚设备写入同样需当轮明确授权。

## 后续上机留痕要求

- 记录实际写入文件的完整 SHA-256、目标分区、写入结果，以及是否完成整镜像回读；没有回读须明确写未回读，不以写入 ACK 代替。
- 逐字转录 `EX1` 至 `EX4` 和 `dropped`；区分未见、已被覆盖和仅低位读数，不把未见当作未发生。
- 结束时记录是否回滚、回滚目标与结果，以及是否完成整镜像回读。

本次记录更新未执行设备命令、未改槽，**不代表现槽已确认未变**；未重构建或更改产物。主机结果为 self-checked，设备运行及独立最终验证尚未验证。
