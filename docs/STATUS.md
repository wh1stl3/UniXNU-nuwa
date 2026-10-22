# STATUS

> 当前唯一真相；更新：2026-10-22 12:40（Asia/Shanghai）。历史见WORKLOG。

## 当前结论

第三轮实错为IIG的kernelContent及缺失公开arm64/kpc.c；第四轮[39723011018](https://github.com/wh1stl3/UniXNU/actions/runs/39723011018)被适配器主动拒绝未知回调模板。已取得全部17个真实IIG生成文件，补入精确回调赋值规则，432块静态转换通过；准备第五轮。见[分析与证据](operations/2026-10-22-ci-third-failure.md)。完整内核构建仍未通过。

## 当前边界

- 用户最新明确授权全部Git和gh操作，无需重复询问；分里程碑提交，格式见COMMIT-QUEUE，不改写历史。两个旧仓及来源树仍只读。
- 设备仓独立，以-D接入正式基座；源CI的临时工作树在云端RUNNER_TEMP、设备仓外。未整体跟进新基座。
- 4KiB；iPhone10,3/d22ap/iOS16.7.16/20H392，8796.141.3；ipad_identity=true。D-002上限8GiB，先512MiB–1GiB过阶段5，未知板值TODO。
- feed和board保持不变，example=true；四类硬停有效，没有镜像、设备动作或_verified=true。

## 已有证据与限制

- [第三轮原始错误摘录](../reports/kernel-ci/39718507532/diagnostics.txt)和[失败分析](../reports/kernel-ci/39718507532/failure-analysis.json)：kernel_built=false；539个.o是所有build目录合计；未观察到旧UIO对齐错误。
- [IIG真实生成短CI](https://github.com/wh1stl3/UniXNU/actions/runs/39722376512)五个deployment目标输出相同，不能修复RPC。候选转换真实OSObject样本11块，保留消息字段/内核include并拒绝未知模板；后续17文件432块已静态转换通过，真实编译/ABI待验证，D-010记录代价。
- [51项顺序检查](../reports/kernel-ci/39718507532/compatibility-check.json)及配方检查通过；清零选项、IORPC原头不变。没有本机make。
- 源CI固定75bc真实配方，boot-progress/设备archive关闭。即使后续源编译通过，也不能称完整nuwa内核、预链接、QEMU或实机通过。
- [Darwin22接口审查](operations/2026-10-22-darwin22-interfaces-and-wsl.md)的archive ABI、13项回调及watchdog scratch覆盖风险仍未解决；WSL预检仍缺目标clang内建、IIG和sysroot，未取得本机完整内核构建证据。D-008采用macOS Actions。
- [来源边界复核](../reports/kernel-ci/39718507532/workspace-check.json)：三棵来源树tracked状态空，board/feed哈希不变。

## 下一步

1. 发布17文件模板验证后的候选并启动第五轮；确认真实生成与KPC/KPERF选择，再按实际编译结果推进。
2. 按实际第一处错误继续适配；成功时检查Mach-O/对象/符号/版本，不能把构建结果写成实机通过。
3. 完成Darwin22 archive、boot-progress/watchdog、nuwa defconfig与donor kernelcache解析，再接回正式-D入口；feed切换独立处理。
4. 命中四类硬停先写NEED-REVIEW再停；仅实体按键待办写PENDING-HUMAN后继续。

## 其余缺口

donor hash/slide/initializer/roots、完整driver符号闭包、SMMU/DMA、用户态ABI/PAC、uefi-nuwa/ADT/板值均未验证。现有PENDING-HUMAN按键项不阻塞本轮CI。
