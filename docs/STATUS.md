# STATUS

> 当前唯一真相；更新：2026-10-22 18:48（Asia/Shanghai）。历史见 WORKLOG。

## 当前结论

**源内核真实平台链接、四个加载器EFI、nuwa FD及BootShim均已取得实际构建证据。EFI/FD/BootShim下载后静态检查通过；未QEMU、未在手机执行本仓固件或XNU。** 本轮R-004 A已完成，不等于iOS可启动。

- 内核：CI15 [39755850870](https://github.com/wh1stl3/UniXNU/actions/runs/39755850870)，ArmCpu/ArmDTPlatform实际force-load，五平台导出、零undefined；20,187,888B，SHA256 `a9e08c693fec4034f613cd554ea94e5855b25b727b4bfb4af46a4103f565bc7a`。65,348项donor指针绑定零缺失，完整ABI/运行未验证。
- 固件：第三轮 [39764322744](https://github.com/wh1stl3/UniXNU-nuwa/actions/runs/39764322744) success，设备输入a8425b3。FD 3,145,728B，SHA256 `a0bbb9645f4af2de66e4e29e1b5deaf508e95c41f33de4fd9f811ab03bde1c83`；BootShim 112B，SHA256 `9346a527441b242c69414fd7e3d6fa17813f281d562fef13d9ba8373d39007a9`。未包含内核或生成boot.img。[实际构建与审计](operations/2026-10-22-firmware-candidate-build.md)。

## 已完成与当前证据

- 四模块UniXNU/UniXNUDxe/DarwinBoot/ShengBootMemoryDxe全部AARCH64 PE32+，位于实际FD中的同一内层FV，独立EFI与内嵌PE哈希一致；665份下载文件的长度/hash通过核对。SEC TE和只读initrd发布器包含同一入口HOB GUID。
- DEPEX核对包括Mu库引入的gEfiPcdProtocolGuid；PCD驱动存在于FD，已确认源码生产协议及平台APRIORI接线。固件卷校验/LZMA解压通过，外层56%已用、1,375,544B空余；内层9,932,800B由构建工具自适应生成。BootShim头image_size=3,145,840、_Payload=112，机器码拷贝量仍仅FD的3,145,728B。
- 前两轮实际首错分别是缺失SEC入口HOB生产链、Git blob CRLF；已通过固定来源最小补丁和仅云端精确目标换行归一化解决。未修改只读源树。四补丁/83项源码静态检查记录在reports/loader-integration/；第三轮实际输入、日志、构建报告、产物检查在reports/firmware-ci/39764322744/。
- 原厂XBL cfg独立提取8,342B，28个DDR行+14个寄存器行，DXE Heap209.75MiB；NoMap/AddDynamicMem与隔壁C表有语义差异，高地址6GiB策略未继承。[接线及内存报告](operations/2026-10-22-loader-source-integration.md)。
- Android既有只读取证：ST FTS SPI/st_fts_m2.ftb、活跃m2_38_0c_0a面板、Adreno740v2、KIOXIA UFS；固定MiCode DT与LineageOS来源。[驱动取证](operations/2026-10-22-android-driver-evidence.md)。本轮无设备操作。

## 下一步

1. 核验恢复路径与候选启动包方案：用户已持续授权可恢复fastboot前提下推送/试启动镜像，见NEED-REVIEW后续授权记录。先核对原厂boot/DTB/打包参数与恢复证据；H-001实体键演练仍未验证，记PENDING-HUMAN并继续软件项。不能把授权或普通重启记录写成硬挂恢复通过；暂不自动修改持久启动链。
2. 完成原厂NoMap/AddDynamicMem、RamManager最终EFI map、SEC初始缓存/DT生命周期及initrd保留/映射审查；UniXNU固件入口源码含ConnectAll后扫描配置，但真实DXE/BDS/FAT挂载尚未验证。固件现有HwResetSystemLib类声明警告需在恢复评估中核对，不因编译通过验收复位。
3. 组装XNU负载前核验CI15 runtime crypto/pthread provider、ARCH_TIMER/startup/GIC/PSCI、13项boot-progress及watchdog scratch；新内核的NativePrelink布局和12处Libm外部PC编码仍待审查，旧CI13 plan不能直接继承。将纯固件入口验证与XNU进入平台专家分别验收。
4. board/bringup-plan内存/地址及_verified仍按原硬停规则。D-002先512MiB–1GiB过阶段5，再抬容量，硬上限8GiB；未知参数TODO，不填假值。

## 当前边界

- board/feed不变、example=true；4KiB，iPhone10,3/d22ap/iOS16.7.16/20H392，8796.141.3；ipad_identity=true是安全属性。
- 两个旧仓与上游源码只读；Git/gh/workflow已有授权，不强推、不改写历史。R-004 A只完成受限固件构建审计；后续设备授权的条件是可恢复fastboot，不能据此声称所有刷写可恢复。
- 实际固件使用Ubuntu24.04/clang18/CLANGPDB，源码内核使用macOS Actions/Xcode16.4/Apple clang17/iphoneos18.5；WSL完整内核构建仍未验证。
- 源CI关闭性能、boot-progress与startup ARCH_TIMER的范围不变，ArmVirt仅独立编译。内核链接/固件静态验收均不替代硬件、SMMU/DMA、根卷及iOS用户态验收；未置任何_verified=true。
