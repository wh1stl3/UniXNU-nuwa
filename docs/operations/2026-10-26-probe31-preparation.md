# PROBE31 / revision39：初始化进度与读取路径观测

> 现场覆盖：20:59:43上海时间本包已单次临时发送并consumed，fastboot boot返回0；待菜单触发后的媒体和人工恢复。ACK不是内核结果，禁止重发。证据 `reports/xnu-entry-probe-trial/2026-10-26-v39/{preflight,launch,consumed}.json`。以下准备/即将启动文字为历史。

状态：离线准备完成，用户随后明确“直接批准实机部署”；新鲜预检已通过，下一步单次临时启动。未提交或推送。用户明确要求媒体之后连续完成下一包，本轮“先不用实机解释PROBE30”不取消编译交付。下文准备中的过程文字为历史，以本节及实际报告为准。

唯一包报告：`reports/xnu-first-entry/entry-probe-31.json`。镜像：`out/trial-boot/xnu-entry-probe-31-read-init/boot-xnu-first-entry.img`，204484608字节，SHA256 `b970ee14ce8b257ab780160dab053de78c2c3dd6df70dd0e1fad8b5c7a82cb6c`。28项离线检查证据齐备：1472透明性、476内部点、96格清零、9项初始化/高度、46绑定及既有回归。独立内核重建逐字节一致，包解析及FAT回读通过。汇总 `reports/kernel-entry-probe/2026-10-26-v39/qualification.json`；重建与包验证控制台日志在v39-preparation。

实际新增诊断未改变probe段大小（225280字节），data/flags/read_state地址也与PROBE30一致。该事实不证明运行时内存内容或后期映射保持完好。

## 变化与范围

保留PROBE30的47处原生调用及配对返回、首指令之后与RET之前的96个标记；原生错误、认证、线程/帧/配对限定和239释放门不变。没有新增人为成功停止点，不强制返回成功，不更改板值、受审内存配置、身份或任何*_verified。

`scripts/read_init_sites.py` 只扩展header初始化观测。A034暂时显示：

| A034 | 代码位置含义 |
| --- | --- |
| F901 | 已经过入口格清理；即将执行A037初始化 |
| F902 | 已经过A037初始化代码；即将执行A036初始化 |
| F903 | 已经过A036初始化代码；即将清除body状态和96格 |
| F904 | 已经过body状态/格清理；即将初始化A038/A039 |
| 00FA / 250 | 初始化尾部恢复传统阶段值，随后继续原生vn_rdwr调用 |

初始化将A037置于A036之前，各步骤之间加入DSB。实际分派/入口时A036/A037的原有含义不变。检查点描述“执行经过此处”，不能把最后可见值当CPU停止位置；绘制调用仍可因无快照而跳过，CPU写入完成也不等于物理扫描显示完成。A034还会被后续266—275的原生读取阶段覆盖。

快照最低高度从800提高到1040，覆盖本版实际最大行1039（从0开始）；不足高度时不启用后续快照绘制，原生控制流继续。没有修改boot_args或板级显示尺寸。这是修复已确认的诊断边界缺口，**不声称它是PROBE30实机根因**。

额外检查点增加绘制和同步成本，重排也改变时序。不能把下一轮行为变化单独归因于高度修复，更不能称其无扰动。原PROBE30代码审计和反例保持历史资格，不重写报告。

## 本轮验证要求

- 新增 `test-read-init.py`：检查点顺序、字段最终值、无视频路径；实际probe_mmu入口对799/800/1039/1040/3200高度的处理；旧版接受800的负对照；遗漏检查点指令的负对照。
- 沿用逐点原生指令对照、寄存器/栈透明性、96格/字段/配对位重置、调度上下文、映射/异常向量、装载及完整既有回归。
- 打包资格必须绑定新read-init证据、生成器和测试源码；删除报告或删除并重封测试项必须被拒绝。不得拿v38报告充当v39检查。
- 使用原始base.adt独立创建v39上下文；独立重建内核逐字节比较；最终打包后解析并回读真实FAT载荷。

内核初次构建：`out/kernel-entry-probe-39-read-init/kernel-entry-probe.macho`，58560512字节，SHA256 `bb70dbb1071b202dc4d49e4b70cc2200c44137f1e80b74ee13303e9ddbddb99e`。构建报告：`reports/kernel-entry-probe/2026-10-26-v39/build.json`。

新ADT：`out/exec-mainline-v39/launch/kernel.macho.adt`，SHA256 `d45511a111a964bc1bec3a258e71c26e63e3ea2312fe408f1580f624fd8e42b4`。保留原root ramdisk和restore-userspace释放门。

首次9项新检查已通过，原报告移存 `reports/kernel-entry-probe/2026-10-26-v39-preparation/read-init-first.json`；完整串行验证将独立产生正式read-init.json。该移动仅针对本轮新生成报告，旧媒体/候选/证据未移动或覆盖。

### 首轮检查失败与续跑

完整验证首次在透明性测试报告失败：`framebuffer_write_in_bounds` 只对revision38识别扩展画面，遗漏布局相同的revision39，因而把入口格的合法y808写入判为越界。已将版本条件改为`revision in (38,39)`，所有矩形坐标和大小不变；未删除越界断言，也未改候选来迁就测试。

首次执行 `reports/kernel-entry-probe/2026-10-26-v39/execution.json` 和原控制台日志保留；前15项通过。修正后从透明性检查续跑，单独记录 `execution-continuation.json`，不重跑无关已通过项，不把首次整轮写成全部成功。透明性1472项及其后至read-dispatch的检查已通过；余项以最终资格汇总为准。

## 实测边界

准备阶段没有操作设备。用户随后直接批准PROBE31实机部署，新预检v39/preflight.json已确认nuwa/kalama、Android1/A槽、三SHA与v38后验一致，候选包与原boot恢复输入复验通过。本轮沿用本会话已确认的拍摄/实体键恢复条件并在发送前通知。PROBE28/29/30均已消费，禁止重发；任何ACK仍不证明内核执行。

下一次实际启动须使用PROBE31最终唯一包报告和新鲜预检，保持可拍摄菜单触发后的过程与实体键恢复条件。未取得实机结果前，仅称离线检查通过和包准备完成，不称读取问题修复、进入用户态或实机通过。
