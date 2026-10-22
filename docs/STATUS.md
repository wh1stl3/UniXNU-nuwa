# STATUS

> 当前唯一真相；更新：2026-10-22 23:38（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**三仓已齐；合并版内核独立核验通过，独立固件CI39805110487已通过依赖安装并进入构建。**

| 仓库 | 当前输入与状态 |
| --- | --- |
| wh1stl3/UniXNU | 合并上游的76dd641；合并版内核CI39793231214及实际内核/三archive/指针绑定静态核验通过 |
| D:/Code/UniXNU-nuwa | 设备脚本、补丁、固定构建profile和证据；board仍example=true |
| wh1stl3/uefi-nuwa / D:/Code/uefi-nuwa | 固件源码0a3a51a，默认/本地分支codex/nuwa-bringup，工作区干净、完整Git fsck通过；子模块尚未初始化 |

固件仓是保留Mu-Silicium历史的独立仓：账号同网络已有uefi-enuma，fork API返回该已有仓时名称断言中止；enuma没有被改动。源导入CI39796387414成功，上游main=42fe563保留，nuwa从验证基线6c67550单开分支。临时导入secret已删除，固件仓Actions关闭，避免继承工作流自动生成镜像。[接入记录](operations/2026-10-22-dedicated-uefi-repository.md)。

固件分支已纳入BootShim尺寸修正、DSC/FDF/包路径和SEC x0/HOB接线，以及从sheng裁剪的只读initrd发布器NuwaBootMemoryDxe。完整2256条Git树逐项比较，原内存/配置图、Resources/Configs/nuwa.toml和全部子模块固定值不变。新发布器保留原模块GUID；AArch64语法检查通过，不是完整链接或实机运行验收。

设备仓新增firmware-dedicated-profile.json，固定固件0a3a51a；31项来源输入与四模块/两外部包/一条剩余Darwin22补丁的接线检查通过，避免重复应用已入固件仓的patch。firmware-candidate工作流选择dedicated，legacy profile和全部历史patch仍保留。此固件profile的UniXNU包仍锁已验证75bc，内核CI独立使用76dd；尚未统一迁移所有固件包输入。普通基座-D入口仍受board示例/缺失字段保护，不能称完整官方构建链已打通。

## 内核与Darwin22加载器

合并版CI[39793231214](https://github.com/wh1stl3/UniXNU-nuwa/actions/runs/39793231214)固定device_ref=3a210b1，真实内核20187912B/SHA77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8。分块ZIP读取完成所选成员CRC与实际文件SHA核对，五平台导出/零undefined/三archive哈希及65348项donor指针零失败。两个prelink标记、Darwin22/iOS16与段起始4KiB静态检查通过；完整ZIP摘要未验证，保留两次EOF。没有执行预链接、生成负载或证明运行ABI。[核验报告](operations/2026-10-22-merged-kernel-artifact-validation.md)。

历史固定负载仍为CI15 39755850870：ArmCpu/ArmDTPlatform真实链接、五导出/零undefined、65348项donor指针零缺失，20187888B，SHA a9e08c693fec4034f613cd554ea94e5855b25b727b4bfb4af46a4103f565bc7a。仍是源内核，不是完成的预链接负载，运行provider/完整ABI未验证。

CI15实际DWARF为608B CommandLine/0x2e0 boot_args，尾字段0x2d0/0x2d8；上游原始DarwinBoot为1024B/0x480。本仓补丁统一结构、局部缓冲区和复制边界，已接入下一固件profile；两版完整DarwinBoot.c的AArch64语法检查、全部成员布局和宿主边界用例通过，完整EFI模块尚未重新链接。PIE宿主一次无诊断139已保留，后续非PIE ASan/UBSan用例通过，精确根因未验证。[修复与证据](operations/2026-10-22-darwin22-loader-fix.md)。

## 实机、入口与恢复

用户已明确恢复本仓实机访问；本轮只读确认ADB的nuwa/Android boot_completed=1，同时存在enuma；只采集nuwa FDT，没有重启或镜像操作。当前观测nuwa为Android=1；以后改变模式前仍重新核对身份，排除enuma。

历史固件CI39764322744的四EFI/FD/BootShim编译与静态检查通过；该旧FD无XNU。v4包3153920B/SHA12864ac6…实际Sending/Booting OKAY、用户黑屏，约29秒fastboot持续可见，BootShim/SEC/DXE/BDS均缺执行证据。20:19最后确认原厂临时boot恢复Android=1，不能代表其他轮操作后的现状；A槽持久unbootable未修复，H-001按键演练仍待办。[实机记录](operations/2026-10-22-v4-firmware-trial.md)。

离线33项入口检查通过，FD/TE/map入口0xa710a838并保存x0；实际L/EL/DAIF/MMU/cache/SPSel与ABL交接仍未知。SEC仅帧缓冲日志，正常横幅前有SMMU调整和清屏，黑屏不能定位SEC。新FDT/splash/initrd映射、保留和生命周期仍需证据；r6旧FAT带旧内核、6GiB ADT和自动启动，不能套用。[入口审查](operations/2026-10-22-arm64-sec-entry-audit.md)。

## 下一步

1. 读取独立固件CI39805110487真实编译/链接结果与产物；已通过依赖安装（4分23秒），当前构建中。39802617878的Azure下载阻塞已取消并保留，不能当成固件源错误。
2. 合并版内核独立静态核验已完成；保留CI15候选输入，后续以明确profile逐步接入新内核，不自动混用不同来源或生成预链接。完整运行ABI/provider/ARCH_TIMER仍待审查。
3. 新固件产物检查用--publisher-name NuwaBootMemoryDxe；legacy默认仍支持旧ShengBootMemoryDxe产物。本地子模块未初始化，31项检查中Mu_Basecore文件借用同固定提交的只读缓存，不能称完整本地构建工具已就绪。
4. 继续ABL/FDT/splash/x0/initrd保留与早期日志回收，审查SM8550 USB许可/4K/DMA/SMMU依赖、UEFI SerialIo桥接；provider/ARCH_TIMER/GIC/PSCI、13项boot-progress、watchdog和NativePrelink完整ABI仍待验收。
5. 新试启动先隔离bootloader状态，结束后按D-016恢复Android并确认完成；只差实体键的项记PENDING-HUMAN继续软件工作。QEMU结果不作实机通过。

## 固定边界

board/feed及所有_verified标志不变；4KiB，iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3，ipad_identity=true为安全属性。D-002先512MiB–1GiB过阶段5，上限8GiB。未知值TODO，不抄其他donor prelink数值；两个旧仓保持只读。用户要求独立本地固件仓后，允许在D:/Code/uefi-nuwa维护固件，AGENTS目录表已更新。

官方72中文页/144路由复核与既有日志出口方案见operations对应报告；本机触控ST FTS SPI、同SoC不替代本板验收。iOS用户态、完整本地内核构建和新固件实机运行仍未验证。

本轮当前FDT938828B/SHAf4636276：splash B8000000/02B00000、initrd B5FB2000–B7FFF1D4。ramoops A7000000/00400000与固件FD Reserved/UEFI FD重叠，不能直接作为固件持久日志区；这是跨阶段所有权问题，不是黑屏根因证明。[实机只读复核](operations/2026-10-22-live-dt-and-firmware-map.md)。

平台契约静态审查新增：Android八CPU affinity/PSCI smc/GICv3与timer属性已取证；对应驱动源码哈希与实际archive一致，实际内核catalogue含ArmCpu/ArmDTPlatform personality。Android FDT路径/大小端/属性宽度不等于目标ADT，未生成ADT或改变board。见[平台契约](operations/2026-10-22-live-platform-contract.md)。
