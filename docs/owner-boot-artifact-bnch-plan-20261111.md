# Owner-defined boot-artifact BNCH：隔离生成与最终 ADT 主机实验

2026-11-11；**当前独立主机验收见第7节；第6节为实现者首次 self-checked 记录。**
第1–5节保留首次方案阶段原文，其“未实施/等待批准”是历史，不是当前阻塞。
主控已转述 reviewer_deep `ses_e39aecf93ffeDFlaanMmAthY5L` 主机范围及
reviewer `ses_e39a3c143ffe2FADCIAiKVazKQ` 窄 AST 方案 PASS WITH CONDITIONS；
未扩大为 payload 集成、认证或上机许可。

## 1. 首个阻塞：正式 API 没有合规扩展点

只读基座 `D:/Code/PortingiOS/UniXNU` HEAD
`693f5d9cae8a408dd18b39f3f9fdc4228c934241`，文件
`scripts/unixnu/devicetree.py` SHA256
`06043e034b5ac7ee6fe0a71bb6ee9fefa75e8a53609a7fa6810dfcd0c83e9c75`。
该文件工作区和暂存区 diff 均为空；基座整体不声明 clean（XnuPrelink 子模块 dirty 保留）。

- `generate(dtb, config, *, unique_chip_id=None, data=False, trust=False, addon=False, root_policies=False)`：290 行。
- `node()`：13–21 行，立即返回序列化 bytes，不是可修改树对象。
- `typed_properties()`：262–277 行，仅转换属性表，不提供节点注入。
- `platform_node()`：280–287 行支持配置子节点，但 generate 只在 378–380 行用于 defaults/options/product/buttons。
- `generate()`：335 行只将 `platform.chosen` 转成 chosen 自身属性；340 行硬编码
  `node('manifest-properties')`；389 行直接返回整棵树的序列化 bytes。

因此不能用当前公开参数向唯一 `/chosen/manifest-properties` 在其序列化前注入 BNCH。
把 `manifest-properties` 塞进 chosen typed table 不会创建子节点；增加另一个 chosen
也不满足唯一性。此结论限于这份固定正式生成器，不声称全仓无其他 producer。
**触发 brief 第1项停止条件：未实现生成器、未运行 initializer、未生成 token/记录/ADT。**

## 2. 设备持有窄适配：具体待审草案（不是现成 API）

请求审查的最小能力是：仅把上述唯一空子节点调用的 properties 参数接到设备验证过的
`list[tuple[str, bytes]]`，其他生成逻辑逐字复用固定正式源码。不得复制 generate 的实现。
本轮不修改基座，也不创建或执行以下适配器。

拟议设备文件 `scripts/generate-owner-boot-artifact-adt.py` 的隔离源码适配设计：

1. 显式 base 路径，核对上述完整 revision 和文件 hash，读取原始源码；拒绝 pin 漂移。
2. AST 精确定位 generate 内 chosen children 中唯一的无参属性
   `node('manifest-properties')`，要求原 AST 结构/命中数一致；不接受任意文本替换。
3. 仅在内存 AST 给该调用增加第二位置参数 `_owner_manifest_properties`。
   在独立模块命名空间编译固定正式源码，保留正确包上下文以使用正式 `.util`；
   向该私有命名空间提供已验证的属性列表。不得修改已导入模块的 globals、sys.modules
   中的正式生成器、node、os.urandom 或其他进程全局对象；不得写适配后的源码副本。
4. 通过私有模块的 generate 调用原正式逻辑，在 manifest 节点编码前传 bytes；
   不解码/重写历史 ADT，不使用审计器当生成器。禁用时传空列表。
5. 必须审查私有包加载/导入隔离、AST 唯一性、pin 拒绝与是否仍符合“不 monkey-patch”边界。
   **这是新窄适配方案而非已存在的扩展点，须主控/reviewer 接受后才能实施。**

拟议内存中唯一语义差分（不应用到基座）：

```diff
-    children = [node('chosen', chosen, [node('memory-map', mappings), node('manifest-properties')])]
+    children = [node('chosen', chosen, [node('memory-map', mappings), node('manifest-properties', _owner_manifest_properties)])]
```

若审查不接受隔离 AST 适配，应另行授权正式 API 的最小扩展：generate 增加默认空的
keyword-only manifest properties 参数，340 行传入 node；设备包装负责实验策略。
这涉及只读基座边界变化，**本任务不执行，也不自动切换此路径**。

## 3. 适配获批后才实施的输入契约

- 现有 board/正式 payload 路径不改，默认关闭且无 BNCH；显式实验开关才允许唯一 BNCH。
- 每候选仅一次 `secrets.token_bytes(48)`；先在全新 ignored 设备 out/目录独占创建记录，
  再生成 ADT。后续必须显式指定复用该记录，存在记录/失败不得自动抽取新值或覆盖。
  区分 create-record 与 reuse-record，不把无开关的默认生成当记录创建。
- 记录包含软件域标签、候选标识、48-byte hex、kernel/base pins、输入配置引用；
  生成后另记最终 ADT hash。标签只在主机记录，不写成硬件 nonce、IM4M 摘要、
  per-boot 唯一、roll 或 replay 保证。不把设备身份原值写入 tracked 文档。
- 拒绝错误类型、重复节点/属性、非48长度、记录与 ADT 不一致、覆盖输出；
  解析检查须保留列表并检测重复，不能先转 dict 掩盖重复。
- 保持 chosen AMNM (`mix-n-match-prevention-status`) little-endian u32=0；不添加 CHMH。
  与新生成的禁用对照做语义 diff，仅允许 BNCH 和正式 `os.urandom(256)` 的 random-seed 变化；
  identity/DRAM/trust 等均不变。正常 seed 不复用 BNCH、不因比较而 monkey-patch RNG。

## 4. 最终原始 ADT 验证模式（待实施，不改旧 fixture）

固定 kernel：设备 `out/mix-n-match-20261110/audit-final/new/kernel.macho`，SHA256
`fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd`。
本轮实际只读 hash 与该值相符，未修改它。

现有 `scripts/research-current-image4-bnch.py`：25–26 行固定 kernel/旧 ADT pin，
61–67 行 variant 删除/替换 BNCH，229–232 行要求旧 ADT 无 BNCH，240 行生成 variant。
因此不能把该脚本的 variant 结果叫最终候选验证。

拟新增设备独立 `scripts/check-owner-boot-artifact-bnch.py`，显式要求 final ADT 路径、
hash 和记录；在运行前严格检查唯一性、bytes/48长度、AMNM、无 CHMH 和记录一致。
直接把读入的同一 bytes 交现有 `binding()` 与 `Run(...).initialize()`，不调用 main/variant，
不调用任何生成器，不删除/替换 BNCH、不改旧 fixture pin。

复用 Run 的原始 SecureDTInit/LookupEntry、原始 initializer/reader 指令和边界。
新增只读观察器记录 BNCH_RETURN 处实际输出48 bytes（现有 watch 161–168 行只记录
长度/errno/边界，不记录 initializer 输出数据），要求与记录精确相同，长度48、errno0、
邻接16-byte前后快照一致、initializer return；记录容量、写入范围、实际 PC 和所有 stub。
不以单独 reader 输出冒充 initializer 数据，不修改寄存器/level/provider/init。
保留模型范围：构造初态主机执行，不是完整 runtime 或认证。

沿用 `docs/image4-bnch-offline-20261110.md` 的既有四矩阵/26项独立结果；
旧缺失 errno2 panic、49长度 errno84 panic 行为不改，不无条件重跑。
新增验证聚焦原始 final bytes、记录错配/重复/类型/长度/默认关闭/复用和边界观察；
若共用 Run 或依赖确有改动，才按增量补相应回归。不扩展 trst/5152 ledger、认证替换或 provider。

## 5. 本轮自检与后续门禁

本轮实际修改只有本说明；既有五份 tracked 脏文件及未 tracked 的 firmware-evaluate
研究脚本保留。设备 HEAD `63769f208783769f7fa4ec5cffc14d3eba37b21a`，无 commit/push。
无新 out/目录、BNCH 记录或最终 ADT，因此其路径为 **无（未生成）**。

实际命令 cwd 均为 `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`：

- PowerShell `git status --short; git diff --stat`，exit0，初始5 tracked文件 +53/-22，
  及1个未跟踪研究脚本；已读取现有 diff，不覆盖。
- `git -C D:/Code/PortingiOS/UniXNU rev-parse HEAD`、针对 devicetree.py 的
  `git diff -- ...` / `git diff --cached -- ...`，exit0；revision及限定 clean 结果如上。
- `Get-FileHash -Algorithm SHA256 ...`，exit0，核对正式生成器与固定 kernel；
  同时记录既有脏文件 hash，用于本轮收尾不变断言。
- 收尾8个 hash 不变断言通过（上述6个既有脏文件/脚本、kernel、正式生成器），
  设备 `git diff --check` exit0。首次 WSL `git diff --no-index --check -- /dev/null
  docs/owner-boot-artifact-bnch-plan-20261111.md` 返回1，外层错误地只接受0而 exit1；
  WSL另有localhost代理提示，无空白错误输出。随后原生 Git 同命令（空文件用 `NUL`）
  实际 exit1、输出0行：no-index 的新文件差异码1，不是空白错误；修正外层判定后exit0。
  `git diff --stat` 仍为既有5文件 +53/-22；新文档另用 no-index stat 统计。
  未执行实现/构建/initializer 测试。

下一第一动作：主控审查第2节隔离适配方案（或明确授权正式 API 最小扩展），再下实现 brief。
独立 verifier 只需复核固定源码 API/pin、文档 diff 和保留断言；本轮无最终 build/test 可复跑。
批准实现后再独立复跑最终生成及原始 ADT initializer 检查；此前验证未完成。
消费者范围、停止机制和包装审查仍为上机前单独门禁，本轮不实现诊断终止、打包或上机入口。

## 6. 实现与首次自检证据（2026-11-11，self-checked；当前验收以第7节为准）

已重读最新共享 context-brief，包含 Device access 第25–31行；本任务没有调用任何设备命令。
只在设备仓新增四份脚本，保留原有混合差分；没有修改基座、board、正式 payload、
旧 BNCH fixture、generic trst/5152 ledger、level/provider/init 或认证比较。

### 实现边界

- `scripts/owner_bnch.py`：固定 revision/生成器及 util SHA；源码一次读取后用于
  hash、AST parse/compile。精确匹配 generate 内唯一 children 赋值及无 keywords 的
  单字符串参数 manifest node 调用；只增第二参数，逆归一 AST 与原始 AST 完整比较。
- 每次私有 UUID 模块名（只作模块隔离，非 token/epoch），仅登记本次 package/util/devicetree，
  不覆盖正式模块；退出删除登记。util 工作文件来源及内容与固定 revision Git blob 核对；
  util 仅进一步导入 Python 标准库 hashlib/os/shutil/subprocess/sys/pathlib。
  devicetree 的 dataclasses/pathlib/os/re/struct/uuid/zlib 均为标准库。
  原 compile_hardware 内的 `.profiles` 不执行，私有包空 `__path__` 不允许从磁盘隐式续载。
  无 import hook、全局 monkey-patch 或 RNG 替换。
- 输入接口只接受 `[]` 或唯一 `('BNCH', bytes48)`；在正式 typed_properties/root dict
  转换前检查跨类型重复和自动属性覆盖（含 name）。严格保序 ADT parser 检查节点/属性
  重复、唯一目标路径、AMNM四字节0、无 CHMH、无目标外 BNCH 和记录逐字节一致。
- 默认关闭不生成 BNCH token/实验记录；禁用加记录参数拒绝。新 ignored 候选目录及记录
  独占预留后抽取一次48字节；显式复用记录绑定 DTB 内容、保序解析配置、identity及
  全部五个关键词实际值的 hash，不按路径认定。异常保留 failed 记录/已抽 token，不覆盖
  或自动重抽；检查失败不发布 final.adt。每轮自检有独立输出目录，不覆盖历史轮。
- `generate-owner-boot-artifact-adt.py` 仅复用固定正式生成逻辑：同一 DTB 快照、配置、
  identity 和五关键词分别跑未修改正式生成器/适配器禁用/启用；保序语义只允许
  chosen/random-seed 的256字节值变化，启用另允许唯一 BNCH。不是已接入 payload 流程。
- `check-owner-boot-artifact-bnch.py` 显式读取 final ADT、其 hash 和同候选记录/输入快照；
  原字节直接送旧 fixture 的 binding/Run.initialize，不调用旧 main/variant 处理 final。
  新只读观察器记录原 initializer 实际48字节输出、长度、errno、返回 PC、邻接边界和
  原始返回 x0；不把 x0 当状态码。可选 failure-controls 单独消费禁用对照和49字节
  负例 fixture；49负例仅用旧 codec 造测试输入，绝不当候选生成器。

### 最终产物与观测

所有路径相对设备仓，均 ignored；token/identity 不输出到 tracked 文档：

| 项目 | 路径 / 结果 |
|---|---|
| 最终 ADT | `out/owner-bnch-20261111-final/final.adt`，13256 B |
| ADT SHA256 | `a03376535b47f4943201a5c1725e4e6b151f36eb02747ff56f869575792feff3` |
| token 记录 | `out/owner-bnch-20261111-final/record.json`（显式复用r2 enabled记录，无新抽取） |
| 同输入正式/禁用对照 | 同目录 `formal.adt` / `disabled.adt` |
| 实际输入/语义比较 | 同目录 `input.dtb`、`config.json`、`keywords.json`、`generation.json` |
| 最终原始 initializer | `out/owner-bnch-20261111-final-initializer/initializer.json` |
| 最终版本11项自检 | `out/owner-bnch-20261111-selfcheck-r3/tests.json`（11/0errors/0failures） |
| 增量失败路径/拒绝测试 | r3 `initializer/initializer.json`、`initializer-negative-checks.json` |
| 命令/退出/源码绑定汇总 | `out/owner-bnch-20261111-evidence/selfcheck.json`（无 token/identity 原值） |

固定 kernel SHA 与第4节完全一致。最终实际 errno0、长度48、输出逐字节匹配记录、
邻接前后16字节未变，终态 initializer return；原始 x0=`0xfffffff005cb1310`，无认证含义。
r3 缺失 errno2、49长度 errno84，均走原 panic/长度48/边界完好。
11项覆盖接口类型/长度、AST漂移、跨类型/自动属性重复、ADT重复、正式三路比较、
启用→禁用无残留、显式复用、输入内容错配、已有输出、生成异常保留、revision/source/util
漂移拒绝、最终实际消费及错误 final hash/record/output 拒绝。旧四矩阵/26项沿用既有
独立结果，未整套复跑，也未跑 generic ledger。

### 完整主机命令及退出

Windows cwd `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`；下列经 WSL 执行的命令 cwd
均 `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`。测试准备用固定正式 profiles.merge
按 arch/soc/os/device+所选 os_overrides 顺序解析配置；identity 从 ignored 本地输入读入，
不重新抽取、不输出。五关键词为 identity、data=false/trust=true/addon=false/root_policies=false。

```powershell
# 最终脚本版本：实际 exit0，11项，5.868s；包含 /usr/bin/python3 的原 initializer 子进程。
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/test-owner-boot-artifact-bnch.py --base /mnt/d/Code/PortingiOS/UniXNU --output out/owner-bnch-20261111-selfcheck-r3

# 最终候选：实际 exit0，显式复用r2 token，不覆盖r1/r2/r3。
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/generate-owner-boot-artifact-adt.py --base /mnt/d/Code/PortingiOS/UniXNU --dtb /mnt/d/Code/PortingiOS/UniXNU/out/nuwa/ios-16.7.16-20H392/nuwa/device-tree/hardware.dtb --config out/owner-bnch-20261111-selfcheck-r2/resolved-config.json --keywords out/owner-bnch-20261111-selfcheck-r2/generate-keywords.json --output out/owner-bnch-20261111-final --enable-owner-bnch --reuse-record out/owner-bnch-20261111-selfcheck-r2/enabled/record.json

# 最终原始输入：实际 exit0；另两失败路径已在r3运行，不重复。
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /usr/bin/python3 -B scripts/check-owner-boot-artifact-bnch.py --kernel out/mix-n-match-20261110/audit-final/new/kernel.macho --adt out/owner-bnch-20261111-final/final.adt --record out/owner-bnch-20261111-final/record.json --adt-sha256 a03376535b47f4943201a5c1725e4e6b151f36eb02747ff56f869575792feff3 --output out/owner-bnch-20261111-final-initializer

# 收尾实际各exit0；record输出14 structured areas，旧差分保留断言通过。
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -m py_compile scripts/owner_bnch.py scripts/generate-owner-boot-artifact-adt.py scripts/check-owner-boot-artifact-bnch.py scripts/test-owner-boot-artifact-bnch.py
wsl -d Ubuntu-22.04 --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 /mnt/d/Code/PortingiOS/UniXNU/scripts/porting-record.py check --device .
git diff --check
```

早期环境检查 Python3.11 import unicorn 失败，未安装/下载；原 fixture 使用现成
`/usr/bin/python3`（unicorn2.1.4/capstone5.0.7），配置准备用支持 tomllib 的 Python3.11。
早期测试r1/r2的 ignored wrong-base 临时 Git fixture 曾生成空测试提交；这不是设备/基座仓
提交，但不符合本任务“不commit”的字面约束，已移除此测试动作，最终r3只 init/写测试 HEAD、
不 commit。旧 fixture 保留未清理，设备及基座 HEAD 未变，未 push。

独立 verifier：将上述测试 output 改为全新 `out/owner-bnch-verifier-20261111`；
生成 CLI 改用全新 `out/owner-bnch-verifier-final-20261111` 并显式复用本最终 record、
config/keywords/input.dtb；最后 checker 先复跑**本固定 final ADT/hash**，改用全新
`out/owner-bnch-verifier-initializer-20261111`。另跑基座 porting-record check 和 git diff --check。
不要覆盖任何现有输出，不打印 token/identity，不调用设备命令或旧 fixture main。

本轮仅 self-checked；受限构造初态的原始 initializer 成功不等于消费者闭环、认证、
真实 runtime 或设备放行。独立审查/verifier 由主控派发；消费者范围/停止机制及包装
仍须上机前审查，本轮不实现诊断终止/上机入口，不打包 boot。

<a id="independent-host-acceptance"></a>
## 7. 主控接受的独立主机里程碑（2026-11-11）

**结论：主机生成及原 initializer 构造态独立验证。** 本节记录主控交付的独立结果，
本次只读现存证据并更新文档，不重跑研究/测试/构建/设备操作，不改四脚本，不 stage/commit/push。
设备完整 HEAD `63769f208783769f7fa4ec5cffc14d3eba37b21a`，实现仍为该 HEAD 上的未提交差分。
base revision `693f5d9cae8a408dd18b39f3f9fdc4228c934241` 及固定 kernel SHA256
`fb1e796d7357b3e7ff7027bb94377d1cd38eae7283a6c72a7460914a200a0fbd` 不变。

### 审查与 Git 写入范围更正

- 主控转述 reviewer 最终 **PASS WITH CONDITIONS（主机静态）**。test08 仅在新 ignored
  fixture 中 `git init`、写 HEAD/objects/info/alternates 的例外获主控批准；无 commit、
  无项目仓 Git 写入。不能表述为“零 Git 写入”。这不追溯抹除第6节已披露的早期r1/r2
  空 fixture 提交；当前获准的最终测试版本不含 commit。
- 不代表认证、runtime、stage5、device 或正式 payload 集成；无新设备候选。

### 独立证据分层（报告内固定 self-checked 标签不改写）

所有路径相对设备仓；退出码没有保存在 JSON 的，明确以主控转述为依据，不补造历史日志。

| 独立动作 | 实际证据与结论 |
|---|---|
| 11项测试 | `out/owner-bnch-verifier-20261111/tests.json`：11/0errors/0failures，记录 argv/cwd；整个命令 exit0 由主控报告 |
| 启用生成及record复用 | `out/owner-bnch-verifier-final-20261111/generation.json`：enabled=true，三路保序比较通过；同目录 record 显式复用首次最终记录；exit0由主控报告，JSON不含完整历史argv |
| 原固定产物 initializer | `out/owner-bnch-verifier-initializer-20261111/initializer.json`：原 ADT hash `a03376535b47f4943201a5c1725e4e6b151f36eb02747ff56f869575792feff3`，原字节/errno0/length48/边界/return；exit0由主控报告；该文件实际 failure_controls 为空 |
| 独立失败控制 | `out/owner-bnch-verifier-20261111/initializer/initializer.json`：missing errno2、oversized49 errno84，均 original panic edge；同根 `initializer-command.json` 记录真实子进程 command/cwd/exit0，控制使用该次 verifier enabled ADT，不冒称存于原固定产物报告 |
| fresh最终 ADT | `out/owner-bnch-verifier-final-20261111/final.adt`，13256B，SHA256 `269170758882aa3b58c1de9f803a0563e774742ea7d1056ed3d9ff90299ce147`，record同目录 |
| fresh checker | `out/owner-bnch-verifier-fresh-initializer-20261111/initializer.json`：final_input_unmodified=true、errno0、length48、输出匹配同目录record、canaries intact、initializer return；主控核实 `/usr/bin/python3 -B` 真实exit0；failure_controls为空，沿用上述独立失败控制，不称fresh重跑 |
| 其余独立检查 | 主控报告 py_compile/porting-record 14区域/git diff --check 各exit0；本次不重跑py_compile或前述实验 |

`tests.json` 实际记录的 argv 为
`scripts/test-owner-boot-artifact-bnch.py --base /mnt/d/Code/PortingiOS/UniXNU --output out/owner-bnch-verifier-20261111`，
cwd=`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`；该JSON不保存解释器和进程退出码。
`initializer-command.json` 的完整实际命令为（同cwd，exit0）：

```text
/usr/bin/python3 -B /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/check-owner-boot-artifact-bnch.py --kernel /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/mix-n-match-20261110/audit-final/new/kernel.macho --adt /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-bnch-verifier-20261111/enabled/final.adt --record /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-bnch-verifier-20261111/enabled/record.json --adt-sha256 2b0610759ada8fef1a8179841b80713f3336d0c76c0860b30101b4f4eb2d6b9b --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/owner-bnch-verifier-20261111/initializer --failure-controls
```

fresh checker 的输入/输出/hash 如表，执行解释器和exit0来自主控交付；fresh报告本身
不保存 command/exit字段，因此不声称本次从JSON恢复了不存在的完整历史argv。

### 直接与传递依赖

主控报告 fixture 及3直接依赖匹配 `out/image4-bnch-offline-20261110/matrix-reviewed.json`。
该现存文件记录 fixture SHA256 `fc2a83e38b7f1fc20c1ad0ae4f77e868fd8c5a95dd689223c8ff37e38311dc4e`，
直接依赖为 audit-image4-runtime-provider.py、build-kernel-entry-probe.py、nuwa_launch_context.py；
它不包含下述传递依赖的历史hash，不能补称历史匹配。

新绑定 `scripts/probe_bootstrap_sites.py` SHA256
`1ec9d2925a8d301080b8ae56dfd3178bd45c2cd8d502a567df16e6ff4976832f`，
tracked blob `0084cafbf1908fe9bfcb9f28b427a694c1badb99`，来源提交
`378a27b24318cc34e9b67b034ceccff8496fe774`（blob/来源由主控交付）。
review仅认可导入时定义/常量，未调用探针生成。
`out/owner-bnch-verifier-dependency-20261111/dependency.json` 实际记录
`__file__=/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/scripts/probe_bootstrap_sites.py`、
resolved_path_matches/sha256_matches=true、loaded_checker_fixture_chain_only=true、
run_initialize_called=false、exit0；此为新增独立绑定，不声称旧matrix已覆盖它。

### 下一动作与本次文档收尾

下一步是**单独 reviewer 受限诊断设计 → deep → 实现/包装/独立核验 → 申请设备授权**。
本主机里程碑不替代消费者范围/停止机制与包装审查，不改阶段等级，不自动产生上机入口。
本次文档核验仅运行 porting-record check 与 git diff --check；真实命令/退出在收尾报告列示，
文档更新本身标 self-checked，不把已获独立主机证据降回“待verifier”。
