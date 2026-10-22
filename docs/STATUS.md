# STATUS

> 当前唯一真相；更新：2026-10-22 21:40（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

UniXNU fork已合并上游主分支：wh1stl3/UniXNU@76dd641包含固定上游5fdbd5d及本仓原5个提交。完整589条Git树核对通过，3份nuwa工作流、设备仓28份patch原哈希保留，fork和设备仓feed不变。21个子模块固定提交已归档。[合并与实际ABI证据](operations/2026-10-22-upstream-merge-and-darwin22.md)。

**仓库已合并，构建迁移未完成。** CI15/固件成功输入仍锁定75bc13d，现有工作流仍使用该历史基线；不能将历史CI成功写成新合并代码编译通过。迁移需审查递归子模块、补丁哈希和构建脚本上下文，不只改一个SHA。

CI15的dSYM与内核UUID匹配，arm_init/machine_routines/pe_init三个编译单元实际boot_args一致：CommandLine608B、sizeof0x2e0、bootFlags0x2d0、memSizeActual0x2d8。当前DarwinBoot仍为1024B/0x480/0x470/0x478，已确认编译类型差异，运行ABI未验证。下一项形成Darwin22加载器最小补丁，必须同步局部缓冲区与长度检查，避免仅缩短结构引起CopyMem越界。

## 实机访问与已完成构建

用户最新明确“实机操作可以继续”，撤销20:26暂停。恢复已授权范围内的设备访问；新镜像/刷写/试启动范围仍依据AGENTS及具体批准判断。本里程碑未访问设备，暂停后的当前状态未知，后续须先重新核对nuwa身份与模式。

- 内核CI15 39755850870成功：ArmCpu/ArmDTPlatform真实链接，五项导出/零undefined，20187888B，SHA a9e08c693fec4034f613cd554ea94e5855b25b727b4bfb4af46a4103f565bc7a。65348项donor指针零缺失；仍是源内核，不是完成的预链接负载，运行provider/完整ABI未验证。
- 固件CI39764322744成功：四EFI、FD3145728B/SHA a0bbb964…、shim112B/SHA9346a527…静态检查通过，未包含XNU。
- v4固件入口包3153920B/SHA12864ac6…实际Sending/Booting均OKAY、用户见黑屏，约29秒fastboot持续可见。没有BootShim/SEC/DXE/BDS执行证据；不能称UEFI阶段通过。[实机记录](operations/2026-10-22-v4-firmware-trial.md)。
- 本仓最后恢复Android/sys.boot_completed=1为20:19，不能代表其他轮操作后的当前状态。A槽持久unbootable未修复；H-001物理键演练仍待办。

## 入口、映射与日志

离线33项检查通过，FD/TE/map入口0xa710a838一致且保存x0。BootShim未准备EL/DAIF/MMU/cache，实际L、x0、SPSel与ABL放置策略仍未知。SEC日志和异常只走帧缓冲，正常横幅前有SMMU调整和清屏，黑屏不能定位SEC。[入口审查](operations/2026-10-22-arm64-sec-entry-audit.md)。

nuwa原厂boot/init_boot/vendor_boot均v4，原厂v4有进入Android证据；当前候选raw shim+FD，无附加DTB/FAT/XNU。历史Android initrd处于Mu静态Kernel保留区，但新候选实际FDT地址/保留/生命周期未验证。后续容器比较先重新进入bootloader隔离状态，恢复也先重进bootloader再临时原厂boot并确认Android=1（D-016）。

r6模板FAT含旧内核、3秒自动启动XNU及6GiB ADT，不能原样套新FD上机；32B ID补零与分段SHA经验可复用，“只支持v1+大ramdisk”仍缺隔离状态对照。[模板复核](operations/2026-10-22-reference-repack-review.md)。

nuwa已打包高通USB设备栈，DXE CDC导出尚未接线；早期RAM记录可参考Mu AdvancedLogger，安全地址/保留和UART仍TODO。SM8550 vermeer有XNU CDC代码但许可、Darwin22/4K/DMA/SMMU依赖待审；sheng UFS日志/Linux读取器只适用于更晚阶段。[日志方案](operations/2026-10-22-log-export-options.md)。

## 下一步

1. 在最新DarwinBoot子模块固定提交上制作Darwin22专用结构/命令行缓冲区补丁，核对旧基线及最新上下文；只做源码适配与静态验证，新的固件生成按硬停范围处理。
2. 迁移合并版构建输入：递归子模块固定、48项选择和本仓兼容补丁逐项检查、构建脚本哈希/输出/参数重新审查；保留可重现的CI15回归路径，不改feed。
3. 继续ABL/FDT/splash/x0/initrd保留审查，明确早期日志回收通道；设备访问已恢复，但首次新操作前重新核对nuwa身份/状态，候选未获执行证据前不升级阶段。
4. 审查SM8550 USB许可和依赖、UEFI协议到SerialIo桥接；provider/ARCH_TIMER/GIC/PSCI、13项boot-progress、watchdog、NativePrelink的12处Libm编码和完整ABI仍待验收。
5. QEMU fixture先核对工具/输入，镜像生成仍按硬停，结果不作实机通过。只差人按键的事项记PENDING-HUMAN继续软件工作；A槽持久修复单列范围。

## 固定边界

board/feed不变、example=true；4KiB、iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3、ipad_identity=true为安全属性。D-002先512MiB–1GiB过阶段5，上限8GiB。未知值TODO，不抄其他donor prelink数值；两个旧仓/源树只读。

[官方72中文页/144路由复核](operations/2026-10-22-official-site-route-review.md)仍可用，官网nuwa页落后于本仓证据；guacamole的16KiB结论不平移。真实驱动优先复用，本机触控是ST FTS SPI；同SoC不替代本板验收。没有新镜像、板内存修改或_verified=true；iOS用户态和WSL完整内核构建仍未验证。
