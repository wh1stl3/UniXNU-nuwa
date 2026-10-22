# STATUS

> 当前唯一真相；更新：2026-10-22 22:14（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

UniXNU fork已合并上游主分支：wh1stl3/UniXNU@76dd641包含固定上游5fdbd5d及本仓原5个提交。完整589条Git树核对通过，3份nuwa工作流、设备仓28份patch原哈希保留，fork和设备仓feed不变。21个子模块固定提交已归档。[合并与实际ABI证据](operations/2026-10-22-upstream-merge-and-darwin22.md)。

**合并版内核CI已触发，正在排队，尚未执行输入门或编译。** 新增独立kernel-merged-source工作流固定76dd641及四个模块，保留原75bc回归入口；原48项选择按序重验通过，46份上游未变、两份保留旧的8796候选字节。60项适配输入哈希/Bash语法及旧基线回归检查通过。历史固件仍锁75bc，新内核profile尚未编译成功。运行[39793231214](https://github.com/wh1stl3/UniXNU-nuwa/actions/runs/39793231214)，device_ref=3a210b1a4a9ed4633e14b567fea32c590162baf3；kernel job queued、steps为空，见reports/kernel-ci/39793231214/dispatch.json。[迁移审查](operations/2026-10-22-merged-kernel-profile.md)。

CI15的dSYM与内核UUID匹配，arm_init/machine_routines/pe_init三个编译单元实际boot_args一致：CommandLine608B、sizeof0x2e0、bootFlags0x2d0、memSizeActual0x2d8。当前DarwinBoot仍为1024B/0x480/0x470/0x478，已确认编译类型差异，运行ABI未验证。已形成Darwin22专用补丁并接入下一版候选清单，结构/局部缓冲区统一608B，复制长度取目标字段；旧基线git apply检查、新子模块RAM上下文、AArch64布局编译和89项接线检查通过。两个版本的生产转换/复制语句各10个宿主用例、各4次ASan/UBSan运行通过。进一步对旧基线和最新模块的完整DarwinBoot.c作AArch64语法检查，两者均通过，使用各自真实私有头及实际UEFI协议头。仍未执行完整EFI链接/打包，已有FD未被更新。[修复与验证](operations/2026-10-22-darwin22-loader-fix.md)。

## 实机访问与已完成构建

用户最新明确“实机操作可以继续”，撤销20:26暂停。恢复已授权范围内的设备访问；新镜像/刷写/试启动范围仍依据AGENTS及具体批准判断。本轮未访问设备，暂停后的当前状态未知，后续须先重新核对nuwa身份与模式。

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

1. 先取合并版CI39793231214真实状态与日志；当前queued，无第一处编译错误可提取。进入执行后核对四模块/输入门，按实际首错推进；完成后下载证据，不将排队写成编译中。命令gh run view/download --repo wh1stl3/UniXNU-nuwa。
2. Darwin22结构/缓冲区修复已接入固件源码候选，完整DarwinBoot模块仍待编译；新固件生成按硬停及已有批准范围判断。宿主PIE一次139无诊断的失败保留，非PIE用例通过不解释手机黑屏。
3. 继续ABL/FDT/splash/x0/initrd保留审查，明确早期日志回收通道；设备访问已恢复，但首次新操作前重新核对nuwa身份/状态，候选未获执行证据前不升级阶段。
4. 审查SM8550 USB许可和依赖、UEFI协议到SerialIo桥接；provider/ARCH_TIMER/GIC/PSCI、13项boot-progress、watchdog、NativePrelink的12处Libm编码和完整ABI仍待验收。
5. QEMU fixture先核对工具/输入，镜像生成仍按硬停，结果不作实机通过。只差人按键的事项记PENDING-HUMAN继续软件工作；A槽持久修复单列范围。

## 固定边界

board/feed不变、example=true；4KiB、iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3、ipad_identity=true为安全属性。D-002先512MiB–1GiB过阶段5，上限8GiB。未知值TODO，不抄其他donor prelink数值；两个旧仓/源树只读。

[官方72中文页/144路由复核](operations/2026-10-22-official-site-route-review.md)仍可用，官网nuwa页落后于本仓证据；guacamole的16KiB结论不平移。真实驱动优先复用，本机触控是ST FTS SPI；同SoC不替代本板验收。没有新镜像、板内存修改或_verified=true；iOS用户态和WSL完整内核构建仍未验证。
