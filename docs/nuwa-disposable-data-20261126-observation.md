# nuwa disposable Data 2026-11-26 刷写门禁记录

## 三分区 named flash 单次授权（2026-11-26）

- 用户当轮明确批准仅本轮按分区名称刷写免 GPT 回读；reviewer 条件为只刷不启动。任一门禁不明或冲突、任一刷写失败或结果不明立即停止，不自动重试、回滚或继续后项。
- 仅功能重建，不是逐字节回滚；旧 loader SHA256 前缀 `692cfcca…`，旧 vendor SHA256 前缀 `6695da98…`；原 recovery 无当前前像。
- 只允许各一次写 `boot_a`、`vendor_boot_a`、`recovery_a`；不切槽、不初始化、不写 userdata、不进入 recovery；完成后留在 bootloader fastboot。无法 fetch 不称回读。
- 写前 self-check：adb 无设备，fastboot 枚举一台，固定设备查询 `product=nuwa`、`is-userspace=no`、`current-slot=a`，均 exit 0；三分区 `getvar partition-size` 分别为 `0xC000000`（201326592）、`0x6000000`（100663296）、`0x6400000`（104857600），均 exit 0，与 `UniXNU-nuwa/docs/nuwa-ufs-info-20261125.md` 历史 GPT 摘要一致，各输入长度均容纳。
- 指定 boot/vendor/recovery 文件分别为 100663296/100663296/104857600 B，SHA256 分别为 `594ff64b1adf14abb54b433ced9e6942b8148547d8ce35235be6baf5caa7b10c`、`493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`、`bc6b688320fe9d1b41c3294c3ec84254e8c0619ded4068d71ce024729c74f55c`。旧 loader 本地文件 `UniXNU-nuwa/.cache/boot-stage12-v4-r4.img` SHA256 `692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5`，旧 vendor 本地文件 `out/nuwa-disposable-data-package-r2/vendor_boot.img` SHA256 `6695da9842f4da4d26c1f028adc48f3ffb8f6f369420653492028a74bf362fa5`，均 self-checked；不证明设备前像。
- `boot_a` 单次 flash：`Sending 'boot_a' (196608 KB) OKAY [4.544s]`，`Writing 'boot_a' OKAY [0.070s]`，exit 0；报告发送大小为 196608 KB，输入文件实际 100663296 B，原因未核实；仅写入确认，非回读。
- 因发送大小与输入文件大小不一致、原因不明，按结果不明止损，停止后续 `vendor_boot_a` / `recovery_a`；不自动重试或回滚，不重启。当前 boot_a 整个分区的实际内容未知。

### 余下两项续行（2026-11-26）

- 主控转述 reviewer `ses_de8c5b5f0ffewjySyNMAkrcalx` 裁定 PASS WITH CONDITIONS：boot 镜像 AVB footer 需定位到分区末端，fastboot 对较小输入按目标分区大小扩展，解释此前 196608 KB 发送量；此解释不是设备回读或启动成功证明，原停止记录保留。
- 原授权继续有效；只刷不启动，绝不重刷 boot_a；本轮 vendor_boot_a 与 recovery_a 迄今均未尝试。各项发送字节数、Sending/Writing OKAY 和 exit 0 必须符合指定，异常立即停止，不重试、不自动回滚；不切槽、不碰 Data。
- 续行门禁 self-checked：工具 `D:\AndroidPhoneStuff\platform-tools\fastboot.exe`，`fastboot version 37.0.1-15733141`，version exit 0。`devices` 脱敏输出 `<serial> fastboot`，唯一设备、与先前固定 serial 一致，exit 0。
```text
product: nuwa                         EXIT=0
is-userspace: no                      EXIT=0
current-slot: a                       EXIT=0
partition-size:boot_a: 0xC000000      EXIT=0
partition-size:vendor_boot_a: 0x6000000 EXIT=0
partition-size:recovery_a: 0x6400000  EXIT=0
```
- 两个指定文件完整路径、长度、SHA256 重新核对：`D:\Code\PortingiOS\nuwa\out\nuwa44-recovery-original\vendor_boot.img` 100663296 B `493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`；`D:\Download\ChromeDownload\twrp-3.7.1_12-v9.0_A16-nuwa-skkk.img` 104857600 B `bc6b688320fe9d1b41c3294c3ec84254e8c0619ded4068d71ce024729c74f55c`。最初尝试使用 Python 做只读门禁时系统未找到 Python、未执行设备命令；随后用 PowerShell 完成上述门禁。
- 单次 `fastboot -s <serial> flash vendor_boot_a` 原始脱敏输出：
```text
Sending 'vendor_boot_a' (98304 KB)                 OKAY [  2.267s]
Writing 'vendor_boot_a'                            OKAY [  0.036s]
Finished. Total time: 2.335s
FLASH_EXIT=0
```
- 单次 `fastboot -s <serial> flash recovery_a` 原始脱敏输出：
```text
Sending 'recovery_a' (102400 KB)                   OKAY [  2.361s]
Writing 'recovery_a'                               OKAY [  0.036s]
Finished. Total time: 2.428s
FLASH_EXIT=0
```
- 两项仅收到刷写确认，未 fetch、未启动；未重刷 boot_a，未重启、切槽、写其他分区或碰 Data，留在 bootloader fastboot。效果和设备侧内容尚未验证。

### 原始 recovery 下一步只读追踪（2026-11-26）

- 本节仅主机静态分析，不是启动授权或安全放行。对象是上面实际刷入的 `bc6b6883…` 原始 recovery 的 ramdisk 和 `493ca426…` .44 原始 vendor_boot；未使用 ZIP 内另一份 recovery。已有 `out/twrp-nuwa-host-20261121/ramdisk.lz4` 与原始 recovery 头指定的偏移 4096、长度 80494888 的 ramdisk 逐字节相等，SHA256 `b763936637df810b73fff9ccb9f67a6b52fbb34329022a314fd9f02ef65cc6b9`。vendor ramdisk 用项目现有 `unixnu.vendor_boot.parse` 从指定原件读取。临时解包仅供只读检查；未改镜像、未访问设备。
- ramdisk `system/etc/init/hw/init.rc:1–6,81–92,103–116,155–156` 导入 recovery rc，late-init 触发 fs 与 boot；满足 USB 属性时启动 adbd。`init.recovery.qcom.rc:32–43,49–50` 在 `ro.hardware=qcom` 时 fs 创建 `/tmp/persist` 并 bind 到 `/mnt/vendor/persist`，其中 `/tmp` 是 init.rc:47 的 tmpfs；这条 bind 自身不是对 persist 分区的写。boot 设置 `sys.usb.config=adb`；属性与服务并发，不能把 adb 可见当作其它动作尚未执行的屏障。
- 同一个 recovery 的 `system/etc/recovery.fstab:55–58` 指向真实 metadata、userdata、persist；persist 为 ext4，未标 `ro`。指定 .44 vendor 的 `first_stage_ramdisk/fstab.qcom:82–86` 亦列 metadata 的 `first_stage_mount,check,formattable`、persist 的 `wait,check` 且未标 `ro`、userdata 的 `latemount,check,formattable`。这些条目提供处理路径，不单凭 fstab 证明对应挂载、检查、修复或格式化实际发生；尤其 vendor persist 条目没有 first_stage_mount，不能据此断言它在 adb 前挂载。
- `init.recovery.service.rc:4–6` 的 recovery 服务没有 `disabled`；init.rc:71–76 的 boot `class_start default` 可启动该服务，非等待用户点击。recovery 二进制的启动处理、bootloader message、数据解密、自动挂载及脚本执行未在此次 rc/fstab 有界追踪中闭合；缺实际参数和二进制行为证据，**不能排除** adb 前自动写真实 persist 或其他禁区，也不能声称已有可达的真实 persist 写操作。modem 明示只读挂载于 `init.recovery.qcom.rc:52–65` 的条件路径，不证明其他禁区安全。
- metadata 的 first-stage/check 和 userdata 的 latemount/formattable 是自动处理的潜在入口，不等于启动必然 format；TWRP 自启动也不等于用户手动执行 Format Data。手动 format 是额外明确交互并可能破坏数据；无交互启动仍可能有挂载、检查、解密或已有指令触发的写入，不能视作只读。实际执行与写入范围尚未验证。
- 审查留痕：前述续行 reviewer `ses_de8c5b5f0ffewjySyNMAkrcalx` 的 PASS WITH CONDITIONS 只解释 boot 发送尺寸并限定只刷不启动；这里没有针对 recovery 启动前写路径的放行审查记录。是否方案 B、是否经 deep_reviewer 未知。三分区没有分区级回读，设备状态只以当时记录为准；本次没有新设备操作。静态追踪 self-checked，独立 verifier 尚未复跑。

- 主控转述：reviewer `ses_de9472eafffeKFd97G3SAqSZF1` 对最终候选及其 diff 给出 PASS WITH CONDITIONS；本次审查和授权范围仅为单次刷写 `vendor_boot_a`，不重启、不初始化、不写其他分区或 Data。是否为方案 B、是否经过 deep_reviewer 未在本次委派中说明。
- 指定候选 `out/nuwa-disposable-data-package-r2/vendor_boot.img`，SHA256 `6695da9842f4da4d26c1f028adc48f3ffb8f6f369420653492028a74bf362fa5`。`Get-FileHash -Algorithm SHA256` 实测相同（self-checked）。
- 所要求的只读回退基线 SHA256 为 `18fa4941696667d1813442022ea71fc48e4c414b1abadb1caf73774fcc76202a`。既有 [操作记录](nuwa-ufs-neon-20261126-observation.md) 第 4 行所列的本工作树 `out/nuwa-ufs-neon-20261126-package/vendor_boot.img` 不存在；`Get-FileHash` 报路径不存在，故未能复核可用回退文件及其哈希。回退仅针对启动载荷，不恢复 Data；另见 [回退记录](nuwa-ufs-neon-20261126.md#reproduction-and-rollback)。
- 在第一个不满足的门禁处停止：未执行设备枚举、flash、回读、模式切换、重启或初始化；无 flash 输出或退出码。候选和回退镜像均无本轮设备分区回读，设备当前槽和状态未核查。

## 路径更正与续行（self-checked）

- 用户指出回退包不在本工作树。实际路径 `D:/Code/PortingiOS/nuwa/worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-package/vendor_boot.img`，实算 SHA256 `18fa4941696667d1813442022ea71fc48e4c414b1abadb1caf73774fcc76202a`；其审查和刷入记录在同工作树 `docs/nuwa-ufs-neon-20261126-observation.md`。先前停止是路径判断错误，不代表该文件不存在。
- 再次实算候选 SHA256 `6695da9842f4da4d26c1f028adc48f3ffb8f6f369420653492028a74bf362fa5`。按用户继续授权，后续仅在唯一 fastboot nuwa 且当前槽 a 时单次刷 `vendor_boot_a`；不重启、初始化、切换模式或写 Data。
- `fastboot devices` exit 0，枚举 1 台；固定 serial 查询 `product: nuwa`、exit 0，`current-slot: a`、exit 0。serial 脱敏不入库。
- 固定同一 serial 单次执行 `fastboot -s <serial> flash vendor_boot_a`，指定上述候选文件，实际输出：

```text
Sending 'vendor_boot_a' (98304 KB)                 OKAY [  2.260s]
Writing 'vendor_boot_a'                            OKAY [  0.030s]
Finished. Total time: 2.322s
FLASH_EXIT=0
```

- 未做分区回读，OKAY 不证明镜像回读一致；未重启、初始化、切槽、写其他分区或 Data，运行效果尚未验证。
