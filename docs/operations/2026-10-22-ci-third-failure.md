# 第三轮CI实际错误与第四轮候选

## 输入与证据

用户最新指令授权全部Git及gh操作，要求下载第三轮并修复后推下一轮。源构建仍固定基座75bc、Apple XNU 1b191cb/8796.141.3；不切feed，设备仓仍独立。

下载命令：`gh run download 39718507532 --repo wh1stl3/UniXNU --dir out/kernel-ci/39718507532`。证据包artifact 12399319854，服务端记录见`reports/kernel-ci/39718507532/artifacts.json`。原始控制台52,230,989字节，SHA-256 `f17b03b58f1ac381dba8e583db86fc34e8022acb4d012afef0cc55a8ba621e2c`；留在忽略的out目录，不提交超大日志或生成源码。提取命令：`python -B scripts/ci/summarize-build-evidence.py 39718507532`。行号按原始LF换行计数，摘录与哈希见diagnostics.txt/failure-analysis.json。

## 实际结果

- 原始控制台34853/34870/34880/34910：OSObject.iig.cpp访问不存在的IORPC.kernelContent。build.json显示原IORPC头未变、51个生成文件含该引用。22.0候选未解决错误。
- 原始控制台99813：No rule to make target osfmk/arm64/kpc.c, needed by kpc.o。公开8796树无此文件，但osfmk/conf/files.arm64:94按kpc+nos_arm_asm选择；source-machine-layer补丁启用nos_arm_asm后暴露该路径。
- 本轮未观察到上一轮UIO数组对齐错误；这只说明当前日志未再出现该错误，不是UIO功能或完整内核通过。build目录总计539个.o，包含辅助库/宿主构建，不能作为539个XNU目标对象通过的证据。kernel_built=false，未到完整链接成功。

## IIG定位与候选

短工作流[39722376512](https://github.com/wh1stl3/UniXNU/actions/runs/39722376512)对真实8796 OSObject.iig生成代码；不运行内核或镜像。16.0、19.0、20.0、21.0、22.0五个目标均exit0、17557字节、8处kernelContent，SHA-256均为77c9e919…，完整值见iig-target-results.json。此前用工具帮助和字符串推断deployment-target能切换模板不成立。

真实生成代码保留内联消息else分支。`scripts/ci/iig-darwin22.py`仅适配固定DriverKit-427.100.5版本的已识别叶子条件，选择内联内容/消息指针，保留其余KERNEL路径。不会全局#undef KERNEL，不扩大IORPC、不伪造provider、不忽略链接错误。真实OSObject样本转换11个块，消息头/port descriptor声明数量保留；未知版本和未知残留模板拒绝。见iig-adapter-check.json。这是源码生成兼容候选，完整生成集和编译尚待下一轮验证。

## KPC配置修复与验证边界

`zzzz-ci-public-profiling.patch`在其他补丁之后，仅从BCM2837 PERF_DBG_BASE去掉kpc和kperf。kperf_kpc.c:39-56直接调用KPC，故不能只移除缺失文件；源CI关闭这两个性能采样选项，保留调试/串口。没有添加stub、借用其他架构KPC或改变正式nuwa板配置。性能采样和donor相关符号需求留待正式archive/ABI审查。

本地检查：`python -B scripts/ci/check-ci-compat.py --base D:/Code/PortingiOSLegacy/common/sources/UniXNU --xnu D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full`；51项210 hunks精确顺序通过，自动变量清零和原IORPC头保留。`build-8796-source.py --base ... --check`的hash/配方bash语法检查通过。均为静态检查，没有本机make证据。

workspace-check.json记录三个只读来源树tracked状态空、board/feed哈希不变。预链接、driver archive、boot-progress/watchdog、QEMU与实机均未验证；没有设备动作、镜像构建或_verified=true。


## 第四轮反馈与模板全集

第四轮39723011018于installhdrs阶段失败：原始控制台226为适配器Unreviewed IIG kernel-only RPC template，主动拒绝IOInterruptDispatchSource未知模板，没有继续内核编译。证据见reports/kernel-ci/39723011018/diagnostics.txt与failure-analysis.json。14个.o为辅助/宿主统计，kernel_built=false。

短CI [39723294640](https://github.com/wh1stl3/UniXNU/actions/runs/39723294640)生成全部17个真实DriverKit实现（全部生成exit0），实际回调模板见callback-template.txt:809对应原始行：rpc.kernelContent = &msg->content.__hdr。它为新分离内容字段赋值；旧消息已在同一msg缓冲区内联。适配器仅新增对此精确赋值的识别和移除，不泛化删除其他语句。17文件432块全部静态适配通过，保留消息字段声明并无split-content引用；完整hash和适配器hash见iig-all-adapter-check.json。完整编译/ABI仍待下一轮。

build入口补充失败时上传未识别生成文件的机制：只进入云端reports/iig-failures及本机忽略out，不提交源码副本。Windows本机仍不执行内核make。

Git HTTPS多次连接443失败后，新增scripts/publish-main-via-api.py：经已授权gh逐项上传相同blob/tree/commit，三层对象ID全部必须与本地Git一致，确认远端未移动后force=false更新main；任何不一致都不改ref。Q-020已实际发布并保持原提交7dfa3c1，证据api-publish-previous.json。此路线不改写已推送历史。
