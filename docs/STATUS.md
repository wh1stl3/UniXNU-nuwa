# STATUS

> 当前唯一真相；更新：2026-10-22 14:56（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

第五至七轮失败证据均已取得；AST与processor目标对象已实际生成，后续t_kpc初始化首错及同类关闭性能模块后的入口已补条件。第八轮为合并明确源码缺口而取消，不作验证。57项225 hunks静态检查通过；修复4dd55f0已发布，[第九轮39736926012](https://github.com/wh1stl3/UniXNU/actions/runs/39736926012)已启动。第九轮已进入最终链接，失败于单个可选display probe符号；正在整理修复证据。完整内核构建仍未通过，见[取证分析](operations/2026-10-22-ci-fifth-failure.md)。

## 当前边界

- 用户授权全部Git、gh、workflow修改和触发CI，无需重复询问；按COMMIT-QUEUE分里程碑提交，不强推或改写历史。API发布校验相同Git对象且force=false。
- 两个旧仓及来源树只读。设备仓独立，以-D接入正式基座；CI临时工作树在云端RUNNER_TEMP、设备仓外，不整体升级基座。
- 4KiB；iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3；ipad_identity=true。D-002上限8GiB，先512MiB–1GiB过阶段5；未知板值TODO。
- feed与board不变，example=true；四类硬停有效，无镜像、设备动作或_verified=true。

## 已有证据与限制

- [第七轮首错](../reports/kernel-ci/39734939751/diagnostics.txt)：task.c无条件初始化t_kpc；已按task.h既有KPC条件保护。AST与定时器表旧错未再出现。
- [第七轮build.json](../reports/kernel-ci/39734939751/build.json)：ast.o/processor.o有实际路径、大小及SHA-256，目标目录674个.o（不含.cpo）；kernel_built=false。51份IIG实现无kernelContent残留，IORPC原头不变。
- [57项顺序检查](../reports/kernel-ci/39736351595/next-compatibility-check.json)及输入hash/bash语法检查通过，仍为静态检查。scheduler/KTRACE/ARM64上下文候选来自源码审查，不能写成已经观察到的链接错误。
- [第八轮状态](../reports/kernel-ci/39736351595/run.json)为cancelled；此前启动/取消不构成内核成功或失败验证。
- 源CI固定75bc/Apple8796真实配方，boot-progress/设备archive及KPC/KPERF关闭；无stub、伪造计数上限或放松断言。即使源内核成功，也不是完整nuwa内核、预链接、QEMU或实机通过。
- [Darwin22接口审查](operations/2026-10-22-darwin22-interfaces-and-wsl.md)：archive ABI、13项回调、watchdog scratch覆盖风险待解决；WSL仍缺目标工具输入，D-008采用macOS Actions。
- [来源边界复核](../reports/kernel-ci/39723736387/workspace-check.json)：三来源树tracked状态空，board/feed哈希不变。

## 下一步

1. 跟踪第九轮39736926012（device_ref=4dd55f0ec8c72e08946c6f597bb3ca3389b65dbd），完成后gh run download取证，按实际首错或链接结果推进。
2. 成功后只读检查普通ARM64 MH_EXECUTE、版本/符号、NativePrelink两项标记，区分构建、静态接口与实机结论；ARM64页大小是运行时初始化，不从文件零值推断。
3. 完成Darwin22 archive、boot-progress/watchdog、nuwa defconfig及donor kernelcache解析，接回正式-D入口；feed切换独立处理。
4. 命中四类硬停先写NEED-REVIEW再停；只差实体按键的项写PENDING-HUMAN继续。

## 新增参考

用户提供的HackiOS开源对照报告已归档，并核验IIG替代、Linux兼容头、PMU不可用实现和返回加载器边界，见[核验记录](operations/2026-10-22-hackios-reference-review.md)。作为独立参考，不自动变更UniXNU主线、donor或验收条件。

## 其余缺口

donor hash/slide/initializer/roots、完整driver闭包、SMMU/DMA、用户态ABI/PAC、uefi-nuwa/ADT和板值未验证。现有按键待办不阻塞CI。
