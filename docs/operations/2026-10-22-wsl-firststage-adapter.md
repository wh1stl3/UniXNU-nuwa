# R-003 A：WSL预检与8796适配入口第一阶段

## 本轮交付

用户批准R-003 A，并确认**没有额外Linux clang、IIG或完整sysroot**。本轮已落地可运行的输入检查与非执行式适配计划；工具链输入仍不齐，**没有取得内核编译/链接证据**。R-003已标approved A，不重新征询同一路线。

新增：

- `config/toolchains/wsl-8796.example.json`：本机主机工具清单，非board/feed配置。已知工具SHA-256固定，未知项null/TODO。
- `scripts/wsl_kernel_adapter.py`：只支持preflight/plan，不运行make、Git、源树装配或镜像生成。
- `scripts/run-wsl-firststage.sh`：在已批准的WSL范围内执行预检与自身测试，输出写本仓。
- `tests/test_wsl_kernel_adapter.py`：防止空输出、错误类型summary、缺失global、空sysroot清单、路径逃逸、哈希变化与shell伪装编译器被误判通过。

## 实际命令与结果

经宿主批准运行：

```powershell
wsl.exe -d Ubuntu-22.04 --exec /bin/sh /mnt/d/Code/UniXNU-nuwa/scripts/run-wsl-firststage.sh
```

WSL内实际命令：

```sh
/mnt/d/Code/PortingiOS/.venv-wsl/bin/python -B -m unittest discover -s tests -p test_wsl_kernel_adapter.py -v
/mnt/d/Code/PortingiOS/.venv-wsl/bin/python -B scripts/wsl_kernel_adapter.py plan
```

测试退出0，9项通过；预检退出2，state=inputs-incomplete。外层脚本完成不等于工具链门通过，它接受“预检成功识别缺输入”并单独记录exit2，未把它改成通过。

证据：[tests.log](../../reports/wsl-firststage/tests.log)、[run.log](../../reports/wsl-firststage/run.log)、[preflight.json](../../reports/wsl-firststage/preflight.json)、[adapter-plan.json](../../reports/wsl-firststage/adapter-plan.json)。精确工具命令、特征输出、哈希和时间在JSON中。

## 已得到的有限正向证据

| 项目 | 本轮结果 | 限制 |
| --- | --- | --- |
| 本机clang/clang++及host槽位 | 4个槽位文件哈希匹配，均指向同一clang14 ELF实现 | 不是4个不同编译器，仍缺XNU扩展 |
| 已有mig/migcom、ld/ar/nm/libtool | 6项身份与旧记录哈希一致；mig是前端脚本，migcom和cctools为ELF | 本轮重新读取校验，不继承旧SWEET/P16内核结论；cctools本轮只验证身份，未做内核链接 |
| MIG后端 | migcom对独立ping例程实际生成header/user/server C文件，退出0；文件非空、header含ping，三个产物SHA-256入JSON | 仅代码生成，不是MIG前端+SDK编译、IIG或目标执行通过；产物仅out/，未入提交队列 |
| 宿主C/C++ | clang对stdio/stdlib/stdint、clang++对new/type_traits的fsyntax-only样例均退出0 | 没有链接XNU SETUP工具，不证明完整宿主构建链 |

MIG输入为本仓自己编写的最小`.defs`文本，不包含上游源文件复制。输出是C/头文件，没有Mach-O、ELF可执行文件、诊断或固件镜像。

## 编译器门及未落实输入

目标C和C++均独立探测以下4项，当前全为false：

1. `__builtin_xnu_type_signature`
2. `__builtin_xnu_type_summary`
3. `__builtin_xnu_types_compatible`
4. `xnu_usage_semantics` attribute

前三项要求来自8796 `osfmk/kern/kalloc.h:684-828`；attribute语义来自该树 `bsd/sys/cdefs.h` 的pointer/data标注。[Apple安全研究说明](https://security.apple.com/blog/towards-the-next-generation-of-xnu-memory-safety/)解释了这类编译器支持为何参与类型布局及allocator区分；不能通过忽略attribute或把summary固定为常量替代。

未来有合格候选时，入口会继续在C/C++下编译只输出到stdout的LLVM IR，检查pointer/data/mixed/union/annotated/array签名、低16位summary和4项类型兼容结果。当前缺特征，**没有执行或声称通过这些语义样例**。测试里的静态IR只用来验证解析器拒绝假成功，不是候选编译器证据；即使未来样例匹配，也不认证完整C++/PAC/allocator语义。

本轮预检阻塞清单：

- Linux IIG路径与哈希TODO。
- C/C++目标编译器缺上述扩展，需要真实支持的Linux工具或经验证的实现方案。
- 目标sysroot、完整宿主输入清单、8796导出内核头的路径/完整性清单TODO；宿主已有系统头能通过简单语法检查，不把“未登记清单”说成物理缺失。
- SDK版本及来源TODO，不能编造版本来跳过MakeInc.cmd的解析契约。
- 完整可写补丁视图、剩余Darwin宿主工具适配、archive生产和实际编译记录门仍未满足；入口始终may_execute_kernel_build=false。

公开资料检索未在本轮定位到**经验证可用**的Linux XNU扩展编译器/IIG供应输入。不能由此推断它们不存在，也不能把普通LLVM升级当作已解决。用户已确认没有现成输入，不再要求用户重复提供不存在的路径。下一项是追踪可获取的实现/供应来源及明确安装/构建范围；本轮未下载或安装工具，未复制工具链源码。

## 8796适配计划的具体内容

计划JSON已固定以下**非执行式**映射与工作项：

- 8796真实原始产物`.unstripped`，所有HMAC封装、符号读取、失效清理、预链接消费者需统一；当前没有直接修改只读脚本或启用替代脚本。
- 源树 `config/MasterVersion:1` 是22.6.0；版本参考8796.141.3，目标arm64/iOS16；这些为主机构建计划信息，不写入feed或board。
- 用显式CC/CXX、MIG/MIGCOM/MIGCC、IIG和已解析sysroot变量描述工具；未知值保持null。没有伪造xcrun/xcodebuild。
- 8796 `makedefs/MakeInc.def:619` 是 `LD = $(KC++) -nostdlib`。计划保留C++驱动契约，把现有cctools ld标为待验证backend；不把带-Wl选项的驱动参数直接交给ld。
- 逐对象编译记录必须来自真正成功执行的C/C++命令，不能使用database-only模式替代编译；需实现archive调度，不能假设本地基座会读取未消费的archives字段。
- nuwa特定watchdog/PMGR/PGZ功能在独立接口门满足前不启用；board保持example，不绕过保护。

## 剩余工作的顺序与边界

先落实编译器真实实现/输入与IIG来源，再补目标sysroot和8796导出头的可复现输入方式；通过本入口的样例门后，才设计完整可写视图和实际Linux宿主构建适配。外部目录写入、安装及来源树覆盖视图超出R-003第一阶段批准范围，需提出具体范围后再执行；这不自动改变已选A路线。

本轮没有硬停四类动作，没有板值/identity/feed修改，没有Git写操作或外发任务；没有QEMU或实机结果。第一阶段的**预检与计划已落地**，第一阶段的**完整工具输入尚未落实**，不能把R-003 A标为整个工具链已完成。
