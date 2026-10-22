# R-007 A：SEC阶段诊断构建与临时试启动

## 授权与固定范围

用户明确批准R-007 A：构建SEC阶段诊断固件、检查产物并准备临时启动包，按既有授权试启动，结束恢复Android并确认boot_completed=1。不扩展为v1/FAT/XNU/刷写/槽位或板内存修改，不置_verified。

固件源码在独立仓wh1stl3/uefi-nuwa的codex/nuwa-sec-trace，固定5e4a8c814b89f62a4ba2bc145249314fed5db787，父0a3a51a；只改Silicon/Silicium/SiliciumPkg/Sec/Sec.c，其LF SHA6af8dd4d45476fb3b0a387b8d85913765c6d6b1bcdab99f3c6275cc9a5b1efaa。完整Git tree/commit通过GitHub API身份核对发布，稳定分支保持。初次本地commit因新检出无作者配置未成功；随后仅该命令使用设备仓相同身份，未改全局Git配置。

config/firmware-sec-trace-profile.json从稳定dedicated profile派生，只改作用域/审批/来源证据、固件提交和SEC hash；31项输入逐项检查通过，四模块/两包/一条Darwin22 ABI patch及board/feed保护相同。本地未初始化子模块仅借固定只读缓存作输入校验，不是本地完整构建。工作流显式选择sec-trace，默认dedicated仍保留。

## 产物审计准备

验收器增加--require-sec-trace，读取实际SEC TE里的六个阶段字符串与状态/x0格式；存在字符串不代替调用/执行证明。同时修正NuwaBootMemoryDxe改名后仍比较旧名字导致漏走HOB/DEPEX检查的问题，强制嵌入PE与独立EFI至少一份hash相同。对稳定CI39805110487补查665项通过，记录reports/sec-trace/stable-artifact-recheck.json；原报告保持。

## 后续受控执行

构建成功后下载，核对固定输入、全inventory、四EFI/FV/DEPEX/HOB/PCD、SEC阶段字符串和BootShim长度/机器码。包仅复用哈希锁定原厂v4头，修改kernel_size并放入该轮实际shim+FD，不加DTB、FAT或XNU；原厂恢复镜像SHAef558db2a4fb021259d7af47a2398d7e56476d759162e7819959cd701a11ff31。

设备动作前按实际Android DT nuwa/kalama筛选，排除同时连接的enuma。进入bootloader后验证product=nuwa、unlocked=yes和槽位观测；按D-016重新进入bootloader隔离状态。临时boot后记录命令接受/USB模式与用户屏幕观察，各自分开；不把ACK写成SEC通过。结束先重进bootloader再临时加载原厂boot，确认实际nuwa Android sys.boot_completed=1。只差实体键记PENDING-HUMAN，恢复若需要用户在场按NEED-HUMAN记录。

当前仅源码/profile与审查工具准备完成，尚未编出这份诊断FD、未生成新boot容器、未执行设备。实际结果随本轮取证追加。

## CI调度与包/恢复脚本

39809636575固定device_ref=f897f90189516fda7d56a6ae43d986f0e937b86d，--profile sec-trace；23:57:18至23:58:06安装通过后进入构建。实际产物尚待取证。

scripts/prepare-sec-trace-boot.py按run_id定位实际artifact，严格比较runner recipe/profile/runid，重新执行全部产物检查和SEC标记门，再哈希核对原厂boot、验证v4/无ramdisk/无signature，仅写kernel_size、拼该轮shim+FD并独立重解析边界/写后hash。只写新out/trial-boot/sec-trace-RUN目录，拒绝覆盖；报告放reports/sec-trace/RUN，不含序列号。

scripts/trial-v4-firmware.py新增--package，仅允许reports/sec-trace下R-007 A/v4/无DTB/FAT/XNU的包，候选路径限out/trial-boot。原厂恢复哈希必须匹配；launch还核对候选哈希，recover不依赖候选文件仍存在或内容正常。launch/recover均先fastboot reboot bootloader重查nuwa，结束显式确认Android=1；不调用flash/erase/set_active。帮助入口已检查，实际设备行为以本轮实测记录为准。

## 诊断固件与包实际生成（2026-10-23 00:05）

CI39809636575 success，00:03:47结束；实际编译5分32秒。31项来源与构建后保护通过；下载后全部665项inventory文件hash、四模块PE/GUID/DEPEX/HOB/PCD/嵌入一致性、SEC TE中全部六阶段/状态格式字符串及BootShim复制量检查通过。字符串存在只作静态检查，不构成调用执行证明。

诊断FD3145728B，SHA9ea347a49e51472adac987cf12e20f9e0d99453a23f2113ad24efcd0a07f2eaf；112B shim仍9346a527。受限v4包3153920B，SHAfbb7940a8ee8cb5f2577a30bc2e5fb5bc31e1b84930c05b40c6304dfe970bcde，唯头字段kernel_size改变，无ramdisk/signature/DTB/FAT/XNU；拼接边界与写后hash检查通过。报告artifact-inspection.json/package.json，二进制仅out/trial-boot/sec-trace-39809636575/boot-sec-trace-v4.img。

00:01只读恢复核对：实际nuwa/kalama、Android完成1、槽A，当前内核5.15.195-MorizukiNeko-260620LTSC为自定义Android内核。当前boot_a SHAef558db2与vendor_boot_a SHA5ad2a9dc分别匹配已有备份；init_boot_a SHA19e95d95匹配上轮已root记录，与备份996572d3不同。恢复只临时加载已验证Android备份boot、继续使用安装的vendor_boot/init_boot，不覆盖rooted init_boot，不称完整恢复为原厂系统。此前文中的“原厂恢复源”沿用文件角色命名，实际是已验证的原Android备份。

新增只读USB VID/PID快照工具，InstanceId仅用于提取VID/PID，不保存序列号；试前状态在usb-before.json。尚未试启动；后续launch/recovery分开记录并确认Android=1。

## 实际试启动与恢复（2026-10-23 00:07–00:09）

实际选择唯一nuwa/kalama且Android=1，adb进入bootloader后额外fastboot reboot bootloader隔离状态；重查product=nuwa、unlocked=yes、current-slot=a。临时启动本轮唯一哈希锁定诊断包fbb7940a：Sending boot.img (3080KB) OKAY 0.082s、Booting OKAY 0.117s，总0.201s。命令退出0仅为ABL命令接受，不是BootShim/SEC执行证明。

用户直接回报原文：“fastboot之后黑屏”。没有报告阶段文字。00:07:21.441至00:07:50.395的15次采样，选中nuwa始终可在fastboot枚举；试中Windows快照含18D1:D00D，另一个Android设备仍在18D1:4EE7。不能据此区分从未交接、迅速返回或显示不可见；本实验未把执行区间缩小到具体SEC子阶段，也没有独立USB日志。

恢复阶段再次fastboot reboot bootloader，然后临时加载201326592B/SHAef558db2的已验证原Android备份boot，Sending OKAY 4.483s、Booting OKAY 0.117s。00:09:01.944明确核对实际nuwa/kalama且sys.boot_completed=1。未执行flash/erase/set_active；末次read-only确认slot_a，boot_a/vendor_boot_a/init_boot_a三个全分区SHA与试前相同。后置USB快照重新为Android枚举。此恢复是回到此前已root/自定义Android环境，不声称完整原厂恢复或A槽标志已修复。

证据：launch.json、usb-during-trial.json、recovery.json、post-recovery.json、usb-after-recovery.json、trial-summary.json。用户观察单独标注来源，不伪装成自动抓取屏幕或SEC日志。所有_verified保持；H-001按键演练不因本次软件恢复完成而标为实机通过。

## 本阶段结论与下一入口门

R-007 A要求的源码、真实构建、产物检查、受限临时包、临时试启动和Android=1恢复均已完成。结果未取得BootShim/SEC/DXE/BDS执行证据；诊断包无XNU，所以本次也不是XNU试启动。

下一步应优先追ABL实际装载/跳转与ARM64入口条件，或建立独立且可回读的早期观测通道。继续往同一帧缓冲出口加字不能消除目前的观测盲区；DXE USB本身也覆盖不到更早失败。新BootShim/诊断范围、内存/地址或持久写入需按具体审批边界处理，本轮不额外生成第二种镜像或重试未批准容器。原厂v4 header可接受的事实不保证自定义payload实际被执行；不从黑屏推出唯一根因。
