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
