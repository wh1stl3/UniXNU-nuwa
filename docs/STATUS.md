# STATUS

> 当前唯一真相；更新：2026-10-22 14:37（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

第六轮[39733594660](https://github.com/wh1stl3/UniXNU/actions/runs/39733594660)最终失败，证据已下载：未再观察到AST错误，首错移至processor.c无条件注册已关闭的KPERF定时器。已给表项加与枚举相同的条件，保留长度断言；53项213 hunks静态检查通过，修复484b97c已发布，[第七轮39734939751](https://github.com/wh1stl3/UniXNU/actions/runs/39734939751)已启动，最终结果待取证。见[取证与分析](operations/2026-10-22-ci-fifth-failure.md)。完整内核构建仍未通过。

## 当前边界

- 用户已授权全部Git、gh、workflow修改与推送触发CI，无需重复询问。分里程碑按COMMIT-QUEUE格式提交，不强推、不改写历史。Git HTTPS失败可用校验相同Git对象、force=false的API发布。
- 两个旧仓及来源树只读。设备仓独立，以-D接入正式基座；源CI临时构建树在云端RUNNER_TEMP、设备仓外，不整体升级基座。
- 4KiB；iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3；ipad_identity=true。D-002上限8GiB，先512MiB–1GiB过阶段5；未知板值TODO。
- feed与board不变，example=true；四类硬停有效，无镜像、设备动作或_verified=true。

## 已有证据与限制

- [第六轮失败摘录](../reports/kernel-ci/39733594660/diagnostics.txt)：原始行352764/352771/352784，KPERF定时器枚举/回调缺失及断言失败；原始66MB日志留out，hash/元数据已提取。
- [build.json](../reports/kernel-ci/39723736387/build.json)：51个IIG实现、51条适配记录，无kernelContent残留，原IORPC头不变。581个.o为全build目录合计，kernel_built=false。
- [顺序检查](../reports/kernel-ci/39733594660/compatibility-check.json)53项213 hunks和配方检查通过；只为静态检查，无本机make证据。KPC/KPERF仍关闭，未伪造计数上限、空实现或放松断言。
- 源CI固定75bc/Apple8796真实配方，boot-progress/设备archive关闭；即使源编译成功，也不能称完整nuwa内核、预链接、QEMU或实机通过。
- [Darwin22接口审查](operations/2026-10-22-darwin22-interfaces-and-wsl.md)：archive ABI、13项回调、watchdog scratch覆盖风险未解决。WSL仍缺clang内建、IIG和sysroot，D-008采用macOS Actions。
- [来源边界复核](../reports/kernel-ci/39723736387/workspace-check.json)：三来源树tracked状态空，board/feed哈希不变。

## 下一步

1. 跟踪第七轮39734939751（device_ref=484b97c57fc2be0a6b5b0455bcca44b5246e0278），完成后检查精确目标对象清单、实际第一处错误与链接结果。
2. 按第一处真实错误推进；成功时检查Mach-O、目标对象/符号、版本与NativePrelink标记，不扩大为ABI或实机结论。
3. 完成Darwin22 archive、boot-progress/watchdog、nuwa defconfig与donor kernelcache解析，接回正式-D入口；feed切换独立处理。
4. 命中四类硬停先写NEED-REVIEW再停；只差实体按键的项写PENDING-HUMAN继续。

## 其余缺口

donor hash/slide/initializer/roots、完整driver符号闭包、SMMU/DMA、用户态ABI/PAC、uefi-nuwa/ADT及板值未验证。现有按键待办不阻塞本轮CI。
