# Darwin22编译记录与通用平台archive构建

## 本轮目标与范围

第十轮已完成8796.141.3源码编译/链接。下一步解决早前F-003的真实编译记录生产缺口，并在同一临时构建树中构建ArmCpu、ArmDTPlatform、ArmVirtPlatform的静态库，核对Darwin22头文件/命令、输出名、Mach-O格式与符号闭包。不接入board、不启用驱动、不重新链接携带这些archive的内核，也不生成诊断/固件镜像。

## 生产与消费契约

8796 makedefs/MakeInc.rule:403与427分别是C/C++实际编译规则。clang-compile-records.patch只在这两处添加-MJ $@.json，保留-c及对象输出、原编译器和链接动作。没有启用会替代编译的BUILD_JSON_COMPILATION_DATABASE。Clang原生fragment格式与directory/file/arguments含义见[官方说明](https://clang.llvm.org/docs/JSONCompilationDatabase.html)。

四项消费者输入：startup.o.json供boot-progress；kern_exec.o.json供watchdog policy；IOPlatformExpert.cpo.json供C++平台驱动；prng_random.o.json供pthread bootstrap。前三项分别对应sheng/scripts/build-boot-progress.py:11,43及build-arm-driver.py:26；最后一项对应基座scripts/build-libpthread-kernel.py:32。本轮只借IOPlatformExpert真实命令编译三项基座源，不调用Darwin23/iOS17的旧生产脚本。未复制上游源树，来源/文件hash见reports/driver-archives-plan/plan.json。

新audit-driver-archives.py只在macOS Actions的RUNNER_TEMP中运行；四项fragment均要求唯一、原输入及实际对象存在，原对象普通ARM64/iOS16。重用命令时替换且只替换唯一源文件和-o，移除-MJ/-MF/-MT/-MQ/-MD/-MMD/-MP，保留ABI和其余警告，追加严格警告检查，避免写坏内核对象及依赖记录。3项参数安全测试和59项228 hunks精确顺序检查通过，实际archive尚待CI。

输出为build/driver-archives/libArmCpu.a、libArmDTPlatform.a、libArmVirtPlatform.a，逐项记录源码/argv/日志、对象SHA、ar成员、定义/导入名称；将导入与本轮内核及三库定义集比较，任何缺失或与内核重复定义失败。Mach-O链接器生成的___dso_handle单独明列，不造provider。符号名闭包仍不证明C++布局/vtable、回调、硬件或donor ABI。若只构建出源内核但archive失败，build.json保留kernel_built=true，整体CI仍失败，两者区分。

workflow仅新增archive产物收集路径，保持固定基座、工具链和手动触发。源内核、驱动对象与archive留在忽略的out；只提交元数据和有界日志。feed、board、全部_verified与实机状态不变。

## 后续接口门

boot-progress的13项真实实现及uefi framebuffer依赖尚未移植，watchdog非union scratch覆盖风险仍未解决。本轮不启用这两项，也不搬入参考板地址。archive成功后再审阅它们；既定iPhone donor解析与正式-D入口另有剩余工作。

## 第十一轮启动

ccaad74d8862a060efbed259a1335f4a79258f04已发布，运行39742250205已启动；base fork workflow安装提交02daabcbcf1387fc67c15efeaef8085614dd97f2，安装前逐字比较旧模板、安装后逐字比较新模板，只增加一条archive产物路径。安装证据reports/driver-archives-plan/workflow-install.json；启动/相同Git对象发布证据reports/kernel-ci/39742250205/。最终记录和库结果待取证。

## 第十一轮实际结果与最小修复（2026-10-22 16:03）

整体CI failure，源内核kernel_built=true，原始内核20,136,488字节、SHA6e918dcb…已按固定解析器只读核验。933份C/C++逐对象记录实际生成，四项关键记录唯一且原对象存在/格式通过，已完整保存到reports/kernel-ci/39742250205/compile-records/；driver-archives/audit.json保存实际argv及对应原对象hash。F-003的记录生产缺口已取得真实证据，不再只靠静态设计。

首次平台编译ArmCpu失败于原始行852093：EXPORT_HDRS/libsa目录不存在，-Wmissing-include-dirs在追加-Werror后变为错误；尚未编出该driver对象，后两库未执行。不把这次整体失败写成内核构建回退，也不称archive已通过。

最小修复仅去掉这一个已不存在的搜索目录，且仅当其在真实构建目录仍不存在时去掉；若目录存在则保留。其他未知缺失-I一律保留，-Werror及ABI/源语义不变；将实际移除路径写入单组件报告。4项命令保护测试通过，新增负例确认未知缺失目录仍保留。未给警告全局降级、未制造空目录或头文件，候选待下一轮真实编译。

原始控制台81,771,040字节、852111行，SHA4d4e76be7fd806934cdab22f241b42df6bd32abef0a7a2afa6682352a728859e，留在out。日志摘录、构建及关键记录hash见reports/kernel-ci/39742250205/。提取器保留不超过2MB的结构化附加报告，大件仅存hash/原始out；完整二进制不入Git。

## 第十二轮启动（2026-10-22 16:05）

最小修复562c22fda45118f46b450390045a53b5a739f981已按相同Git对象发布，第十二轮39744948467已启动。仍为59项输入、严格archive检查，运行最终结果待取证；见reports/kernel-ci/39744948467/。未在本轮合入VFS或改board/feed，便于核对真实首错。
