# v4固件入口包首次实机临时启动

2026-10-22 20:15–20:22（Asia/Shanghai）。用户明确批准：“临时启动咱们已准备的v4固件入口包，检查ABL、SEC和DXE/BDS的实际结果”。本轮仅fastboot临时加载候选与原厂恢复；没有flash/erase/改槽位，没有生成或修改镜像、board/feed或_verified。

## 实际结果

| 层次 | 本轮证据 | 结论 |
| --- | --- | --- |
| 输入/目标 | 镜像3153920B/SHA12864ac6cc0ffc9909f4abbdfab91bfee216c3fdcfc5ab0d52b4d4b9cf4579f9；nuwa/kalama身份，fastboot product=nuwa、unlocked=yes、slot=a | 对指定实机执行了指定候选的临时启动命令 |
| ABL命令受理 | Sending 3080KB OKAY，Booting OKAY，fastboot退出0，约0.194s | 实机观察到命令层接受；不能扩大为已完成内核装载/BootShim跳转 |
| 屏幕 | 用户在启动后观察问题中回复“黑屏” | 只记录黑屏，未观察到UEFI/UniXNU菜单；不推定异常类型 |
| USB/bootloader | 启动后约29s的15次采样均仍枚举到同一nuwa fastboot序列；后续product查询可响应；Windows接口VID_18D1&PID_D00D | 观测期内fastboot接口持续可见；不能判断是否完全未跳转或短暂执行后返回 |
| BootShim / SEC | 无入口标记、串口或可归属日志 | 未验证，不能写实机通过，也不能断言SEC崩溃 |
| DXE / BDS | 无可归属日志或菜单证据 | 未验证；固件bring-up阶段1未获通过证据 |
| XNU | 候选不含本仓内核/新FAT负载 | 本轮未验收XNU/iOS执行 |

原始证据reports/v4-firmware-trial/launch.json、usb-after-launch.json、summary.json；命令由scripts/trial-v4-firmware.py执行，ADB选择同时核对产品和root DT，主机有另一台enuma但未对其重启/写入。序列号只在进程内用于选择，日志脱敏。USB全主机ADB计数不是nuwa的专用计数，不能拿它判断nuwa ADB状态。

## 恢复全过程与本轮新事实

1. 候选命令后直接对仍可响应的nuwa执行已锁定原厂v4 boot临时启动：Sending196608KB OKAY，但Booting返回Load Error；记录recovery.json。原厂输入SHAef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31与此前成功恢复时完全相同。
2. 执行`fastboot -s <selected-nuwa> reboot bootloader`，成功；重新枚举、读取product=nuwa，未改slot或分区。记录reset-bootloader.json。
3. 再临时加载同一原厂boot：Sending/Booting均OKAY。按ADB产品及DT nuwa/kalama识别目标，等待sys.boot_completed=1，恢复成功。记录recovery-after-loader-reset.json。
4. 最后再次读取nuwa Android sys.boot_completed=1，boot reason为bootloader，pstore目录为空，见post-recovery.json。恢复后的boot reason描述的是本次原厂启动上下文，不能归因候选失败点。H-001未按键，保持未验证。

上述只证明同一原厂输入在重进bootloader前失败、后成功，不能直接归因内存破坏或某个ABL缺陷。但后续镜像版本/ramdisk大小对照必须隔离bootloader状态：每个实验从重新进入的bootloader开始，每轮结束重进bootloader后再执行原厂恢复，不能凭未隔离状态的一次Load Error作唯一接受条件结论。该事实也再次限制参考F-016的外推。

本轮结束时nuwa已在原厂boot临时启动的Android，boot_completed=1；A槽持久启动状态仍未修复。没有以刷写/改槽位达到恢复，也没有把临时恢复写成持久正常启动或硬挂按键恢复已验收。

## 下一步

首要缺口是观测能力。先只读核对原厂ARM64入口/候选BootShim头与执行前提、现有SEC DebugLib输出出口，确定可回收的早期日志或可区分阶段的标记；获得证据后再决定诊断改动。黑屏本身不能证明面板、内存或DT导致失败，也不能跳过BootShim/SEC直接排查DXE/BDS。

当前v4包既未被命令层拒绝，也没有固件执行成功证据。保留原镜像/hash供受控对照；不为了追求Booting OKAY混入r6旧内核/6GiB ADT，不自动重打v1，不修改内存板值。任何新增诊断镜像/板字段范围按已有授权和具体硬停规则落实，不在本轮单次已准备包测试中扩大设备写入范围。
