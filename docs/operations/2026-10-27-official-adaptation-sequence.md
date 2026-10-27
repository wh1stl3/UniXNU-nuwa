# UniXNU官网：移植顺序与nuwa当前任务对应

核对日期2026-10-27。直接查看官网当前页面；不是宣称这些章节刚刚发布。对照本仓STATUS、10月25日官网复核和本轮桌面输入记录。本次仅网页/文档核对，没有设备动作、代码迁移、上游版本跟进或重新构建PROBE41。

## 1. 官网有两条相互配合的顺序

[移植总流程](https://unixnu.com/porting/steps)：硬件证据→共享SoC/OS支持和组件→设备配置→解析实际依赖与补丁顺序→ADT/固件→驱动适配→构建/逐层启动→发布记录。模板默认SM8550+iPadOS17，不能作为nuwa iOS16配置直接使用。

[驱动适配顺序](https://unixnu.com/porting/drivers)：平台/内存与DMA→存储、root、持久Data→显示/刷新/亮度→触摸和按键→GPU/Metal→Wi-Fi→DSP/音频/电源。这里的存储包括RamBlock等实现，不表示当前RAMDisk读取成功即可称UFS通过。

[运行检查点](https://unixnu.com/porting/bring-up)：UEFI→UniXNU菜单→payload→DarwinBoot→内核入口/平台→存储/root/launchd→用户态及Data、可见输出。nuwa已到比入口更深的原生文件读取路径，但根到launchd/EL0尚未闭环，不能把当前诊断挂载升级为官网完整root/Data阶段通过；用户态也不等于SpringBoard桌面。

以上是依赖顺序；当前离线输入准备可以并行于等待实机读数。硬件验证仍按前置条件推进，遵守本仓脚本串行和设备暂停约定。

## 2. 比单纯增加组件更直接的工程检查

[驱动章节](https://unixnu.com/porting/drivers)要求追踪初始化调用者、provider匹配、清理归属、所选OS编译记录和私有ABI，最后检查archive对象/符号及prelink输入。对nuwa的新显示/HID实现，每项都要有来源pin、依赖、ABI证据、构建输出和实际初始化入口；仅列入TOML或编译出.a不算已接入。

[组件目录](https://unixnu.com/reference/components)单列硬件范围、OS ABI、板级依赖、构建阶段与已有设备结果；解析器按依赖顺序构建。数组覆盖会替换继承数组，不能只写一个新组件导致旧选择丢失。当前旧格式设备仓尚未完成Format2资格，不在本次查询中执行迁移或官方fetch/build示例。

[SoC支持](https://unixnu.com/porting/soc-support)区分共享控制器资源、板级连线/内存/电源和OS身份/ABI。继续参考SM8550实现，但保留nuwa硬件证据和iOS16/8796输入；Format2迁移必须另行冻结和核验完整输入，不与当前41候选混用。

## 3. 显示到桌面的推荐推进方式

[显示指南](https://unixnu.com/porting/display)先稳定固件scanout，再接入匹配OS的MobileFramebuffer/IOSurface后端；先验证CPU呈现、swap完成和surface生命周期，再启用GPU呈现。它给出NativeLegacyDisplay、NativeGOPPresenter和NativeGOPWire的代码入口，并要求分别记录请求刷新率与实际测量值。nuwa的HEX只支持诊断显示，不证明这些用户态接口可用。

[输入指南](https://unixnu.com/porting/input)按电源/总线/识别/协议帧/坐标/接触ID/释放事件再到HID报告推进。对不同传感器必须换协议实现；读取芯片ID不能代替触控手势验证。[GPU指南](https://unixnu.com/porting/gpu)前置条件是平台DMA和基本呈现，再到供电/固件、命令/围栏、已知图像和用户态前端；同A740仍须核对板级电源、固件及OS ABI。

## 4. root、Data与日志不能漏掉

[平台/OS服务](https://unixnu.com/porting/platform)把root策略、RamBlock持久化、加密服务、KeyStore状态接口和prelink均列为有独立输入/结果的集成项。对nuwa，先前完成的三份桌面组件摘要与文件清点不是可启动完整根；仍需OS/cryptex命名空间、缓存引用/依赖闭包、可写Data布局及服务内容核验。

[日志指南](https://unixnu.com/porting/log-capture)明确分层：菜单阶段Advanced Logger二维码；XNU入口用UART或画面；存储验收后才接持久writer/reader，先完成手动回收，再自动化。二维码导出不是退出BootServices后的内核日志。当前不占用未经审查的日志区域、不照搬sheng分区/复位地址，也不因“离线”暂停公开资料查询。

## 5. 当前nuwa的具体优先级

| 优先级 | 任务 | 本地证据/下一完成条件 |
| --- | --- | --- |
| 1 | 保留41诊断包，继续原生读取→exec→EL0闭环 | 40最后边界为资源块表调用；41已合格未启动，设备仍暂停 |
| 2 | 离线推进完整OS/SystemOS/AppOS命名空间、缓存依赖与Data设计 | 3组件、532配置、44缓存头已清点；引用闭包/组合尚待完成 |
| 3 | 固定iOS16 OS/ABI契约及显示初始化/构建依赖 | 追踪当前8796输入，不套iPadOS17原生类布局 |
| 4 | CPU帧呈现及swap生命周期，再接输入 | 静态契约/构建先做，硬件完成和实际HID事件留给恢复实测后验证 |
| 5 | GPU/Metal，再到网络、音频和性能 | 不抢在root/Data及基本显示前，也不将CPU呈现当GPU通过 |

官网顺序支持继续离线推进桌面前置项，不要求每个静态项目单独实测；也不能仅凭指南把239、身份/内存或verified审阅边界解除。既有PROBE41、原始证据和迁移修改保持。

## 后续执行约定已生效

用户2026-10-27明确要求以后按官网指南执行。规范已落实到设备仓AGENTS.md第0节，固件仓引用同一入口，决策D-071；后续任务必须按该节定位依赖、查阅对应官方章节、追踪实现/构建交接并分别核验完成条件。此处不变更既有实测结论或授权边界。

用户随后要求将每阶段具体方法和步骤落为规则，已建立[阶段开发执行规则](../DEVELOPMENT-STAGES.md)，由两仓AGENTS强制引用，决策D-072。本文保留官网与nuwa顺序对应；具体任务方法统一在该执行规则维护，避免多份清单漂移。
