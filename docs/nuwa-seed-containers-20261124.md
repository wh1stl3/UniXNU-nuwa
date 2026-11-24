# nuwa Data seed：第一批容器目录（2026-11-24）

状态：self-checked；**未经 reviewer 复核最终产物、未上机**。reviewer 对方案的 `Pass with conditions` 仅限第一批 8 条，不是对最终产物的复核。其余 29 条为待补/存疑，未创建；未创建任何 plist，也未调整既有条目权限。

## 第二次制作和出包

先前编码日志中的 `e3d9b7be1b23e17f6f8ca97bb5ef07d2d36d2e2171f267172fa72290d5e6e669` 是 `SHNGSEED2` 内容身份，而非文件 SHA-256。实际重算旧 `seed-edited.raw` 与旧 `seed-roundtrip.raw`，二者 SHA-256 均为 `340e2c202115100c76ed35d4f32426d71ae904f3cc457edaf2ef44b494ab7f9b`，`cmp` 退出 0。

本次按用户指示两次从 `seed.raw.bak` 上传重做，挂载后建立 `.fseventsd/no_log`，增加 8 项，删除整个 `.fseventsd` 后 sync、detach，再以只读且保留 ownership 的挂载核对。两次只读清单均为 328 条，与旧 `post.txt` 340 条的差异仅为 **缺失原 `.fseventsd` 目录及其 11 条子项**；并非完全一致。第二次按用户授权的 `.fseventsd` 限定例外继续。清除动作同时删除了备份里已有的 fsevents 条目，不能称最终 seed 仅新增目录；旧记录中多出的两条位于 `/private/var/.fseventsd/`，用户判定为 macOS 挂载产生，具体生成时点未独立确认。

第二次 raw 的 guest 和宿主 SHA-256 均为 `394046d64805f469d441bc26ba523bbba9cef7a94e29871c2c4f9dd9700323c8`，8,589,934,592 B。官方编码器产物 2,281,632 B，SHA-256 `fc233a71a8ea9aa4bf58d604fccb5606cd3327e51eb66641581c5456a8e90ed5`；其 `SHNGSEED2` 身份为 `904117b3076cd6486d2231b48413b37dd45aaf9ce46e9b1d000a16b57214dcf3`。用官方 `regions()` 解码的 8,589,934,592 B raw 含 8 个 extent，`cmp` 退出 0、逐字节一致；随后 `sha256sum` 对原 raw 与回环 raw 均得到上述 `394046d6…700323c8`。

### 打包

基包 `4400518` 的 outer SHA-256 为 `02fb3bebced7516e714f4719b6c0f76d704d2789be8c35ee15df9dbcc7428897`。`out/seed-containers-20261124/package-from-baseline.py` 从该 outer 提取 FAT，使用以下命令替换 seed，再运行 UniXNU 官方打包器（命令以 WSL 路径记载）：

```sh
mcopy -o -i /mnt/d/Code/PortingiOS/nuwa/worktree-display-dsp/out/nuwa-containers-probe-20261124-package/payload.img /mnt/d/Code/PortingiOS/nuwa/worktree-display-dsp/out/seed-containers-20261124/seed-final-encoded.img ::/EFI/UniXNU/Payloads/scratch-data.img
/home/wh1stl3/.local/bin/python3.11 -B /mnt/d/Code/PortingiOS/UniXNU/unixnu vendor_boot --stock /mnt/d/Code/PortingiOS/nuwa/worktree-display-dsp/.cache/stock/vendor_boot_b.img --ramdisk /mnt/d/Code/PortingiOS/nuwa/worktree-display-dsp/out/nuwa-containers-probe-20261124-package/payload.img -o /mnt/d/Code/PortingiOS/nuwa/worktree-display-dsp/out/nuwa-containers-probe-20261124-package/vendor_boot.img -D /mnt/d/Code/PortingiOS/nuwa/worktree-display-dsp --out /mnt/d/Code/PortingiOS/nuwa/worktree-display-dsp/out/nuwa-containers-probe-20261124-package/context --config /mnt/d/Code/PortingiOS/nuwa/worktree-display-dsp/out/nuwa-lsd-deep-20261124-package/build-input.toml --local-module soc:sm8550=/mnt/d/Code/PortingiOS/nuwa/UniXNU-sm8550-common -j 1
```

| 产物 | 大小 | 哈希 |
|---|---:|---|
| kernel | 52,203,520 B | SHA-256 `a16c1629b63ef666995c5fcaa9c088495621d856a73d8ed4c40b8fea51d41424` |
| vendor_boot | 100,663,296 B | SHA-256 `d8d57a241bfbda143b0d6b007a95da7ede1e18ffdc61ad79108f3d5e9e9d1ed6` |
| CHMH | 48 B | SHA-384 `b11c162e9620b45fd9556934618d2bca62c781414f0a6389844423e0531799663bba843f685a7c810271a474ff411813` |
| outer 回读 FAT | 67,108,864 B | SHA-256 `4be7d19b98ec266d0cf7724871636aecaf7922ea03d9c59a5b7772b4fba36427` |
| 编码 seed | 2,281,632 B | SHA-256 `fc233a71a8ea9aa4bf58d604fccb5606cd3327e51eb66641581c5456a8e90ed5` |

路径：`out/nuwa-containers-probe-20261124-package/vendor_boot.img`。CHMH 不变：`scripts/build-chmh-only-payload.py:digest_material` 绑定 kernel、loader、trust、args 和 parent-adt 的 SHA-256，不绑定 seed；仍是未认证实验身份，认证 NOT REACHED。纯 Python `audit-package.py` 对 FAT 全部文件逐项比较，仅 `scratch-data.img` 内容改变；基包外层 FAT 以外字节不变，outer 回读 FAT 与 staging 一致。`audit2.py` 检查 args 必需/禁区、`display-scale=03000000`、无 `text-fixups` 和 seed 哈希，均 self-checked。`fsck.fat -vn` 退出 0；`mdir` 和独立 FAT 表计数均为剩余 **11,488,768 B**。复用 `relative_layout` 对增长后的 seed 重算，剩余窗口 5,026,463,744 B；窗口基址真实分配及运行态未验证。

相对上一次设备观察的两个计划变量为 seed 目录和 12 帧+续行优先探针；探针设计用于观测显示，但它改变内核解析及存储，不能仅凭设计断言对系统行为绝无影响，也不能仅凭启动行为变化单独归因 seed。本次 seed 还按授权删除了既有 `.fseventsd`，故它也是实际 seed 差异的一部分。最终包未上机，需 `deep_reviewer` 和独立 verifier；未授权刷写。

记录检查：在 UniXNU 工作目录运行字面的 `python3.11 scripts/porting-record.py check --device .` 因该目录没有 `porting.toml` 失败；改用 `/home/wh1stl3/.local/bin/python3.11 scripts/porting-record.py check --device ../nuwa/worktree-display-dsp --base origin/display/20h392-dsp-diag`，输出 `nuwa: 14 structured areas checked`，self-checked。

## 首次制作的只读复核（历史）

将回环 raw 上传 VM，以 `hdiutil attach -readonly` 只读挂载，并以 `mount -u -o rdonly,owners` 临时启用 ownership；`mount` 确认 `read-only` 且无 `noowners`。全树清单为 342 条，较编辑阶段的 `post.txt` 340 条多出以下两条，逐行 diff 仅这两条：

```text
.fseventsd/0000000000be98e7 | 0600 | 0:0
.fseventsd/0000000000be98e8 | 0600 | 0:0
```

只读卷已卸载；两条出现的时点及原因未证实，不能称逻辑清单完全一致。依本轮止损条件未制作新 vendor_boot。第一次只读挂载尝试用 `mount -u -o owners` 失败，自动卸载；第二次显式保留 `rdonly` 成功。日志为 `out/seed-containers-20261124/roundtrip-inventory.log`。本差异不推翻下文最初执行的 raw `cmp` 结果：`post.txt` 在 writable 卸载之前采集。

两个具体风险：`iconscache/Library/Caches` 若以 0:0 创建会挡住 501 写入；空 `db/dslocal` 目录可能被消费者当成坏库。

## 输入与挂载

原始 raw 与宿主 `seed.raw.bak` 均为 8,589,934,592 B，SHA-256 `2a7e965a8c625cfe57e723b07dd582e96114d857c0cbd1857ce3863072f43479`。上传耗时 100 s，逻辑速率 85.9 MB/s（SSH 压缩）；guest 输入同 hash。guest 可用 451 GiB。

挂载命令：

```text
hdiutil attach -readwrite -noverify -noautoopen -imagekey diskimage-class=CRawDiskImage seed-containers-20261124.raw -mountpoint /tmp/nuwa-seed-containers-20261124
```

输出原文：

```text
/dev/disk6
/dev/disk7           EF57347C-0000-11AA-AA11-0030654
/dev/disk7s1         41504653-0000-11AA-AA11-0030654  /private/tmp/nuwa-seed-containers-20261124
```

卷根即 `/private/var`。初次挂载为 `noowners`，临时执行 `sudo mount -u -o owners /private/tmp/nuwa-seed-containers-20261124` 后 `noowners` 消失，`mobile` 显示真实 `501:501`；未改系统配置。

## 清单和增量

`pre.txt` 332 条、`post.txt` 340 条，均包含根 `.`；按 `lstat` 收集全树路径、mode、uid:gid，不跟随符号链接。8 条均为新建，无已存在跳过；原有条目 mode/uid/gid 变化 **0**。`comm -13 pre.txt post.txt` 全文：

```text
containers/Bundle/Application | 0755 | 0:0
containers/Data/Application | 0755 | 0:0
containers/Data/InternalDaemon | 0755 | 0:0
containers/Data/PluginKitPlugin | 0755 | 0:0
mobile/Containers | 0755 | 501:501
mobile/Containers/Shared | 0755 | 501:501
mobile/Containers/Shared/AppGroup | 0755 | 501:501
mobile/Library/Caches/com.apple.LaunchServices | 0755 | 501:501
```

每行即创建后实际 `lstat` 结果；完整 pre/post 和执行日志保存在 `out/seed-containers-20261124/`。未验证 ACL、xattr、文件 flags、时间戳或文件内容不变，目录增量及 mode/uid/gid 检查不覆盖这些属性。

## 卸载和只读检查

先 `hdiutil detach /dev/disk6`，输出 `"disk6" ejected.`。随后 `hdiutil attach -nomount -readonly -noverify -imagekey diskimage-class=CRawDiskImage` 重附镜像，`sudo fsck_apfs -n /dev/disk6` 输出：

```text
** The volume /dev/rdisk7s1 with UUID B0E0F71F-A265-4038-8F5C-6D3632859DEF appears to be OK.
** The container /dev/disk6 appears to be OK.
```

命令 exit 0；只读重附后的 `hdiutil detach /dev/disk6` 输出 `"disk6" ejected.`。完整输出在 `out/seed-containers-20261124/fsck.log`。

## 产物

编辑后 raw：`out/seed-containers-20261124/seed-edited.raw`，8,589,934,592 B，SHA-256 `340e2c202115100c76ed35d4f32426d71ae904f3cc457edaf2ef44b494ab7f9b`；guest 与宿主 hash 一致，下载 205 s。

WSL 官方 `UniXNU/drivers/DarwinBoot/Test/packed_ramdisk.py` 编码得到 `out/seed-containers-20261124/seed-encoded.img`，2,486,432 B，SHA-256 `628b0b0a7709af3f7f364d2bbc2ecc73faadf115be3aa0ca5b2db2803b0bde52`。编码器输出的 `sha256` 为大镜像 `SHNGSEED2` 身份，不是 raw 文件 SHA-256。

使用官方 `regions()` 展开至 `seed-roundtrip.raw`（8,589,934,592 B，8 extents），`cmp seed-edited.raw seed-roundtrip.raw` 退出 0，逐字节一致。完整编码和比对输出在 `out/seed-containers-20261124/encode.log`；本轮未做独立 verifier 复跑。
