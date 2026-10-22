# STATUS

> 当前唯一真相；更新：2026-10-22 14:25（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

第五轮[39723736387](https://github.com/wh1stl3/UniXNU/actions/runs/39723736387)实际12:48已失败，证据已下载：IIG适配无残留，首错为ast.c无条件引用已关闭KPERF的类型。已给include和AST调用加条件保护；52项212 hunks静态检查通过，修复db30d6d已发布，[第六轮39733594660](https://github.com/wh1stl3/UniXNU/actions/runs/39733594660)已通过输入检查，真实编译进行中。见[第五轮分析](operations/2026-10-22-ci-fifth-failure.md)。完整内核构建仍未通过。

## 当前边界

- 用户已授权全部Git、gh、workflow修改与推送触发CI，无需重复询问。分里程碑按COMMIT-QUEUE格式提交，不强推、不改写历史。Git HTTPS失败可用校验相同Git对象、force=false的API发布。
- 两个旧仓及来源树只读。设备仓独立，以-D接入正式基座；源CI临时构建树在云端RUNNER_TEMP、设备仓外，不整体升级基座。
- 4KiB；iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3；ipad_identity=true。D-002上限8GiB，先512MiB–1GiB过阶段5；未知板值TODO。
- feed与board不变，example=true；四类硬停有效，无镜像、设备动作或_verified=true。

## 已有证据与限制

- [第五轮失败摘录](../reports/kernel-ci/39723736387/diagnostics.txt)：原始行253481/253484，KPC_MAX_COUNTERS未定义，ast.o失败。原始59MB日志留out，hash/元数据已提交。
- [build.json](../reports/kernel-ci/39723736387/build.json)：51个IIG实现、51条适配记录，无kernelContent残留，原IORPC头不变。581个.o为全build目录合计，kernel_built=false。
- [顺序检查](../reports/kernel-ci/39723736387/compatibility-check.json)52项212 hunks和配方检查通过；只为静态检查，无本机make证据。KPC/KPERF仍关闭，未伪造计数上限或空实现。
- 源CI固定75bc/Apple8796真实配方，boot-progress/设备archive关闭；即使源编译成功，也不能称完整nuwa内核、预链接、QEMU或实机通过。
- [Darwin22接口审查](operations/2026-10-22-darwin22-interfaces-and-wsl.md)：archive ABI、13项回调、watchdog scratch覆盖风险未解决。WSL仍缺clang内建、IIG和sysroot，D-008采用macOS Actions。
- [来源边界复核](../reports/kernel-ci/39723736387/workspace-check.json)：三来源树tracked状态空，board/feed哈希不变。

## 下一步

1. 跟踪第六轮39733594660（device_ref=db30d6d13d5f5fabc3a110d535b1ce3b658c28d5），取完成后的证据检查ast.o与真实链接结果；本轮继续观察最终结果。
2. 按第一处真实错误推进；成功时检查Mach-O、目标对象/符号、版本与NativePrelink标记，不扩大为ABI或实机结论。
3. 完成Darwin22 archive、boot-progress/watchdog、nuwa defconfig与donor kernelcache解析，接回正式-D入口；feed切换独立处理。
4. 命中四类硬停先写NEED-REVIEW再停；只差实体按键的项写PENDING-HUMAN继续。

## 其余缺口

donor hash/slide/initializer/roots、完整driver符号闭包、SMMU/DMA、用户态ABI/PAC、uefi-nuwa/ADT及板值未验证。现有按键待办不阻塞本轮CI。
