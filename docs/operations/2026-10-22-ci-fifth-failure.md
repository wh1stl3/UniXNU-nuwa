# 第五轮CI取证与禁用KPERF后的AST修复

## 实际运行与下载

第五轮39723736387，device_ref=4313f2d1c1a5abd9f96d11073b2e343b8aedadfe，实际于2026-10-22 12:48结束并失败；此前STATUS记录的是12:42运行中快照，不代表随后一直在编译。

命令：`gh run view 39723736387 --repo wh1stl3/UniXNU --json status,conclusion,jobs,headSha,url,createdAt,updatedAt`；`gh run download 39723736387 --repo wh1stl3/UniXNU --dir out/kernel-ci/39723736387`；`python -B scripts/ci/summarize-build-evidence.py 39723736387`。

结果与artifact元数据见reports/kernel-ci/39723736387/run.json、artifacts.json。原始控制台59,106,160字节、614415行，SHA-256为6ed4a293a36bfc50bf13cd2636aad649a22585057c416e00e2e627350a443106；保留忽略out，不提交大日志、生成源码或产物。带原始行号摘录见diagnostics.txt，完整统计见failure-analysis.json。

## 第一处实际错误

原始行253481/253484：osfmk/kperf/kperf_kpc.h:43,45的KPC_MAX_COUNTERS未定义；make在ast.o失败。ast.c:74无条件包含该头；ast.c:257-260无条件调用kperf_kpc_thread_ast。KPC/KPERF已由D-010关闭，头文件内仅KPC为真时包含定义所需头，却无条件声明kpcdata数组。不能填造计数上限或恢复缺失arm64/kpc.c的路径。

最小修复disabled-kperf-ast.patch仅在ast.c的该include及对应AST_KPERF处理块外加#if KPERF。启用性能采样时保留原行为，禁用时不引用其类型和实现。其他调用者位于可选kperf或kpc编译单元；本次不扩展到其他无失败证据的接口，不改header布局或添加stub。

## 本轮已验证的进展

build.json记录51个真实生成实现、51份适配记录，总共1296次模板转换（17定义在三个构建输出位置），kernelContent残留文件为0，IORPC原头哈希相同。日志未再观察到缺失arm64/kpc.c或上一轮UIO数组错误。581个.o为全部build子目录合计，不是581个XNU目标对象成功，更不是完整内核通过；kernel_built=false，尚无成功链接产物。

## 修复验证和边界

- `git -C D:/Code/PortingiOS/common/sources/xnu-ios16-full apply --check D:/Code/UniXNU-nuwa/patches/xnu-8796-ci-candidates/disabled-kperf-ast.patch`返回0，只检查不写来源。
- `python -B scripts/ci/check-ci-compat.py --base D:/Code/PortingiOS/common/sources/UniXNU --xnu D:/Code/PortingiOS/common/sources/xnu-ios16-full`：52项212 hunks精确顺序静态检查通过，清零和原IORPC头保留。
- `build-8796-source.py --base ... --check`输入hash和bash配方语法检查通过，没有本机make。
- workspace-check.json：三来源树tracked状态空，board与基座feed的既有hash不变。

修复待第六轮真实编译；不把生成/静态检查称ABI、QEMU或实机通过。没有改feed、board、donor、内存或地址，无镜像/设备操作和_verified=true。

## 第六轮启动

修复db30d6d13d5f5fabc3a110d535b1ce3b658c28d5已发布；第六轮39733594660使用该精确设备输入，基座仍固定75bc。14:25快照中主机/依赖/输入检查成功、真实编译进行中，最终结果未验证；元数据与发布证明见reports/kernel-ci/39733594660/。


## 第六轮实际结果与定时器表修复

第六轮39733594660最终失败，编译步骤于14:31:06结束。已执行gh run view与gh run download，并使用同一摘录脚本取证；run.json/artifacts.json/diagnostics.txt/failure-analysis.json均位于reports/kernel-ci/39733594660/。原始控制台66,009,696字节、686506行，SHA-256为1c6b3e0c1619cddd837bc348c91f371e5877e737e32829e7f256db9e434588c4，留在忽略out。

原始行352764、352771、352784：processor.c:151的kperf_timer_expire、RUNNING_TIMER_KPERF未定义，继而表长度断言失败；processor.o未构建成功。未观察到上一轮AST的KPC_MAX_COUNTERS错误；无ast.o产物清单，暂不单独宣布该对象通过。683个.o仍为所有build目录合计。

同一符号引用审查：timer_call.h:211-217已对RUNNING_TIMER_KPERF枚举使用KPERF条件，kperf.h中的回调声明属于受限KPERF接口；其余调用位于可选kperf/kptimer.c。processor.c:149-154的表项漏条件。disabled-kperf-timer.patch只给该表项加同样#if KPERF，保留RUNNING_TIMER_QUANTUM和原static_assert，不填假函数或放松断言。

单项git apply --check通过；完整53项213 hunks精确顺序及适配配方bash语法检查通过。修复待第七轮实际编译。为区分辅助对象与目标对象，下一轮build.json将额外记录XNU目标目录对象数、ast.o/processor.o的实际路径/字节数/哈希，原全build计数继续保留。

## 第七轮启动

484b97c57fc2be0a6b5b0455bcca44b5246e0278已发布，第七轮39734939751已启动；实际结果未验证，构建入口将记录目标对象数量和ast.o/processor.o证据，保留所有原始失败退出码。


## 第七轮实际结果与关闭性能模块后的剩余入口

第七轮39734939751失败，首错原始行404291：task.c:1513无条件初始化new_task->t_kpc，但task.h:384-387仅KPC为真时定义该字段。task.c:3047处销毁路径已保护；其余真实字段使用在可选kpc_common.c。disabled-kpc-task.patch仅给初始化加#if KPC，不新建字段或改变原结构定义。

本轮build.json首次给出精确目标证据：ast.o为73896字节、SHA-256 21a6c61593bdff78f0d3b5466b72ac7e0f8b07c7c8709df8b824dfbeea721874；processor.o为143264字节、SHA-256 5226e6a12dfdaa02c1a515f1a5d3e6735937270fe52e8c5de7188f6b699b4d42。路径均在目标osfmk/DEVELOPMENT目录。目标目录674个.o、全部build目录703个.o；这里不包含.cpo，不把数量当作完整内核或链接成功。kernel_built=false，IIG残留仍为0、原IORPC头未变。

原始控制台68,699,001字节、714074行，SHA-256 9bde5e32572a915ee1b7859a377c19bba99b554dd81e2855d4c79749bed70c06，保留out。元数据、摘录和对象报告位于reports/kernel-ci/39734939751/。

同时完成相关调用的源码检查（related-kperf-calls.json为受限文本扫描，不是完整预处理/ABI证明）：

- sched_prim.c:3754在was_idle分支无条件调用kperf_running_setup；该inline会引用可选kperf_is_sampling/kptimer_running_setup。disabled-kperf-scheduler.patch只保护这一性能分支及对应头，保留quantum定时器setup和activate；kern/kpc.h只在KPC启用时包含。
- 标准BSD单元kern_ktrace.c:211/369/394/506的reset/disable调用没有性能模块保护。disabled-kperf-ktrace.patch保护这些调用及头，KDEBUG重置/禁用、所有权状态流程保持。KTRACE_KPERF直接配置调用者只找到可选osfmk/kperf/kperf.c及kperfbsd.c；不新增虚假provider或成功stub，不把缺失性能服务伪装为可用。

上述scheduler/ktrace问题是源级发现，并非第七轮实际链接错误；第七轮还未成功链接，不混写证据等级。三项候选合并后56项222 hunks、配方hash/bash语法静态检查通过，下一轮进行实际编译验证。日志提取器增加真实ld/undefined-symbol/clang命令行错误及精确目标字段，为链接阶段取证做准备。

## 第八轮启动

8dd1b52e6d10a633f9248e4d54a3ce1f09cb1eff已发布，第八轮39736351595使用56项候选及既定IIG适配，最终结果未验证。运行元数据及相同Git对象发布证明见reports/kernel-ci/39736351595/。


## ARM64上下文KPC审查与第八轮取消请求（2026-10-22 14:54）

第八轮运行中继续审查，确认arm64/pcb.c:183,519无条件调用kpc_off_cpu；kern/kpc.h:163-166的inline引用kpc_off_cpu_active和kpc_off_cpu_internal，两者在仅optional kpc选择的kpc_thread.c:52,191定义。该配置已关闭KPC，属于与既有错误同类的明确源码缺口。disabled-kpc-context.patch仅保护该include与两次回调，不改pmap/扩展上下文切换代码。

为批量覆盖而避免再花一整轮等待已知缺口，已执行gh run cancel 39736351595，请求返回0。run.json保留服务端当前状态；取消作业不作为失败、成功或修复通过的证据。下一轮包含该额外候选。x86/i386和optional monotonic实现未纳入修改，ktrace中的纯extern声明也不当作链接引用。

下一候选57项225 hunks精确静态检查、输入hash和配方bash语法检查通过；见该运行目录next-compatibility-check.json及next-source-input-check.json，引用审查见kpc-context-review.json。没有源树/board/feed写入、镜像或设备动作。

## 第八轮取消确认与第九轮启动（2026-10-22 14:56）

服务端已确认第八轮cancelled；原始状态和请求记录已更新。4dd55f0ec8c72e08946c6f597bb3ca3389b65dbd已发布，第九轮39736926012采用57项完整候选。结果未验证，继续观察编译/链接；启动及发布证明见reports/kernel-ci/39736926012/。


## 第九轮进入链接与display probe条件修复（2026-10-22 15:09）

第九轮39736926012首次到达最终LD mach.development.bcm2837.unstripped。原始行851223-851227只有一个未解析符号_native_legacy_display_probe，引用来自_bsd_init/bsd_init.o。kernel_built=false，尚无完整make/链接成功。本轮目标841个.o、全build目录870个.o，C++的.cpo不在此计数内；ast.o/processor.o保持实际哈希证据，IIG残留0、IORPC原头未变。

原始控制台81,743,282字节、851242行，SHA-256 5181e69961465dd140f51405f4606f1531349e19008da5825346358bf2634ab6，留在out。run.json、原始行号摘录、统计与build.json见reports/kernel-ci/39736926012/。

基座baseline:319给bsd_init.o传XNU_NATIVE_LEGACY_DISPLAY（默认0），:600-614仅开启该选项时加入真实Legacy archive。offline-component-load-probes.patch:75-80却在运行时boot-arg分支中无条件引用provider；即使boot-arg不设置，也必须链接该符号。IOUserClient中的同类调用已经有该构建条件。

zzzz-display-probe-feature.patch仅给bsd_init.c的该运行时分支增加同样的XNU_NATIVE_LEGACY_DISPLAY构建条件。默认源CI不链接此archive，所以不引用其功能；开启并提供archive时保留原行为。不启用未知设备库、不新增stub/弱化导入或忽略链接错误。58项226 hunks及输入hash/bash配方静态检查通过，待第十轮。

另外，入口在finally记录原始kernel文件是否存在及大小/hash，便于区分链接产物已产生但后续make检查失败的情况；kernel_built仍要求完整命令成功和普通ARM64 MH_EXECUTE检查通过，不因存在文件就置成功。

## 第十轮启动（2026-10-22 15:11）

526651af94610f40c3223eae9550deaa3c44ae57已发布，第十轮39738601892采用58项完整输入验证可选display引用条件修复；结果未验证。HackiOS参考核验单独提交7bc0b1a，未改变本轮工具链、供体或RPC实现。
