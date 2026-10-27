# Darwin22接口审查与本机WSL构建可行性

## 结论

**当前本机输入、现有基座入口和本轮约束下，直接完成8796内核构建不可行。** 没有取得本机完整内核编译/链接通过的证据，未尝试运行会clone/apply的基座构建脚本。不能把这写成“WSL永远不能构建XNU”：Linux交叉工具链移植是另一条尚未完成的工程路径，候选与代价见 `NEED-REVIEW.md` R-003。

静态审查已完成本轮要求的产物名、静态库/符号、boot-progress、watchdog及NativePrelink契约核对，发现下述确定差异与条件性风险。**Darwin22兼容性门尚未通过，feed不切换。** 未生成镜像、未编译内核、未访问设备；没有Git写操作。

## 基线、命令与证据

输入树只读：

| 树 | HEAD | 用途 |
| --- | --- | --- |
| `D:/Code/PortingiOSLegacy/common/sources/UniXNU` | `75bc13dd34dc4e403826793739e316a264ce00dd` | 本地基座实际构建入口 |
| `D:/Code/PortingiOSLegacy/common/sources/xnu-ios16-full` | `1b191cb58250d0705d8a51287127505aa4bc0789` | 8796.141.3接口定义 |
| `D:/Code/PortingiOSLegacy/common/sources/UniXNU-sheng` | `a599a1a8a92093b5077543e071b72130769eb325` | 查找缺失生产者与版本绑定，未复制代码/板值 |

复现静态审查：

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' -X utf8 -B scripts/audit-darwin22-interfaces.py
```

[interfaces.json](../../reports/darwin22-audit/interfaces.json) 保存输入哈希、文件行号与命中片段、13项回调声明/参考定义、脚本解析来源、主机布局模型和watchdog字符串算例。源树前后tracked status均返回0且为空。脚本Git命令白名单仅 `status/diff/log/show`；本轮没有重跑会调用rev-parse或apply --check的上一轮脚本。原48项文本结果只作为已有证据保留。

WSL枚举在沙箱内返回 `Wsl/EnumerateDistros/Service/E_ACCESSDENIED`；经宿主批准在沙箱外只读枚举成功，得到 `Ubuntu-22.04`。因此不是“本机没有WSL”。继续执行：

```powershell
wsl.exe -d Ubuntu-22.04 --exec /bin/sh /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/probe-wsl-toolchain.sh
```

经批准的脚本只查询主机、工具版本/路径、有限范围SDK目录和预处理器内建；仅将记录写本仓 [wsl-toolchain.log](../../reports/darwin22-audit/wsl-toolchain.log)。没有apt、clone、make构建、Mach-O/ELF产物或设备操作。

## F-001 · 8796产物名与脚本消费不一致（确定差异）

8796 `makedefs/MakeInc.kernel:50,90,147,369` 的原始链接产物是 `mach.development.bcm2837.unstripped`。当前基座仍在以下位置用 `.unstripped.noctf`：

- `scripts/build-xnu-4k-baseline.sh:74,738`：失效清理目标；`:757`：source-crypto HMAC封装输入。
- `scripts/build-corecrypto-14.py:82`：namespacing时的kernel符号输入。
- sheng `board.toml` 的prelink kernel路径（仅用于识别依赖，未复制到nuwa）。

第一批候选 `external-archive-dependencies.patch` 只把依赖规则挂到8796真实 `.unstripped` 目标，**没有修复这些消费者**。必须统一产物命名与清理/符号审计/封装/预链接路径，不能靠改feed或凭空改扩展名宣称链接格式相同。当前nuwa board未填写该路径。

## F-002 · 静态库仍绑定Darwin23与iOS17（确定差异，二进制ABI未验证）

| 组别 | 当前生产/消费契约 | 对8796的审查结论 |
| --- | --- | --- |
| corecrypto与libpthread | 基座 `build-corecrypto-14.py:17-18,74-85` 固定2023 provider/ios17；`build-libpthread-kernel.py:2,11,49,77-78,93-115` 固定Darwin23 revision、iOS17 build-version，并用checkpoint kernel做定义/导入集合检查。pthread bootstrap补丁还写519.120.4。 | 不可复用17.x archive或已存report作Darwin22 ABI证据。须用8796头文件/编译记录重建，重做collision隔离和undefined-symbol闭包。相同pthread注册函数名不证明callback表布局相容。 |
| ArmCpu/ArmDTPlatform/ArmVirtPlatform、UFS | 基座脚本`:555-576`仅检查并force-load archive；通用生产脚本位于sheng `scripts/build-arm-driver.py`，依赖实际IOPlatformExpert.cpo.json，`:104`校验iOS17 deployment。 | nuwa没有该生产流程；需8796配置与头文件重建。仅有personality patch或同SoC不足以证明C++类布局、vtable、DMA接口兼容。 |
| AES/Virtio/RAM block | `build-native-aes-bindings.py:49-52,106-120` 和 `build-native-virtio-bindings.py:61-84` 从既有candidate与审计记录生成original-bindings，目标ios17。基座`:663-671`还要求两个storage archive的bindings一致。 | donor改变后必须用iPhone donor重新解析符号及原组件绑定。未取得本轮8796对象，不能做实际nm/link检查；不得沿用sheng绝对地址或旧绑定报告。 |
| PMGR与显示/GPU附加库 | sheng `build-sheng-platform-power.py:30-47,72,101-127` 固定provider storage/slot表、iOS17检查和original绑定。其余显示/GPU生产脚本同样消费现成candidate。 | 只能作为接口来源审阅，不能当nuwa可用库。未抄原地址/slide/roots。缺失具体实现保持TODO。 |

所有外部库的主链接选择位于基座 `build-xnu-4k-baseline.sh:522-714`，外层有source-corecrypto条件；某些功能还要求AES/prelinked/owner-root等闭包。不能通过随意关闭真实provider、制造空stub或跳过undefined-symbol检查凑链接成功。

还发现一处本地入口与文档契约的缺口：官方摘录包含 `[kernel] archives`，但扫描本地 `scripts/unixnu/*.py` 未找到 `archives` 消费者，`kernel.py:38-59`只调用baseline脚本，后者只主动调用少数helper并消费大批预制archive。**在board里填archives并不能证明本地版本会执行它。** 扫描结果存JSON；需设备仓适配实际调度入口或先比较上游差异，本轮未改基座/board。

## F-003 · 编译记录生产者缺口（未验证）

基座 `kernel.py:51-57` 在boot-progress模式下先bootstrap一次，期待 `startup.o.json`。sheng `build-boot-progress.py:11,43`分别读取startup和kern_exec编译记录；Arm/PMGR脚本还读IOPlatformExpert.cpo.json。读取的是实际编译命令（file/arguments/directory）。

对当前8796 makedefs、基座baseline及49个补丁搜索 `-MJ`、`.o.json`、`.cpo.json`，未找到生成这些逐对象文件的配置；也没有本轮实际产物可核验。8796 `MakeInc.def:955-970` 的 `BUILD_JSON_COMPILATION_DATABASE=1` 会替代编译动作，且关闭后续对象依赖的链接/调试步骤，**不能用“拿到compilation database”代替实际编译成功**。未来需明确定义真正编译时的记录生成与bootstrap顺序，不能使用旧10063记录拼装8796命令。

## F-004 · boot-progress回调（仅声明/参考定义检查）

候选boot_progress.h声明的13项 `init/start/active/bind/putc/stage/irq/poll/user_breakpoint/user_abort/critical_exit/process_stage/exit`，在sheng `package/BootProgress.c` 或 `BootFaultProbe.c` 均找到同名定义，具体原型与行号存JSON。部分8796基础接口也存在，例如 `task.h:526,1016` 的shared-region slide/all-image-info、`arm/thread.h:169` 的find_user_regs。

但本仓没有对应C实现，基座也没有 `build-boot-progress.py`；它来自sheng，编译脚本将设备package映射成kits/sheng，还依赖uefi-sheng的framebuffer头路径。参考实现有UFS/Virtio统计等强导入和大量可选弱导入，`:965-980`启monitor线程。这不是一组可独立空链接的打印函数。

不启用 `XNU_BOOT_PROGRESS` 时头文件走no-op分支；启用时必须提供真实回调archive与依赖，并以8796实际编译命令核验类型/符号/锁与中断上下文。本次没有宣称函数名对应即ABI通过，也没有创建nuwa诊断镜像。

## F-005 · watchdog接口与条件性scratch覆盖风险

候选zzz补丁在Data mount后、launchd前调用 `sheng_boot_watchdog_policy(void *, uint64_t)`。定义在sheng `package/BootWatchdogPolicy.c:25`，C参数形状相符；它调用mkdir/open/write/fchown/fchmod/fsync/sys_fstat64/sys_close，8796 `bsd/kern/syscalls.master` 有相应输入定义。sysproto.h为生成头，不能把原树没有生成文件当成函数不存在，也不能在未生成/编译时认定目标ABI通过。

其行为是根据 `sheng-disable-watchdogd` / `sheng-disable-jobs` 写scratch Data的launchd `disabled.plist` 与migration marker，使用O_EXCL拒绝覆盖已有配置；不提供硬件watchdog后端。nuwa没有复制或启用该策略，未写任何设备内容。

静态审查发现一个需在移植前处理的条件性缺陷：

- policy缓冲区768字节，复制到 `scratch+0x200`（参考`:21,56`）。
- SystemOS补丁在非union模式把环境字符串放 `scratch+0x400`，vector在+0x500，fallback在+0x600（原补丁`:83-85,140-146`）。
- 纯主机字符串算例：12个有效标签，jobs=157字节，含watchdog禁用条目的policy=584字节，两者均在输入缓冲上限内；写入范围为 `[0x200,0x448)`，与环境字符串起点0x400重叠72字节。JSON保存完整算例。仅复现字符串/区间运算，没有执行内核copyout或真实Data写入。

这只在相关policy与非union环境路径同时启用时构成覆盖风险，不宣称当前未配置的nuwa已触发故障。不能直接搬入参考实现；需独立scratch分配/布局或严格不重叠边界，并验证launchd环境仍保留，后续设备内容变更另审阅。

## F-006 · NativePrelink的Darwin22契约

`native_prelink.py:14-20,122-141`要求普通ARM64 subtype0、MH_EXECUTE、4KiB对齐，按original符号名寻找唯一native目标；不能复用donor外的符号绑定。`emit_prelink.py:117-156`要求稀疏索引marker值1，选early-security-init时还要求security-init marker值1与选中安全扩展的只读可执行代码范围。两项8796补丁的文本适用性已在上一里程碑验证，但本次没有源内核Mach-O来检查marker是否真正导出。

`emit_prelink.py:226-238`按kmod记录大小196、address偏移156、start/stop偏移180/188读取。8796 `mach/kmod.h:51,68-70,87-100,121-136` 的64字节名字及pack(4)定义可建立相同静态布局模型（JSON记录address=156/start=180/stop=188/size=196）。**该局部布局契约静态一致**，不是完整预链接/IOKit ABI通过；需要最终目标编译和iPhone donor实际组件验证。原始root集合、slide、initializer地址及kernelcache哈希继续TODO。

## F-007 · 本机WSL工具链门（当前不可直接构建）

本轮实际清单：Ubuntu22.04.5/WSL2，默认clang14.0.0，make4.3；默认Python3.10.12，旧项目独立Python3.12.14仍存在，因此可选用后者满足驱动Python版本，不把Python视为不可解阻碍。

默认PATH未找到xcrun、xcodebuild、ditto、IIG、MIG、ctfconvert/ctfmerge等。已有ext4 prefix中确实保留Linux MIG/migcom和aarch64-apple-darwin cctools，**没有忽略这些可复用工具**；它们不在默认PATH，也不能替代完整Xcode/SDK和编译器语义。

仅预处理探测（stdin文本、无目标文件）用当前clang14的 `__has_builtin` 得到：

```text
xnu_type_signature=0
xnu_type_summary=0
xnu_types_compatible=0
```

8796 `osfmk/kern/kalloc.h:684,721,763,827-828,1484`直接依赖这些XNU编译器内建。现有默认编译器不满足这一输入契约；没有用零值宏或删除类型校验规避它。

有限范围SDK目录检索（/opt、/usr/local、旧仓common/tools和common/cache，maxdepth5）未发现*.sdk，常见SDK目录不存在。这个结果**不证明主机其他路径绝无SDK**，只能表述为没有已配置、已验证的完整目标/宿主SDK输入。旧资料报告只是帮助定位工具，本轮不采用旧SWEET/P16内核试编译结论作UniXNU证明，也不把CI生成头当本轮源构建输入。

当前基座 `kernel.py:43`明确要求xcodebuild；8796 `MakeInc.cmd:103-214`通过xcrun解析SDK、编译器、MIG/IIG与其他工具；基座脚本还使用ditto、plutil、macosx installhdrs与ios17部署参数。仅设置XNU_SDKROOT路径或安装常规LLVM不解决这些调用链。Apple官方[系统要求](https://developer.apple.com/xcode/system-requirements)将Xcode列为macOS工具；LLVM的[Mach-O linker说明](https://lld.llvm.org/MachO/index.html)提供ld64.lld交叉链接能力，但不等同提供XNU所需编译器内建、SDK头和IIG。

最后，本轮禁止任何Git写操作，而默认内核/libpthread入口含clone与apply；board还为example=true。不能直接运行该入口“试试”并绕过这些约束。结果是**当前路径不可行且未编译**，不是“内核编译失败后确认硬件不支持”。按用户本轮第2项，写R-003后停止，等待选择下一条工具链路径。
