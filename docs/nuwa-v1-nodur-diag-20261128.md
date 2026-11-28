# V1-NODUR 挂接与写错误同屏诊断 — 2026-11-28

**主机 self-checked，未操作设备；deep_reviewer 和独立 verifier 待完成。**
主控转述 ordinary reviewer **PASS**，仅绑定 daily r3 outer SHA-256
`be2865cf826e05f50d7ae02a0c77ec53a0b4b83b377b628ce466603f7defe3e4`。
基于 `research/nuwa-ufs-owner-api-20261126` 的
`68ec8b2c0019bab13268f996ac5c19662131c74b` 加本次工作树增量；UniXNU
构建 pin 为 `693f5d9cae8a408dd18b39f3f9fdc4228c934241`。
构建前后远端 UniXNU HEAD 为 `fdf81eaa832ce5c850d3c53c698407aa722a4653`，
nuwa HEAD 为 `fe6b859367cc7b0641e9ae7dda46d8b5c6fc4fb0`；未合并。
沿用 UniXNU/RamBlock `4be2d7eb05ef5a98126c91e0302c149140c0e3e1`
的 `PersistOverlay.h` / `DirectDisk.h`（BSD-2-Clause-Patent），不改上游。

## 屏幕字段

普通诊断页及 critical panic 安全带同时显示以下三行，保留原 `DATA0` 和
`S` 两行；以 1440×3200、scale 3 模型检查了 80 列与 `y < height/8`。

```text
D1 st=<state> h=<header> pres=<present> why=<reason>
D2 wr=<writes> er=<errors> ufs=<code>:<status>:<sense>
D3 first=<source>/<IOReturn> after=<source>/<IOReturn>
```

- `st` 是 `native_data_persist_state`，不是 APFS 的 `DATA0 st`。
  `2/3` 分别为 resumed/fresh，`4` 为拒绝或失败，`5` 为后续降级，
  `7` 为旧 v1 header 未匹配且未 reset 的 Kept；它是取样时状态。
  `h` 是上游 header 检查结果，`pres` 为当前 bitmap 的在场页数。
- `why=ok` 只证明 provider 窗口打开，不单独证明 overlay 活跃；
  须结合 `st`。`why=legacy-v3` 和 `why=legacy-disposable` 分别是
  实际读出的旧标记；`why=window` 是其余窗口/资格预检拒绝的汇总，
  包括 GPT、seed、范围、归属及旧标记读取失败，不能细分这些原因。
  `why=-` 表示尚未记录打开结果。
- `wr` 为成功写入计数，`er` 为已有持久层错误计数；未激活而提前拒写
  不一定递增这两个计数。`first` 是 block 写路径的首次失败；`after`
  是进入 gate 后、`storeAttached` 已置位时的首次失败。二者的低 32 位
  是实际返回的 IOReturn 十六进制；`-/00000000` 表示尚无记录。
  参数错误或 gate 不存在时只可计入 `first`。
- `inactive` 表示未活跃/不可写 overlay 路径，`ufs-w` 是提交至 store
  的写失败，`ufs-r` 是部分写的读取失败，`prior` 表示此前已锁定失败；
  其他来源为 `arg`、`gate`、`offline`、`copy`、`overlay`、`memory`。
  本轮直接返回 `NotReady` 的路径与异步 completion 的 `IOError` 均记录。
- `ufs` 是本次启动的**首次底层 store-write 失败**，不保证与 `first`/
  `after` 指向同一请求；`0:00:000000` 表示未见此类失败。code `1..9`
  是 `CombinedRead::End`（`2` Guard、`3` Transport、`4` Response、
  `5` Scsi）；`100` 为 admission/span/ownership 拒绝，`101` 为
  lock/source/window 前置拒绝，`102` 为成功响应但字节数不足，`103`
  为完整响应未获 slot completion 接受。仅 `5` 的 status/sense 是
  已归属的 SCSI status 与 sense key/ASC/ASCQ；其余不赋予 SCSI 含义。

这批信息只观察既有决策，不改变 R4/Owner API、读写准入或锁协议；新增
一次性原子诊断 latch，涉及既有存储路径，必须复审。实际画面、故障先后
及窗口内容尚未验证；即使取得照片，汇总的 `window` 原因仍可能需要
进一步证据，不能承诺单张照片必然给出完整根因。

## 产物与边界

日常包不含 `sheng-data-reset`。它仍是此前允许写入的 V1-NODUR 数据路径，
不承诺掉电耐久或原地覆盖不撕裂；CHMH 为实验绑定，不是认证。

| 项目 | 值 |
| --- | --- |
| outer | `out/nuwa-v1-nodur-diag-20261128-daily-r3/vendor_boot.img` |
| outer 字节数 | `100663296` |
| outer SHA-256 | `be2865cf826e05f50d7ae02a0c77ec53a0b4b83b377b628ce466603f7defe3e4` |
| kernel SHA-256 | `03f228f685a888ad38378be65cac587e6c78febb969c954ddadcea56bbaa259e` |
| FAT SHA-256 | `4cf8dbda6606ffb8a3019d9efe2e95d7b9282651bb1c66709231ee325647fc56` |
| CHMH SHA-384 | `05116c89651c7863b87b6ede98cc3c42dcce9cec6798fdcfb5d5763c93b8178c18b41a9534aca4116f7d1fd629807cbb` |
| FAT 空闲 | `11021824` B |

packager 核对 outer/FAT、seed/trust、参数及绑定；`reset=false`、
`device_release=false`。本轮没有接设备或取得设备写入授权。

## self-check 与复跑

WSL Ubuntu-22.04 root，设备工作树内：

```sh
p=/home/wh1stl3/.local/bin/python3.11
base=/mnt/d/Code/PortingiOS/UniXNU
b=out/nuwa-v1-nodur-diag-20261128-build-r3
pkg=out/nuwa-v1-nodur-diag-20261128-daily-r3
template=../worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-package/vendor_boot.img
cpo=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json

$p -B scripts/build-nuwa-display-native.py --base "$base" --cpo "$cpo" \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 --r35l-dir out/nuwa-r35l-regs-full-20261121 \
  --cpu-only --no-software-vsync --candidate --mg-reset --hid-standin --crashcap --pixsig \
  --data-persist-diag --data-candidate-gpt ../.cache/device-evidence/20261107-recovery/gpt-sda.bin \
  --data-v1-retained --post-event --out "$b"
$p -B tests/test-nuwa-v1-retained.py "$base" "$b"
$p -B scripts/test-nuwa-postevent.py --renderer "$b/BootProgress.c" --kernel "$b/native-with-stabs.macho"
$p -B tests/test-nuwa-data-persist.py "$base"
$p -B scripts/package-nuwa-crashcap.py --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --v1-retained-template "$template" --post-event
$p -B scripts/package-nuwa-crashcap.py --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --v1-retained-template "$template" --post-event --audit-only
fsck.fat -vn "$pkg/readback-fat.img"
```

构建、20 个 ASan/UBSan retained 情形、panic 行宽与 host framebuffer、
链接反汇编、旧 reason fixture、打包审计和 FAT 检查均 exit 0。
故障注入包括两种旧标记、旧标记读取的 SCSI 失败、挂接前后拒写、
已激活 overlay 的 store 读/写 SCSI 失败及首错保持；旧 non-V1 renderer
的 post-event 测试也 exit 0。测试输出在 `out/nuwa-v1-nodur-diag-20261128-*`。
独立 `verifier` 复跑构建/打包时必须使用新 `$b`、`$pkg` 目录，再核对
最终 hash；本次自检不等于独立验证。

`porting-record.py check --base origin/main` 首次在 WSL 失败：该工作树的
`.git` 引用是 Windows 绝对路径，Linux Git 无法解析。显式设置当前工作树
的 Linux Git 路径后复跑，输出 `nuwa: 14 structured areas checked`：

```sh
GIT_DIR=/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/.git/worktrees/worktree-ufs-owner-api-20261126 \
GIT_WORK_TREE=/mnt/d/Code/PortingiOS/nuwa/worktree-ufs-owner-api-20261126 \
  "$p" -B "$base/scripts/porting-record.py" check \
  --device /mnt/d/Code/PortingiOS/nuwa/worktree-ufs-owner-api-20261126 --base origin/main
```
