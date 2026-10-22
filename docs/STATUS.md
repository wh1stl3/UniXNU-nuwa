# STATUS

> 当前唯一真相；更新：2026-10-22 14:54（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

第七轮已确认ast.o/processor.o实际生成，首错t_kpc初始化已加条件；第八轮39736351595已请求取消，以批量合入新确认的两处ARM64 KPC上下文回调保护。57项225 hunks静态检查通过，准备以新提交重跑。取消不作构建验证；完整内核仍未通过。见[取证与分析](operations/2026-10-22-ci-fifth-failure.md)。

## 当前边界

- 用户已授权全部Git、gh、workflow修改与推送触发CI，无需重复询问。分里程碑按COMMIT-QUEUE格式提交，不强推、不改写历史。Git HTTPS失败可用校验相同Git对象、force=false的API发布。
- 两个旧仓及来源树只读。设备仓独立，以-D接入正式基座；源CI临时构建树在云端RUNNER_TEMP、设备仓外，不整体升级基座。
- 4KiB；iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3；ipad_identity=true。D-002上限8GiB，先512MiB–1GiB过阶段5；未知板值TODO。
- feed与board不变，example=true；四类硬停有效，无镜像、设备动作或_verified=true。

## 已有证据与限制

- [第七轮失败摘录](../reports/kernel-ci/39734939751/diagnostics.txt)：原始行404291，task.c的t_kpc字段缺失。原始69MB日志留out，完整hash在failure-analysis.json。
- [build.json](../reports/kernel-ci/39734939751/build.json)：ast.o/processor.o有实际路径、大小与哈希，目标目录674个.o（不含.cpo），kernel_built=false；51份IIG实现无kernelContent残留，IORPC原头不变。
- [下一轮顺序检查](../reports/kernel-ci/39734939751/next-compatibility-check.json)56项222 hunks（第八轮输入；新候选57项225 hunks）及配方检查通过，只为静态检查，无本机make证据。scheduler/KTRACE是相关源码发现，尚无其实际链接失败结论；无stub或放松断言。
- 源CI固定75bc/Apple8796真实配方，boot-progress/设备archive关闭；即使源编译成功，也不能称完整nuwa内核、预链接、QEMU或实机通过。
- [Darwin22接口审查](operations/2026-10-22-darwin22-interfaces-and-wsl.md)：archive ABI、13项回调、watchdog scratch覆盖风险未解决。WSL仍缺clang内建、IIG和sysroot，D-008采用macOS Actions。
- [来源边界复核](../reports/kernel-ci/39723736387/workspace-check.json)：三来源树tracked状态空，board/feed哈希不变。

## 下一步

1. 确认第八轮取消最终状态，发布含ARM64上下文保护的57项候选并重跑，取实际第一处错误/链接结果；成功后检查Mach-O和NativePrelink标记。
2. 按第一处真实错误推进；成功时检查Mach-O、目标对象/符号、版本与NativePrelink标记，不扩大为ABI或实机结论。
3. 完成Darwin22 archive、boot-progress/watchdog、nuwa defconfig与donor kernelcache解析，接回正式-D入口；feed切换独立处理。
4. 命中四类硬停先写NEED-REVIEW再停；只差实体按键的项写PENDING-HUMAN继续。

## 其余缺口

donor hash/slide/initializer/roots、完整driver符号闭包、SMMU/DMA、用户态ABI/PAC、uefi-nuwa/ADT及板值未验证。现有按键待办不阻塞本轮CI。
