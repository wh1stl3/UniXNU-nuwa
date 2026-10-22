# STATUS

> 当前唯一真相；更新：2026-10-22 16:47（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**8796.141.3源内核已真实编译、链接成功；尚无本仓完整nuwa启动链验收。** 第十三轮[39747264803](https://github.com/wh1stl3/UniXNU/actions/runs/39747264803)源内核再次成功，普通ARM64/Darwin22.6、0未解析符号、两项NativePrelink标记1；整体CI失败于后续平台archive，不是内核编译失败。未QEMU、未实机。

## 本轮结果

- ArmCpu真实对象和libArmCpu.a已生成；ArmDTPlatform唯一实际error为platformStageReset缺noreturn声明。已增加与无条件WFE循环一致的前置属性声明，4项命令保护测试通过，不放宽-Wmissing-noreturn或其余-Werror；三项既有风格警告仍可见。下一轮真实编译待触发。见[archive记录](operations/2026-10-22-darwin22-archive-build.md)。
- VFS桥接已进入真实内核，参考选择65,348项donor指针绑定零失败；固定官方只读plan的119段布局/指针检查通过。仅静态检查通过，未emit，完整ABI/PC-relative未验收。见[接口记录](operations/2026-10-22-donor-vfs-bridge.md)及[实际plan](../reports/donor-compat/ci13-readonly-plan.json)。
- 用户所指并行boot.img确已打包；独立内存拆读核对203,157,504字节、FD/内核/ADT及FAT内容hash一致。但payload无EFI、固件日志无DarwinBoot/UniXNUDxe/UniXNUPkg，加载器集成尚缺证据。可复用shim/cwd修正与UEFI对账方法，不能据此确认XNU启动。见[过程文档与boot复核](operations/2026-10-22-reference-boot-process-review.md)。来源仓现有授权不导入本仓。

## 下一步

1. 发布最小noreturn声明修复并启动下一轮，取三个平台archive的实际编译/符号闭包结果；不以ArmCpu单库成功验收全部驱动。
2. 审阅正式nuwa构建所需的DarwinBoot/UniXNU固件入口、boot-progress 13项回调及watchdog接口，处理scratch覆盖风险，再接-D入口。参考容器打包经验可用，板值和来源镜像不直接搬入。
3. 对既定iPhone donor继续审查12处Libm外部PC编码及真实roots/初始化器；119段只读布局通过不等于指令/ABI或可启动性通过。禁止宽泛oracle豁免，无新镜像。
4. 暂不安排该源内核上机；需要改板值、生成镜像或fastboot boot前，先按本仓NEED-REVIEW硬停。只差实体按键记PENDING-HUMAN，不阻塞软件侧。

## 当前边界

- 全部Git、gh、workflow修改及CI触发已有用户授权；按COMMIT-QUEUE分里程碑，不强推/改写历史。API发布校验相同Git对象且force=false。
- 两个旧仓及来源树只读，设备仓独立；CI临时源树在云端RUNNER_TEMP、设备仓外，不整体升级基座。
- feed和board不变，example=true。4KiB；iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3；ipad_identity=true（安全属性）。D-002连续窗口上限8GiB，先512MiB–1GiB过阶段5，未知板值TODO。
- 四类硬停保持，无新诊断/固件镜像、设备动作或_verified=true。

## 证据与剩余限制

- 第十三轮实际内核20,136,616字节，SHA08c23dc162e934a2e9c59780da0a3d69c8f7f422c9f167b80a87b10e550927e3；[实际构建](../reports/kernel-ci/39747264803/build.json)、[产物检查](../reports/kernel-ci/39747264803/kernel-inspection.json)、[archive检查](../reports/kernel-ci/39747264803/driver-archives/audit.json)。源输入ff8abe167a039560c816892b78b00660b5518888、60项补丁；原件忽略保存在out，不提交二进制。
- 真正工具链为macOS Actions/Xcode16.4/Apple clang17/iphoneos18.5 SDK；iOS16链接metadata不表示使用16SDK。WSL本机仍缺目标工具链输入，不写成本机通过。首轮完整成功见[第十轮证据](operations/2026-10-22-ci-source-kernel-success.md)。
- 933份真实C/C++记录、51项IIG实现无kernelContent残留、原IORPC头不变。源CI关闭KPC/KPERF、boot-progress和设备archive，三个平台库仍是独立审查，未链接回源内核。源编译成功不验收RPC/driver ABI。
- [指令清点](operations/2026-10-22-donor-pc-relative-inventory.md)：9已知常量池完整hash通过，剩余12外部编码（4ADRP）未验收；参考候选30段4,201,824字节保持不证明语义。参考roots/slide没有写入本仓board。
- [Darwin22接口审查](operations/2026-10-22-darwin22-interfaces-and-wsl.md)：正式nuwa配置、watchdog scratch布局、13回调及UFS/framebuffer依赖仍缺，SMMU/DMA、UEFI实机内存图、用户态ABI/PAC未验证。
- [三件产物审查](operations/2026-10-22-parallel-three-artifacts-review.md)与新boot过程复核互补；来源文档/实际运行SHA已分开核对，当前workflow新增trustcache/仅固件步骤不归于已下载产物。
- [HackiOS参考](operations/2026-10-22-hackios-reference-review.md)仅作独立对照，不改变主线/donor/验收条件。现有按键待办不阻塞软件工作。
