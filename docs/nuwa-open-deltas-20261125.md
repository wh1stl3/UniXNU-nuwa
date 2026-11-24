# nuwa 卡点排查清单（2026-11-25）

## 1 一句话用法

遇到新卡点时，先在本清单按关键词查对应差异或他人手段，再考虑新开调查。

## 2 seed 剩余差异

基准是旧 raw 与 merlinx **规格**的离线比较，不是当前设备卷；下列路径均相对 `/private/var`。规格不是设备运行态，差异不证明因果。来源：[seed diff:7-13,198-211](nuwa-seed-diff-merlinx-20261124.md)、[初批记录:3,47](nuwa-seed-containers-20261124.md)。

### 共有目录的 10 条元数据差异，未处理

| 路径 | nuwa mode / uid:gid | merlinx mode / uid:gid | 来源 |
|---|---|---|---|
| `Keychains` | 0755 / 0:0 | 0755 / 64:0 | [diff:202](nuwa-seed-diff-merlinx-20261124.md) |
| `containers/Shared/SystemGroup/systemgroup.com.apple.lsd.iconscache/Library` | 0755 / 501:501 | 0755 / 0:0 | [diff:203](nuwa-seed-diff-merlinx-20261124.md) |
| `containers/Shared/SystemGroup/systemgroup.com.apple.mobilegestaltcache/Library` | 0755 / 501:501 | 0755 / 0:0 | [diff:204](nuwa-seed-diff-merlinx-20261124.md) |
| `db/diagnostics` | 0751 / 0:0 | 0755 / 0:0 | [diff:205](nuwa-seed-diff-merlinx-20261124.md) |
| `empty` | 0755 / 0:0 | 0555 / 0:0 | [diff:206](nuwa-seed-diff-merlinx-20261124.md) |
| `mobile` | 0711 / 501:501 | 0755 / 501:501 | [diff:207](nuwa-seed-diff-merlinx-20261124.md) |
| `mobile/Library` | 0711 / 501:501 | 0755 / 501:501 | [diff:208](nuwa-seed-diff-merlinx-20261124.md) |
| `root/Library` | 0700 / 0:0 | 0755 / 0:0 | [diff:209](nuwa-seed-diff-merlinx-20261124.md) |
| `root/Library/Preferences` | 0700 / 0:0 | 0755 / 0:0 | [diff:210](nuwa-seed-diff-merlinx-20261124.md) |
| `run` | 0775 / 0:0 | 0755 / 0:0 | [diff:211](nuwa-seed-diff-merlinx-20261124.md) |

不顺手统一：reviewer 的有条件方案只覆盖新增 8 条，既有属性未调整；跨版本规格不是本 donor 的权限合同，尤其 `iconscache` 用 0:0 新建可能挡住 501 写入。见 [containers:3,47,69-84](nuwa-seed-containers-20261124.md)；具体逐项 reviewer 原话未留在上述记录，不能扩大为逐项批准。

### 四个缺失 plist

旧 raw 的检查仅限是否普通文件：[diff:229-247](nuwa-seed-diff-merlinx-20261124.md)。初批没有创建 plist：[containers:3](nuwa-seed-containers-20261124.md)。后续运行卷状态未核实。

| 路径 | 状态与判断 |
|---|---|
| `mobile/Library/Preferences/com.apple.DataMigration.plist` | 旧 raw 不存在；[merlinx 规格](https://github.com/Dracen-W/UniXNU-merlinx/blob/fb616afa1231b0ad2b6a6f4832a299b76b64031c/data-seed.json) 写 21H461 的迁移成功状态，不能复制成 20H392 已迁移的事实。 |
| `mobile/Library/Preferences/com.apple.frontboard.plist` | 旧 raw 不存在；merlinx 写 watchdog scale 100，属调整策略而非缺失必然故障，未证 nuwa 需要。 |
| `db/com.apple.xpc.launchd/disabled.plist` | 旧 raw 不存在；系统域是否有运行态覆盖或其他禁用来源未证，不能凭空生成名单。 |
| `db/com.apple.xpc.launchd/disabled.501.plist` | 旧 raw 不存在；501 域同理，不能从文件缺失推断 job 已启用。 |

`lsd.iconscache/Library/Caches`、`mobilegestaltcache/Library/Caches` 等在旧 raw 缺失而规格中为 0:0；`lsd/Library/Caches` 亦缺但不在 merlinx 规格之内，[diff:38-39,213-227](nuwa-seed-diff-merlinx-20261124.md)。父 Library 已是 501:501，创建叶目录应先确认实际消费者写权限，不能照抄 0:0；mobile 下缓存及容器以 501:501 建立的依据和初批情况见 [containers:47,67,71-84](nuwa-seed-containers-20261124.md)。8 条主机候选见 [containers:3,69-84](nuwa-seed-containers-20261124.md)；后续 30 条主机候选及两处 501:501 处理见 [full:3-9](nuwa-seed-full-20261125.md)，均未上机。

## 3 未比对维度

**尚无数据，不要当成已验证没有差异**：xattr、ACL、文件 flags、时间戳、13 条 plist 内容逐字节、目录 inode / 枚举顺序。原检查范围见 [diff:229-249](nuwa-seed-diff-merlinx-20261124.md)、[containers:84](nuwa-seed-containers-20261124.md)。

## 4 跨项目手段台账

本机列指 nuwa 的对应手段及效果，不是来源项目的结果；未验证不表示该项目未运行。

| 手段 | 来源项目 + commit / 版本 | 原文要点 | 代价 | 是否已在本机验证 | 适用卡点类型 |
|---|---|---|---|---|---|
| S5 禁 agent + 两缓存目录 | [merlinx fb616afa](nuwa-iconservices-survey-20261125.md) | 两份 disabled 规格为 true；`lsd.iconscache/Library/Caches`、`mobile/Library/Caches/com.apple.IconsCache`；LS 首建及锁屏/Dock，不证单项因果 | 禁 agent、目录权限跨版本 | 未验证 | 图标、XPC |
| S4 lite=2 禁 agent | [sheng c8f92b20](nuwa-iconservices-survey-20261125.md) | “no iconservicesagent PID ... Settings opened ... icon artwork was missing” | 图标缺失 | 未验证 | 图标、agent |
| S2 同步等待后的观察 | [raphael 684cccb4](nuwa-iconservices-survey-20261125.md) | lsd 从 IconServices sync wait 进入 signing scan；未给越过手段 | 因果和耗时未知 | 未验证 | 同步 XPC |
| R1 720s LS 回复采样 | [raphael 684cccb4](nuwa-seed-full-comparison-20261124.md) | “720s snapshots ... LS serves store replies”；无桌面 | 长时间观测，非预置库 | 未验证 | 建库慢 |
| R2 HFS+ 根卷 + data_ark | [raphael SWEET main，未 pin](nuwa-seed-full-comparison-20261124.md) | 合并 OS/cryptex；写 activation 状态，项目称桌面、未接触摸 | 不同卷架构；预置不是真认证 | 未验证 | 无可写卷 |
| S6 Metal | [QEMU 97b75b1f](nuwa-iconservices-survey-20261125.md) | 无 Metal 时 agent 在 CoreImage 崩溃并重试；有 Metal 后 Settings 打开 | 改运行环境；多数行图标仍缺符号 | 未验证 | agent 崩溃 |
| S8 CoreUI fixup | [sirius 官方设备文档，版本未 pin](nuwa-iconservices-survey-20261125.md) | “crashes=0 at 335 s”；symbol 绘空 | 改系统代码映射 | 未验证 | agent 崩溃、图标 |
| S7 launchctl bootout + disable | [macOS 26.6.1 issue 14751](nuwa-iconservices-survey-20261125.md) | 请求快速失败，回退通用图标 | 改服务状态；不证明 iOS 同效 | 未验证 | 同步 XPC |
| Linux mkapfs + catalog | [fajita main，未 pin](nuwa-seed-full-comparison-20261124.md) | “mkapfs ... formats the image”；Linux 不需 root/FUSE | donor 文件重建及 WSL 未证 | 未验证 | 无可写卷 |
| macOS Data seed 与长启动 | [Odin3 main，未 pin](nuwa-seed-full-comparison-20261124.md) | “A macOS host ... Data seed”；“~14 min to SpringBoard” | 触摸及二次启动未证；Linux 构建其他介质，不是 Linux mkapfs Data seed | 未验证 | 建库慢、无显示 |

## 5 按卡点类型索引

- 图标不出：先看 S5、S4、S8；目录存在不等于图标库可用。
- 同步 XPC 卡死：先看 S2、S7，核对第 7 节对端与 domain。
- agent 崩溃重试：先看 S6、S8、S4。
- 建库慢：先看 R1、Odin；采样回复与耗时，不把慢直接判死锁。
- 无显示：先看 Odin、S6，分别区分 SpringBoard 出现、呈现与触摸。
- 无可写卷：先看 fajita、R2；RAM 卷或临时 seed 不能替代真实 UFS 持久根卷验收。

## 6 不应照抄的项

- enuma 资产或其他 donor 文件：跨机型资产明确禁止；跨大版本布局和权限不是 nuwa 合同。
- 空 `db/dslocal`：可能被消费者视作坏库，[containers:47](nuwa-seed-containers-20261124.md)。
- 凭空写 disabled 名单或迁移成功、`data_ark` 激活状态：伪造状态或改变服务可用性，不是认证成功。
- 预置或跨机复制 csstore：未找到所查项目预置证据，动态 donor 内容未知；目录不等于数据库，[comparison:56-60](nuwa-seed-full-comparison-20261124.md)。

## 7 别的项目关掉 / 替换 / 绕过了什么

以下按具体行为而非移植效果分类；多数未经 nuwa 验证。D 系为禁用、T 为替换、B 为绕过、C 为关闭子系统。

| ID / 手段 | 来源项目 + commit / 版本 | 原文摘录或配置 | 代价 | 本机验证 |
|---|---|---|---|---|
| D1 禁 iconservicesagent | [merlinx fb616afa](https://github.com/Dracen-W/UniXNU-merlinx/blob/fb616afa1231b0ad2b6a6f4832a299b76b64031c/data-seed.json)，手机硬件、iPadOS 17 | 两份 disabled 均为 `com.apple.iconservices.iconservicesagent: true` | 禁用图标服务；单项效果未分离 | 未验证 |
| D2 禁 agent | [sheng c8f92b20](nuwa-iconservices-survey-20261125.md)，平板 | `lite=2`；“All app icon artwork was missing” | 图标缺失 | 未验证 |
| D3 其余 disabled labels | merlinx fb616afa，同 D1 | 两份名单均含下方 30 个 label，均 `true`；是规格，不是实机读入证据 | 各服务能力被关，影响未逐项验证 | 未验证 |
| T1 HFS+ 组合根 | [raphael SWEET main，未 pin](nuwa-seed-full-comparison-20261124.md)，手机、iOS 16 | “assemble ... one 16 GiB ... HFS+ volume” | 换根卷架构，触摸未接 | 未验证 |
| T2 RAM `/private/var` | [thyme main，未 pin](nuwa-seed-full-comparison-20261124.md)，手机、iOS 16.5 | “save works; the load at boot hangs” | 重启恢复挂起，不满足持久目标 | 未验证 |
| T3 Linux mkapfs | [fajita main，未 pin](nuwa-seed-full-comparison-20261124.md)，手机 | “mkapfs ... formats the image” | Linux 目录生成不证明 donor 无损重建 | 未验证 |
| T4 macOS Data seed | [Odin3 main，未 pin](nuwa-seed-full-comparison-20261124.md) | “A macOS host ... the Data seed” | 非 Linux mkapfs Data seed；触摸未证 | 未验证 |
| T5 Solid State 属性候选 | [raphael 684cccb4 S2](nuwa-iconservices-survey-20261125.md)，手机 | NativeRamBlock 发布 Solid State medium；“Build and handset qualification pending” | 改驱动，未证效果；不能归因于已越过等待 | 未验证 |
| T6 CoreUI fixup | [sirius S8](nuwa-iconservices-survey-20261125.md)，官方文档未 pin | “crashes=0 at 335 s”；“symbol draws empty” | 系统代码映射改动，符号缺失 | 未验证 |
| B1 root auth skip | [nuwa AGENTS:27-28](../AGENTS.md)，当前仓 | `rootvp not authenticated` → `8796-nuwa-root-auth-skip` opt-in | 不做 root 认证 | 主控转述实机 / self-checked；认证 NOT REACHED |
| B2 trust cache 初始化前移 | [nuwa AGENTS:29](../AGENTS.md) | lockdown 前 `trust_cache_runtime_init` + `load_static_trust_cache` | 当前 `{0,0}`，加载为空操作 | 主控转述实机 / self-checked；真实 trust 未验证 |
| B3 initproc exec policy skip | [nuwa AGENTS:30](../AGENTS.md) | 仅 initproc 忽略 `ip_mac_return`，opt-in | 首 exec 不受签名策略约束 | 主控转述实机 / self-checked；认证 NOT REACHED |
| B4 unverified root | [dizi 官方记录 @ 8542980d](https://github.com/UniXNU/UniXNU/blob/8542980d02b4d2cc5c32ee3542de1760b2562aac/docs/.vitepress/device-records/dizi.toml) | `native-ufs-allow-unverified=1`；“OS and SystemOS volumes are not authenticated” | 未认证，placeholder manifest | 未验证该项目做法 |
| C1 watchdogd | merlinx fb616afa，见 D3；[nuwa r34](nuwa-userspace-20261119-observation.md) | `com.apple.watchdogd: true`；nuwa r34 args `disable-watchdogd=1` | 丧失 watchdog 监督；参数存在不证明服务禁用生效 | nuwa 参数及观察为主控转述 / self-checked，生效未验证 |
| C2 GPU | [dizi 官方 @ 8542980d](https://github.com/UniXNU/UniXNU/blob/8542980d02b4d2cc5c32ee3542de1760b2562aac/docs/.vitepress/device-records/dizi.toml) | “GPU code itself ... is not built ... stubs ... ‘not ready’”；CPU copy | 无 GPU 加速 | 未验证该项目做法 |
| C3 睡眠 | dizi 官方 @ 8542980d | “CPU cores cannot be restarted after sleep, so sleep is turned off in the Data seed” | 无睡眠 | 未验证 |
| C4 SMP 入口门 | [nuwa SMP 记录](nuwa-smp-gate-20261123.md) | 默认关闭，`sheng-smp` 非零才准入次核 | 仅单核候选；运行门及次核未验 | 主机 self-checked，未上机 |
| C5 显示路径 deferred | [nuwa AGENTS:31](../AGENTS.md) | “显示服务缺失 → deferred，只有 vinfo 观测带” | 无 UI；不是证明有意关闭显示 | 历史主控转述 / self-checked |

D3 其余 30 个 label：`com.apple.watchdogd`、`com.apple.bluetoothd`、`com.apple.cryptexd`、`com.apple.PerfPowerServices`、`com.apple.liveactivitiesd`、`com.apple.ScreenTimeAgent`、`com.apple.dmd`、`com.apple.UsageTrackingAgent`、`com.apple.thermalmonitord`、`com.apple.duetexpertd`、`com.apple.coreduetd`、`com.apple.webbookmarksd`、`com.apple.searchd`、`com.apple.suggestd`、`com.apple.triald`、`com.apple.siriknowledged`、`com.apple.spotlightknowledged`、`com.apple.fairplayd.A2`、`com.apple.ReportMemoryException`、`com.apple.privacyaccountd`、`com.apple.purplebuddy`、`com.apple.CommCenter`、`com.apple.privacyaccountingd`、`com.apple.chronod`、`com.apple.cloudd`、`com.apple.maild`、`com.apple.amsaccountsd`、`com.apple.amsengagementd`、`com.apple.locationd.pipelined`、`com.apple.accessoryupdaterd`。未找到可核对的其他项目 iPhone OS disabled 清单；merlinx 硬件为手机但跑 iPadOS，不要称 iPhone donor 名单。

## 8 症状 → 先查哪些关停项

1. **同步 XPC 永久等待**：先查客户端与对端的实际 service/domain、`db/com.apple.xpc.launchd/disabled{,.501}.plist` 和运行态退出/重启，参考 S2、S6、S7；当前 nuwa 栈不能确定对端或 selector，[lsd symbols:90-104](nuwa-lsd-stack-20261124-symbols.md)。
2. **daemon 反复重启 / 非零退出**：查其容器及父目录 uid/gid/mode、对应 plist、实际 exit reason 和 watchdog 参数 `disable-watchdogd`；参考 S6、C1 与 [containers:47,71-84](nuwa-seed-containers-20261124.md)。
3. **图标 / 资源缺失**：查 IconServices agent 的 domain、崩溃计数、`lsd.iconscache/Library/Caches` 与 `mobile/Library/Caches/com.apple.IconsCache`；参考 S4–S6、S8。
4. **启动卡阶段**：查该阶段涉及的 disabled 名单、实际 `lite` 档位及已加载服务，参考 D1–D3、D2；不能从另一机器标签清单推导本机配置。
5. **单核满载 / 无空闲**：查 `sheng-smp` 等实际参数与 CPU 在线状态、服务重启计数和重复失败栈，参考 C4、S6；忙不等于已确定 agent 在重试。

## 9 判定关停是否生效：PEER 思路模板

1. 先记录本次启动载荷、真实挂载卷及 domain；只读检查 `/private/var/db/com.apple.xpc.launchd/disabled.plist` 与 `disabled.501.plist` 对应键、类型、值，并记录不存在 / 读取失败，不能把缺文件等同 false。不同版本的持久配置路径和加载时机须由该版本证据确认。针对本 donor 的候选 agent，原始 LaunchDaemon 是 system domain、`RunAtLoad=false`，见 [最终包轮次记录](nuwa-final-20261125.md)；不证明它是所采 XPC 对端。该记录由最终包轮次生成，若尚未出现则以其提交为准。
2. 在允许的运行态工具存在时只读查询对应 launchd domain 的服务状态和禁用状态，结合 PID、退出码、重启次数及时间序列；没有 PID 也可能是按需未启动、查询错 domain 或启动失败，不单独证明 disabled 被读取。
3. 现有主机 fixture 行为 `PEER icon=4096 cm=4095 lsd=4094 SB=4093`，见 [最终包轮次记录](nuwa-final-20261125.md)：仅 PID 1–4096、异步非一致采样，`-` 不证明全局缺席。未来可设计**只读、限量**扩展行 `PEER <domain> <label> cfg=<true|false|absent|error> query=<enabled|disabled|unknown> pid=<number|none|unknown> exit=<value|unknown> restarts=<count|unknown> t=<time>`：这是建议格式，不是现成 API 或已实现字段。必要时采样多次，探针不得发起同步请求来验证对端。
4. 判定“已生效”需同一启动的配置值、对应 domain 的运行态禁用状态和可复核的加载链证据一致；仅 PID 缺失或请求快速失败不够。具体 plist 被读取仍需版本匹配的 launchd 读取证据，运行态状态本身不能证明来自哪一个文件。

状态：仅文档整理 / self-checked；本轮无设备、代码或产物变更。full 和 PEER 为并行工作记录，不将主机候选冒充设备实测。
