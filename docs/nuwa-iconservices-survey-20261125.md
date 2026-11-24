# IconServices 检索摘录（2026-11-25）

只检索摘录；其他设备仅作参照。以下“同一处”要求公开记录明确指出 lsd 的 `ISIconManager _init` 同步等待；仅出现 IconServices 同步等待不等同完整堆栈。

## 命中表

| 编号与来源 | 位置及原文摘录 | 是否同一处阻塞 | 处理手段 | 结果 |
|---|---|---|---|---|
| S1 本地 nuwa `worktree-display-dsp`，未提交状态，`docs/nuwa-lsd-stack-20261124-symbols.md:67-68,90-101` | “`-[ISIconManager _init] + 0x1b8`”；“`+[ISIconManager sharedInstance]`” | 是本案，非他人记录 | 栈符号化 | 记录未确定对端。 |
| S2 [Gsjsjzhznsz/UniXNU-raphael @ 684cccb4 `porting.toml`](https://github.com/Gsjsjzhznsz/UniXNU-raphael/blob/684cccb40278bb5add0999e909af88e7f2eb407c/porting.toml)，[官方生成页 Storage](https://unixnu.com/devices/raphael-gsjsjzhznsz#storage-and-root) | “lsd progressed from IconServices sync wait to original signing scan; IconServices ISStoreMapTable faults in original throttle_lowpri_io.” | **部分吻合**：公开记录明确 lsd 的 IconServices 同步等待，但未给 ISIconManager 符号。 | 后续候选让 NativeRamBlock 发布 Solid State medium 属性；原 throttle 保留。 | 原文称该候选 “Build and handset qualification pending”；不能将已越过等待归因于候选。该次无桌面。 |
| S3 [UniXNU/UniXNU-sheng @ c8f92b20 `reports/ipados27-touch-frame-gaps.md`](https://github.com/UniXNU/UniXNU-sheng/blob/c8f92b208068eeaa4cd2b0f592671f04ee70076e/reports/ipados27-touch-frame-gaps.md)，[官方页](https://unixnu.com/zh/devices/sheng) | “A synchronous XPC wait involving iconservicesagent overlapped 4.444 seconds of a flip gap.” | 部分吻合；SpringBoard 采样，未注明 ISIconManager 或 lsd。 | 同报告另有 lite=2 禁用 agent | 非相同 run 的因果证明。 |
| S4 同 S3 | “lite=2 recorded no iconservicesagent PID or associated main-thread wait. Settings opened. All app icon artwork was missing” | 否；未标 lsd 栈。 | 禁用 agent | 设置可打开，Home/Dock 图标画面缺失。 |
| S5 [Dracen-W/UniXNU-merlinx @ fb616afa `data-seed.json`](https://github.com/Dracen-W/UniXNU-merlinx/blob/fb616afa1231b0ad2b6a6f4832a299b76b64031c/data-seed.json) | `systemgroup.com.apple.lsd.iconscache/Library/Caches`, 0:0、0755；`mobile/Library/Caches/com.apple.IconsCache`, 501:501、0755；`com.apple.iconservices.iconservicesagent: true` 出现在两份 disabled plist 规格中。 | 未说明相同阻塞 | 预置空目录；另在 seed 配置禁用 agent | [本地对比 `nuwa-seed-full-comparison-20261124.md:13,26`](nuwa-seed-full-comparison-20261124.md) 引官方记录：“lsd completes its first LaunchServices build and SpringBoard draws the Lock Screen and Dock”；未证明这些单项产生该结果；未列预置图标数据库。 |
| S6 [xVanTuring/UniXNU-qemu @ 97b75b1f `README.md`](https://github.com/xVanTuring/UniXNU-qemu/blob/97b75b1f63c6b7e895cd7646029db741d5fe5488/README.md#state)，iPadOS 17 | “without `--metal` Settings stays white: iconservicesagent crashes in CoreImage ... and IconServices retries. With it Settings opens ... most row icons lack their symbol” | 否；Settings 而非 lsd 初始化栈 | 为 agent 提供 Metal | Settings 打开；大多数行图标缺符号。QEMU，非实体机。 |
| S7 [actions/runner-images issue #14751](https://github.com/actions/runner-images/issues/14751)，macOS 26.6.1 / image 20260824.0517.1 | “main thread parked in `xpc_connection_send_message_with_reply_sync` under `-[ISConcreteIcon generateImageWithDescriptor:]` / `_ISRetryRequest`”；“unload the agent so requests fail fast and fall back to a generic icon” | 否；macOS 图标生成，非 lsd 初始化 | `launchctl bootout` + `launchctl disable` | 原报告 probe <0.5 秒；评论称另一 probe 0.1 秒、Qt app 正常，fallback 通用图标。未证明 iOS 同效。 |
| S8 [UniXNU 官方 sirius 设备文档，本地 `UniXNU/docs/zh/devices/sirius-huajifruit.md:388-389,764`](https://unixnu.com/zh/devices/sirius-huajifruit) | “With the CoreUI fixup ... crashes=0 at 335 s”；“so the symbol draws empty”；“iconservicesagent 154 s (it no longer crashes)” | 否；agent 的 GL 崩溃 | 修改 CoreUI 调用点 | 335 秒采样无该崩溃，符号绘空；非同一栈。 |
| S9 [Gsjsjzhznsz/UniXNU-raphael @ 684cccb4 `porting.toml`](https://github.com/Gsjsjzhznsz/UniXNU-raphael/blob/684cccb40278bb5add0999e909af88e7f2eb407c/porting.toml)，[官方页 Display](https://unixnu.com/devices/raphael-gsjsjzhznsz#display) | “SpringBoard ... at 1005 seconds ... welcome ... no icon desktop” | 未标同一栈，也未将其归于 S2 的那次运行 | 长时间观察 | 约 1005 秒欢迎文字，无图标桌面；不是等待后同一阻塞恢复的证据。 |

## 有／无

公开来源**有 lsd 的 IconServices 同步等待记录**（S2），但**未找到明确到 `+[ISIconManager sharedInstance] → -[ISIconManager _init]` 的同一处完整堆栈**。S2 称后续进到 signing scan，但没有给出越过所用的处理或耗时。S3 是另一个涉及 agent 的同步等待，S7 是 macOS 不同调用栈。

## 有出处的手段（非对本机的效果声明）

1. S5：Data seed 预置空缓存目录；修改 Data 文件系统，数据库未预置，单项效果和代价未报告。
2. S4、S5：禁用 agent / 写 disabled 配置；修改 launchd 持久配置。S4 图标缺失；S5 单项效果未分离。
3. S7：macOS launchctl bootout + disable；改变 launchd 服务及禁用状态，原文未指明落盘文件；通用图标代替，iOS 效果未报告。
4. S6：为 QEMU agent 提供 Metal；需改变运行环境及载荷/插件，行图标仍缺符号。
5. S8：CoreUI fixup；修改载荷中的系统代码映射，符号为空，非相同阻塞。
6. S2：NativeRamBlock 声明固态介质属性的后续候选；修改驱动/内核构建，候选未编译和上机验证，运行效果及代价未报告。

## 未找到与检索边界

- 未找到完整 `ISIconManager _init` 栈的公开同例；未找到通过 XPC 超时／中断修复该栈、手工 bootstrap agent 后修复该栈、替换图标来源修复该栈、或等待后该栈自然恢复及其耗时。
- 已检索 `ISIconManager`、`IconServices`、`iconservicesagent`、`iconservices`、`IconCache`、`iconscache`、`systemgroup.com.apple.lsd`，以及 `lsd` / `sync wait` / `iOS port` / `SpringBoard` / `launchctl bootstrap` 的组合；GitHub UniXNU issues、discussions 搜索结果及官方设备文档，社区 merlinx、fajita、raphael、dby-w09、thyme、Odin3、sheng 的索引及本地既有对比记录。未找到不代表不存在。
- 本地 `D:/Code/PortingiOS` 内容搜索命中上限 100 条且截断；工具默认忽略规则和二进制文件，未穷尽隐藏目录、out、`.cache` 及全部日志。`rg` 不在 PATH，故全树含隐藏和忽略项搜索未完成；`ISIconManager` 精确搜索结果仅命中 S1，但同样受工具忽略规则限制。公开搜索是索引检索，并非 GitHub 全部代码、Issue、PR 和讨论的穷尽遍历。

状态：仅检索摘录，未操作设备，未提交。
