# STATUS

> 当前唯一真相；更新：2026-10-22 17:49（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**源内核已编出，并成功真实链接ArmCpu与ArmDTPlatform；完整nuwa启动链仍未验收。** 第十四轮三平台archive编译/闭包通过；[第十五轮39755850870](https://github.com/wh1stl3/UniXNU/actions/runs/39755850870)于17:45:40整体success。下载内核20,187,888字节、SHAa9e08c693fec4034f613cd554ea94e5855b25b727b4bfb4af46a4103f565bc7a，与runner一致；五项平台导出存在，未解析符号0。仅编译与静态检查通过，未QEMU、未在手机执行本仓XNU。

## 本轮结果

- CI15精确设备输入ca8db300bf68ebc4853e023f08b920da0eab5de0；保持原make argv，仅追加两库及依赖，真实第二次make退出0；普通ARM64、8796.141.3/Darwin22.6，两项NativePrelink标记1。[平台链接及来源报告](operations/2026-10-22-driver-reuse-and-platform-link.md)。
- 同轮内核新SHA下，65,348项donor指针绑定再次零缺失。CI13的119段只读plan不直接继承给新内核；完整布局/指令/ABI仍未验收，没有emit。
- Android只读ADB确认ST FTS SPI（fts_touch_spi、st,spi、st_fts_m2.ftb）、活跃m2_38_0c_0a面板、Adreno740v2、KIOXIA UFS。MiCode nuwa DT与LineageOS SM8550 fts_spi源码固定提交对照；Android仍boot_completed=1。[实机观测报告](operations/2026-10-22-android-driver-evidence.md)。
- 驱动优先复用真实开源实现；不以虚拟uinput-goodix/备用DT节点/旧I2C版误判触控，不套用sheng板值。UFS host窗口与stream cell和UniXNU源对应，DMA/SMMU接管未验证。

## 下一步

1. **转入运行配置审查**：Darwin22真实crypto/pthread provider与初始化、startup ARCH_TIMER、平台注册/GIC/PSCI；保留原boot profile依赖检查，不以两库链接成功代替可启动性。当前无待运行CI；不要为同一已通过输入空转重跑。
2. 处理boot-progress 13回调和watchdog scratch覆盖，审查DarwinBoot/UniXNU固件入口，再接-D正式nuwa配置。触发镜像生成或板内存/地址修改前先NEED-REVIEW硬停。
3. 对新内核继续官方只读plan及12处Libm外部PC编码/roots/初始化器审查；不平移旧plan或扩大oracle豁免。
4. 沿ST FTS SPI、活跃m2面板及UFS/GPU的已固定源码做最小依赖审查，补精确芯片修订、TLMM/IRQ/SID和电源时序证据；Android只读信息可继续采，未知项TODO。

## 当前边界

- 全部Git、gh、workflow修改及CI触发已有用户授权；按COMMIT-QUEUE分里程碑，不强推/改写历史。API发布校验相同Git对象且force=false。
- 两个旧仓及来源树只读，设备仓独立；CI临时源树在云端RUNNER_TEMP、设备仓外，不整体升级基座。
- feed和board不变，example=true。4KiB；iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3；ipad_identity=true（安全属性）。D-002连续窗口上限8GiB，先512MiB–1GiB过阶段5，未知板值TODO。
- 四类硬停保持，无新诊断/固件镜像或_verified=true；仅Android只读ADB采集，无写入/重启。

## 证据与剩余限制

- 最新reports/kernel-ci/39755850870含实际构建、三archive、平台链接、下载独立解析、五导出、原argv和边界hash；大日志/二进制忽略在out。reports/donor-compat/ci15-kernel-bindings.json为新内核的指针名清点。
- 933份真实编译记录，51个IIG实现无kernelContent残留，原IORPC头不变；实际工具链macOS Actions/Xcode16.4/Apple clang17/iphoneos18.5 SDK。iOS16 metadata不等于16 SDK，WSL本机完整构建未验证。
- 源CI保留关闭性能采样、boot-progress与startup ARCH_TIMER的范围；两库已链接，但crypto/pthread、时钟及完整driver/RPC ABI未验收。ArmVirtPlatform仅独立编译，不与实机平台一起force_load。
- [donor指令清点](operations/2026-10-22-donor-pc-relative-inventory.md)：12处外部编码含4ADRP未验收；原CI13只读plan/参考roots/slide不构成正式配置。
- [参考boot复核](operations/2026-10-22-reference-boot-process-review.md)：容器已打包，FD内DarwinBoot/UniXNU加载器集成未验证，不代表XNU启动。
- [接口审查](operations/2026-10-22-darwin22-interfaces-and-wsl.md)：watchdog scratch、UFS/framebuffer依赖、SMMU/DMA、UEFI连续可用内存图及用户态ABI/PAC仍未验证。
