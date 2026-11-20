# 20H392 display 329/330：运行时 gate 缺证停机

状态：仅静态审查；未实现适配、未放行运行。设备仓
`display/20h392-abi@bb6ff5f488e587e49194a115bb5b728ca1c0daee`；
已审观察规格 `4e1daca3a74212bf3ec45bd864e9ea556f15d7b4`
在另一分支，本轮只读取其内容，不合并。donor 为
`UniXNU/out/ipsw/20H392/kernelcache.decompressed`，既有记录 SHA256
`2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221`；
本轮未重复哈希或已确认读写。以下地址省略 `0xfffffff000000000` 前缀。

## 最早缺证与验收

已审规格的首个缺证转移仍是 `5c0c22c` caller 入口到实际 gate 对象、
取得和调用返回后的释放：静态 vtable 调用锚不能证明实际 gate 身份或
全借用期覆盖。`5c121ac–5c12214` 的 C `runAction` 只覆盖该已知
timeout 入口；`5c118d8` 的 `commandSleep` 等待时释放 gate、返回时重取。
不能把它外推为其他 330 caller 的连续排他，也不能排除同线程递归重入。
`5c10084` 的 sender 不自行获取 gate。实际对象身份、覆盖和重入需要运行时
证据；已审 `4e1daca` 给出不扰动关联观测的前提和向量，本轮无运行授权。

既有 `scripts/derive-nuwa-display-abi.py:532–541` 可复算 donor 指令：
`5c11980` 为 `f9452508 d63f0100`（329 调用），`5c119dc` 为
`9240016b f900192b`（日志 TimingEnable 位），`5c11a74` 为
`f9452908 d63f0100`（330 调用），330 Legacy 目标 `5c0fbe8`。
这些静态锚不证明 329 与 nuwa 事件等价，不证明 copy 后 timeout 的状态，
也不证明 completion 重入时引用安全。`5c0c22c` 的既有指令锚为
`f9445108`，见同脚本 `:477`。本轮没有重新执行派生脚本。

成功、copy 后 timeout、completion 重入三条路径的同 generation 唯一终结、
引用顺序均未闭合；既未证明也未证伪实际合同。329 guard 保留，330 仍为
donor；不报可适配，不将禁用软件 timer 当作排除 timeout 或重入。
要求的正常/超时/重复拒绝确定性 host 夹具未交付：在真实 gate 和状态合同
未知时，构造模型只能验证假设，不能作为合同验收。不得以此替代
`4e1daca` 的完整轨迹、溢出及未知处理要求。

恢复条件：取得经审查的不扰动、按对象 generation 关联的运行证据，
闭合上述 caller gate 与 329 状态事件，并覆盖成功、copy 后 timeout、
completion 重入的引用与唯一终结顺序；再实现针对已证合同的确定性夹具，
提交 deep review。此处不是运行或设备授权。

本轮不做设备操作、strict emit、构建、donor 修改或漏洞复现；未有独立
verifier。既有静态事实来自 `nuwa-display-abi-20261120.md` 和 `4e1daca`，
不当作本轮新反汇编或运行结果。
