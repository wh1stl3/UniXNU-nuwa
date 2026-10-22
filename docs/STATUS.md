# STATUS

> 当前唯一真相；更新：2026-10-22 15:09（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

第九轮[39736926012](https://github.com/wh1stl3/UniXNU/actions/runs/39736926012)已进入最终链接，失败只剩native_legacy_display_probe可选provider引用。已让该调用服从已有display构建开关，保留真实archive要求与完整链接检查；58项226 hunks静态检查通过，准备第十轮。完整内核尚未构建成功，见[取证分析](operations/2026-10-22-ci-fifth-failure.md)。

## 当前边界

- 用户授权全部Git、gh、workflow修改和触发CI，无需重复询问；按COMMIT-QUEUE分里程碑提交，不强推或改写历史。API发布校验相同Git对象且force=false。
- 两个旧仓及来源树只读。设备仓独立，以-D接入正式基座；CI临时工作树在云端RUNNER_TEMP、设备仓外，不整体升级基座。
- 4KiB；iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3；ipad_identity=true。D-002上限8GiB，先512MiB–1GiB过阶段5；未知板值TODO。
- feed与board不变，example=true；四类硬停有效，无镜像、设备动作或_verified=true。

## 已有证据与限制

- [第九轮链接错误](../reports/kernel-ci/39736926012/diagnostics.txt)：原始行851223-851227，唯一未解析符号native_legacy_display_probe来自bsd_init.o；全部编译步骤已到最终LD，仍无完整make成功。
- [第九轮build.json](../reports/kernel-ci/39736926012/build.json)：目标841个.o（不含.cpo），ast.o/processor.o有实际大小/hash；kernel_built=false，51个IIG实现无kernelContent残留，IORPC原头不变。
- [下一轮顺序检查](../reports/kernel-ci/39736926012/next-compatibility-check.json)58项226 hunks及配方hash/bash语法检查通过，只为静态检查。D-011使可选provider调用条件与archive选择一致，无stub或链接错误抑制。
- [第八轮状态](../reports/kernel-ci/39736351595/run.json)为cancelled；此前启动/取消不构成内核成功或失败验证。
- 源CI固定75bc/Apple8796真实配方，boot-progress/设备archive及KPC/KPERF关闭；无stub、伪造计数上限或放松断言。即使源内核成功，也不是完整nuwa内核、预链接、QEMU或实机通过。
- [Darwin22接口审查](operations/2026-10-22-darwin22-interfaces-and-wsl.md)：archive ABI、13项回调、watchdog scratch覆盖风险待解决；WSL仍缺目标工具输入，D-008采用macOS Actions。
- [来源边界复核](../reports/kernel-ci/39723736387/workspace-check.json)：三来源树tracked状态空，board/feed哈希不变。

## 下一步

1. 发布display probe构建条件修复，启动第十轮；完成后取完整make/链接结果和原始Mach-O，按实际首错推进。
2. 成功后只读检查普通ARM64 MH_EXECUTE、版本/符号、NativePrelink两项标记，区分构建、静态接口与实机结论；ARM64页大小是运行时初始化，不从文件零值推断。
3. 完成Darwin22 archive、boot-progress/watchdog、nuwa defconfig及donor kernelcache解析，接回正式-D入口；feed切换独立处理。
4. 命中四类硬停先写NEED-REVIEW再停；只差实体按键的项写PENDING-HUMAN继续。

## 新增参考

用户提供的HackiOS开源对照报告已归档，并核验IIG替代、Linux兼容头、PMU不可用实现和返回加载器边界，见[核验记录](operations/2026-10-22-hackios-reference-review.md)。作为独立参考，不自动变更UniXNU主线、donor或验收条件。

## 其余缺口

donor hash/slide/initializer/roots、完整driver闭包、SMMU/DMA、用户态ABI/PAC、uefi-nuwa/ADT和板值未验证。现有按键待办不阻塞CI。
