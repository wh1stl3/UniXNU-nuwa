# nuwa SB0 R 前检与 WX 刷入 — 2026-11-27 实机观察

状态：设备动作已执行，主机日志 self-checked；R 屏幕结果来自用户照片（主控转述）。
W 已由用户手动选择并确认，但 reviewer 判定提交状态 UNKNOWN；R 读回载荷已刷入，
读回屏幕仍待用户照片。本轮不是认证、DMA 独占或掉电持久性证据。

## 范围与授权

- 用户长程授权「继续直到 UFS 写入候选上机」，本轮明确要求先送上机已审 R，取得
  BLANK 基线，然后只刷一次 WX 菜单 outer 并交用户手动选择。
- `deep_reviewer` PASS WITH CONDITIONS（session `ses_de752aa79ffeo8MJPXWJpXCKGu`）
  接受 WX outer 的无输入复位门禁，并要求刷 W 前先跑 R。本轮按该条件执行。
- 本轮写入只有：R 轮 `boot_a`、`vendor_boot_a` 各一次；WX 轮 `vendor_boot_a` 一次。
  未刷 recovery，未动 B 槽、`userdata`、`metadata`，未初始化、未自动重试。
- 主机执行前核对：nuwa 唯一（另一台 fastboot 设备 `product=enuma`，全程未操作）。

## 设备身份与写前像

WSL 原生 ADB 37.0.1，`shell -T -n`，唯一 nuwa 处于 recovery、uid 0：

```text
uid=0(root) ... context=u:r:su:s0
ro.product.device=nuwa
ro.boot.hardware=qcom
ro.boot.slot_suffix=_a
ro.boot.verifiedbootstate=orange
blockdev --getsize64 /dev/block/by-name/boot_a         = 201326592
blockdev --getsize64 /dev/block/by-name/vendor_boot_a  = 100663296
boot_a        -> /dev/block/sde14
vendor_boot_a -> /dev/block/sde24
```

只读设备 SHA-256（R 写入前；serial 已脱敏，原始输出在 `out/sb0-r-precheck-20261127/`）：

```text
f4dc081b32a1eced559cad9d1e42e9e1b462aadb7c222f0744f2997994cd4e0a  boot_a
493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad  vendor_boot_a
```

只保存了哈希，没有抓取整分区镜像。输入文件核对：

| 输入 | 字节 | SHA-256 |
| --- | --- | --- |
| r4 loader `boot-stage12-v4-r4.img` | 1,495,040 | `692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5` |
| R outer `R-package-r4/vendor_boot.img` | 100,663,296 | `3f5ffaee9b88439cd7ecbb6f630b4e133b5dbe5a3e5d488d61831c02ee3b7668` |
| WX menu outer `WX-package-manual/vendor_boot.img` | 100,663,296 | `7f1f3c3d097e3e187030a24e66d136750a2a024c3abad59a3b857eafbefa4986` |

R 刷入前 bootloader：`product: nuwa`、`is-userspace: no`、`current-slot: a`、
`slot-count: 2`、`unlocked: yes`、`partition-size:boot_a 0xC000000`、
`partition-size:vendor_boot_a 0x6000000`。

## R 刷入与第一次启动

命令与结果（Windows fastboot 37.0.1，`-s <nuwa-serial>`，每次一条，exit 0）：

```text
fastboot flash boot_a <...>/boot-stage12-v4-r4.img
  Sending 'boot_a' (1460 KB)   OKAY [0.035s]
  Writing 'boot_a'             OKAY [0.004s]
  Finished. Total time: 0.075s

fastboot flash vendor_boot_a <...>/R-package-r4/vendor_boot.img
  Sending 'vendor_boot_a' (98304 KB)  OKAY [2.264s]
  Writing 'vendor_boot_a'             OKAY [0.035s]
  Finished. Total time: 2.333s
```

`fastboot reboot` exit 0，时间 `2026-11-26T16:44:21.843Z`。随后 90 秒内每约 5 秒轮询
`adb devices -l` 与 `fastboot devices`：nuwa 在 adb/fastboot 中均未出现；在场的只有
另一台 enuma 的 bootloader。轮询结束时（t+91.0 s）无 nuwa USB 枚举；未发送任何 adb
写或挂载命令。

用户照片（主控转述，不是主机读屏）给出 R 终态：

```text
NUWA SB0-R READONLY
BLANK  LU0 target=57393401  pages=770  writes=0
```

该结果满足 `deep_reviewer` 对 W 前 R 前检的条件：770 页全零、写命令为 0。主机没有
屏幕内容或帧缓冲副本，未独立判读。

## 恢复入口演练

用户在 R 停屏状态下按电源+音量减进入 fastboot。主机随后在 fastboot 重新识别到唯一
nuwa（`product=nuwa`、`is-userspace=no`、`current-slot=a`、
`partition-size:vendor_boot_a=0x6000000`），与本轮 R 刷入后的状态一致。该入口动作
为用户报告；主机只确认设备确实重新枚举为 nuwa fastboot。

## 刷 WX 前的只读核对及限制

bootloader 不支持 `fastboot fetch`：

```text
fastboot fetch vendor_boot_a <out>
fastboot: error: Unable to get max-fetch-size. Device does not support fetch command.
exit 1
```

`fastboot getvar all` 也不提供分区内容哈希。因此**没有取得刷 WX 前的分区字节回读**。
当前内容身份由以下事实共同约束，而不是一次新的字节哈希：

1. 本会话以精确期望哈希各写入一次，两次均 `Sending/Writing OKAY`、exit 0；
2. 用户观察到的 R 标记来自该 `vendor_boot_a` 载荷，说明 R outer 确实被执行；
3. 从 R 停屏到 fastboot 之间没有主机写入，用户只做了按键入口操作；
4. `boot_a` 仍为本轮写入的 r4 loader，容量与槽位未变。

该限制不构成对分区内容的字节级证明；若需要，可在下一次 recovery 会话用
`sha256sum /dev/block/by-name/{boot_a,vendor_boot_a}` 补做回读。

## WX 刷入与第二次启动

输入实际字节数与分区容量一致（100,663,296 B），SHA-256 为
`7f1f3c3d097e3e187030a24e66d136750a2a024c3abad59a3b857eafbefa4986`。只刷一次：

```text
fastboot flash vendor_boot_a <...>/WX-package-manual/vendor_boot.img
  Sending 'vendor_boot_a' (98304 KB)  OKAY [2.269s]
  Writing 'vendor_boot_a'             OKAY [0.036s]
  Finished. Total time: 2.338s
```

exit 0。`fastboot reboot` exit 0，时间 `2026-11-26T16:49:19.214Z`。30 秒内轮询
adb/fastboot：nuwa 均未出现；在场的只有 enuma bootloader；Windows PnP 也没有新的
nuwa/ADB/QDLoader 接口。主机未发送 adb 写、挂载或菜单选择命令，未代选、未改配置。

WX 菜单默认 10 秒无输入进入 Power off，第二项 W 需要用户自行选择并确认。上述 30 秒
轮询结束时菜单尚未选择；后续用户已手动选择并确认，见下节。不得把「30 秒无 USB」
当作 W 成功、失败或设备关机的原因。

## W 尝试（用户操作）与 reviewer 判定

用户在 WX 菜单中手动选择第二项并确认（主机未代选、未改配置）。用户照片转录：

```text
屏幕停在约 4.5 秒
出现 IRQ-off hard lock 提示
未见 NUWA SB0-W 结果行
```

没有可读的 W 终态记录。reviewer 判定 W 提交状态为 **UNKNOWN**
（session `ses_de73aed4effeI37YjM1d49ytt0`）。按实验约束，UNKNOWN 不得重试 W，
必须以 R 读回确认 SB0 页的实际字节；本次不再次选择 W。

W 硬锁停屏后，用户按电源+音量减进入 fastboot；主机重新识别到唯一 nuwa。

## R 读回刷写与启动

fastboot 身份与容量：

```text
product: nuwa
is-userspace: no
current-slot: a
slot-count: 2
partition-size:vendor_boot_a: 0x6000000
partition-size:boot_a:         0xC000000
```

只读内容核对仍受 bootloader 限制：`fastboot fetch` 不支持（见上节错误），
`fastboot getvar all` 不提供分区哈希，因此没有对当前 `vendor_boot_a`/`boot_a`
做新的字节回读。当前 `vendor_boot_a` 为 W outer 的依据是本会话按
`7f1f3c3d…` 精确写入、WX 菜单与 W 实际执行；`boot_a` 自 r4 loader 写入后没有
主机写入，且同一 r4 loader 实际启动了 WX 菜单。该证据不替代字节哈希。

按 UNKNOWN 后只选 R 的约束，只把 R outer 再刷入 `vendor_boot_a` 一次：

```text
fastboot flash vendor_boot_a <...>/R-package-r4/vendor_boot.img
  Sending 'vendor_boot_a' (98304 KB)  OKAY [2.260s]
  Writing 'vendor_boot_a'             OKAY [0.030s]
  Finished. Total time: 2.323s
```

输入 100,663,296 B，SHA-256
`3f5ffaee9b88439cd7ecbb6f630b4e133b5dbe5a3e5d488d61831c02ee3b7668`，exit 0。
`fastboot reboot` exit 0，时间 `2026-11-26T16:53:09.916Z`。随后 30 秒内轮询
adb/fastboot：nuwa 均未出现；在场的只有 enuma bootloader；Windows PnP 也没有新的
nuwa/ADB/QDLoader 接口。主机未发送 adb 写、挂载或菜单选择命令。

R 读回屏幕尚未取得，需用户拍照。可能的分类包括 `BLANK`、`EXACT-SB0`、
`MISMATCH`、`IO-FAIL`，本记录不预设；在拿到用户照片前不得称 R 读回通过或失败。

## 边界

- R 的 `BLANK` 只说明读到 770 页零页且 `writes=0`；不证明旧固件 DMA 已撤销、SMMU
  独占、掉电持久性或认证。
- WX 的 W 路径仍是一次非 FUA 的 `WRITE(10)`；即使屏幕报 GOOD，也只证明命令完成，
  不是持久性。任何 `UNKNOWN` 或没有终态记录都必须按 R 处理，不得重试 W。
- W 提交状态为 reviewer 判定的 `UNKNOWN`；屏幕没有 `NUWA SB0-W` 结果行，不能据此
  认定写入已提交或未提交。是否发生写入等待 R 读回照片。
- 本记录不把 R 基线当作 W 的授权，也不把本次 R 读回当作再次选择 W 的许可。
- 原始命令输出与时间线仅在 `out/sb0-r-precheck-20261127/`、`out/sb0-wx-flash-20261127/`、
  `out/sb0-r-readback-20261127/`（Git 忽略，序列号已或可脱敏），本文件只保留结论与哈希。
