# 现有驱动复用与真实平台链接

2026-10-22。按用户补充，优先从UniXNU、同SoC机型及其他开源适配复用真实驱动；本仓维护适配与来源引用，不复制整棵上游树。D-014及AGENTS第7节记录此约定。

## 第十四轮实际结论

[39750542014](https://github.com/wh1stl3/UniXNU/actions/runs/39750542014)于17:10:51完成success，输入2b02285b806dfa2e6a9592d1347ea6542cb8aba1。真实源内核20,136,616字节，SHA256=298101014d8e1d3dc5b107e05e6731b9aa78be148537a61b80a9617cc0cbed80，与runner记录相同；8796.141.3、Darwin22.6、普通ARM64、0未解析符号及两标记1均静态检查通过。

| 实际archive | 字节 | SHA256 |
| --- | ---: | --- |
| libArmCpu.a | 242704 | 08f5c9893e944141a6f79408accf961211515e26bc1139c2a156702ea6928d85 |
| libArmDTPlatform.a | 186328 | 6fc05a09ef83813a05db7cc9bbca40de66247d306f4bf1456068ca9b412f7090 |
| libArmVirtPlatform.a | 186296 | 7771d1f5c70db36cae6276c9ecdc12b9623b4d53c05a3ca336f1efadee4071ed |

三者实际编译退出0，成员均为索引+对应普通ARM64/iOS16对象；现有内核同名冲突和全局缺失导入均为空。ArmDTPlatform noreturn声明已取得实际编译证据。此轮没有把archive链接回内核，不能称平台可运行。真实argv、源/声明hash及导入定义见reports/kernel-ci/39750542014/driver-archives/audit.json；原件在忽略的out/kernel-ci/39750542014/。

证据命令：gh run view、gh api actions/runs/.../artifacts、gh run download；脚本scripts/ci/summarize-build-evidence.py及inspect-source-kernel.py。下载取证未调用任何设备命令。

## 来源选择

| 功能 | 优先复用来源 | nuwa仍需处理 |
| --- | --- | --- |
| CPU/GIC/PSCI、平台专家 | 固定UniXNU 75bc13d的ArmCpu、ArmDTPlatform；ArmVirtPlatform仅虚拟平台备选 | 已以8796实际头和编译记录生成三库；下一门是真实链接，然后审阅平台/时钟/中断运行条件 |
| 启动管理器与DarwinBoot | UniXNU package/UniXNUPkg及drivers/DarwinBoot；uefi-sheng的DSC/FDF接线 | 三模块和库映射缺一不可；有源模板，不需新写加载器。nuwa固件包/厂商模块及运行证据仍待落地 |
| UFS与DMA/SMMU | UniXNU NativeUfs/GccUfs/SmmuTakeover及sheng生产脚本；Linux/Qualcomm仅作寄存器与时序依据 | 当前源既有真实根卷实现又保留早期probe，不能只读文件头注释断定能力。需8796存储头/ABI、原组件绑定、密钥/策略输入、nuwa DT/IRQ/SID证据；不能搬现成iOS17 archive |
| 显示/GOP | UniXNU NativeMobileDisplay/NativeGOPPresenter及uefi-sheng入口模式 | 复用传输/几何校验，nuwa framebuffer、面板、电源与缓存属性须独立证据 |
| Adreno740 | UniXNU NativeAdreno及sheng Gmu/GPU/SMMU实现 | 同SoC优先沿用实现；仍需nuwa电源/命令数据库/固件输入与iPhone GPU ABI，不等同源码可直接启动 |
| 触控 | 实测nuwa IC对应的开源协议实现，再接UniXNU HID层 | sheng TouchBoard.h明确是Novatek/板级SPI与GPIO值，不能套给当前仅有候选的nuwa控制器；IC/总线/IRQ未知保持TODO |
| 启动屏幕/异常观测 | sheng BootProgress.c、BootFaultProbe.c及四个公共头 | MIT文件可作为引用来源；Font.h、UFS/Virtio强导入、8796异常/生命周期接口需真编译和闭包，不写空回调 |
| watchdog策略 | sheng BootWatchdogPolicy.c仅为临时launchd策略 | 不是硬件watchdog后端；既有scratch覆盖案例仍需独立分配/布局修正后再启用，不把禁用服务当驱动 |

固定本地源文件hash、SPDX和tracked状态见reports/driver-reuse/local-source-manifest.json。Arm通用驱动文件及LICENSE为BSD-2-Clause-Patent；BootProgress/BootFaultProbe/BootWatchdogPolicy文件明确MIT。其他模块逐文件审阅，NativeUfs文件SPDX与目录LICENSE名称存在差异，后续引入具体改动时记录适用通知，不以仓库API的NOASSERTION替代文件许可。当前只有只读引用。

## 同SoC仓实际核对

- [hanzi123-bilp/unixnu-fuxi](https://github.com/hanzi123-bilp/unixnu-fuxi)固定59a91fbb20c6fc45695d4918702e61d420d73e0f；主要是sheng派生package/脚本，drivers目录未发现独立C/C++源，不能把README残留sheng功能表当fuxi实机结果。
- [yyx2025/UniXNU-vermeer](https://github.com/yyx2025/UniXNU-vermeer)固定c381c8d165a141a1997a83aa60b435d70378bd5d；同样有sheng package，触控/预检gitlink仍指sheng组件，不证明nuwa触控适用。
- [mansar1337/UniXNU-vermeer](https://github.com/mansar1337/UniXNU-vermeer)固定d4dbb3683023a17bb468b9774f52c87f3060e739；有源码/平台构建入口，README明确UFS/GPU/触控及硬件handoff未完成。其源crypto/pthread与iOS17平台配方可作调度参考，不能冒充Darwin22库。

通过GitHub树API固定提交、完整树未截断、文档有界摘录及submodule清点存same-soc-remote-inventory.json。0个drivers目录源文件不代表整个仓无适配代码，package已单独纳入清单；没有clone来源仓到本设备仓。官网此次访问失败，未凭缓存宣称官网新状态。

## 下一门：两库真实重链接

scripts/ci/build-8796-source.py在原配方最后一次make处记录实际展开argv，并继续执行原make。独立archive审查通过后，platform-link-audit.py再使用同一argv，只追加两项：LD_KERNEL_ARCHIVES里的原firehose+ArmCpu/ArmDTPlatform force_load，以及XNU_EXTERNAL_KERNEL_ARCHIVES的真实依赖。

该阶段先核对三库报告对应当前原内核，并重新检查所选两库独立闭包，避免借ArmVirtPlatform满足导入；实际文件hash不能变化。真实make退出必须0，最终MH_EXECUTE必须包含五项driver导出、没有undefined且hash发生变化。只使用原已移植的external archive依赖规则触发重链接，不删原对象凑结果。记录完整链接日志和元数据；大日志/二进制不入Git。

此阶段是**源链接验证**：保持原CFLAGS、原crypto/pthread范围、原start.o的ARCH_TIMER=0及全部运行开关，不启用正式nuwa硬件配置，不绕开原boot profile的crypto依赖检查。源provider的运行初始化、时钟、pmap及完整C++ ABI仍待后续真实运行，不把“只追加静态库能链接”写成“已能启动”。缺少运行provider不通过关检查/填stub解决。ArmVirtPlatform不与实机平台一起强制链接。

7项主机命令保护测试通过：保留所有原参数与空/含空格参数、保护旧对象和依赖输出、拒绝已有archive/provider覆盖及非本轮输出树。完整60项源输入、适配shell语法检查通过；真实重链接结果须下一轮CI取证。本轮feed、board和全部_verified保持原值，无预链接/固件/诊断镜像生成或实机动作。
