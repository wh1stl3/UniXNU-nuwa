# 8796源内核首轮CI

## 本轮交付与范围

用户允许全部Git命令，并选择公开设备仓。已登录wh1stl3并创建[基座fork](https://github.com/wh1stl3/UniXNU)与[设备仓](https://github.com/wh1stl3/UniXNU-nuwa)，证据见`reports/official-ci-plan/repository-setup.json`。尚未创建uefi-nuwa。

新增`ci/workflows/nuwa-8796-source.yml`供安装到基座fork；`scripts/ci/build-8796-source.py`留在设备仓。官方完整workflow仍会在kernel后预链接，并要求完整board；本轮专用入口仅验证源内核，不依赖未知donor地址，也不移除board的example保护。

不是重写XNU构建系统：CI固定checkout UniXNU 75bc，调用其`build-xnu-4k-baseline.sh`。工作目录为云端`RUNNER_TEMP/nuwa-8796-source`，在设备仓外；本地没有克隆或复制上游源码树。`feeds.toml`不改，版本只通过该次源构建的环境变量指定。最终正式设备构建仍需完整模块、defconfig及接口门。

## 固定输入

- UniXNU：`75bc13dd34dc4e403826793739e316a264ce00dd`，不整体升级e95b。
- Apple tag `xnu-8796.141.3`的annotated tag对象`f625db25f47631424dc62ac1c3414b6e530f7e8a`，解引用到`1b191cb58250d0705d8a51287127505aa4bc0789`，与本地审查完全同一源码提交。
- 复用`reports/xnu-8796-sequence/results.json`的48项virtual-pass选择（3项延期/不适用不混入），逐一校验原始/设备候选hash，组装完整46项xnu+2项NativePrelink目录。不是用8个候选目录覆盖完整模块。
- 基座baseline/firehose脚本先校验SHA-256，再在内存适配：3处`.unstripped.noctf`改成8796产物`.unstripped`；内核C/链接及firehose部署目标17改16。仅云端临时构建树写入适配后脚本。
- DriverKit/TrustCache恢复输入固定8796.141.3；libplatform/libdispatch/AvailabilityVersions暂沿用75bc原配方，兼容性未验证。该范围不能冒充所有Darwin22 archive已适配。
- macos-15-intel、Xcode16.4、实际SDK记录；device_ref要求精确40位提交。

## 证据与判据

本地执行：

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -X utf8 -B scripts/ci/build-8796-source.py --base D:/Code/PortingiOS/common/sources/UniXNU --check
```

`reports/official-ci-plan/source-input-check.json`记录48项输入hash与适配后脚本hash；适配脚本用`bash -n`检查，不执行make或Git写入。这里只能称输入/脚本静态检查通过。Windows没有运行内核构建。

云端实际流程会执行基座的checkout/apply/installhdrs、真实firehose archive构建与XNU make；保留失败退出状态，不提供空provider/stub，不压掉undefined-symbol错误，不用BUILD_JSON_COMPILATION_DATABASE替代编译。

boot-progress、PGZ probe及可选设备archive关闭。这是明确的源编译配置，不是nuwa设备配置；13项回调、watchdog、Darwin22 archive、SMMU/DMA及用户态ABI问题仍未验证。没有运行NativePrelink、IPSW获取、payload/bootimg/固件构建或设备动作。

只有make成功、原始kernel存在且解析为普通ARM64 subtype0/MH_EXECUTE，才记录`kernel_built=true`并保存hash、file/otool结果。即使成功也仅为**云端源内核构建通过**，不是预链接通过、QEMU通过或实机通过；`device_verified`始终false。首轮结果为失败，见下。

失败时上传控制台、主机工具清单及build.json（含对象数和应用后的源状态）；成功时额外上传原始Mach-O。工作流只手动触发，不因发布设备代码自动构建。

## 首轮运行

设备仓已发布`b74502128c20549a107025a91ed4ace1e25dce1a`；Q-001至Q-013的分别提交映射见`reports/official-ci-plan/milestone-commits.json`。本地旧分支实际为master，推送前已改名为约定的main，没有改写提交。

GitHub CLI原OAuth授权缺workflow scope，第一次写入返回404；只读确认ADMIN/default main及scope后，经用户网页确认补充workflow授权，安装成功。基座workflow提交`4e4c04aa4dec8dc2af48234e3e3faec9704c73cb`；[运行39715232540](https://github.com/wh1stl3/UniXNU/actions/runs/39715232540)已启动，初次观察主机及输入预检完成、编译步骤进行中，结果未验证。

只读跟踪命令：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/observe-kernel-ci.ps1`。状态/完成后原始日志进入`reports/kernel-ci/<run>/`；下载的构建产物只放`out/kernel-ci/<run>/`，不提交。

首轮最终失败：镜像20260824.0482.1/macOS15.7.9、Xcode16.4(16F6)、SDK18.5、Apple clang17；IIG/MIG存在，48项补丁实际应用、headers步骤和firehose构建完成（lipo报告arm64）。build.json统计所有build子目录共有29个.o，未把它当成29个XNU目标对象或完整内核证据。首个真实错误在run.log:4503：旧`-enable-trivial-auto-var-init-zero-knowing-it-will-be-removed-from-clang`不被识别；没有内核产物。

新增`patches/xnu-8796-ci-candidates/clang17-zero-init.patch`只删除8796 MakeInc.def:309这一个过渡开关，保留:308的`-ftrivial-auto-var-init=zero`。Git apply --check返回0；按照实际文件名顺序检查原48项+1项，49项172 hunks静态检查通过且清零选项仍在。证据`compatibility-check.json`与`failure-analysis.json`。修复待真实重跑，原49独立38/11及后续48项统计不改写。

## 第二轮运行

兼容修复已发布`dbbf029d8c9893759f86d828507e309ade8d11eb`，[第二轮39716728005](https://github.com/wh1stl3/UniXNU/actions/runs/39716728005)已启动，当前编译中。调度命令：`scripts/start-kernel-ci.ps1 -DeviceRef dbbf029d8c9893759f86d828507e309ade8d11eb`；跟踪器传`-RunId 39716728005`。记录时无最终结果。

发布后`post-publish-workspace-check.json`确认三来源树tracked status均空，board SHA-256仍8601b3e5…，基座feed仍dec145fe…；完整hash在JSON，没有改变只读来源树或已批准板配置。

第二轮最终失败，旧clang开关问题已越过。首个错误run.log:11187是对齐8的char typedef不能作为数组元素，后续:16673是IIG生成rpc.kernelContent而8796 IORPC没有该字段。build.json的所有build目录对象共48个，不代表完整内核编译或链接通过。

UIO新增候选保留原typedef，通过声明宏对char数组变量施加原对齐；36处调用的UIO_SIZEOF参数与字节范围不变，详见uio-candidate.json。50项209 hunks内存顺序检查通过，真实clang17验证待重跑。

## IIG纯文本检查与下一轮候选

[检查39717772747](https://github.com/wh1stl3/UniXNU/actions/runs/39717772747)只执行Xcode/IIG查询和二进制字符串枚举，没有内核或镜像构建。作业成功，iig-help.txt确认`--deployment-target`选项；options-strings.txt同时包含四字段旧IORPC与kernelContent新生成模板。下一轮使用Makefile已有OTHER_IIG_FLAGS入口传22.0（DriverKit生成目标），不修改8796 IORPC。此时“能选旧模板”仍是待编译验证的推断，不能写为ABI通过。

## 第三轮运行

设备提交4be1fb48c7389b61fba4a245f58e2bae4e2a9a62，[第三轮39718507532](https://github.com/wh1stl3/UniXNU/actions/runs/39718507532)已启动。宿主fork的head为a3cacd5（新增工具检查workflow），源构建workflow内仍checkout固定75bc，不代表把基座实现升级到a3cac/e95b。当前编译中，最终结果未验证。


第三轮最终结果：失败；证据包现已下载并提取真实错误，见[第三轮分析](2026-10-22-ci-third-failure.md)。原始日志52MB保留out/，提交带原始行号/哈希的摘录，未提交生成源码或构建产物。deployment-target五目标实际生成相同，候选被否证，D-010接替该部分。

## 第四轮运行

修复提交7d6675ee49578eac2b02c5b65a0ac42b29dc1fd4已推送；[39723011018](https://github.com/wh1stl3/UniXNU/actions/runs/39723011018)于2026-10-22 12:33启动。第一次Git推送连接重置，HTTP/1.1重试后成功；只读API确认远端精确提交后才调度。12:34观察实际主机检查、依赖安装、固定输入检查均成功，编译步骤进行中。完整构建结果未验证。

工作流宿主head为caa9acb（仅新增IIG生成探针），源构建仍checkout75bc。第四轮使用51项补丁和固定IIG内联RPC适配；保留IORPC头，关闭KPC/KPERF性能采样，不运行预链接/镜像/设备。完成后优先gh run download获取证据包；旧observe脚本先下载大run日志可能挂起，不能以空run.log判断没有错误。
