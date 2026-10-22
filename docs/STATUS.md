# STATUS

> 当前唯一真相；更新：2026-10-23 00:36（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**本机ABL/UEFI静态审查发现BootShim将绝对FD地址误填为相对text_offset；特定变量分支下会在复制前因装载地址越窗返回错误。源码最小修正已备妥，实际错误码/运行分支仍未验证。新shim与容器待R-008 A审批，尚未生成。nuwa保持Android boot_completed=1，尚未进入XNU。**

详见[交接证据与源码候选](operations/2026-10-23-abl-handoff-and-relative-offset.md)，reports/abl-handoff/。新审批见[NEED-REVIEW R-008](NEED-REVIEW.md)。

## 当前输入

| 输入 | 当前状态 |
| --- | --- |
| wh1stl3/UniXNU@76dd641 | 合并上游并保留nuwa补丁；内核CI39793231214成功，真实内核静态核验通过 |
| wh1stl3/UniXNU-nuwa | board仍example=true，普通基座-D完整入口未打通；feed不变 |
| wh1stl3/uefi-nuwa | 稳定codex/nuwa-bringup@0a3a51a；诊断codex/nuwa-sec-trace@5e4a8c8只改SEC.c，本地检出仍干净，未应用0006 |
| 固件CI39809636575 | R-007 SEC诊断四EFI/3MiB FD/112B shim真实构建及665项静态检查通过；FD SHA9ea347a4，shim9346a527 |
| 新BootShim候选0006 | 只把头text_offset的FD_BASE改0；FD复制/入口目标A7100000不变，git apply --check通过，未编译 |

## ABL交接的新证据与局限

现有abl_a/b均SHA38a837fa…匹配只读备份；当前uefi_a/b均SHAd95cd6c7…，RAM解包98PE。QcomBds以Kernel描述符发布KernelBaseAddr/KernelSize，ABL查询同名同GUID变量，在普通平台、raw64、image_size非零分支加上头的text_offset。本机匹配xbl_config原表Kernel窗口[A8000000,B8000000)；旧头A7100000会算为14F100000，在空间检查失败。该条件模型与源补丁见relative-offset-preview.json；不是运行变量或实测拒绝码。

fastboot boot先发送OKAY再调用BootLinux，返回路径不在此报告该加载错误；所以R-007 ACK不证明BootShim已执行。最终交接代码存在x0=DTB、x1–x3=0、cache/MMU处理，但实际PC/EL/DAIF/MMU/cache/SPSel仍未验证。

pstore/常见bootloader_log无日志；logfs仅一条无会话归属的无可启动槽位信息。ABL lplog指向blackbox/minidump，blackbox不存在；96MiB minidump已只读到RAM筛选，有五个Raw_Dmp!头，无匹配的明文加载错误；尚未解码内部dump/压缩/会话，不能断言没有记录。未保存完整固件/内存镜像，未用Android ramoops作新日志区。

## 已完成试验与设备状态

R-007 A已完成：2026-10-23 00:07临时v4包3153920B/SHAfbb7940a…发送/Booting OKAY；用户“fastboot之后黑屏”，约29秒15次fastboot持续。BootShim/SEC/DXE执行未验证，包不含XNU。按D-016前后重进bootloader隔离状态，00:09已验证Android备份boot恢复nuwa/kalama、boot_completed=1；boot_a/vendor_boot_a/init_boot_a全分区SHA与试前相同，未flash/erase/改槽。[试验报告](operations/2026-10-22-sec-stage-diagnostic-trial.md)。

本轮仅ADB只读，00:33收尾仍Android完成1。当前为既有自定义/rooted Android，不称完整原厂恢复；A槽持久unbootable标志未修复。enuma排除在目标操作外。H-001实体键演练留PENDING-HUMAN，不是停因。

## 内核、加载器与平台剩余门

合并版8796内核20187912B/SHA77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8。Darwin22/iOS16、4KiB段起始、两prelink标记、五平台导出、零undefined、三archive哈希、65348项donor指针零失败。只校验选定ZIP成员CRC/文件SHA，完整ZIP摘要未核验，两次EOF保留。完整NativePrelink/运行ABI未验证，历史payload输入仍CI15 a9e08c69，未自动切换。[内核核验](operations/2026-10-22-merged-kernel-artifact-validation.md)。

608B CommandLine/0x2e0 boot_args修复已实际编译链接DarwinBoot EFI；源/布局/边界检查通过，运行ABI未验证。当前无XNU固件黑屏不能据此归因。[加载器修复](operations/2026-10-22-darwin22-loader-fix.md)。

Android DT已取证八CPU affinity、PSCI smc、GICv3/timer；Android路径/大端cells/宽度不等于Apple ADT。未生成目标ADT或正式平台运行配置，ARCH_TIMER/BOOT_PROGRESS仍0，provider/13回调/watchdog硬件及ABI验收未完成。[平台契约](operations/2026-10-22-live-platform-contract.md)。

现有Android FDT声明splash B8000000/02B00000、initrd B5FB2000–B7FFF1D4；ramoops A7000000/00400000与FD Reserved/UEFI FD重叠，不可直接套用。它不是候选实际x0或UEFI运行map。[映射](operations/2026-10-22-live-dt-and-firmware-map.md)。

## 下一步

1. 等待R-008具体方案审批。倾向A：只重编修正相对text_offset的112B shim，复用FD9ea347a4，严格限定shim差异在头8B范围，更新检查门后受限v4打包；当前未生成任何新镜像。
2. 获批A后按D-016隔离bootloader，重新筛选nuwa并核对恢复源，一次临时对照/采样后恢复Android=1。若仍黑屏继续现有dump/独立观测，不把ACK当阶段通过。
3. 若选择B，继续解析现有minidump结构及会话，寻找可回收BootLinux实际错误；易失BOOT_SERVICE_ACCESS变量不能从Android持久变量库追溯。未知日志缓冲区/USB前提保持TODO。
4. 入口通路之后还需目标ADT、内存窗口审批、真实provider/定时器配置及完整预链接/负载，才能推进XNU；没有实机或QEMU执行通过结论。

## 固定边界

board/feed/内存图及所有_verified不变；4KiB、iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3；ipad_identity=true为安全属性。D-002先512MiB–1GiB过阶段5，硬上限8GiB。未知板值不编造，不套其他donor的slide/early_security_init/roots。两个旧仓只读，独立固件源码授权范围明确；Git/GitHub/workflow持续授权。本机完整内核构建、iOS用户态和固件运行阶段仍未验证。
