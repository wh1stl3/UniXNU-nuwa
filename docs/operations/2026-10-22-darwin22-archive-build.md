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

## 第十二轮真实结果与C++诊断/声明收口（2026-10-22 16:21）

整体failure，源内核仍kernel_built=true，933份记录和四项原对象均有效；原内核SHA73cc11b99f1541ac36a51a70cd5f88265ff76559c0399a7090026b2cc0790eee已检查。libsa不存在路径已实际移除，没有再次触发该错误。

ArmCpu实际26条错误均是诊断升级，分类见failure-categories.json：11条missing-designated-field-initializers、9条suggest-override、1条suggest-destructor-override、5条missing-prototypes。首次原始行852100为vm_kern.h遗漏kmg_type_hash的指定初始化；其余包括旧OSMetaClass声明、IOLib/kalloc宏以及ArmCpu五个真实C导出。本轮没有报告缺类型/字段定义或调用类型不兼容，但不由此推断完整ABI通过。

下一候选仅对前三类添加-Wno-error=<精确名称>，仍显示警告，不改任何头文件/结构/初始化表达式，不关闭其余-Werror或函数原型检查。过去的“所有警告均为error”范围在此明确收窄为三项有证据的风格兼容例外；未知/类型/头文件缺失错误仍拒绝。原始编译器行为及数据初始化语义不因诊断严重度改变。

五项missing-prototypes通过include/nuwa/ArmCpuExports.h补前置声明解决：gic_diag、sgi_selfprobe、ipi_selftest、spi_attach、spi_count。只在ArmCpu编译强制包含该声明头，记录hash；声明与固定上游实际定义逐项去空白一致，见prototype-check.json，没有新增实现、stub或修改硬件行为。4项命令保护测试通过，真实编译待下一轮。

下一轮也含Q-040已审查的VFS真实函数，共60项231 hunks；第十二轮为59项，不能把静态候选当作本轮已编译。原始控制台81,798,190字节、852406行，SHAfe08444e15402d0c6829b58a14efdb424112d93189d1acb6b81eab2a0853f753，原件留out；有界证据见reports/kernel-ci/39744948467/。
