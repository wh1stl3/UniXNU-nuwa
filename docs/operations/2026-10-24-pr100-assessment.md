# PR #100 对 nuwa / iOS 16 移植的评估

评估日期：2026-10-24（北京时间）。固定合并提交：[bd127c008cdc584b83cf00eaea269e4f1adf3cc8](https://github.com/UniXNU/UniXNU/pull/100)。当前已验证的基座仍为 e553e467，XNU 为8796.141.3／Darwin22；本轮没有合入PR、执行安装器或操作手机。

**结论：值得采用为独立WSL构建路线，暂不能替换现有macOS CI。** 它解决了之前WSL链路中多项真实缺口，可改善后续源码迭代速度；它本身不会修复nuwa的MMU切换、CPU/GIC/定时器或donor ABI问题。

## 已有价值和本轮证据

| 能力 | 本轮核验 | 对 nuwa 的意义 |
| --- | --- | --- |
| 给上游clang增加XNU类型内建函数 | 固定LLVM提交的7个既有文件与PR补丁严格上下文检查通过；补丁有实际类型分类实现 | 有望解除现有clang14缺少kalloc类型语义的工具链门；尚未编译新clang或证明语义等价 |
| Mach-O内核链接器、MIG、IIG、firehose与kernel支持库 | 完整审阅安装/构建入口及固定版本；未安装或构建整套工具 | 比仅套xcrun脚本完整，是真实可继续适配的实现 |
| Linux上的8796源码兼容修正 | makesyscalls/向量汇编条件/kextsymboltool三项在原版8796隔离副本上可应用、可重复执行 | 这三项可复用；未重放完整64项设备补丁序列 |
| xcrun/clang/install/plutil适配 | 最终32项隔离检查全部符合预期，包括正例和预期拒绝 | 证明局部脚本行为，不等于工具链或内核构建通过 |
| Ubuntu22.04工具来源 | 版本化LLVM24源404，脚本已实现的滚动源回退可用；amd64索引包含clang24/lld24/llvm24/libclang24-dev | 本机发行版有依赖供应路径；本轮未修改APT或安装软件 |

本机WSL为Ubuntu22.04.5 x86_64，16 CPU、约15GiB内存；新工具链、clang24和libclang开发头尚未安装。首次需要编译clang、链接器等；安装器默认按全部16 CPU并行，没有按本机内存配额限流，应在独立构建环境限制并行度。没有测得可靠的完整安装耗时，不给出虚构ETA。

## 迁移前必须解决的三项问题

**1. iOS16版本必须贯彻到全部辅助工具。** `linux_env()`默认SDK17.0和arm64-apple-ios17.0，firehose与`prepare-xnu.py libs`也显式指定iOS17；其Libc/profile支持源按XNU10063选取。[环境实现](https://github.com/UniXNU/UniXNU/blob/bd127c008cdc584b83cf00eaea269e4f1adf3cc8/scripts/unixnu/kernel.py)、[支持库实现](https://github.com/UniXNU/UniXNU/blob/bd127c008cdc584b83cf00eaea269e4f1adf3cc8/scripts/linux/prepare-xnu.py)。

实测：即使外层DARWIN_TRIPLE=arm64-apple-ios16.0，辅助命令中的显式`-target arm64-apple-ios17.0`仍会使编译器选择iOS17。只改一个环境变量不够，需为内核、firehose、cc_kext、IIG和版本依赖建立一致的Darwin22 profile。

**2. IIG是最明确的兼容阻塞。** PR选用[iig-port@ea6d147](https://github.com/Nyktis/iig-port/blob/ea6d147d668ca15d490da638012243fcd705f30d/iig.cpp)，版本标识DriverKit-440。该版本源码中的`deployment_target`只出现于声明、赋值及参数校验，没有用于选择RPC代码生成ABI；生成模板仍含`rpc.kernelContent`和split-content路径。PR给IIG的补丁只补Darwin解析目标和libclang资源目录，不修改RPC模板。

现有nuwa适配器只接受已核验Apple IIG 427.100.5的固定banner，并为Darwin22保留inline RPC与四字段IORPC，不能直接套到这个生成器。因此传`--deployment-target 22.0`不构成兼容证明。需要适配新生成器并对照当前已编译通过的8796输出，实际编译生成代码，核对结构偏移、消息长度、dispatch和descriptor。本轮没有编译运行新IIG。

**3. 构建成功与类型/运行时ABI验收需要分别完成。** 安装器对clang主要检查某个builtin是否存在，对不少已有输出仅检查文件存在；本轮检查环境中的clang14确实缺三个XNU builtin，也不接受PR需要的析构降低选项，不能直接复用系统clang。必须对构建后的patched clang执行本仓已有C/C++类型signature/summary/compatible语义样例；随后完成真实8796内核、ArmCpu/ArmDTPlatform archives、符号闭包、boot_args/IIG ABI与预链接验收。当前没有取得这套工具链的完整8796产物证据。

## 安装与隔离决定

[安装脚本](https://github.com/UniXNU/UniXNU/blob/bd127c008cdc584b83cf00eaea269e4f1adf3cc8/scripts/linux/setup-toolchain.py)即使传PREFIX，仍会写`/usr/bin`的xcrun/plutil/codesign、`/usr/lib`静态库、`/usr/local`的libdispatch和APT源；它不是只在指定目录内安装。建议在独立WSL发行版或容器中构建，并固定实际包版本、源码提交和工具文件哈希。

codesign是明确用于宿主SETUP流程的空操作，本轮验证了不存在文件也返回0；这不提供任何目标签名证明，不应将它当作设备认证能力。无需因此调整nuwa现有认证策略。

本轮首次install模式检查在D盘DrvFS得到0777而不是0644；相同真实GNU install在Linux原生临时文件系统得到0644，故该项是挂载权限语义差异。初始失败报告保留，最终样例分别记录复制行为和原生文件系统权限。建议构建目录与工具链置于WSL原生ext4；两份旧资料库仍保持只读。

## 推荐验收顺序

1. 在隔离环境建立固定版本的Linux工具链与Darwin22 profile，统一所有显式目标和支持源。
2. 通过类型builtin语义样例、MIG/IIG生成与真实8796头文件编译，解决RPC ABI。
3. 复现当前8796补丁和真实平台archives构建，核对版本、符号闭包及预链接结果。
4. 再编译正式入口修正与MMU后／arm_init日志，完成包验收及单独实机试验；通过后再考虑替代macOS CI。

当前建议保留已跑通的macOS CI推进内核修正，Linux迁移作为独立工具链工作，不把首次大规模编译放在实机问题的关键路径上。

机器证据：设备仓`reports/pr100-assessment/2026-10-24/`中的assessment.json、fixtures-final.json、context-check.json、host.json、sources.json和APT索引记录；复现脚本`scripts/audit-pr100-fixtures.py`。最终32项局部检查、两份补丁上下文检查通过；**未执行安装器、未构建patched LLVM／IIG／完整内核，也没有新实机通过声明。**
