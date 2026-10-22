# STATUS

> 当前唯一真相；更新：2026-10-23 01:07（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**R-009 A已获批准并完成空AUTO解析静态审查；固件源2ab6827d保留PIL、仅取消AUTO ABL，独立profile33项输入检查通过，CI39819452729已从固定设备提交6af9701启动；本地新FD打包/试启动门已备妥，待真实产物。nuwa此前已回Android完成1，尚未进入XNU。**

[本轮构建/试验记录](operations/2026-10-23-pil-no-auto-build-trial.md)，reports/pil-no-auto/。

照片显示DXE驱动加载，但同帧没有NUWA-ENTRY；候选和原厂都含相应驱动，精确归属/启动时序仍需连续录像，不能宣布候选SEC/BDS实机通过。[完整构建、试验、照片与同SoC对照](operations/2026-10-23-relative-offset-trial-and-pil-stop.md)。

## 当前输入与产物

| 输入 | 当前状态 |
| --- | --- |
| wh1stl3/UniXNU@76dd641 | 合并上游并保留nuwa补丁；内核CI39793231214成功，真实内核静态核验通过 |
| 设备仓 | board仍example=true，普通基座-D完整入口未打通；feed不变 |
| wh1stl3/uefi-nuwa | 稳定0a3a51a；SEC诊断5e4a8c8；当前本地codex/nuwa-no-auto-abl@2ab6827d，父910ee079保留正确BootShim头，只追加RAW配置替换，已等同发布GitHub，工作树干净 |
| R-007 FD | CI39809636575，四EFI/3MiB FD/112B旧shim、665项静态检查通过；FD9ea347a4完全复用 |
| R-008新shim | 本机WSL clang14/llvm-objcopy真实编译112B，SHA8a3b5476…，relative offset=0、FD目标A7100000不变，全部指令与旧版相同 |
| R-008新包 | 3153920B/SHA8b420abe64ac1738685879497d6a3e167a40873887b2122db01e8ae864ed2dfb，对R-007包仅4106/4107两字节变化，无XNU/新增DTB/ramdisk/FAT |
| R-009源码候选0007 | 保留PIL驱动，只将内嵌配置AUTO ABL行改注释；RAW输入指向nuwa本地配置，其他字段不变，已应用并提交2ab6827d；空AUTO控制流静态通过，尚未编译 |

## 本轮真实试验与当前设备

R-008首次与用户要求的同包录像复试，均先重新进入bootloader隔离状态；Sending/Booting OKAY，每次15次采样nuwa fastboot均false，与R-007持续true不同。用户原话“很多日志 Auto calling什么 什么panic”，后提供清晰末屏照片。ACK仍不代替阶段证据。

两次恢复检查分别00:41:49、00:43:49确认实际nuwa/kalama Android=1；两份记录只有ADB识别/等待，没有重新下发原Android boot，回返机制未确定，不声称已执行原boot临时恢复。postcondition确认boot_a/vendor_boot_a/init_boot_a三个全分区hash与试前相同；logfs/minidump也完全未变。当前仍既有自定义/rooted Android，非完整原厂恢复，未修复持久A槽标志。enuma未作为目标，无flash/erase/改槽。

## 新阻塞与同SM8550参考

照片末尾：Pil_abl Failed to read from partition / Failed to load ELF file / Auto processing of uefipil.cfg failed. Calling target panic。**这是Qualcomm PIL/ABL加载错误，非XNU panic。** 候选FD的PILDxe独立匹配错误字符串和CFG FFS，实际RAW配置6868B/SHA51facfcb…带[AUTO] ABL；候选APRIORI在BdsDxe前安排PILProxy/PIL/SPSS。不能为满足不需要的自动ABL路径去刷ABL或猜分区GUID，也不能认为取消AUTO就证明UFS/BlockIo已可用。

已只读核对官方同SoC来源：uefi-sheng@0eb4514d默认SHENG_VENDOR_HW=0，PIL三项有条件门；uefi-fuxi@bb25ad75的最小链没有PIL且未记录真机运行；nx729j模板仍带PIL/原CFG，不能机械复制；vermeer官方只记录内核CI等状态，未找到PIL运行结论。固定提交/文件SHA/片段见sm8550-pil-references.json。未借用预链接、身份或板级内存值，未升级上游。

## ABL契约与内核剩余门

本机ABL/UEFI静态核对：普通平台、raw64、image_size非零且两Kernel变量成功时，ABL会将Image.text_offset加到KernelBaseAddr。旧头A7100000在同机原厂Kernel表[A8000000,B8000000)条件下越窗；已修正头语义，运行变量/实际旧错误仍未捕获。ACK发于BootLinux前，实际L/EL/MMU/cache/PC继续未验证。[契约报告](operations/2026-10-23-abl-handoff-and-relative-offset.md)。

8796源内核20187912B/SHA77742999fc1c1b6a94c9603664d946553070f73c6eed83ce9fcca06d70d73ac8，Darwin22/iOS16、4KiB段起始、五平台导出、零undefined、三archive hash、65348项donor指针零失败。完整NativePrelink/运行ABI仍未验证，历史payload输入仍CI15 a9e08c69，未自动切换；选定ZIP成员校验不等于完整ZIP摘要核验。[内核核验](operations/2026-10-22-merged-kernel-artifact-validation.md)。

608B CommandLine/0x2e0 boot_args修复已真实编译链接DarwinBoot EFI，运行ABI未验证。本机WSL仅新增shim编译通过，不是完整XNU本机构建通过。目标ADT/真实provider/定时器/watchdog/13回调仍待运行验收；ARCH_TIMER/BOOT_PROGRESS仍0，Android DT不能直接当Apple ADT。ramoops与FD保留区重叠，未占用作日志。

## 下一步

1. 跟进已启动的CI39819452729（device6af9701、firmware2ab6827d、pil-no-auto），按真实终态/首错推进；当前run-initial.json保留状态，不凭旧产物替代新FD。
2. 构建成功后下载并严格检查实际RAW SHA/空AUTO、PILDxe原SHA、正确相对头0、SEC标记、四EFI和FD；再按R-009 A受限v4打包/临时试启动并以Android完成1收尾。B未获批准，不自动切换。
3. H-003连续录像仍可补首屏时序，不阻塞静态/构建工作。R-009暂停已解除，Git/GitHub持续授权。
4. 入口/BDS打通后仍需目标ADT、内存窗口、真实provider配置、完整预链接与负载才能推进XNU。无QEMU或XNU实机执行通过结论。

## 固定边界

board/feed/内存图及所有_verified不变；4KiB、iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3；ipad_identity=true为安全属性。D-002先512MiB–1GiB过阶段5，硬上限8GiB。未知板值不编造，不套其他donor的slide/early_security_init/roots。两个旧仓只读，独立固件源码授权明确；Git/GitHub/workflow持续授权。
