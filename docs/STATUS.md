# STATUS

> 当前唯一真相；更新：2026-10-23 00:06（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**合并版8796内核、独立uefi-nuwa的四EFI/FD/BootShim均已真实编出并独立静态核验。尚未进入XNU；R-007 A已明确批准，诊断CI39809636575与临时包静态检查通过，下一步按已授权试启动并恢复Android。**

| 输入 | 实际状态 |
| --- | --- |
| wh1stl3/UniXNU@76dd641 | 合并上游且保留nuwa补丁；内核CI39793231214成功，实际内核与三archive已核验 |
| wh1stl3/UniXNU-nuwa | 设备脚本/patch/profile/证据；board仍example=true，普通基座-D完整构建仍未打通 |
| wh1stl3/uefi-nuwa@0a3a51a | 本地D:/Code/uefi-nuwa干净独立检出；默认codex/nuwa-bringup，保留Mu历史/main且enuma不变；本地子模块未初始化 |
| 独立固件CI39805110487 | 固定设备0b9dbd6、固件0a3a51a、UniXNU包75bc13；四EFI/FD/BootShim编译和665项产物静态检查通过 |

## 本轮构建与实际产物

合并版源内核20187912B，SHA77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8。Darwin22.6/8796.141.3/iOS16、4KiB段起始、两prelink标记、五平台导出、零undefined和三archive格式/哈希检查通过；65348项donor指针零失败。只分块获取选定ZIP成员并校验CRC/文件SHA，完整ZIP摘要未校验，两次EOF历史保留。未执行完整预链接或运行ABI验收。[内核报告](operations/2026-10-22-merged-kernel-artifact-validation.md)。当前历史固定payload输入仍为CI15 a9e08c69，未自动切换新内核。

独立固件新FD3145728B，SHA7f6f16c8c58c4695c1d883e1597e52379042175e4b668ad5e99e4e6a648707de；shim112B/SHA9346a527…，复制3MiB且image_size包含shim。四模块UniXNU/UniXNUDxe/DarwinBoot/NuwaBootMemoryDxe的GUID、PE/FV、DEPEX/协议、PCD、SEC x0/HOB检查通过。Darwin22的608B/0x2e0 boot_args修复已完成真实EFI编译链接；运行ABI仍未验证。新FD不含XNU，未生成新Android boot容器，未上设备。[固件报告](operations/2026-10-22-dedicated-firmware-build.md)。

前次39802617878在Azure Ubuntu镜像下载cross-GCC依赖长期Get/Ign，取消后未编译/无产物；日志保留。改官方Ubuntu HTTPS镜像、有限超时/重试/非交互后，39805110487安装4分23秒、构建5分37秒成功。不能把网络问题归为固件源码首错。

## 实机与入口

本轮只读确认nuwa在Android、boot_completed=1；同时连接enuma，目标筛选排除它。未重启/临时boot/刷写设备。当前Android FDT938828B/SHAf4636276：splash B8000000/02B00000，initrd B5FB2000–B7FFF1D4。ramoops A7000000/00400000与FD Reserved/UEFI FD重叠，不能直接用作固件持久日志区；不据此归因黑屏。Android FDT不等于候选ABL交接x0或运行UEFI映射。[映射证据](operations/2026-10-22-live-dt-and-firmware-map.md)。

历史旧v4候选SHA12864ac6实际Sending/Booting OKAY、用户黑屏、约29秒fastboot持续可见，没有BootShim/SEC/DXE/BDS执行证明。D-016：每次容器对照隔离bootloader状态，恢复先重进bootloader，再原厂临时boot并确认Android=1。A槽持久unbootable是既有状态，未修改；H-001按键恢复演练仍记PENDING-HUMAN，非本轮停因。用户已恢复设备访问，后续仍重新筛选nuwa。[旧试验](operations/2026-10-22-v4-firmware-trial.md)。

SEC现有日志仅帧缓冲，第一条正常文字前有SMMU调整与45MiB清屏；没有独立USB/UART持久出口。已有33项静态入口审查不能证明实机入口条件。实际L/EL/DAIF/MMU/cache/SPSel、BootShim重叠复制、FDT/initrd保留仍未验证。

## 平台与加载器剩余门

实际驱动源码hash与本次archive一致；实际内核catalogue含ArmCpu/ArmDTPlatform personality。实机FDT八CPU affinity、PSCI smc、GICv3与timer属性已清点，但Android路径/大端cells/宽度不等于Apple ADT，尚未写入board或生成ADT。实际构建仍ARCH_TIMER=0、BOOT_PROGRESS=0；provider初始化、CPU/GIC/PSCI硬件、13项回调、watchdog及完整NativePrelink ABI继续未验证。[平台契约](operations/2026-10-22-live-platform-contract.md)。

## 下一步

1. R-007 A已批准：SEC诊断源码固定在uefi-nuwa/codex/nuwa-sec-trace@5e4a8c8，只改SEC.c；31项profile输入检查通过。诊断CI39809636575固定device=f897f90，success；665项产物检查与实际SEC全部阶段标记检查通过。
2. 诊断输入/源哈希已固定；编译四EFI/FD/BootShim并独立检查，包括实际SEC TE中的六阶段标记；再准备受限v4 raw shim+FD临时容器，不混旧r6 FAT/旧内核/6GiB ADT，不自动改v1或添加XNU。具体SHA由实际产物取得。
3. 临时实机验证沿既有可恢复授权；先核对身份/原厂恢复源，观察阶段文字，结束恢复Android=1。若无文字仍不能断言未进SEC；继续ABL交接/独立日志方案，不靠更多DEBUG宣称USB日志已建立。
4. 后续再完成目标ADT、内存窗口、真实provider/定时器运行配置及预链接/载荷集成。未知字段保持TODO；QEMU/静态结果不替代实机。

## 固定边界

board/feed/内存图及所有_verified不变；4KiB、iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3；ipad_identity=true仅安全属性。D-002先512MiB–1GiB过阶段5、硬上限8GiB。未知板值不编造，不复用其他donor的slide/early_security_init/roots。两旧仓只读；独立固件本地目录用户已授权。Git/GitHub/workflow持续授权，无需重复询问。

官方72中文页/144路由复核与早期日志选项见对应operations；iOS用户态、完整本地内核构建及新固件实机运行未验证。

R-007执行记录：[诊断构建与试启动](operations/2026-10-22-sec-stage-diagnostic-trial.md)。固件稳定分支0a3a51a保持；本地当前切到诊断分支5e4a8c8，完整树与单文件差异已核对。新profile保留稳定版所有来源/板值/feed/模块/ABI patch，仅变固件提交与SEC输入hash。修正产物验收器在发布器改名后漏走HOB/DEPEX检查的分支，并对稳定版补做通过的检查；不改历史报告。

临时包脚本prepare-sec-trace-boot.py只接受对应sec-trace来源与实际SEC标记通过的产物，再复用固定原厂v4头仅改kernel_size；试启动脚本支持R-007包报告与D-016强制bootloader复位，恢复不依赖诊断image仍可读。本轮诊断boot包已生成并静态检查通过，尚未操作设备。

诊断FD9ea347a4、v4临时包fbb7940a（3153920B）已核验，包无XNU/DTB/FAT。恢复前置确认nuwa Android=1，boot/vendor_boot与备份相同，当前已root init_boot与历史记录相同。下一动作：试启动本包，采集屏幕/USB/命令结果后按D-016恢复Android=1。
