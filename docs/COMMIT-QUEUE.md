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

## Q-021 · 完整IIG模板候选与发布兜底

```text
[unixnu-nuwa][kernel] 按完整生成证据补入旧RPC回调规则并保留未知模板失败边界

[Change] 保存第四轮主动拒绝的错误和全17个IIG定义生成证据；仅识别移除旧IORPC不需要的新字段回调赋值，未知模板继续失败；云端保留失败源码；增加对象ID一致、force=false的API发布兜底。
[Evidence] reports/kernel-ci/39723011018/diagnostics.txt原始行226；callback-template.txt原始行809；短CI39723294640生成17文件exit0，iig-all-adapter-check.json静态转换432块、字段声明保留；api-publish-previous.json已发布同一7dfa3c1。
[Risk] 全集转换不等于真实内核编译/ABI通过，性能采样关闭；feed/board不变，无预链接、镜像、QEMU或设备动作。
```

## Q-022 · 第五轮源构建启动

```text
[unixnu-nuwa][build] 发布完整模板适配候选并启动第五轮源编译

[Change] 记录4313f2d按相同Git对象经API发布和第五轮精确设备输入，更新STATUS与证据下载入口。
[Evidence] reports/kernel-ci/39723736387/api-publish.json确认force=false及相同commit；run.json；https://github.com/wh1stl3/UniXNU/actions/runs/39723736387，device_ref=4313f2d1c1a5abd9f96d11073b2e343b8aedadfe。
[Risk] 运行中，无完整内核编译/链接或ABI通过结论；feed/board不变，无预链接、镜像、QEMU或设备动作。
```

## Q-023 · 第五轮证据与AST条件修复

```text
[unixnu-nuwa][kernel] 根据第五轮真实错误保护关闭KPERF时的AST接口

[Change] 下载第五轮证据并保留原始行号和大日志hash；仅给ast.c性能采样头和AST处理块增加KPERF条件，继续关闭缺失公开实现的性能采样。
[Evidence] reports/kernel-ci/39723736387/diagnostics.txt原始行253481/253484；build.json的51个IIG实现无kernelContent残留；compatibility-check.json为52项212 hunks通过，单项git apply --check及bash语法检查通过；workspace-check.json确认来源/board/feed不变。
[Risk] 修复待第六轮真实编译和链接；581个.o是全部build目录合计，尚无完整内核、driver/donor ABI、QEMU或实机通过结论；无镜像或设备操作。
```

## Q-024 · 第六轮源构建启动

```text
[unixnu-nuwa][build] 发布AST修复并启动第六轮8796源构建

[Change] 记录db30d6d已发布与第六轮精确设备输入，继续观察真实编译及链接结果。
[Evidence] reports/kernel-ci/39733594660/run.json、api-publish.json；https://github.com/wh1stl3/UniXNU/actions/runs/39733594660；device_ref=db30d6d13d5f5fabc3a110d535b1ce3b658c28d5，主机/依赖/输入检查成功。
[Risk] 尚无第六轮最终结果，启动及输入检查不代表内核、ABI或实机通过；feed/board不变。
```

## Q-025 · 第六轮证据与定时器表条件修复

```text
[unixnu-nuwa][kernel] 对齐关闭KPERF时的定时器枚举与回调表边界

[Change] 保存第六轮真实失败证据，给processor.c的性能采样表项增加与枚举相同的KPERF条件，保留长度断言；下一轮记录精确XNU目标对象数及关键对象哈希。
[Evidence] reports/kernel-ci/39733594660/diagnostics.txt原始行352764/352771/352784；timer_call.h:211-217；compatibility-check.json为53项213 hunks通过，单项git apply --check及配方语法检查通过。
[Risk] AST旧错未再观察到但本轮无该对象产物清单；完整编译/链接待第七轮，driver/donor ABI、QEMU及实机未验证；feed/board不变，无镜像或设备动作。
```

## Q-026 · 第七轮源构建启动

```text
[unixnu-nuwa][build] 发布定时器表修复并启动第七轮源构建

[Change] 记录484b97c已发布与第七轮精确输入，继续跟踪最终编译和链接结果。
[Evidence] reports/kernel-ci/39734939751/run.json、api-publish.json；https://github.com/wh1stl3/UniXNU/actions/runs/39734939751；device_ref=484b97c57fc2be0a6b5b0455bcca44b5246e0278。
[Risk] 记录时仍运行中，尚无完整编译/链接或ABI成功证据；feed/board不变，无镜像或设备动作。
```

## Q-027 · 第七轮证据与关闭性能模块的剩余入口

```text
[unixnu-nuwa][kernel] 对齐任务字段及调度跟踪对关闭性能模块的条件边界

[Change] 保存第七轮真实错误和关键目标对象证据，给t_kpc初始化加与结构相同的KPC条件；根据同类源码审查保护scheduler/KTRACE剩余引用，保留量子定时器、KDEBUG和断言；完善链接日志取证。
[Evidence] reports/kernel-ci/39734939751/diagnostics.txt原始行404291；build.json包含ast.o/processor.o实际路径和哈希；related-kperf-calls.json；next-compatibility-check.json为56项222 hunks通过，配方语法检查通过。
[Risk] scheduler/KTRACE是源级发现，不是已确认的第七轮链接错误；完整编译/链接待第八轮，性能采样仍关闭，driver/donor ABI、QEMU与实机未验证；feed/board不变，无镜像或设备动作。
```

## Q-028 · 第八轮源构建启动

```text
[unixnu-nuwa][build] 发布关闭性能模块的剩余条件修复并启动第八轮

[Change] 记录8dd1b52已发布和第八轮精确输入，跟踪实际编译和链接结果。
[Evidence] reports/kernel-ci/39736351595/run.json、api-publish.json；https://github.com/wh1stl3/UniXNU/actions/runs/39736351595；device_ref=8dd1b52e6d10a633f9248e4d54a3ce1f09cb1eff。
[Risk] 记录时仍在运行，未取得完整内核或ABI成功证据；feed/board不变，无镜像或设备动作。
```

## Q-029 · ARM64上下文关闭KPC边界

```text
[unixnu-nuwa][kernel] 保护关闭KPC时的ARM64上下文回调并批量重跑

[Change] 根据源码审查给arm64/pcb.c的性能计数头与两处回调加KPC条件，保留原pmap及上下文切换；请求取消第八轮以合并已确认缺口，取消结果不当作验证。
[Evidence] reports/kernel-ci/39736351595/kpc-context-review.json：调用行183/519及optional kpc实现定义；cancel-request.json；next-compatibility-check.json为57项225 hunks通过，配方hash/bash语法检查通过。
[Risk] 新候选尚待实际编译；源码缺口不冒充已观察到的链接错误，取消不算成功或失败验证；feed/board不变，无镜像、设备动作或_verified=true。
```

## Q-030 · 第八轮取消确认与第九轮启动

```text
[unixnu-nuwa][build] 确认第八轮取消并以完整条件修复启动第九轮

[Change] 保存第八轮cancelled最终状态，发布4dd55f0并启动第九轮57项输入；重写当前STATUS，区分实际错误、源码审查和取消结果。
[Evidence] reports/kernel-ci/39736351595/run.json、cancel-request.json；reports/kernel-ci/39736926012/run.json、api-publish.json；https://github.com/wh1stl3/UniXNU/actions/runs/39736926012，device_ref=4dd55f0ec8c72e08946c6f597bb3ca3389b65dbd。
[Risk] 第九轮最终编译/链接未验证，取消不是构建验收；完整driver/donor ABI、QEMU及实机未验证，feed/board不变。
```

## Q-031 · HackiOS用户报告与原始来源核验

```text
[unixnu-nuwa][docs] 归档HackiOS开源对照报告并核验可复用边界

[Change] 收录用户提供报告及来源哈希，读取固定提交公开实现，区分真实源码、IIG替代/类型描述降级、PMU不可用行为与可返回加载器；保持当前基座和验收边界。
[Evidence] docs/operations/2026-10-22-hackios-reference-review.md；reports/hackios-review/原始来源hash和短摘录；kernel 8e611870、userland 906425b固定提交。
[Risk] 未执行上游代码或独立复现实机，不推导nuwa硬件、完整RPC或供体ABI通过；报告建议不作执行指令，无板值、feed、镜像或设备修改。
```

## Q-032 · 第九轮链接证据与可选display调用条件

```text
[unixnu-nuwa][kernel] 对齐可选display probe调用与archive构建开关

[Change] 保存第九轮到达最终链接的真实证据，仅给bsd_init中的可选Legacy provider调用加已有构建条件；保留archive要求和完整链接错误检查；记录D-011和原始kernel存在性/hash证据。
[Evidence] reports/kernel-ci/39736926012/diagnostics.txt原始行851223-851227只有native_legacy_display_probe未解析；baseline:319,600-614；next-compatibility-check.json为58项226 hunks通过，配方语法检查通过。
[Risk] 完整make/链接仍失败，修复待第十轮，目标841个.o不含.cpo；driver/donor ABI、QEMU及实机未验证，feed/board不变，无镜像或设备操作。
```

## Q-033 · 第十轮源构建启动

```text
[unixnu-nuwa][build] 发布display条件修复并启动第十轮完整源构建

[Change] 记录526651a发布和第十轮精确58项输入，继续取完整make、链接与原始Mach-O证据。
[Evidence] reports/kernel-ci/39738601892/run.json、api-publish.json；https://github.com/wh1stl3/UniXNU/actions/runs/39738601892；device_ref=526651af94610f40c3223eae9550deaa3c44ae57。
[Risk] 最终构建结果未验证；源构建不是预链接、完整driver ABI或实机通过，feed/board不变，无镜像或设备动作。
```

## Q-034 · 8796源内核完整构建成功

```text
[unixnu-nuwa][build] 确认8796源内核完整构建成功并核验下载产物

[Change] 保存第十轮最终success和真实产物元数据，加入只读Mach-O/版本/NativePrelink标记检查，更新源构建完成与设备接口待办边界。
[Evidence] CI39738601892完整配方和链接成功；reports/kernel-ci/39738601892/acceptance.json与kernel-inspection.json：20,136,488字节、SHA bdaad81373d00df8334cb5a453b32f06a5e607c3e7d8cde812e4f5f927e19ced，8796.141.3/Darwin22.6.0，未解析符号0，两项标记1；board/feed哈希不变，来源树tracked状态空。
[Risk] BCM2837源CI关闭性能采样及可选设备archive；WSL本机、driver/RPC ABI、donor预链接、完整nuwa启动/QEMU/实机未验证；无诊断/固件镜像生成、设备动作或_verified=true。
```

## Q-035 · 真实编译记录与Darwin22平台archive候选

```text
[unixnu-nuwa][build] 补实际编译记录并独立构建Darwin22平台archive

[Change] 仅在C/C++真实编译中追加Clang记录；用本轮原命令构建ArmCpu/ArmDTPlatform/ArmVirtPlatform库，清除原对象及依赖输出副作用，记录格式/哈希/ar成员和符号闭包，扩充CI产物收集。
[Evidence] reports/driver-archives-plan/：59项228 hunks精确顺序、输入hash及配方语法检查通过；3项参数保护测试通过；固定基座三来源文件hash和原消费路径；D-012及本轮操作文档。
[Risk] 实际fragment、archive编译及符号闭包待CI，完整C++/donor ABI和硬件未验证；不接入board或重新链接带库内核，feed/板值不变，无诊断/固件镜像、设备动作或_verified=true。
```

## Q-036 · 第十一轮Darwin22平台archive构建启动

```text
[unixnu-nuwa][build] 发布真实编译记录候选并启动平台archive验证

[Change] 保存设备ccaad74发布、workflow唯一收集路径变更及第十一轮精确输入，继续跟踪实际记录与库构建结果。
[Evidence] reports/driver-archives-plan/workflow-install.json：base fork提交02daabcb、前后模板逐字核验；reports/kernel-ci/39742250205/；https://github.com/wh1stl3/UniXNU/actions/runs/39742250205，device_ref=ccaad74d8862a060efbed259a1335f4a79258f04。
[Risk] 本轮尚运行，fragment和archive未验证；第十轮源内核成功不等于完整设备ABI/实机；feed/board不变，无诊断/固件镜像、设备动作或_verified=true。
```

## Q-037 · 并行仓三件产物可用性与接入方案

```text
[unixnu-nuwa][docs] 核验并行仓三件真实产物并明确接入缺口

[Change] 只读校验run24内核、53MB预链接和3MiB固件及输入哈希，独立核对donor manifest，重放本仓只读plan并定位VFS缺口；给出复用成果和启动闭环的具体路径。
[Evidence] reports/parallel-progress-review/：candidate及FD哈希匹配，VFS函数与10063上游定义一致，本仓plan实际缺_vfs_getvfs_with_vfsops；实际配置清空、4项UEFI预检错误及12处豁免中4处ADRP均有来源；操作报告列出验收门槛。
[Risk] 现有三件不证明nuwa启动/桌面；false资格标记为工具默认未验收，不当作emit失败；DarwinBoot集成未验证，未运行对方脚本或修改其目录，未生成镜像或操作设备，feed/board不变。
```

## Q-038 · 第十一轮真实编译记录与平台首错

```text
[unixnu-nuwa][build] 取得真实编译记录并清除平台命令中无效libsa路径

[Change] 保存第十一轮源内核成功和933份记录计数，收录四项真实fragment/原对象及平台首错；仅在精确libsa目录不存在时移除该搜索项，记录移除路径，保留其余检查。
[Evidence] reports/kernel-ci/39742250205/：kernel_built=true、四项记录及原对象通过，原始行852093为-Werror,-Wmissing-include-dirs；4项参数保护测试通过，未知缺失目录仍保留；提取器保存有界附加证据。
[Risk] ArmCpu对象及后续两库尚未构建通过，修复待重跑；符号闭包/完整ABI/预链接和实机未验证；feed/board不变，无诊断/固件镜像、设备动作或_verified=true。
```

## Q-039 · 第十二轮平台archive验证启动

```text
[unixnu-nuwa][build] 发布无效搜索目录修复并启动第十二轮验证

[Change] 保存562c22f发布和第十二轮精确输入，保持59项补丁及严格平台archive检查，继续按实际首错推进。
[Evidence] reports/kernel-ci/39744948467/run.json和api-publish.json；https://github.com/wh1stl3/UniXNU/actions/runs/39744948467，device_ref=562c22fda45118f46b450390045a53b5a739f981。
[Risk] 本轮最终结果尚未验证，VFS与完整驱动/预链接ABI仍有待办；feed/board不变，无诊断/固件镜像、设备动作或_verified=true。
```

## Q-040 · donor指针表清点与真实VFS桥接

```text
[unixnu-nuwa][kernel] 清点真实donor绑定并回移唯一缺失的VFS接口

[Change] 加入只读完整指针表清点，回移真实VFS函数/声明/导出并独立计数donor候选，保留原版本/板级边界。
[Evidence] reports/donor-compat/：65,348项计数与参考报告一致，本仓1缺失而run24为0；函数及lookup锁/引用语义与上游一致，唯一声明/导出及60项231 hunks和配方静态检查通过。
[Risk] VFS候选实际编译/目标导出待下一轮；指针名清点不验收布局/PC-relative/完整ABI或硬件，组件选择仅供分析；feed/board不变，无预链接镜像生成、设备动作或_verified=true。
```

## Q-041 · 第十二轮平台诊断与导出声明

```text
[unixnu-nuwa][build] 补平台导出声明并明确旧头文件风格诊断边界

[Change] 保存第十二轮真实26条诊断及源内核/记录成功证据；补五项匹配实际定义的ArmCpu前置声明，仅三项风格诊断保留为可见警告，其他-Werror及原型检查继续保留。
[Evidence] reports/kernel-ci/39744948467/：原始行852100起，11/9/1条旧初始化及override风格、5条missing-prototypes；prototype-check.json及4项命令保护测试通过；libsa路径修复已实际生效。
[Risk] 新声明/诊断策略与60项下一输入尚待实际archive编译；不更改结构/初始化/硬件实现，完整ABI/预链接/实机未验证；feed/board不变，无镜像生成或_verified=true。
```

## Q-042 · 第十三轮平台与donor接口验证启动

```text
[unixnu-nuwa][build] 发布平台声明修复并启动含VFS桥接的第十三轮

[Change] 保存ff8abe1发布和第十三轮精确60项输入，分开跟踪源内核、平台archive和donor绑定证据。
[Evidence] reports/kernel-ci/39747264803/run.json及api-publish.json；https://github.com/wh1stl3/UniXNU/actions/runs/39747264803，device_ref=ff8abe167a039560c816892b78b00660b5518888。
[Risk] 当前启动不是archive或完整ABI验收，实际编译/链接及donor计划仍待取证；feed/board不变，无预链接/固件镜像生成或设备动作。
```

## Q-043 · donor外部编码与已有候选字节核对

```text
[unixnu-nuwa][kernel] 清点donor外部编码并核对已有候选代码保持

[Change] 新增只读完整PC-relative清点，核对9个完整常量池和参考候选30段可执行字节；纠正前次豁免原因计数键名误读，保留未知站点拒绝。
[Evidence] reports/donor-compat/pc-relative-inventory.json：236,910内部编码、12外部/4ADRP，集合与参考完全一致；4,201,824字节逐段同hash，官方首拒绝0xfffffff005b8c1cc；实际为6窗口外/6入口oracle。
[Risk] 字节保持和指纹不证明12处代码/数据分类、目标语义、完整ABI或实机；只读既有文件，未调用emit或生成镜像，feed/board及_verified不变。
```


## Q-044 · 参考boot过程与真实driver/donor接口

```text
[unixnu-nuwa][kernel] 复核参考boot链路并补真实平台复位声明

[Change] 只读核对并行boot及过程文档，划清容器与loader证据；保存CI13真实内核/ArmCpu archive及零缺失donor绑定/官方只读plan，补ArmDTPlatform不返回声明。
[Evidence] reports/parallel-progress-review/boot-*核对203157504字节镜像及五项hash，实际run3761554；reports/kernel-ci/39747264803首错原始行852588、源内核08c23dc、ArmCpu archive42350fb；reports/donor-compat/ci13-*为65348绑定零失败和119段只读布局通过，4项命令保护测试通过。
[Risk] 参考FD加载器集成无证据，12处指令/完整ABI未验收；新声明待下一轮真实平台编译，三库未全部通过或接回内核；feed/board不变，无镜像生成、设备操作或_verified=true。
```


## Q-045 · 第十四轮平台声明验证启动

```text
[unixnu-nuwa][build] 发布参考链路审查和平台声明并启动第十四轮

[Change] 保存2b02285相同Git对象非强制发布及第十四轮精确输入，继续真实平台archive验证。
[Evidence] reports/kernel-ci/39750542014/run.json与api-publish.json；https://github.com/wh1stl3/UniXNU/actions/runs/39750542014，device_ref=2b02285b806dfa2e6a9592d1347ea6542cb8aba1。
[Risk] 当前仅已触发，三个archive完整闭包及新声明真实编译待取证；feed/board不变，无新镜像、设备操作或_verified=true。
```


## Q-046 · 三库成功取证与真实平台链接门

```text
[unixnu-nuwa][build] 验收第十四轮三库编译并接入两库真实重链接审查

[Change] 保存CI14实际成功证据和开源驱动固定来源，记录原make参数并仅追加ArmCpu与ArmDTPlatform真实archive，保留全部运行/编译开关与provider边界。
[Evidence] reports/kernel-ci/39750542014下载内核29810101与runner一致，三库编译和符号名闭包通过；reports/driver-reuse为固定来源与7项命令保护测试、60项源输入静态检查。
[Risk] 下一重链接仍待实际CI，完整ABI/时钟/crypto与硬件未验证；feed/board不变，无预链接/固件镜像或_verified=true。
```


## Q-047 · 第十五轮真实平台链接启动

```text
[unixnu-nuwa][build] 发布两库重链接审查并启动第十五轮

[Change] 保存ca8db30同Git对象非强制发布及第十五轮精确输入，跟踪真实源内核和平台链接。
[Evidence] reports/kernel-ci/39755850870/run.json与api-publish.json；https://github.com/wh1stl3/UniXNU/actions/runs/39755850870，device_ref=ca8db300bf68ebc4853e023f08b920da0eab5de0。
[Risk] 本轮真实链接结果待取证，完整ABI/硬件未验证；feed/board不变，无镜像生成或_verified=true。
```


## Q-048 · 实机Android驱动取证与源码筛选

```text
[unixnu-nuwa][device] 只读确认ST触控和活跃面板并固定匹配开源来源

[Change] 增加白名单ADB采集与Android绑定/DT证据，核对MiCode nuwa DT和LineageOS SM8550 fts_spi源码；排除虚拟Goodix、旧I2C版本及DT默认面板误判。
[Evidence] reports/android-driver-evidence/20261022T092529Z为st,spi/fts_touch_spi、运行态m2_38_0c_0a、Adreno740v2/KIOXIA及采集前后boot_completed=1；reports/driver-reuse/st-spi-source-crosscheck.json与MiCode固定提交对照。
[Risk] 当前Android内核为自定义版本，公开源码不是已证明的精确模块输入；芯片修订/时序、GPL源移植边界和XNU运行未验证；feed/board不变，无写入设备、镜像生成或_verified=true。
```


## Q-049 · 第十五轮平台真实链接成功

```text
[unixnu-nuwa][kernel] 确认两平台库真实链接并复核新内核donor绑定

[Change] 保存CI15最终成功证据、真实make参数及下载内核/archives独立核对，更新主线到运行provider与时钟/启动条件；补UFS本机DT与UniXNU源的静态对应。
[Evidence] reports/kernel-ci/39755850870为20,187,888字节SHAa9e08c69、五平台导出、零undefined、make退出0；reports/donor-compat/ci15-kernel-bindings.json为65,348绑定零失败，来源树tracked clean和feed/board hash不变。
[Risk] ARCH_TIMER等运行开关仍保持原范围，crypto/pthread、完整布局/PC-relative/ABI及硬件未验证；Android观测不是XNU实机通过，无新镜像或_verified=true。
```


## Q-050 · 加载器源码接线与原厂内存证据

```text
[unixnu-nuwa][loader] 接入四模块加载器候选并隔离参考内存策略

[Change] 固定CI15双平台库内核，准备BootShim长度和nuwa四模块接线补丁，裁剪sheng只读initrd发布器；独立提取原厂配置并记录与参考C表的差异。
[Evidence] reports/loader-integration含75项静态检查、两来源树git apply --check退出0、8342字节原文及来源hash；config/loader-candidate.json固定所有输入，board/feed不变。
[Risk] 固件编译/分派、initrd映射保留、动态内存语义、XNU运行provider及预链接ABI未验证；无新镜像或设备动作，后续生成停于R-004。
```


## Q-051 · 获批的受限固件构建入口

```text
[unixnu-nuwa][firmware] 按R-004 A接入独立EFI与FD构建流程

[Change] 记录用户批准，固定三个来源与跨平台LF哈希，在Actions临时树应用接线补丁并直接构建四模块EFI、FD和BootShim，始终归档日志与批准范围内产物。
[Evidence] config/firmware-ci-inputs.json、.github/workflows/firmware-candidate.yml、scripts/ci/build-firmware-candidate.py；Python语法及workflow结构检查通过。
[Risk] 真实编译/模块产物检查待CI，运行/内存所有权未验证；不打boot.img、不生成预链接或负载、不改board/feed或操作设备。
```


## Q-052 · 首轮固件取证与入口HOB修复

```text
[unixnu-nuwa][firmware] 补齐首轮缺失的SEC入口HOB生产链

[Change] 保存第一轮真实失败及BootShim成功产物证据，复用固定sheng的DEC和SEC入口HOB实现；增加下载FD嵌套FV/PE/DEPEX与shim机器码检查器。
[Evidence] reports/firmware-ci/39761427579首错error4000、112字节shim及3145728字节拷贝计数；83项源码静态检查、8项格式检查与入口补丁apply检查通过。
[Risk] EFI/FD实际编译仍待第二轮，缓存/DT/内存生命周期及硬件未验证；R-004 A内继续，不打boot.img、不改板值、不操作设备。
```


## Q-053 · 固件CI跨平台换行修复

```text
[unixnu-nuwa][build] 按第二轮证据归一化精确SEC补丁目标换行

[Change] 记录第二轮输入通过后的CRLF应用错误，仅云端补丁目标转换LF并保存前后hash，保留严格apply；扩展SEC与发布器HOB GUID产物检查。
[Evidence] reports/firmware-ci/39762744079包含failure、commands、输入hash和最终run；源码语法检查通过，首轮BootShim证据保留。
[Risk] 第三轮真实编译待运行，EFI/FD尚未通过；R-004 A边界不变，不改board/feed/内存表、不打boot.img或操作设备。
```


## Q-054 · 固件构建与下载静态验收完成

```text
[unixnu-nuwa][firmware] 四EFI及nuwa FD和BootShim实际构建并通过静态审计

[Change] 归档第三轮成功证据及产物hash，修正检查器遗漏的Mu PCD库DEPEX并验证对应提供者；完成R-004 A并记录可恢复fastboot条件下的后续镜像授权。
[Evidence] CI39764322744输入a8425b3成功，665份下载文件hash一致，四EFI内嵌/独立一致，SEC-HOB/PCD/FV/PE/shim通过；四项负向检查均拒绝异常。
[Risk] 未QEMU/实机、未包含XNU负载或生成boot.img；缓存/DT/initrd/map/复位仍未验证，board/feed不变，未置_verified=true。
```


## Q-055 · 恢复与映射核对及固件入口包准备

```text
[unixnu-nuwa][loader] 验证原厂临时恢复并准备nuwa v4固件入口包

[Change] 增加多设备身份门、DT/initrd静态审计和哈希锁定v4打包；归档fastboot/A槽及原厂boot临时恢复证据，记录授权内方案与未验收条件。
[Evidence] nuwa unlocked=yes，原厂ef558db2临时启动回Android boot_completed=1，当前boot/init_boot与原始hash一致；候选3153920B/SHA12864ac6，原v4头仅kernel_size变化、内嵌FD一致。
[Risk] A槽持久启动与硬挂按键恢复未验收；新固件包未执行，DT物理放置/生命周期及DXE未验证；无新增XNU/FAT、未flash/改槽位或board/feed，未置_verified=true。
```


## Q-056 · 外部驱动来源报告复核

```text
[unixnu-nuwa][docs] 纠正驱动报告的触控品牌与复用判据

[Change] 只读核对外部报告并保存来源hash，明确ST FTS SPI方向、官方sheng GPU状态、可选feeds解析及UFS/显示运行门槛；保留可用索引。
[Evidence] 本机st,spi/fts_touch_spi/st_fts_m2.ftb与固定LineageOS ST源一致；base75bc13d feeds解析支持device/base目录，官网2026-10-22列sheng GPU/Metal可用。
[Risk] 官网sheng支持不等于nuwa或Darwin22通过；面板/PHY/DMA/ABI仍未验证，本轮未改feed/board/源树或执行设备动作。
```


## Q-057 · r6重打包与接受条件复核

```text
[unixnu-nuwa][loader] 验证v1重打包修正并隔离参考旧负载风险

[Change] 增加仅RAM模板审计，复现gzip OS和32B ID差异，核对旧FAT内容及新FD布局试算；记录脚本边界缺口和v4实际恢复反例。
[Evidence] r6模板ed8c4015原ID与AOSP一致，同FD仅0x1009及ID前20B变化；原FAT旧内核e3cfe478、timeout3/default xnu、ADT6GiB，新FD投影总长203194368B。
[Risk] Booting OKAY不验收UEFI，参考测试未证明唯一版本/ramdisk阈值；本轮无新镜像/设备动作，未继承旧负载、未改board/feed或_verified。
```


## Q-058 · v4候选首次临时实机启动与完整恢复

```text
[unixnu-nuwa][firmware] 记录v4命令接受与黑屏并完成原厂临时恢复

[Change] 增加哈希/身份门的单候选临时启动与恢复脚本，归档屏幕和USB观测及原厂恢复两次结果，记录R-006实施与D-016状态隔离。
[Evidence] SHA12864ac6候选Sending/Booting OKAY、15次采样fastboot持续可见、用户报黑屏；同一原厂boot首次Load Error，重进bootloader后成功且最终nuwa Android boot_completed=1。
[Risk] BootShim/SEC/DXE/BDS均未验证，ACK不等于执行；未flash/改槽位或镜像/board/feed，未置_verified，A槽持久启动和H-001仍未验收。
```
