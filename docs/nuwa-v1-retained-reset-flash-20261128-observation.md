# nuwa retained v1 reset r3 单次刷写 — 2026-11-28

状态：**device/self-checked**。reset r3 仅刷入 `vendor_boot_a` 一次，bootloader
返回 Sending/Writing OKAY、exit 0；未重启、未启动。刷后最后一次只读查询仍为
nuwa、bootloader fastboot、槽位 a。没有分区字节回读、运行时或 Data 挂载证据。

## 授权、审查及保留条件

- 用户当轮授权只刷一次 reset r3 到 `vendor_boot_a`，不重启、不切槽、不刷其他
  分区、不初始化、不写 `userdata`。日常包只核对哈希，不刷。
- `deep_reviewer` 对 r3 两份最终 outer 的终审为 **PASS WITH CONDITIONS**，
  会话 `ses_de05c0974ffeUCPfM5MRsnAzb5`；是深审，不是“方案 B 审查，未经
  deep_reviewer”。该审查核对了两包 outer、FAT、kernel、CHMH 和目标机器码；
  不等于设备运行、介质耐久或队列所有权证明。
- 终审原要求刷前具备本次启动域的 retained 队列交接及旧 DMA 已排除依据，
  否则不刷。**用户当轮明确接受缺少该独立证据的残余风险，仍要求本次刷入**；
  这不是声称队列交接或旧 DMA 排空已证实，瞬时 `DB=0` 也不构成排空证据。
- 终审另要求 LU0 `[59491258, 61588475)` Data 窗口有已校验备份或用户明确
  同意丢弃。未找到该窗口已校验备份；用户在本轮明确选择“接受丢弃风险”，
  知悉将来启动 reset 包后窗口已有 Data 可能无法恢复。此确认不是本轮启动、
  初始化或写 `userdata` 的授权，且本轮未执行这些动作。
- `out/nuwa-boot-payload-write-20261115-01/ROLLBACK-r9.md` 保留在
  `UniXNU-nuwa/`。刷前实算同仓 `out/nuwa-ufs-apfs-root-chmh-20261115-r8/vendor_boot.img`
  为 100663296 B、SHA-256
  `8e09fae228f985eb4efc7bcf9d8c2c55b594f499af1f48a91f53db431e1ff66e`，
  `out/nuwa-boot-payload-write-20261115-01/vendor_boot_a.stock.img` 为
  100663296 B、SHA-256
  `493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`，
  与已有回滚记录一致；未执行回滚。恢复启动载荷不能恢复 Data 窗口 bitmap。

## 设备门禁及产物

首次只读门禁在 12:28:50–12:28:51 完成。等待风险确认后，12:40:01 在同一
主机进程重新枚举：`adb devices -l` exit 0、0 台；`fastboot devices` exit 0、
2 台，逐台只读 product 为 `enuma` 和 `nuwa`；唯一 nuwa 与首次选择的固定
serial 相同。serial 不入库。

| # | 时间 +08:00 | 字段 | 读数 | exit |
| --- | --- | --- | --- | ---: |
| 1 | 12:40:01.160 | product | `nuwa` | 0 |
| 2 | 12:40:01.202 | is-userspace | `no` | 0 |
| 3 | 12:40:01.240 | current-slot | `a` | 0 |
| 4 | 12:40:01.276 | partition-size:vendor_boot_a | `0x6000000` | 0 |
| 5 | 12:40:01.312 | product | `nuwa` | 0 |
| 6 | 12:40:01.348 | is-userspace | `no` | 0 |
| 7 | 12:40:01.383 | current-slot | `a` | 0 |
| 8 | 12:40:01.423 | partition-size:vendor_boot_a | `0x6000000` | 0 |

两次门禁各八项均 exit 0、全部匹配，无失败重试。刷前重新实算：

| 产物 | 长度 | SHA-256 | 操作 |
| --- | ---: | --- | --- |
| `out/nuwa-v1-retained-20261128-reset-r3/vendor_boot.img` | 100663296 B | `213cdf065fe5eab45215f96c2efb12a8c320d51a4efadfcd586dd71140dd942d` | 唯一刷写 |
| `out/nuwa-v1-retained-20261128-daily-r3/vendor_boot.img` | 未单独核对 | `25eed03ccca975d6fad9d2cb743a2b3ba47cef45f7c66fecf96457f771f47180` | 只核哈希 |

reset 镜像的只读文件句柄从实算哈希一直持有到刷写返回，禁止并发修改。

## 唯一刷写及刷后状态

```text
12:40:01.774 fastboot -s <fixed-nuwa> flash vendor_boot_a <reset-r3>
Sending 'vendor_boot_a' (98304 KB)                 OKAY [  2.266s]
Writing 'vendor_boot_a'                            OKAY [  0.030s]
Finished. Total time: 2.328s
12:40:04.143 exit 0
```

标准输出为空；以上 fastboot 回执来自标准错误。未重试，无 AVB footer 警告。
刷后对同一 serial 查询，12:40:04.190 `product=nuwa`、12:40:04.227
`is-userspace=no`、12:40:04.266 `current-slot=a`，均 exit 0。未执行 reboot、
切槽、初始化、其他分区刷写或主机 `userdata` 写入；最后观测时设备仍在
bootloader fastboot。bootloader 的 OKAY 不是分区内容回读。

## 未验证及后续停点

reset 尚未启动，**Fresh (state 3)**、日常 **Resumed (state 2)**、真实 Data
读写、介质 FUA/flush 耐久和交互均未验证；认证仍 NOT REACHED。reset 参数不是
自清除标志：未来启动须另获当轮授权，且终审要求 reset 只启动一次，观察到
Fresh 才能考虑切换日常包；失败或结果不明即停止，不自动重试或继续启动。
主机构建与测试仅 self-checked，独立 verifier 未复跑。

本轮 WSL 主机自检：`tests/test-nuwa-v1-retained.py /mnt/d/Code/PortingiOS/UniXNU
out/nuwa-v1-retained-20261128-build-r3` 的 12 个情形 exit 0；另从 UniXNU 目录
执行 `scripts/porting-record.py check --device <本工作树> --base origin/main`
检查 14 个区域。WSL 首次检查因工作树 `.git` 中为 Windows 绝对路径而失败；
改以 WSL 绝对路径设置 `GIT_DIR` 与 `GIT_WORK_TREE` 后检查 exit 0。新增待提交
路径另按同一记录的 `check_changes` 校验；这些均为 self-checked。
