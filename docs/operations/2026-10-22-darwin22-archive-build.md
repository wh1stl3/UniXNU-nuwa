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
