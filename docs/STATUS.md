# STATUS

> 当前唯一真相；更新：2026-10-22 16:03（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

**8796.141.3源内核已编译、链接成功。** [第十轮39738601892](https://github.com/wh1stl3/UniXNU/actions/runs/39738601892)于15:20完成，完整配方退出成功，产物已下载并与runner哈希对齐；普通ARM64 MH_EXECUTE、Darwin22.6.0、LC_SOURCE_VERSION=8796.141.3、未解析符号0、NativePrelink两项标记=1，静态检查通过。尚不是完整nuwa可启动内核；未预链接、未QEMU、未实机。见[成功取证](operations/2026-10-22-ci-source-kernel-success.md)。

## 本轮推进

[第十一轮39742250205](https://github.com/wh1stl3/UniXNU/actions/runs/39742250205)已完成：源内核再次完整构建成功，933份真实C/C++记录及四项消费者输入已取得；整体CI失败在ArmCpu的不存在libsa搜索目录被-Werror拒绝。仅移除已确认不存在的该目录候选、保留其余头文件检查，4项参数保护测试通过，待发布重跑；平台archive尚未通过。见[本轮记录](operations/2026-10-22-darwin22-archive-build.md)。

## 当前边界

- 用户授权全部Git、gh、workflow修改和触发CI，无需重复询问；按COMMIT-QUEUE分里程碑提交，不强推或改写历史。API发布校验相同Git对象且force=false。
- 两个旧仓及来源树只读。设备仓独立，以-D接入正式基座；CI临时工作树在云端RUNNER_TEMP、设备仓外，不整体升级基座。
- 4KiB；iPhone10,3/d22ap/iOS16.7.16/20H392、8796.141.3；ipad_identity=true。D-002上限8GiB，先512MiB–1GiB过阶段5；未知板值TODO。
- feed与board不变，example=true；四类硬停有效，无诊断/固件镜像、设备动作或_verified=true。

## 已有证据与限制

- [运行状态](../reports/kernel-ci/39738601892/run.json)和[构建记录](../reports/kernel-ci/39738601892/build.json)：完整make/链接成功；输入526651af94610f40c3223eae9550deaa3c44ae57，48项移植选择加10项CI兼容补丁。此前实际错误及修复见[过程记录](operations/2026-10-22-ci-fifth-failure.md)。
- 原始内核20,136,488字节，SHA-256 bdaad81373d00df8334cb5a453b32f06a5e607c3e7d8cde812e4f5f927e19ced；保存在忽略的out/kernel-ci/39738601892/，不提交二进制。[只读产物检查](../reports/kernel-ci/39738601892/kernel-inspection.json)包含版本、符号和标记；标记存在不等于donor兼容。
- 真实工具为macOS Actions、Xcode16.4、Apple clang17、iphoneos18.5 SDK；链接metadata指定iOS16.0不表示使用了16.0 SDK。WSL本机路线仍缺目标输入，不能写成本机编译通过。
- 841个目标.o（不含.cpo），51个IIG实现无kernelContent残留、原IORPC头不变。源CI关闭KPC/KPERF、boot-progress和可选设备archive；编译成功不验收RPC/driver ABI或这些功能。
- [Darwin22接口审查](operations/2026-10-22-darwin22-interfaces-and-wsl.md)：archive输出/符号、13项回调、watchdog scratch覆盖风险仍待解决；正式nuwa配置尚未接齐。
- [边界复核](../reports/kernel-ci/39738601892/acceptance.json)：下载文件与runner SHA相同，三来源树tracked状态空，board/feed哈希不变。文件段对齐不能替代运行时页大小或实机验证。

## 下一步

1. 发布第十一轮无效libsa搜索目录的最小修复并重跑平台archive验证，保留-Werror及未知缺失目录报错；四份真实命令和原对象证据见reports/kernel-ci/39742250205/。源内核已成功与archive尚未验证分开记录；不把符号名闭包扩大成完整ABI通过。
2. 收口boot-progress 13项回调、watchdog接口和scratch布局风险，再建立正式nuwa配置并接回-D入口；保持feed，未知板值TODO。
3. 只读解析既定iPhone donor的kernelcache，补齐真实hash/roots等证据；不移用iPadOS17的prelink数值，不生成镜像。任何board身份/内存/基址变更先硬停审查。
4. 当前不安排这份源内核上机；达到可启动链路前置条件后，在NEED-REVIEW列出至少两条验证路径、代价和最小批准范围。只差实体按键的待办不阻塞软件侧工作。

## 并行产物可用性

用户指出的只读参照仓现已真实产出run24源内核、53MB预链接候选及3MiB FD，hash已核对；donor身份及VFS桥接有可复用证据。实际驱动被清空、预链接代码/常量豁免、4项UEFI保留区及DarwinBoot接线仍待收口，不能据此确认nuwa可启动。采用复用证据并补齐本仓接口的路径，见[具体方案](operations/2026-10-22-parallel-three-artifacts-review.md)。未生成镜像或修改参照仓。

## 新增参考

用户提供的HackiOS开源对照报告已归档，并核验IIG替代、Linux兼容头、PMU不可用实现和返回加载器边界，见[核验记录](operations/2026-10-22-hackios-reference-review.md)。作为独立参考，不自动变更UniXNU主线、donor或验收条件。

## 其余缺口

donor hash/slide/initializer/roots、完整driver闭包、SMMU/DMA、用户态ABI/PAC、uefi-nuwa/ADT和板值未验证。现有按键待办不阻塞软件侧工作。
