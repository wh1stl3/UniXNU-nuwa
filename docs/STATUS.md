# STATUS

> 当前唯一真相；更新：2026-10-22 18:22（Asia/Shanghai）。历史见 WORKLOG。

## 当前结论

**咱们的源内核已真实链接 ArmCpu、ArmDTPlatform；加载器源码候选已接线，尚未生成或验证本仓启动镜像。** CI15 [39755850870](https://github.com/wh1stl3/UniXNU/actions/runs/39755850870) success，下载内核20,187,888字节、SHA a9e08c693fec4034f613cd554ea94e5855b25b727b4bfb4af46a4103f565bc7a，五平台导出、零undefined。仅构建与静态检查通过，未QEMU、未在手机执行本仓XNU。

**R-004 A已获用户明确批准，首轮受限固件CI [39761427579](https://github.com/wh1stl3/UniXNU-nuwa/actions/runs/39761427579) 已失败，精确首错为缺失入口HOB GUID/生产者；最小补丁已准备。** 只编译四个EFI模块、FD与BootShim并检查产物；不打boot.img、不操作手机。

## 本轮结果

- 固件第一轮BootShim实际成功：112B/SHA9346a527，头image_size3145840，下载机器码确认拷贝3145728B。EDK因gSiliciumEntryArgHobGuid缺失失败；固定sheng来源补齐DEC/SEC生产链，83项静态检查通过，待第二轮。[构建记录](operations/2026-10-22-firmware-candidate-build.md)。

- 三份源码候选补丁：BootShim image_size包含自身；nuwa DSC/FDF/包路径/库接入UniXNU应用、UniXNUDxe、DarwinBoot和只读initrd发布模块；裁掉借用sheng模块的AddMemory/GCD扩展逻辑，不继承其内存策略。
- 75项静态检查通过，两个来源树真实git apply --check退出0；原始内核/输入/补丁/board/feed哈希固定。只在内存模拟应用，未修改任何参考源树。[接线及内存报告](operations/2026-10-22-loader-source-integration.md)。
- 从参考现有xbl_config原件独立提取8,342字节原始cfg：28个DDR行+14个寄存器行，DXE Heap精确209.75MiB；隔壁整理文本的42行相同，但其C表改写了NoMap/AddDynamicMem、拆分FD并追加高地址策略。原始表和差异已入库，未直接转换成运行内存表。
- Android只读既有证据：ST FTS SPI/st_fts_m2.ftb、活跃m2_38_0c_0a面板、Adreno740v2、KIOXIA UFS；固定MiCode DT与LineageOS来源。[驱动取证](operations/2026-10-22-android-driver-evidence.md)。本轮未操作手机，上轮采集后boot_completed=1。

## 下一步

1. 发布入口HOB首错修复，启动第二轮固件CI；检查实际编译结果并下载四模块EFI/FD。固定三个来源及LF归一化输入hash，仅在Actions RUNNER_TEMP独立树应用补丁。
2. 下载EFI/FD/BootShim及报告，核对AARCH64 PE、GUID/DEPEX、FV内容、FD大小和shim头。通过前不声称完整固件可启动；源内核不包含在此固件构建中。设备执行/boot.img/板值仍为后续独立审批范围。
3. 在任何XNU负载/启动镜像组装前，继续核验CI15 runtime crypto/pthread provider、ARCH_TIMER/startup/GIC/PSCI、13项boot-progress及watchdog scratch；新内核的NativePrelink布局和12处Libm外部PC编码仍待审查，旧CI13只读plan不能直接继承。
4. 原厂NoMap/AddDynamicMem语义、RamManager最终EFI map、initrd保留/映射与FAT挂载、DarwinBoot连续分配均为TODO；按D-002先512MiB–1GiB过阶段5，再抬容量。板字段修改仍单独审阅。

## 当前边界与证据

- feed和board不变、example=true；4KiB，iPhone10,3/d22ap/iOS16.7.16/20H392，8796.141.3；ipad_identity=true为安全属性。连续窗口硬上限8GiB。
- Git/gh/workflow已有持续授权；不得强推/改写历史；两个旧仓及上游源码只读。四类硬停不因Git授权解除。
- reports/loader-integration/为本轮原始cfg、75项静态检查、apply检查与来源状态；config/loader-candidate.json是审计清单，不是新增board字段。
- reports/kernel-ci/39755850870/为两库实际重链接和下载核对；reports/donor-compat/ci15-kernel-bindings.json为65,348个指针绑定零缺失，不等于完整ABI通过。
- CI工具链为macOS Actions/Xcode16.4/Apple clang17/iphoneos18.5；WSL完整内核构建未验证。源CI关闭性能、boot-progress和startup ARCH_TIMER的范围不变，ArmVirt仅独立编译。
- 四模块源码接线不保证DXE/BDS/协议安装和initrd发布成功；完整nuwa启动链、SMMU/DMA、根卷和iOS用户态仍未验证。R-004 A范围内已生成BootShim，EFI/FD尚无成功产物；无boot.img/设备动作或_verified=true。
