# 最新上游日志能力审阅

2026-10-24，北京时间。用户要求核查UniXNU最新PR是否已合入二维码日志。

## 结论

当前上游main固定到 **bd127c008cdc584b83cf00eaea269e4f1adf3cc8**。GitHub最新PR/合并状态、组织/全站PR关键词检索与整棵main源码检索均未找到二维码日志实现或对应PR；这项否定仅限本次固定版本和记录的搜索范围，不宣称所有社区fork均无实现。全树qr-code/qrcode/二维码等关键词仅命中文档package-lock.json里的qrcode可选依赖，不能当成内核日志编码器。

[PR #88](https://github.com/UniXNU/UniXNU/pull/88) 实际是电脑端USB终端/CDC日志与GSC1屏幕捕获，2026-10-23 17:36:41（北京时间）合入，merge141d16a43bfe46859487f32c0519c428cc473a49。源文档明确要求giulia协议2和设备端实现；屏幕尺寸/格式、shell、输入和USB驱动均有依赖，单改USB身份或装电脑脚本不会使nuwa兼容。没有二维码功能，当前不能据此替代MMU后/C初始化前的独立日志通道。

[PR #100](https://github.com/UniXNU/UniXNU/pull/100) 是Linux内核构建支持，2026-10-24 19:48:53（北京时间）合入，正是当前main。它增加自建clang的XNU内建函数、Mach-O工具链、mig/iig和xcrun/plutil/codesign替身；环境目前声明arm64-apple-ios17.0及17.0 SDK/fakeroot。nuwa是Darwin22/XNU8796/iOS16路线，需要移植现有64项适配及版本/工具链约束后实际验证，不能把“Linux可构建”直接写成“nuwa8796已可本地构建”。setup还会以root写工具链与/usr/bin，当前没有运行安装脚本。

## 对主线的决定

不为不存在的二维码方案切换日志路线，不直接移植giulia设备地址或USB后端。保留已实机成功的入口探针证据，下一候选以正式源码入口修正和早期C/异常可观测性为目标；USB终端列为后续设备驱动接入项。Linux构建值得独立资格化，可减少每轮Mac CI等待，但需要先适配8796而非整体跟进最新版。

本轮只fetch上游refs并先diff；D:/Code/UniXNU-integration工作树HEAD仍e553e467，未merge、未改模块pin、未构建/安装/启动手机。最近实机事实仍入口探针01于20:53:19恢复Android1/A槽/三SHA不变。

机器证据reports/upstream-debug-review/2026-10-24/review.json包含实际查询、合并状态、全树关键词结果和固定源文件SHA/URL。网页搜索缓存曾把PR88显示为Open，以本次GitHub API的mergedAt/mergeCommit为准。
