# STATUS

> 当前唯一真相；更新：2026-10-23 00:11（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**R-007 A已完成：SEC诊断固件真实构建及产物静态检查通过，临时启动后用户黑屏、fastboot持续可见，尚无SEC/DXE执行证据；已恢复nuwa Android并确认boot_completed=1。尚未进入XNU。**

| 输入 | 当前状态 |
| --- | --- |
| wh1stl3/UniXNU@76dd641 | 上游合并保留nuwa补丁，合并版内核CI39793231214及实际文件核验通过 |
| wh1stl3/UniXNU-nuwa | 设备脚本/patch/profile/证据，board仍example=true；普通基座-D完整入口仍未打通 |
| wh1stl3/uefi-nuwa | 稳定codex/nuwa-bringup@0a3a51a；诊断codex/nuwa-sec-trace@5e4a8c8只改SEC.c，本地当前诊断分支干净；子模块未初始化 |
| 稳定固件39805110487 | 四EFI/3MiB FD/112B shim构建与665项静态检查通过，FD7f6f16c8；发布器改名后的HOB/DEPEX分支已补查通过 |
| SEC诊断39809636575 | 固定device=f897f90、firmware=5e4a8c8、UniXNU包75bc13，四EFI/FD/shim及665项检查、实际SEC全部标记通过 |

## 本轮实机结果与恢复

诊断FD3145728B/SHA9ea347a49e51472adac987cf12e20f9e0d99453a23f2113ad24efcd0a07f2eaf，shim112B/SHA9346a527…；受限v4包3153920B/SHAfbb7940a8ee8cb5f2577a30bc2e5fb5bc31e1b84930c05b40c6304dfe970bcde。原Android备份头只改kernel_size，无新增DTB/ramdisk/FAT/XNU。

2026-10-23 00:07按D-016重新进入bootloader后，Sending/Booting OKAY、用户原话“fastboot之后黑屏”，约29秒15次采样选中nuwa始终可在fastboot枚举，Windows USB18D1:D00D。没有报告[NUWA-ENTRY]文字，不能据此确定从未交接/快速返回/显示不可见，更不能声称SEC失败点已定位。

恢复前再次重进bootloader，临时加载已验证原Android备份boot SHAef558db2；00:09:01重新确认nuwa/kalama、sys.boot_completed=1。boot_a/vendor_boot_a/init_boot_a全分区SHA与试前相同，未flash/erase/改槽。当前是此前自定义Android内核/已root环境，不称完整原厂恢复；既有A槽持久unbootable标志未修复。enuma排除在目标操作外。H-001按键演练仍待办，不是本轮停因。[完整记录](operations/2026-10-22-sec-stage-diagnostic-trial.md)，reports/sec-trace/39809636575/。

## 内核与Darwin22加载器

合并版源内核20187912B/SHA77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8。Darwin22.6/8796.141.3/iOS16、4KiB段起始、两prelink标记、五平台导出、零undefined、三archive哈希与65348项donor指针零失败。选定ZIP成员CRC/文件SHA已检查，完整ZIP摘要未核验，两次EOF保留。未执行完整预链接或运行ABI验收；当前历史固定payload输入仍CI15 a9e08c69，未自动切换。[核验](operations/2026-10-22-merged-kernel-artifact-validation.md)。

608B CommandLine/0x2e0 boot_args修复已完成真实DarwinBoot EFI编译链接；C布局/边界用例和源哈希门通过，运行ABI仍未验证。此次固件未携带XNU，黑屏不能归因到其Darwin22交接。[加载器修复](operations/2026-10-22-darwin22-loader-fix.md)。

## 入口、日志与平台剩余门

诊断源码只在SEC平台/内存/HOB/FV/DXE调用边界加WARN和已有x0值，移除全屏清零；原SMMU/内存/解压调用保留，源码与实际TE标记可复核。但出口仍只有FrameBufferSerialPortLib，没有独立USB/UART或跨重启日志，不能覆盖ABL/BootShim/最早SEC汇编。实际L/EL/DAIF/MMU/cache/SPSel、复制重叠和FDT/initrd保留继续未知。

当前Android FDT938828B/SHAf4636276声明splash B8000000/02B00000、initrd B5FB2000–B7FFF1D4；ramoops A7000000/00400000与FD Reserved/UEFI FD重叠，不能直接用作固件持久日志区。Android FDT不等于候选x0或UEFI运行映射。[映射](operations/2026-10-22-live-dt-and-firmware-map.md)。

实际驱动源码hash与archive一致，内核catalogue含ArmCpu/ArmDTPlatform personality；八CPU affinity、PSCI smc、GICv3与timer属性已取证，但Android路径/大端cells/宽度不等于Apple ADT。尚未写正式配置或生成ADT，ARCH_TIMER/BOOT_PROGRESS仍0；provider初始化、CPU/GIC/PSCI硬件、13回调、watchdog、完整NativePrelink ABI未验证。[契约](operations/2026-10-22-live-platform-contract.md)。

## 下一步

1. 转向ABL实际装载/跳转与ARM64入口交接审查，确定可独立回收的早期观测方案。当前屏幕结果未缩小到SEC子阶段；不能靠同一出口更多DEBUG宣称定位。
2. 若设计新BootShim/独立RAM/USB诊断，先固定来源、运行前提、数据保留与读取路径；地址所有权未知保持TODO，不直接套Android ramoops。新镜像/内存地址范围按具体审批规则落实；R-007本轮已完成，不自动扩大到新类型镜像。
3. 当前设备已回Android=1，下一设备动作重新筛选nuwa。沿D-016隔离状态与恢复，实体键待办记PENDING-HUMAN继续独立软件工作。
4. 后续完成目标ADT、内存窗口、真实provider/定时器运行配置及预链接/负载，再讨论进入XNU；QEMU/静态检查不替代实机。

## 固定边界

board/feed/内存图及所有_verified不变；4KiB、iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3；ipad_identity=true为安全属性。D-002先512MiB–1GiB过阶段5、硬上限8GiB。未知板值不编造，不套其他donor的slide/early_security_init/roots。两旧仓只读；独立固件本地目录授权明确，Git/GitHub/workflow持续授权。iOS用户态、完整本地内核构建和新固件执行阶段均未验证。
