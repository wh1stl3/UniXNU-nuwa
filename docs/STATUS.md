# STATUS

> 当前唯一真相；更新：2026-10-22 17:37（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**第十四轮CI真实成功：8796.141.3源内核和三个通用平台archive均已编译，符号名闭包静态检查通过。尚无完整nuwa启动链验收。** [39750542014](https://github.com/wh1stl3/UniXNU/actions/runs/39750542014)于17:10:51完成；普通ARM64/Darwin22.6，0未解析符号，两项NativePrelink标记1。未QEMU、未运行本仓XNU实机内核。

## 本轮结果

- ArmCpu、ArmDTPlatform、ArmVirtPlatform三库真实编译成功，复位noreturn修复生效；CI14未把三库链接回内核。[来源和下一链接门](operations/2026-10-22-driver-reuse-and-platform-link.md)。
- 下一轮将原make实际argv保持不变，仅追加ArmCpu和ArmDTPlatform真实库及依赖，验证最终内核五项导出和零undefined；7项命令保护测试、完整源输入和shell语法检查通过，[第十五轮39755850870](https://github.com/wh1stl3/UniXNU/actions/runs/39755850870)已触发，device_ref=ca8db300bf68ebc4853e023f08b920da0eab5de0，实际重链接待取证。
- 复用驱动优先采用UniXNU和已有开源实现，固定提交/许可/依赖。同SoC不代替nuwa板级证据。已清点fuxi/vermeer来源，不复制上游树。
- 用户提供已root的Android ADB：只读采集已确认fts_touch_spi绑定SPI0.0、DT compatible=st,spi，固件名st_fts_m2.ftb；Adreno740v2、KIOXIA UFS及1440x3200 DSI模式已记录。活跃面板m2_38_0c_0a已由运行态双源确认；MiCode nuwa DT及LineageOS SM8550 fts_spi源码固定提交对照完成。精确芯片修订和XNU适配未验证，所有板配置保持原值。[Android取证与来源](operations/2026-10-22-android-driver-evidence.md)。

## 下一步

1. 跟踪第十五轮39755850870，以实际链接日志/产物核对结果，失败按第一处真实error推进。
2. 沿已确认ST FTS SPI/活跃m2面板及UFS/GPU绑定审查源实现、时序和依赖；保留TLMM/IRQ/SID解析及精确芯片TODO，不把Android观测当XNU验收。
3. 继续DarwinBoot/UniXNU入口、boot-progress 13回调/watchdog scratch与真实crypto/pthread接口审查，再接-D正式配置。
4. 保持donor PC-relative/完整ABI门；改板级内存/地址、生成镜像或fastboot boot前先NEED-REVIEW硬停。

## 当前边界

- 全部Git、gh、workflow修改及CI触发已有用户授权；按COMMIT-QUEUE分里程碑，不强推/改写历史。API发布校验相同Git对象且force=false。
- 两个旧仓及来源树只读，设备仓独立；CI临时源树在云端RUNNER_TEMP、设备仓外，不整体升级基座。
- feed和board不变，example=true。4KiB；iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3；ipad_identity=true（安全属性）。D-002连续窗口上限8GiB，先512MiB–1GiB过阶段5，未知板值TODO。
- 四类硬停保持，无新诊断/固件镜像或_verified=true；仅Android只读ADB采集，无写入/重启。

## 证据与剩余限制

- 第十四轮20,136,616字节源内核SHA298101014d8e1d3dc5b107e05e6731b9aa78be148537a61b80a9617cc0cbed80，下载与runner一致；933份真实编译记录、51项IIG实现无kernelContent残留，原IORPC头不变。见reports/kernel-ci/39750542014/。
- 真实工具链macOS Actions/Xcode16.4/Apple clang17/iphoneos18.5 SDK；iOS16链接metadata不等于16 SDK。本机WSL完整构建未验证。
- 源CI仍关闭性能采样、boot-progress、startup ARCH_TIMER；三个库独立编译成功不代表已链接或硬件可运行。crypto/pthread、时钟和完整driver/RPC ABI仍待审查。
- [donor指令清点](operations/2026-10-22-donor-pc-relative-inventory.md)：12处外部编码含4ADRP未验收；65,348绑定零缺失及119段只读plan仅静态检查通过，未emit，不改roots/slide。
- [参考boot复核](operations/2026-10-22-reference-boot-process-review.md)：容器已打包，但FD内DarwinBoot/UniXNU加载器集成未验证，不代表XNU启动。
- [接口审查](operations/2026-10-22-darwin22-interfaces-and-wsl.md)：watchdog scratch覆盖、13回调、UFS/framebuffer依赖、SMMU/DMA、UEFI内存图及用户态ABI/PAC未验证。
