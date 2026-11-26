# nuwa SB0 R 前检、WX、只恢复候选与受控冷启动 — 2026-11-27 实机观察

状态：设备动作已执行，主机日志 self-checked；R1/R2、只恢复候选和受控关机冷启动
结果来自用户照片（主控转述）。W 回执 UNKNOWN，R2 为 EXACT-SB0；受控关机冷启动
68 s 的 DATA 行为 `st=2`，reviewer PASS（`ses_de72a2665ffe1B5ch6qJ7GJVQF`）。
该冷启动是非空恢复的**单次、状态级**证据；突发断电耐久与文件级内容保留延期，
未拍到 `DATA mnt`。本记录不是认证或文件系统挂载验收。

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

用户照片 `r_2.jpg` 的 R 读回结果为 `EXACT-SB0`：R2 独立读回确认 SB0 页字节与
原写页一致，其余 769 页为零（按 R 合同；照片转录只给出该分类）。主机未读屏。

## 两次 R、W 与刷写顺序

| 顺序 | 操作 | `boot_a` | `vendor_boot_a` | 结果 |
| --- | --- | --- | --- | --- |
| 1 | R1 刷入并启动 | r4 `692cfcca…` | R `3f5ffaee…` | 照片 `r_1.jpg`：`BLANK`，770 页，`writes=0` |
| 2 | 用户从 R 停屏按电源+音量减进入 fastboot | 不变 | 不变 | 主机重新识别唯一 nuwa |
| 3 | 刷 WX 菜单 outer 并启动 | 不变 | WX `7f1f3c3d…` | 用户选择并确认 W；约 4.5 秒后 IRQ-off hard lock，无 `NUWA SB0-W` 结果行；W 回执 UNKNOWN |
| 4 | 用户从 W 停屏按电源+音量减回到 fastboot | 不变 | 不变 | 主机重新识别唯一 nuwa |
| 5 | 只刷 R outer 并启动（R2） | 不变 | R `3f5ffaee…` | 照片 `r_2.jpg`：`EXACT-SB0` |
| 6 | 用户从 R2 停屏按电源+音量减回到 fastboot | 不变 | 不变 | 下一轮开始状态 |

R1 写入为 `boot_a` 与 `vendor_boot_a` 各一次；WX 与 R2 均只写
`vendor_boot_a` 一次。所有写入均 `Sending/Writing OKAY`、exit 0；没有 recovery、
B 槽、`userdata`/`metadata` 写入或初始化。复位/回 fastboot 均由用户按键完成，
主机未发送除刷写后的 `fastboot reboot` 之外的复位命令。

## 证据链验收

reviewer 验收 W/R 证据链（session `ses_de7382000ffesoU8SSOnqOcwcU`）：
接受「W 写入效果经复位后 R 独立读回证实」，即 R2 的 `EXACT-SB0` 证明 W 的目标页
字节确实存在；同时 W 自身的命令完成回执仍是 `UNKNOWN`，FUA/断电保持未证。
本记录把两个结论分开保留：

- **W 回执 UNKNOWN**：屏幕没有 `NUWA SB0-W` 结果行，不能据此判定 WRITE(10) 是否
  完成、是否 FULL GOOD 或是否被设备侧记为已消费。
- **写入效果已读回**：复位后由 R2 独立读回为 `EXACT-SB0`，证明目标 LBA 的页内容
  与预期写页一致；这是观测到的介质效果，不是 W 命令回执，也不证明 FUA 或掉电保持。

## 只恢复候选启动（outer `6695da98…`）

候选在 `2026-11-26T16:59:10Z` 启动；60 秒轮询内设备未枚举，随后用户照片给出
93 s / 112 s 两个采样。本轮没有再次启动或刷写，以下均为该次启动的照片转录。

### 身份与刷写

- 唯一 nuwa fastboot；`product=nuwa`、`is-userspace=no`、`current-slot=a`、
  `partition-size:vendor_boot_a=0x6000000`、`partition-size:boot_a=0xC000000`。
- 候选 outer：100,663,296 B，SHA-256
  `6695da9842f4da4d26c1f028adc48f3ffb8f6f369420653492028a74bf362fa5`；
  `boot_a` 仍为 r4 loader
  `692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5`。
- 刷前分区字节回读不可用：bootloader 不支持 `fetch`，`getvar` 不含分区哈希。
  身份来源是功能链：R2 的 `EXACT-SB0` 由当前 `vendor_boot_a` 的 R outer
  `3f5ffaee…` 产生，`boot_a` 自 r4 写入后无主机写入，r4 loader 实际启动了
  R/WX；本轮 `getvar` 的 product、槽位、容量一致。**这不是新的分区字节哈希。**
- 只刷一次：

```text
fastboot -s <nuwa-serial> flash vendor_boot_a <...>/nuwa-disposable-data-package-r2/vendor_boot.img
  Sending 'vendor_boot_a' (98304 KB)  OKAY [2.259s]
  Writing 'vendor_boot_a'             OKAY [0.035s]
  Finished. Total time: 2.327s
```

  exit 0。`fastboot reboot` exit 0，时间 `2026-11-26T16:59:10.164Z`。
- 60 秒内每约 4 秒轮询：nuwa 始终未出现在 adb/fastboot；在场的只有 enuma
  bootloader；Windows PnP 也只有 enuma 的 Android Bootloader Interface。
  主机未发送 adb 写、挂载或菜单选择命令。

### 照片与转录

照片只留在本地 `media/`，**不入 Git**；下表 SHA-256 为本地文件哈希。

| 文件 | 字节 | SHA-256 | 屏幕采样 | 本地 mtime（+08） |
| --- | --- | --- | --- | --- |
| `6695.jpg` | 5,103,914 | `e094161ebda8ccf9ed95f3b2c69f5489f5165bbbe943e3370d6ff38f3a87a645` | `t=93s` | 2026-11-27 01:01:54 |
| `6695_stuck.jpg` | 4,274,713 | `7fbe3f9f4ab7d8a90410fe23135aca8291442cc8d49bbbe3c19b1f58fd5fd126` | `t=112s` | 2026-11-27 01:02:01 |

采样时刻以屏幕 `t=` 行为准；本地 mtime 是落盘/复制时间，两者不用于换算。

**93 秒（`6695.jpg`）vision 转录摘要**：顶部状态行
`nuwa-r35] t=93s n=80 np=2 i=0s q=1807 =0 r=0 f=1057813`；关键 DATA 行：

```text
DATA hdr=9 gpt=0/0 lba=36bc0f9 | pres=22 ld=642 wr=26 sy=0 er=0 st=3
```

同屏可读的还有 `NEON LU ... ok`、`NEON MS ...`、`OBS worker=2 ...` 和
`UFS TIME ...`。DATA 行完整、无遮挡；整块屏幕在画面内，照片略倾斜，底部白色
横条和 `0123456789` 自检字形没有覆盖 DATA 行。

**112 秒（`6695_stuck.jpg`）vision 转录摘要**：顶部状态行
`nuwa-r35] t=112s n=97 np=2 i=0s q=198* l=0 r=0 f=1048363`；

```text
EX2 p6 launch sig=1 code=0x00000000 n=1 pc=...
EX1 p9 MSUEar sig=1 code=0x00000000 n=1 pc=...
tzinit[17] exited -- no exit reason available -- (signal 0, exit status 45 )
```

随后是可读的 `frames ...` 列表和 `pages=0x000000000126baa`、
`free=0x0000000000ffd43`。EX1/EX2 与 `tzinit[17]` 块完整；顶部状态行贴近屏幕上缘，
行首标记可能被曲面边缘裁掉，但 `t=112s` 及关键字段可读，无关键行截断。

### 三个独立结论

1. **93 秒 DATA 行，`st=3`**：reviewer 判读为打开时 seed 匹配、接受 generation 0
   SB0、空映射与空日志，候选**未自行初始化**。`wr=26` 是本轮写入页次，不是
   断电落盘回执。
2. **112 秒用户态退出**：`tzinit[17]` exit status 45、`p6 launch sig=1`、
   `p9 MSUEar sig=1`。这是本轮用户态退出记录，不归因历史 SIGTRAP。
3. **未拍到 `DATA mnt`**：因此不声称 APFS 已在 `/private/var` 可写挂载。

reviewer 验收结论（session `ses_de7302407ffeQUPMTwmr0IAt9q`）为
**PASS WITH CONDITIONS**。此前 W 回执 `UNKNOWN` 与 R2 `EXACT-SB0` 的区别继续保留：
`st=3` 本轮结果不改变 W 回执，也不把 R2 的写入效果扩展为 W 命令完成或 FUA 证明。

### 下一轮判据

- 断电重启后拍全 DATA 行；判据为 `gpt=0/0`、同一 `lba=36bc0f9`、`st=2`、
  `pres>0`、`er=0`。
- `st=6` 记为非空重放成功，但环满只读。
- `st=3` 不通过非空恢复验收。

该判据已由 2026-11-27 的受控关机冷启动满足，结果见下节。

## 受控关机后冷启动（`6695_2.jpg`）

### 过程事实

- 用户从 UniXNU 菜单选择 `Power off` 正常关机，随后按键冷启动；同一候选自动进入。
- 期间没有重刷启动分区、没有重新初始化、没有写 SB0；主机未连接设备，本轮为纯
  记录整理。
- reviewer 验收 session `ses_de72a2665ffe1B5ch6qJ7GJVQF`，结论 PASS。

### 照片与转录

照片只留在本地 `media/`，**不入 Git**；下表 SHA-256 为本地文件哈希。

| 文件 | 字节 | SHA-256 | 屏幕采样 | 本地 mtime（+08） |
| --- | --- | --- | --- | --- |
| `6695_2.jpg` | 5,103,000 | `cbfa59080390afcf9827edfe869f91094dde3ff5218cf9ba59b3879a78dc8f96` | `t=68s` | 2026-11-27 01:08:28 |
| `6695_stuck_2.jpg` | 4,180,865 | `ac81bd3e722c7c940fb7a73887df973e6a03dbcc9bacbfd808f135745a02b24d` | `t=112s` | 2026-11-27 01:08:36 |

采样时刻以屏幕 `t=` 行为准；本地 mtime 是落盘/复制时间。

**68 秒（`6695_2.jpg`）vision 转录摘要**：顶部状态行
`nuwa-r35] t=68s n=58 np=1 i=0s q=1438* =0 r=0 f=1165268`；关键 DATA 行：

```text
DATA hdr=9 gpt=0/0 lba=36bc0f9 | pres=27 ld=726 wr=2 sy=0 er=0 st=2
```

同屏可读的还有：

```text
OBS worker=2 anchor=0 bind=3 result=0 depth=32 base=fffffff151400000
UFS TIME vf=3046ms rd=45812ms blk=495229 1934MiB req=17093
```

DATA 行完整、无遮挡；屏幕四边在画面内，照片略倾斜，底部自检字形没有覆盖
DATA 行。

**112 秒（`6695_stuck_2.jpg`）vision 转录摘要**：顶部状态行
`nuwa-r35] t=112s n=97 np=2 i=0s q=197* l=0 r=0 f=1048609`；

```text
EX1 p9 MSUEar sig=1 code=0x00000000 n=1 pc=...
EX2 p6 launch sig=1 code=0x00000000 n=1 pc=...
tzinit[17] exited -- no exit reason available -- (signal 0, exit status 45 )
```

随后是可读的 `frames ...` 列表和 `pages=0x000000000126bac`、
`free=0x0000000000ffd39`。EX1/EX2 与 `tzinit[17]` 块完整；顶部状态行贴近
屏幕上缘，行首标记可能被曲面边缘裁掉，但 `t=112s` 及关键字段可读，无关键行截断。

### 结论

1. **`st=2` = 非空重放成功（状态级）**：命中预设判据 `gpt=0/0`、同一
   `lba=36bc0f9`、`st=2`、`pres=27>0`、`er=0`。这是单次实机、状态级证据，
   不是突发断电耐久或文件级内容保留证明。
2. **`pres 22→27` 与 `wr 26→2` 不能相减解读**：两者是不同启动的采样/计数，
   不是可做差值的累计量，也不能据此推算写入页数或持久化进度。
3. **112 秒用户态退出不推翻 68 秒读数**：同一轮 112 秒仍出现 `tzinit[17]`
   exit 45、`p6 launch sig=1`、`p9 MSUEar sig=1`，这是用户态退出记录；68 秒的
   DATA 行独立成立。
4. **未拍到 `DATA mnt`**：不验收文件系统挂载，也不声称 APFS 在 `/private/var`
   可写。
5. **证据等级与延期项**：reviewer 判据为上述 DATA 行；结论仅覆盖一次受控关机
   冷启动、状态级非空恢复。突发断电耐久与文件级保留为延期项，用户已接受该风险。

## 边界

- R 的 `BLANK` 只说明读到 770 页零页且 `writes=0`；不证明旧固件 DMA 已撤销、SMMU
  独占、掉电持久性或认证。
- WX 的 W 路径仍是一次非 FUA 的 `WRITE(10)`；即使屏幕报 GOOD，也只证明命令完成，
  不是持久性。任何 `UNKNOWN` 或没有终态记录都必须按 R 处理，不得重试 W。
- W 回执为 reviewer 判定的 `UNKNOWN`；R2 的 `EXACT-SB0` 只证明目标页的写入效果，
  不补出 W 的命令完成回执，也不证明 FUA/掉电保持。
- R2 的 `EXACT-SB0` 与 W 回执 `UNKNOWN` 必须并列保留，不能用一个覆盖另一个。
- 本记录不把 R 基线当作 W 的授权，也不把本次 R 读回当作再次选择 W 的许可。
- 只恢复候选 93 s 的 `st=3` 是空 generation 0 SB0 的可读状态，不满足非空恢复；
  `wr=26` 是本轮写入页次，不是掉电落盘回执。
- 受控关机冷启动 68 s 的 `st=2` 是非空重放的单次、状态级证据；`pres 22→27` 与
  `wr 26→2` 不能相减解读。突发断电耐久与文件级保留为延期项，用户已接受该风险。
- 未拍到 `DATA mnt`，不声称 APFS 在 `/private/var` 可写挂载；112 s 的
  `tzinit[17]` exit 45 和 `p6 launch sig=1`、`p9 MSUEar sig=1` 只作为本轮
  用户态退出记录，不归因历史 SIGTRAP，也不推翻 68 s 的 DATA 行。
- 所有照片只留在本地 `media/`，不入 Git；本文件只保留文件名、哈希、采样时刻和
  转录摘要。
- 原始命令输出与时间线仅在 `out/sb0-r-precheck-20261127/`、`out/sb0-wx-flash-20261127/`、
  `out/sb0-r-readback-20261127/`、`out/sb0-resume-20261127/`（Git 忽略，序列号已或
  可脱敏），本文件只保留结论与哈希。
