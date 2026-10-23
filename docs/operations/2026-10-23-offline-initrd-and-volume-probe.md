# 离线 ABL 拼接审查与系统卷探针

## 范围与当前状态

用户说明目前不在设备旁，中午可配合。本轮完全离线：没有 ADB/fastboot 命令、设备模式切换、临时启动或刷写。SHENGMEM 运行日志仍未取得，不把未读到日志当成驱动未执行。R-011 已进入 UniXNU 菜单并恢复 Android 的结论不变，未进入 XNU。

本次产出两部分：固定安装版 ABL 的相关静态指令；构建只含配置标记的 FAT32 组件并用本机 WSL 工具验收。**探针卷未接入固件或 Android 启动包，目前不能直接用于实机试启动。**

## 安装版 ABL 的代码证据

只读来源为归档 abl_a.img，SHA256 `38a837fa917ff45e5be7cf6a421e0417015d875db503d1fb2dbc4d89080b0188`。与此前 `reports/abl-handoff/live-inputs.json` 中安装版 A/B 摘要一致；这不是本轮重新读取设备的结果。内存解包得到 LinuxLoader PE SHA256 `b489faff3f66a415af69b73fe23a59fb9469da0b70aeb4a1792201e22b5bb116`，未输出或改写固件二进制。

`audit-abl-handoff.py` 增加 `--output`、`--focus-ranges`：新报告只能放本仓 reports 内且不能覆盖既有文件；旧 disassembly.json 保持不变。下面地址均为 PE preferred VA，**不是运行 PC 或可填写的板地址**。

| 代码位置 | 可直接观察的行为 |
| --- | --- |
| c8a4–c8b0 | 比较调用上下文的版本字段与3，低版本跳过前置复制 |
| c8b8–c8f8 | 通过 BootServices +0x160（CopyMem）复制 info+0x94 指定的字节数，然后按该原始长度推进目标地址，没有按512对齐 |
| c8fc–c974 | 存在受条件控制的附加复制分支；不能忽略 recovery 路径或宣称所有分支均执行 |
| c978–c9b8 | 后续复制使用 info+0x7c 的源偏移及 info+0x78 的长度，再推进目标 |
| cbe0–cc40 | 版本至少4时按若干页对齐长度定位另一个源段，复制 info+0x90 字节 |
| cc44–cc98、cd60–cd84 | 调用768d0处理后段，使用返回末地址调整记录的长度 |
| 768d0–76ac0 | 后段辅助函数可移除既有20字节尾部，复制附加内容，再调用76b70生成尾部 |
| 76bcc–76bdc | 生成辅助路径把末地址按4对齐；不能据此推导512字节块设备对齐 |

与 vendor/generic ramdisk 和 bootconfig 的对应关系来自其数据使用方式及附近日志，是静态语义归属；内部分支是否在 fastboot boot 的本候选中走过、fragment 是否筛选、实际指针和最终长度均未验证。完整相关字节/指令见 `abl-initrd-focused.json`、`abl-initrd-fields.json`；`abl-initrd-contract-check.json` 固定14处指令检查和报告哈希。大范围初始提取仅保留在忽略的 out，不提交无关反汇编。

恢复后 Android 头字段示例中 vendor 长30899943B，模512余231；generic 长2969050B，两者和33868993B。实际 Android chosen 长33870292B，差1299B仍未分配给具体内容。即使把 generic 字段换成整扇区 FAT，也不能推导整段 chosen 从 FAT 的 BPB 开始或总长能被512整除。不能通过把末地址向上取整来“修复”，因为那会扩大未经确认的可读范围。

复现（输出路径必须尚不存在）：

```powershell
python -B scripts/audit-abl-handoff.py --output reports/system-volume-audit/abl-initrd-focused.json --range 0xc470:0xc570 --range 0xc89c:0xc9c8 --range 0xcbe0:0xcc98 --range 0xcd60:0xcdac --range 0xee00:0xf500 --focus-ranges --quiet
python -B scripts/audit-abl-handoff.py --output reports/system-volume-audit/abl-initrd-fields.json --range 0xf500:0xf7b0 --range 0x768d0:0x76c80 --range 0xd0e0:0xd340 --focus-ranges --quiet
```

## 同 SoC 来源评估

`same-soc-contracts.json` 固定实际读取的源码、提交、SHA、依赖及适用边界。

- UniXNU/uefi-sheng@329b473df1e53a3bfa64b2b39b79670c4c02279b 的 ShengBootMemoryDxe.c，SHA060a248a44fd06dc36af48b84f7b077e4d773255b38d7ba169750f04a1171bd4；许可依据固定 README 的 BSD-2-Clause（不在 GPL 目录）。它提供既有 FDT/HOB→只读 BlockIo 机制，但同样要求整个 initrd 整扇区，不提供 v4 拼接拆分方案；其 DRAM/GCD 扩展政策不适用于本次 nuwa 接线，不复制。
- 本地 UniXNU-sheng@a599a1a8a92093b5077543e071b72130769eb325 的 board.toml 未声明本次所需的 `[bootimg.image]` header_version；该快照不能回答安装版 nuwa ABL 的具体行为。不从空缺推导默认版本，更不借用 prelink/地址字段。

结论：同 SoC 代码可继续复用既有发布机制，但无法替代实际 initrd 捕获，暂不引入另一板内存策略或仅凭 header_version 切换容器。

## FAT32 探针组件

复用固定 UniXNU@75bc13dd 的 `scripts/unixnu/payload.py:write_volume` 中 mformat/mcopy 制卷方法，未运行完整 payload.build，未生成伪内核或伪 ADT。构建前用只读 git show 比较本地源码与固定提交，记录源码归一化 SHA；依赖 mtools 4.0.32、dosfstools fsck.fat 4.2，均在本机 WSL Ubuntu-22.04 执行。

命令：`python -B scripts/build-volume-probe.py`。脚本要求新输出目录，避免覆盖既有组件。静态配置为 `config/volume-probe/unixnu.toml`，仅含一个 exit action，菜单标题 `NUWA VOLUME PROBE - NO XNU`，等待60秒后回固件；不引入 OS entry、driver、内核参数或板值。配置键与实际固定 Config.c 的解析字段核对；未执行目标 C 解析器，不将 Python TOML 解析视作完整运行验收。

- 组件：`out/volume-probe/volume-probe.fat.img`，67108864B（64MiB），SHA256 `bc0b3eae88e0dd8a528b3469d0fa9c3fa21c99097af842cab42c28cfa5068ff2`。
- FAT32：512B扇区，129022个数据簇；标签NUWAPROBE。此容量是磁盘文件容量，**不是**新内存基址、board dram_size 或 XNU owned_memory_size。
- mtools目录检查、mtype配置逐字节读回、fsck.fat -n 均退出0；命令/完整输出见 `volume-probe.json`。这属于离线制卷与静态检查通过，非 QEMU 或实机通过。
- 二进制仅在忽略的 out，未提交。未复制上游源码进本仓；两个旧目录只读。

## 后续方案与中午最小验证

当前推荐先取得同一已验收固件的运行 SHENGMEM 信息，再选择运输路径，不追加一次无明确观察目标的试验。

| 路径 | 作用与代价 | 当前状态 |
| --- | --- | --- |
| A：沿用 chosen initrd，加有明确边界的载荷定位 | 保留官方 BlockIo/FAT 发现链；需先确认候选 x0/chosen、vendor 前缀与 bootconfig，不能硬编码 Android 地址或全局搜索一个 FAT 字符串就信任 | 首选先取证；定位/保留策略未实现 |
| B：FV 内嵌小探针卷，UEFI 动态分配后发布 BlockIo | 可独立验证 Config.c 文件发现；需要新增 FV RAW 资源读取/内存保留接线并编译。小配置成功也不解决真实大内核运输及 FD 空间 | 备选，未实现，不宣称可启动 |

当前没有新的完整试启动包。中午用户在场后，若执行现有包的定向日志复测，应先通知录像并重新核对 nuwa 身份、原 boot 摘要与恢复门；观察从 SEC/DXE 开始到菜单，优先读 SHENGMEM 的 device tree、initrd start/end、no initrd、not a whole number of sectors、block device 状态。录像中的指针仅作为该次运行证据，不自动变成 board 常量。

本次不设置自动启动或中午定时任务。用户未回到设备旁前不做设备动作；新试验缺日志/恢复条件时才按硬停规则写 NEED-REVIEW，不因离线生成探针组件另设审批门。真实 Darwin22预链接、目标ADT和XNU验收仍独立待办。
