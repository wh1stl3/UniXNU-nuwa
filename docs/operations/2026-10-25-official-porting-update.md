# 官网移植指南复核：Format 2、QR 日志与 DT panic 区

核查日期：2026-10-25（北京时间）。本轮仅查阅，未迁移board/SoC配置，未改固件、未启动新设备试验。搜索摘要可能是旧版；以直接打开的页面和固定源码为准。

固定来源：UniXNU `16e592abee8a550dec8154ed1f38b5ebc4f16213`；UniXNU-sm8550-common `23b2049fcd9e30356161def84231334fb55ecca9`。逐文件SHA、URL与本地检查边界见 `reports/upstream-porting-review/2026-10-25/review.json`。源码只读副本在out，不纳入本仓。

## 与当前卡点最直接相关：上游已有 DT panic 区补丁

[固定版本补丁](https://github.com/UniXNU/UniXNU/blob/16e592abee8a550dec8154ed1f38b5ebc4f16213/patches/xnu/native-dt-panic-region.patch) 的SHA256为 `b60c2a9a72ea23832f1e64348a5c5d1152cf05db6c156283dd8a93c804cd89cb`，已列入该版本ARM64 patch series。

它在 `XNU_DT_PANIC_REGION` 启用时选DT路径，绕开平台固定 `PLATFORM_PANIC_LOG_PADDR` 的选择，并检查reg属性长度、非零地址、区域边界/加法溢出、panic长度及映射返回值。它不跳过整个PE_create_console，也不关闭当前panic机制。与本轮模型在BCM旧panic区0x3c0fc000的读失败有直接关联。

下一主线优先对照8796源码移植此补丁和配置开关，验证无pram节点时只跳过旧日志恢复、console仍正常初始化；不可直接拿iPadOS17构建套iOS16。补丁未应用到nuwa，8796编译与实机修复均未验证。

## QR 日志：有实现，覆盖固件阶段

[官网日志流程](https://unixnu.com/porting/log-capture) 与[固定版本驱动INF](https://github.com/UniXNU/UniXNU/blob/16e592abee8a550dec8154ed1f38b5ebc4f16213/package/UniXNUPkg/Driver/AdvancedLogDxe/AdvancedLogDxe.inf) 已复核。

路径为 **Tools → Advanced Logger**：打开插件时读取Advanced Logger内存缓冲的快照，通过OneSend循环QR帧传出文本`.log`。菜单按键可调整轮换速度，Enter/Escape退出；电源键只有映射为Enter时可用。

接入项：

- firmware DSC/FDF加入 `AdvancedLogDxe.inf`；必须有平台Advanced Logger producer及debug输出路由。
- 固定版本INF依赖AdvLoggerPkg、MsGraphicsPkg、AdvancedLoggerAccessLib、QrEncoderLib等，Depex要求gAdvancedLoggerProtocolGuid。
- 配置设备模型PCD以生成日志名；payload启用tools或手写action="tools"入口；重新构建firmware/payload/bootimg。
- nuwa当前本地固件HEAD `a155c495c863e06d400b515315e3b8f7791dc308`。在nuwa DSC/FDF中未找到AdvancedLogDxe引用，在当前rg文件清单中未找到所需AdvancedLogger/QrEncoder INF；可能存在未初始化依赖，不能据此称依赖已就绪。固件接入和实机QR导出均未验。

**适用边界：UEFI菜单/加载器报错、ExitBootServices之前。** 不把UEFI缓冲导出视为pmap之后的XNU日志通道。当前继续使用本地画面/探针；持久内核日志另需nuwa的存储区域、writer/reader与恢复链。不得套sheng的日志分区或PMIC地址，不为接QR改已验收设备内存值。

隐私：原始音视频不上传；QR导出的文本日志也先本地检查敏感信息。文档中的OneSend接收流程不等于授权上传用户录像到第三方。

## 迁移体系：共享SoC与分层配置

[实时迁移指南](https://unixnu.com/porting/migration) 已说明Format 2、共享SoC仓、ARM64/SoC/OS/device分层、DTS转换和规范组件名。数组覆盖不会自动追加，迁移前须冻结完整输入与输出。

[SM8550共用仓](https://github.com/UniXNU/UniXNU-sm8550-common/tree/23b2049fcd9e30356161def84231334fb55ecca9) 含SoC资源、配置及patch series；其GPU/电源共享实现仍保留部分Sheng运行时符号，不可机械重命名。所查主仓树只有 `profiles/os/ipados-17.7.11-21H461/profile.toml` 这一OS配置。nuwa的iOS16/8796、iPhone10,3身份和ABI应保留并单独形成OS层；不能把迁移格式当作OS升级授权。

采用顺序：先提交当前可复现pmap里程碑与修正记录；再做独立迁移提交，逐项比较SoC资源、组件、补丁和ABI。当前不更改board内存/地址、固件pin、认证与_verified。

## 文档记录与同SoC页面

[porting.toml指南](https://unixnu.com/porting/records) 将实现、host验证和device验证分级，要求按子系统记录输入、发现、完成条件与下一步，站点由固定设备revision生成。nuwa当前还是旧格式仓，尚未接入该记录/CI；本轮继续落实README、STATUS、DECISIONS、WORKLOG与交接，不生成一份假称通过新schema的porting.toml。

[sheng页面](https://unixnu.com/devices/sheng) 已转为按领域渲染的记录，页面标签implemented应按其证据类型理解，不能一概当成所有硬件项目都已验收。板级内存、存储、触控、电源及OS ABI不得照搬。

[nuwa官网页面](https://unixnu.com/devices/nuwa) 仍列旧构建阶段，落后于本仓本轮pmap实测；页面也指向本仓STATUS为当前真相。本轮未推送、未改官网、未发PR。公开状态更新需在设备提交发布后单独提交上游文档/记录更新，不能声称本地commit自动更新官网。

## 决定

1. 主线优先：评估固定版本DT panic区补丁与8796配置，保留真实console。
2. QR作为固件独立诊断功能，先完成producer/库/DSC/FDF和源码pin清单；不替代内核日志。
3. Format2迁移另开后续里程碑，保持iOS16目标与nuwa板值；本轮仅查阅、记录和本地提交已验证结果。
