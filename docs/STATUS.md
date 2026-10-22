# STATUS

> 当前唯一真相；更新：2026-10-22 21:04（Asia/Shanghai）。历史见WORKLOG。

## 实机操作暂停

用户2026-10-22 20:26明确：“deepseek开始推送包了，不要做实机操作”。本仓暂停全部ADB、fastboot和USB/设备状态查询，直至用户明确恢复本仓设备访问；已有长期设备授权在暂停期间不执行。只继续仓库内离线分析/文档和Git同步。设备暂停后的状态以该轮操作为准，本仓不轮询、不抢占、不自动执行恢复。

## 当前结论

**已实际临时启动本仓v4固件入口候选：Sending/Booting均OKAY，但用户见黑屏，约29秒15次采样fastboot始终可见。BootShim/SEC和DXE/BDS均未取得执行证据；不能称UEFI阶段通过。** 随后重进bootloader并临时加载原厂boot，本仓最后确认nuwa恢复Android、sys.boot_completed=1（20:19，不能代表暂停后的当前状态）。A槽持久启动状态仍未修复。

- 候选：out/trial-boot/firmware-v4/boot-firmware-v4.img，3153920B，SHA12864ac6cc0ffc9909f4abbdfab91bfee216c3fdcfc5ab0d52b4d4b9cf4579f9；只含raw shim+FD，原v4头仅改kernel_size，无附加DTB或新增FAT/XNU。[首次实机记录](operations/2026-10-22-v4-firmware-trial.md)。
- 构建：固件CI39764322744 success，四EFI/FD/BootShim下载静态检查通过，FD3145728B/SHAa0bbb964…、shim112B/SHA9346a527…。实际启动命令不把这项静态证据升级为固件运行验收。R-004 A完成。
- 本仓源内核：CI15 39755850870，ArmCpu/ArmDTPlatform真实链接、五导出/零undefined；20187888B/SHAa9e08c693fec4034f613cd554ea94e5855b25b727b4bfb4af46a4103f565bc7a，65348项donor指针零缺失。未加入本次候选，XNU与iOS执行仍未验证。

## 实机与恢复证据

- 本轮从nuwa Android=1进入bootloader，核对product=nuwa、unlocked=yes、slot=a后执行唯一锁定候选。另一台enuma没有被重启或写入；日志不保存设备序列号。
- 候选命令成功后屏幕黑屏，USB为Android Bootloader Interface/VID_18D1&PID_D00D，fastboot product仍可查询。缺少早期入口日志，无法定位是否曾执行BootShim/SEC、是否返回或何处失败。
- 同一原厂boot ef558db2…：在该轮状态直接临时加载报Load Error；reboot bootloader后再次加载成功，nuwa/kalama身份及Android boot_completed=1已确认。每次对照须重新进入bootloader隔离状态，不能以一次Load Error判断唯一格式/大小门槛（D-016）。未flash/改槽位，H-001物理键演练仍open，H-002已完成。
- 当前boot_a/init_boot_a此前整分区hash与原始备份一致；原厂临时恢复不等于A槽持久启动修复。本轮post-recovery boot reason=bootloader、pstore空，不能据此归因候选失败点。

## 静态映射与参考方案

nuwa原厂boot/init_boot/vendor_boot均v4；原厂v4有进入Android的实机证据。当前Android initrd[0xb5fb2000,0xb7fff1d4)处于固定Mu静态Kernel保留区[0xa8000000,0xb8000000)，但新候选实际DT地址/映射与生命周期仍未知。RamManager会将EFI图空隙加入Conventional，发布器不保留新initrd；加入新FAT前须核验。

r6 v1回环已在RAM复现OS字节0x1009和ID前20B差异，32B ID补零与分段SHA修正可吸收；其原FAT含旧内核、3秒默认启动XNU和6GiB ADT，不能随新FD直接上机。咱们FD套该模板的RAM投影总长203194368B，未写镜像。[复核](operations/2026-10-22-reference-repack-review.md)。

驱动报告索引可用，但本机触控是ST FTS SPI；官方sheng GPU已列可用。设备feeds可选，“同SoC可直接用”不能代替Darwin22/硬件验收；feed保持。[复核](operations/2026-10-22-driver-source-report-review.md)。

## 离线入口与SEC日志审查

33项静态断言通过：FD首分支/TE/map均指0xa710a838，入口机器码保存x0到0xa710a8d8，拷贝尺寸与cache调用吻合。SEC实际日志为帧缓冲绘字，WARN/ERROR已开，异常也走同一出口；正常横幅前先有SMMU调整和清屏。BootShim不准备EL/DAIF/MMU/cache，实际L/x0/SPSel仍未知；text_offset的FD_BASE值与ABL放置策略、原厂EFI入口差异待澄清，不能凭头字段直接归因。只读归档ABL包含BootLinux/ARM64检查路径，不代表当前设备分支。全程未访问设备、未生成镜像。[完整审查与最小待测清单](operations/2026-10-22-arm64-sec-entry-audit.md)。

## 日志导出可行性

离线确认nuwa构建已列入高通USB设备栈，协议提供Start/Send/HandleEvent，可在DXE实现CDC ACM导出到Windows日志文件；目前未实现、未实机验证。优先复用Mu AdvancedLogger早期RAM记录候选，USB就绪后补发；若故障早于DXE，仍需已验证的UART或保留RAM读回路径。安全缓冲区地址/长度、UART路由、跨重启保留均TODO，不能声称普通USB线已能抓BootShim/SEC。设备暂停保持。[通道比较与源码证据](operations/2026-10-22-log-export-options.md)。

## 下一步

1. 入口头、BootShim机器码和SEC日志实现已完成首轮离线核对。下一步可离线追归档ABL的实际加载/交接分支，日志通道已完成离线比较，下一步固定Mu日志组件版本并核对安全RAM/USB协议依赖；未知地址、UART路由和RAM读回路径继续TODO。实机暂停不解除，不能以黑屏归因某阶段或先验收DXE/BDS。
2. 仅在用户明确恢复本仓设备访问后，后续任何容器对照从重新进入bootloader开始；结束后重进bootloader再用ef558db2原厂boot恢复Android并确认完成。保留候选原hash，不自动换v1或混入参考负载。H-001按键项记待办继续软件项。
3. 新FAT的映射/保留、CI15 runtime crypto/pthread provider、ARCH_TIMER/startup/GIC/PSCI、13项boot-progress、watchdog scratch和NativePrelink布局/12处Libm编码继续审查；XNU负载另验收。
4. A槽持久启动若要修复，先明确具体授权动作；不在临时固件测试中顺带改槽位。board/bringup-plan内存/基址及_verified保留硬停规则，未知值TODO。

## 边界与记录

board/feed不变、example=true；4KiB，iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3，ipad_identity=true为安全属性。D-002先512MiB–1GiB过阶段5、上限8GiB。两个旧仓/源树只读，镜像在out，Git/gh已授权且不强推。

本轮reports/v4-firmware-trial/保存实际启动/USB/用户屏幕观察/首次恢复失败/bootloader重进/再次恢复成功及最终Android状态；scripts/trial-v4-firmware.py执行哈希与目标门。新固件未获执行通过，未置_verified=true，WSL完整内核构建和iOS用户态仍未验证。
