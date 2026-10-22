# COMMIT-QUEUE

早期仅排队由宿主提交。用户于2026-10-22后续明确允许全部Git命令，允许将积压里程碑依次提交并发布到公开设备仓；以下保留每项历史描述，不把当时“未执行Git写入”的记载当成现行禁令。提交映射另记WORKLOG/证据，禁止改写既有提交。

## Q-001 · 49 补丁复跑

```text
[unixnu-nuwa][kernel] 复现8796补丁独立检查38通过11失败

[Change] 保留原始证据，新增49补丁复跑日志并补充可移植性报告，沿用D-006先适配8796的路线。
[Evidence] reports/patch-portability-8796-recheck/results.json；49项patch/sha256/exit_code与原记录差异为0；XNU检查前后status为空；报告docs/operations/2026-10-22-patch-portability-8796.md。
[Risk] 独立检查不代表累积应用、编译、ABI、QEMU或实机通过；feed未切换。
```

## Q-002 · 集成审查与 board 写入前硬停

```text
[unixnu-nuwa][docs] 明确只读基座集成约束并提交首版board审阅方案

[Change] 记录显式out目录、设备模块覆盖和Xcode工具链约束；规划独立uefi-nuwa目录，提交R-002最小board占位方案并在写入前硬停。
[Evidence] docs/operations/2026-10-22-readonly-base-integration.md；基座scripts/unixnu/config.py:66、tree.py:65、kernel.py:43；docs/NEED-REVIEW.md R-002。
[Risk] 远端最新提交与diff未取得；WSL构建、完整补丁集、donor预链接与板级数值未验证；未创建board或固件树，未执行Git写操作。
```

## Q-003 · 落地获批的 board 占位

```text
[unixnu-nuwa][device] 按R-002批准创建nuwa最小示例board

[Change] 创建与R-002候选A一致的board.toml，保留example=true、既定iPhone donor身份和ipad_identity=true；未知字段仅TODO，审批记录标为approved并落地。
[Evidence] 用户回复A；board.toml与docs/NEED-REVIEW.md获批TOML代码块逐字匹配（忽略末尾换行），仅9项赋值，无内存/地址或prelink数值。
[Risk] 仅为不可构建占位配置；IPSW组件、ADT、内存、bootimg和预链接未验证；未执行Git写操作或生成镜像。
```

## Q-004 · NativePrelink补充检查

```text
[unixnu-nuwa][kernel] 确认NativePrelink两项在8796独立静态检查通过

[Change] 新增只读NativePrelink检查脚本、逐补丁日志与审查报告，同时记录获批board的TOML语法解析结果。
[Evidence] reports/native-prelink-8796/results.json及两项patch.log；docs/operations/2026-10-22-native-prelink-8796.md；源树前后status为空。
[Risk] 原49项统计不变；累计应用、Darwin22接口、donor初始化地址、编译、QEMU及实机均未验证；feed未改。
```

## Q-005 · 第一批8796候选

```text
[unixnu-nuwa][kernel] 适配五项8796候选并识别PGZ探针对缺失API的依赖

[Change] 以只读源文件内存生成五个候选diff，保留原补丁哈希与逐项理由；记录PGZ probe虽可apply却引用8796缺失API的风险。
[Evidence] reports/xnu-8796-candidates/results.json；五项独立git apply --check返回0，源树前后status为空；docs/operations/2026-10-22-8796-context-candidates.md。
[Risk] 候选尚未接入完整xnu覆盖模块；其余适配、累计应用、Darwin22接口和编译未完成；feed及板级数值未改。
```

## Q-006 · 8796完整候选选择集与入口验证

```text
[unixnu-nuwa][kernel] 完成48项8796候选内存顺序检查及合并diff验证

[Change] 补齐public-entitlements、SystemOS和boot-progress适配，D-007明确两项不适用及PGZ探针延期；新增严格内存顺序模拟与最终合并diff审计，验证最小board可被基座status识别。
[Evidence] reports/xnu-8796-sequence/results.json：48项顺序模拟成功、51项基线模拟与Git独立结果无差异、合并diff的git apply --check返回0；reports/board-integration/status.log返回0；docs/operations/2026-10-22-8796-selected-sequence.md。
[Risk] 没有磁盘顺序应用、编译或ABI验证；候选未接入构建，feed未切换，board仍example；WSL工具链及驱动兼容性未验证。
```

## Q-007 · Darwin22接口审查

```text
[unixnu-nuwa][kernel] 记录8796产物与archive接口缺口及watchdog条件性覆盖风险

[Change] 新增只读接口审查脚本与证据，核对unstripped产物、Darwin23 archive生产者、13项boot-progress回调、watchdog和NativePrelink布局；记录非union环境路径与584字节watchdog policy的scratch覆盖算例。
[Evidence] reports/darwin22-audit/interfaces.json；docs/operations/2026-10-22-darwin22-interfaces-and-wsl.md；输入三树前后tracked status为空；kmod64静态模型156/180/188/196与预链接消费者一致。
[Risk] 只有静态接口审查与主机字符串/布局运算，未编译或验证完整ABI；archive与callback生产流程仍未适配nuwa，feed未改。
```

## Q-008 · WSL工具链门与R-003暂停

```text
[unixnu-nuwa][build] 判定当前WSL入口无法直接完成8796内核构建并提交路线审阅

[Change] 新增只读WSL工具/SDK清单及XNU内建预处理探测，记录现有Linux MIG/cctools与Python输入；R-003列出WSL交叉工具链和macOS构建例外两条路径及代价，按用户要求停止。
[Evidence] reports/darwin22-audit/wsl-toolchain.log：clang14三项XNU内建探测均0，xcrun/xcodebuild/IIG未配置；docs/operations/2026-10-22-darwin22-interfaces-and-wsl.md；docs/NEED-REVIEW.md R-003。
[Risk] 不代表WSL永久不可能构建XNU；完整内核编译、archive ABI、SDK输入及后续工具链路线未验证；未改feed或板值、未执行Git写操作、未生成镜像。
```

## Q-009 · R-003 A批准

```text
[unixnu-nuwa][docs] 按R-003批准保持WSL并启动工具链适配第一阶段

[Change] R-003标记approved A，恢复本仓工具链预检/适配工作；记录用户确认没有额外编译器、IIG或sysroot。
[Evidence] 用户本轮回复A及输入询问回复没有；docs/NEED-REVIEW.md R-003，docs/WORKLOG.md。
[Risk] 当前输入仍不足以构建内核；批准不包含工具安装、来源树写入、Git写操作、feed或board改动及镜像生成。
```

## Q-010 · WSL第一阶段入口与验证

```text
[unixnu-nuwa][build] 落地WSL工具链预检与8796非执行式适配计划

[Change] 新增主机工具profile、严格输入预检、MIG后端代码生成样例及8796适配计划；固定已有工具哈希，记录缺失的目标编译器扩展、IIG和sysroot输入。
[Evidence] reports/wsl-firststage/tests.log：9项测试通过；preflight.json：MIG后端及宿主C/C++语法样例通过，目标特征缺失；run.log中预检退出2；adapter-plan.json的executable=false。
[Risk] 预检与计划已落地但完整工具输入未齐；没有内核compile/link、完整ABI、QEMU或实机证据；feed、board和上游源树未改，未执行Git写操作。
```

## Q-011 · 官方CI与仓库结构核查

```text
[unixnu-nuwa][docs] 确认官方Actions使用基座fork并保持设备仓独立

[Change] 记录官方macOS build路线和三仓职责；对比75bc基座与缓存fb2bb快照的kernel/baseline差异，识别已有archive调度实现，准备官方CI接入范围。
[Evidence] https://unixnu.com/building#macos-runner 与官方sheng构建页；reports/official-ci-plan/local-comparison.json及两个diff；docs/operations/2026-10-22-official-ci-route.md。
[Risk] 缓存新快照不是当前远端最新证明；实际workflow源文件尚未核验，未fork/push/触发Actions，8796覆盖及ABI门仍未过，feed未改。
```

## Q-012 · 固定官方CI输入并生成工作流候选

```text
[unixnu-nuwa][build] 核验官方macOS工作流并准备固定工具链与失败证据候选

[Change] 新增只读API审计及候选生成器，核验e95b的workflow、archive/bootstrap和预链接入口；生成默认kernel、固定runner/Xcode并保留失败证据的工作流diff；记录wh1stl3与用户解除Git命令限制的后续授权。
[Evidence] reports/official-ci-plan/remote-audit.json：75个新增提交、完整tree差异491项；candidate-check.json：5个hunk内存精确匹配；docs/operations/2026-10-22-official-ci-route.md。
[Risk] 尚未安装workflow或触发CI，完整8796 compile/link、driver ABI与donor预链接未验证；GitHub CLI登录待完成，feed与board未改；不整体跟进新基座或继承旧48项结论到e95b。
```

## Q-013 · 创建远端仓库并准备8796源构建入口

```text
[unixnu-nuwa][build] 建立公开设备仓并准备固定75bc的8796源内核CI

[Change] 按用户后续Git授权和公开选择创建wh1stl3基座fork与设备仓；新增手动源内核工作流和基座配方适配入口，固定同一8796提交与48项补丁选择；沿用基座真实make/archive过程，保持feed及board不变。
[Evidence] reports/official-ci-plan/repository-setup.json；source-input-check.json：48项hash和适配后bash语法检查通过；ci/workflows/nuwa-8796-source.yml；docs/operations/2026-10-22-source-kernel-ci.md。
[Risk] 专用入口仅验证源编译/链接，可选设备archive与boot-progress关闭，尚无云端执行结果；donor预链接、完整ABI、QEMU及实机均未验证，未生成固件/启动镜像。
```

## Q-014 · 发布里程碑并启动源构建CI

```text
[unixnu-nuwa][build] 发布13项里程碑并启动首轮8796源内核Actions

[Change] 将积压里程碑分别提交并推送设备仓main，保存提交映射；在基座fork安装手动源构建workflow，新增只读CI跟踪器，修正发布脚本对原master分支名的假设。
[Evidence] reports/official-ci-plan/milestone-commits.json；基座workflow提交4e4c04aa4dec8dc2af48234e3e3faec9704c73cb；https://github.com/wh1stl3/UniXNU/actions/runs/39715232540，设备输入b745021。
[Risk] 此提交记录启动时状态，未取得完整内核构建结果；预链接、设备archive ABI、QEMU及实机未验证；feed/board未改。
```

## Q-015 · 首轮真实错误与clang17兼容补丁

```text
[unixnu-nuwa][kernel] 根据首轮CI移除过期clang开关并保留自动变量清零

[Change] 保存首轮实际主机/源码构建日志和失败分析；新增clang17兼容补丁，仅移除过期启用参数，保留-ftrivial-auto-var-init=zero；扩展CI输入与顺序检查，保留原48项统计。
[Evidence] reports/kernel-ci/39715232540/run.log:4503；toolchain.log；failure-analysis.json；compatibility-check.json：49项172 hunks精确检查通过；source-input-check.json：bash语法检查通过。
[Risk] 首轮完整内核构建失败；此修复尚待真实CI重跑，不代表Darwin22驱动或donor预链接通过，feed/board不变，无固件或设备动作。
```

## Q-016 · 第二轮固定输入与边界复核

```text
[unixnu-nuwa][build] 启动clang17修复后的第二轮源编译并复核来源边界

[Change] 新增限定仓库和完整device_ref的手动调度脚本，记录第二轮构建；更新README当前决策与设备仓入口，保存发布后三来源树和board/feed哈希检查。
[Evidence] https://github.com/wh1stl3/UniXNU/actions/runs/39716728005，device_ref=dbbf029d8c9893759f86d828507e309ade8d11eb；reports/official-ci-plan/post-publish-workspace-check.json。
[Risk] 记录时仍编译中，无内核链接成功证据；设备archive ABI、donor预链接、QEMU及实机未验证。
```

## Q-017 · UIO声明与IIG目标兼容候选

```text
[unixnu-nuwa][kernel] 保留UIO字节布局并以IIG生成目标适配Darwin22接口

[Change] 保存第二轮两类真实错误及IIG工具选项证据；把36处UIO数组改为保留原字节数和对齐的声明宏，设置IIG deployment-target 22.0候选，IORPC结构保持原样；记录用户GitHub持续授权。
[Evidence] 第二轮run.log:11187,16673；工具检查39717772747的iig-help.txt/options-strings.txt；compatibility-check.json：50项209 hunks精确顺序通过，清零与IORPC头不变。
[Risk] 第三轮实际IIG生成与完整内核编译/链接待验证；纯文本检查成功不是内核或实机通过，完整设备archive ABI仍未验证。
```

## Q-018 · 第三轮源构建启动

```text
[unixnu-nuwa][build] 以固定50项输入启动第三轮8796源构建

[Change] 记录UIO/IIG兼容候选发布及第三轮手动构建，继续使用75bc源码配方与既定8796提交。
[Evidence] reports/kernel-ci/39718507532/run.json；https://github.com/wh1stl3/UniXNU/actions/runs/39718507532；device_ref=4be1fb48c7389b61fba4a245f58e2bae4e2a9a62。
[Risk] 记录时仍在编译，尚无完整内核或ABI通过证据；feed/board不变，未运行预链接、QEMU或设备动作。
```

## Q-019 · 第三轮实际错误与内联RPC候选

```text
[unixnu-nuwa][kernel] 根据第三轮证据适配内联RPC并关闭缺失实现的性能采样

[Change] 下载第三轮证据并保存原始行号/哈希摘录；以真实五目标生成否证deployment-target候选；增加固定IIG叶子模板适配，保留IORPC原布局；源CI关闭KPC及依赖KPERF，记录D-010。
[Evidence] reports/kernel-ci/39718507532/diagnostics.txt原始行34853/99813；IIG短CI39722376512五目标同hash；compatibility-check.json为51项210 hunks；iig-adapter-check.json转换真实样本11块、拒绝未知模板；workspace-check.json确认来源与feed/board边界。
[Risk] 完整IIG生成集与内核编译/链接待下一轮；性能计数采样关闭，完整driver/donor ABI未验证；未生成固件/诊断镜像，预链接、QEMU与实机均未验证。
```

## Q-020 · 第四轮源构建启动

```text
[unixnu-nuwa][build] 发布第三轮修复并启动第四轮8796源构建

[Change] 记录7d6675e已推送和第四轮精确输入，更新当前状态及跟踪方式；原始大控制台保留out而提交摘录，避免旧观察器下载大日志阻塞。
[Evidence] reports/kernel-ci/39723011018/run.json；https://github.com/wh1stl3/UniXNU/actions/runs/39723011018；device_ref=7d6675ee49578eac2b02c5b65a0ac42b29dc1fd4；主机/依赖/输入检查成功，编译进行中。
[Risk] 尚无第四轮完整编译/链接结果，内联RPC适配不是完整ABI验收；feed/board不变，预链接、QEMU及实机未验证。
```
