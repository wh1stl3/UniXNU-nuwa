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
