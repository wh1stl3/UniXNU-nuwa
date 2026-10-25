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


## Q-059 · 同设备协作暂停

```text
[unixnu-nuwa][docs] 按用户要求暂停本仓全部实机访问

[Change] 将全部ADB/fastboot/USB查询暂停写入当前状态，只继续离线分析和Git同步，用户明确恢复前不执行原有长期设备授权。
[Evidence] 用户明确另一轮开始推包并要求不要实机操作；本仓设备命令均已结束，最后Android=1为20:19恢复记录，Q-058已推送。
[Risk] 暂停后当前设备状态未知，不用历史恢复结果替代当前状态，不自动轮询或抢占恢复。
```


## Q-060 · ARM64与SEC入口离线审查

```text
[unixnu-nuwa][firmware] 离线核对BootShim入口并确认SEC日志仅走帧缓冲

[Change] 增加只读产物/源码审计，核对ARM64头、拷贝机器码、FD→TE→SEC及日志掩码/实现，列出交接/cache与早期观测待测项。
[Evidence] 33项静态断言通过，实际FD分支和TE/map指向0xa710a838并保存x0；构建报告链接FrameBufferSerialPortLib和Null DebugAgent，归档ABL仅解压到RAM查看路径字符串。
[Risk] 实际L/EL/MMU/cache与DT可达性仍未验证，屏幕日志不能定位黑屏阶段；设备暂停保持，无设备访问、新镜像、板值/feed或_verified改动。
```


## Q-061 · 非显示日志通道离线评估

```text
[unixnu-nuwa][docs] 确认USB日志导出接口并限定早期故障覆盖范围

[Change] 比较USB CDC、早期RAM补发、UART和文件日志，列出Mu开源日志组件及安全缓冲区/USB功能接线待办。
[Evidence] nuwa DXE配置和CI39764322744打包记录包含高通USB设备驱动，协议头提供Start/Send/HandleEvent；当前SEC仍链接帧缓冲输出。
[Risk] USB导出尚未实现或实机验证，DXE前挂死不能保证回收；RAM地址/生命周期与UART路由仍TODO，无设备访问、新镜像或board/feed改动。
```


## Q-062 · 官方全站结构与路线复核

```text
[unixnu-nuwa][docs] 遍历官方文档并补充Darwin22加载器与USB日志检查项

[Change] 增加站点遍历/发布路由交叉检查与LP64头布局比较，记录72页导航、相关源码固定引用和nuwa分阶段推进顺序。
[Evidence] 全部72中文页HTTP200且144路由清单中中文遗漏0；8796头608B命令行与DarwinBoot1024B导致尾字段偏移不同；找到SM8550 vermeer CDC及sheng UFS/Linux日志实现。
[Risk] CI15编译类型、完整ABI和本机USB均未验证，其他机型/P16或虚拟机结果不作nuwa验收；feed/board/版本及实机暂停不变，没有新镜像。
```

## Q-063 · 上游合并与实际Darwin22类型核对

```text
[unixnu-nuwa][build] 合并UniXNU主分支并确认CI15实际boot_args布局

[Change] 将固定上游5fdbd5d合入fork并保留nuwa工作流及设备补丁，增加完整树和DWARF审计，记录实机访问恢复。
[Evidence] fork合并76dd641的589条树等于上游加3份原工作流，28份patch哈希和feed不变；UUID匹配的CI15三个编译单元均为608B命令行与0x2e0结构。
[Risk] 合并版尚未构建，历史CI仍固定75bc；Darwin22加载器修复和运行ABI未验证，本轮未访问设备或生成镜像。
```

## Q-064 · Darwin22加载器ABI修正

```text
[unixnu-nuwa][loader] 统一Darwin22的608B命令行布局与复制边界

[Change] 增加设备专用BootArgs补丁并接入候选清单，按应用后哈希保护两个修改文件，扩展三来源虚拟接线审计。
[Evidence] 原基线git apply检查及最新模块RAM上下文通过；AArch64真实EDK头布局与CI15全部成员偏移一致，89项接线检查和两版各10例宿主ASan/UBSan边界用例通过。
[Risk] 完整模块和运行ABI未验证；PIE宿主一次无诊断139已保留，非PIE测试通过不证明根因；未生成新固件、访问设备或修改board/feed。
```

## Q-065 · 合并版内核构建profile

```text
[unixnu-nuwa][build] 固定合并版模块并保留8796补丁的独立CI入口

[Change] 新增76dd固定profile与独立内核工作流，保留旧基线默认入口和两份变化挂载patch的8796字节，增加完整树/blob及真实适配函数审查。
[Evidence] 原48项顺序RAM应用通过，46份上游未变，两份新上游对8796独立git检查失败；60项适配输入哈希及Bash语法、旧基线检查通过。
[Risk] 新模块真实编译/链接和运行ABI待CI；未改feed/board、生成固件/boot镜像或访问设备，不把静态检查当实机通过。
```

## Q-066 · CI调度与完整加载器C语法检查

```text
[unixnu-nuwa][loader] 核对两版完整DarwinBoot语法并记录合并版CI排队

[Change] 扩展真实头文件下的完整C翻译单元检查，记录39793231214调度与固定设备输入，更新下一轮取证入口。
[Evidence] 两版完整DarwinBoot.c均通过AArch64 clang语法检查；新CI固定device_ref=3a210b1，查询为queued且steps为空，尚无编译结果。
[Risk] 未完成EFI库链接/打包或运行ABI验收；合并版内核仍待runner与真实构建，未生成固件或访问设备。
```

## Q-067 · 独立固件仓与源历史导入准备

```text
[unixnu-nuwa][firmware] 创建独立uefi-nuwa并隔离源历史导入

[Change] 创建公开固件仓并关闭其Actions，增加仅bare Git历史传输任务和既有固件源码迁入脚本，保留同网络enuma。
[Evidence] GitHub仓库创建记录及Actions关闭；fork API返回已有enuma时名称断言中止，固定Mu基线/上游main并在源码脚本检查原始blob和patch哈希。
[Risk] 源历史尚待导入，临时import secret结束后须删除；固件仓尚未编译或实机验证，不生成镜像或改板值。
```

## UEFI-001 · 独立固件源码已云端提交0a3a51a

```text
[unixnu-nuwa][firmware] Own the pinned nuwa UniXNU firmware integration

[Change] Apply reviewed shim, loader wiring and SEC HOB changes; import the read-only initrd publisher.
[Evidence] Device patch hashes and upstream blobs checked; memory maps and module GUID retained.
[Risk] Source migration only; no firmware build, boot image or hardware execution.
```

## Q-068 · 固件仓源码接线与本地检出

```text
[unixnu-nuwa][firmware] 接入独立固件仓并补齐可独立使用的本地检出

[Change] 固定uefi-nuwa的0a3a51a并接入dedicated构建profile，保留legacy与历史patch；建立D:/Code/uefi-nuwa，更新目录边界及发布器产物名。
[Evidence] 源导入CI成功且临时secret已删除，2256条Git树/31项输入与模块接线检查通过，本地HEAD一致、工作区干净、完整fsck通过且共享缓存依赖已移除。
[Risk] 新固件尚未编译或实机验证，本地子模块未初始化；合并版内核CI已成功但产物下载两次EOF尚未独立校验，未改board/feed或生成镜像。
```

## Q-069 · 合并版内核独立产物核验

```text
[unixnu-nuwa][kernel] 分块取回并核验合并版8796内核与平台库

[Change] 增加严格HTTP Range证据下载，摘要工具支持新仓与提取目录，实际内核解析器核对平台导出与三archive；调度独立固件CI。
[Evidence] 39793231214实际内核SHA77742999、五导出零undefined，三archive哈希与65348项donor指针检查通过，完整ZIP摘要未验证。
[Risk] 仍为静态检查，未执行预链接或设备；39802617878固件尚在构建，CI15候选与board/feed保持。
```

## Q-070 · 实机DT映射与固件CI依赖阻塞

```text
[unixnu-nuwa][build] 保存nuwa实机映射并限制固件CI依赖下载等待

[Change] 增加只读FDT采集与固件区域交集报告；runner Ubuntu镜像改archive HTTPS，安装设有限超时重试和非交互模式。
[Evidence] nuwa boot_completed=1，FDT SHAf4636276；39802617878日志为Azure cross-GCC包Get/Ign阻塞后取消，未进入编译；更新安装脚本Bash语法通过。
[Risk] 未生成新固件或执行镜像；候选ABL交接映射、日志持久性及新镜像下载效果仍未验证，board/feed不变。
```

## Q-071 · 实机平台属性与已链接驱动契约

```text
[unixnu-nuwa][device] 核对nuwa平台属性与实际链接驱动的ADT消费契约

[Change] 增加只读平台契约审查，检查精确驱动源码hash和实际内核catalogue，记录八CPU/PSCI/GIC/timer原始属性与转换缺口。
[Evidence] ArmCpu和ArmDTPlatform源码与CI记录一致，内核catalogue含两类匹配；39805110487依赖安装4分23秒成功进入构建。
[Risk] 未生成ADT或证明平台运行，ARCH_TIMER和boot-progress仍禁用，固件结果待取证；board/feed及_verified不变。
```

## Q-072 · 独立固件构建验收与SEC诊断审阅

```text
[unixnu-nuwa][firmware] 验收独立固件四模块并提交SEC阶段诊断范围

[Change] 保存39805110487构建与665项下载审计；准备仅SEC阶段WARN的源码补丁预览，R-007列两种日志路径并停在新诊断镜像生成前。
[Evidence] FD3MiB/SHA7f6f16c8与112B shim9346a527静态检查通过；Darwin22完整EFI编译链接成功，诊断patch严格RAM应用和git apply --check通过。
[Risk] 新FD无XNU且未实机执行；诊断patch未编译或应用，帧缓冲可见性/独立日志/入口条件仍未验证，board/feed及内存图不变。
```

## UEFI-002 · R-007诊断源码已发布5e4a8c8

```text
[unixnu-nuwa][firmware] Add approved SEC stage tracing for the nuwa entry trial

[Change] Add WARN stage/x0 markers around platform, memory, HOB, FV and DXE handoff; preserve splash contents.
[Evidence] R-007 A approved; exact source/patch hashes and git apply check recorded in the device repository.
[Risk] Diagnostic framebuffer output only; no ABL/BootShim visibility, USB logging or hardware pass claimed.
```

## Q-073 · R-007诊断构建接入

```text
[unixnu-nuwa][firmware] 固定获批SEC阶段诊断源码并接入专用CI输入

[Change] 发布独立固件诊断分支5e4a8c8，新增sec-trace profile与工作流选项；强化实际SEC标记、发布器HOB/DEPEX及嵌入PE一致性检查。
[Evidence] 固件完整tree/commit身份与单文件差异匹配，31项输入通过；稳定产物665项补查通过，R-007 A明确批准构建/临时容器/试启动和Android恢复。
[Risk] 诊断固件尚待编译，阶段文字仍依赖显示路径；未操作设备，board/feed/内存图与稳定固件分支保持。
```

## Q-074 · 诊断CI调度与受限临时包/恢复脚本

```text
[unixnu-nuwa][device] 接好获批诊断v4临时包及隔离bootloader的恢复路径

[Change] 增加R-007专用产物重验与v4打包，试启动工具支持固定包报告并在启动/恢复前强制bootloader复位，恢复不依赖诊断文件完整性。
[Evidence] 39809636575固定f897f90/sec-trace，依赖48秒成功后进入构建；两脚本帮助入口正常，v4头/原厂恢复哈希及输出边界保持严格检查。
[Risk] 实际诊断产物/包和实机结果待取证；尚未操作设备或更改board/feed/内存/槽位，屏幕与早期入口仍未验证。
```

## Q-075 · SEC诊断产物验收与临时启动包

```text
[unixnu-nuwa][firmware] 验收SEC诊断固件并生成受限v4临时包

[Change] 保存39809636575成功证据及665项检查，生成仅kernel_size更新的shim加FD容器，加入不含序列号的USB状态采集。
[Evidence] FD9ea347a4、shim9346a527，SEC实际TE标记完整；3153920B包SHAfbb7940a，nuwa身份/Android完成及boot和vendor_boot备份哈希匹配。
[Risk] 包不含XNU且尚未执行；当前rooted init_boot保留，屏幕/SEC/DXE与恢复结果以随后实测为准，board/feed与内存图不变。
```

## Q-076 · SEC诊断实测与Android恢复

```text
[unixnu-nuwa][device] 记录SEC诊断黑屏结果并完成nuwa Android恢复

[Change] 临时试启动唯一锁定诊断包，保存用户屏幕反馈、15次fastboot/USB采样和前后bootloader隔离及原Android备份恢复记录，R-007 A标完成。
[Evidence] 包fbb7940a发送/Booting OKAY，用户FASTBOOT后黑屏；00:09:01实际nuwa boot_completed=1，boot/vendor_boot/init_boot全分区SHA与试前相同。
[Risk] BootShim/SEC/DXE执行仍未验证，包无XNU；当前恢复为既有自定义/rooted Android，未修复持久A槽标志或建立独立日志通道。
```

## Q-077 · ABL交接取证与BootShim相对偏移候选

```text
[unixnu-nuwa][loader] 核对本机ABL变量交接并提出BootShim相对偏移修正

[Change] 保存同机ABL和UEFI变量发布/消费反汇编、既有日志筛选，准备只改text_offset的源码补丁，R-008列出两条候选并暂停新镜像生成。
[Evidence] 两槽ABL38a837fa匹配备份，UEFI98PE含QcomBds发布器；条件模型A8000000+A7100000越窗，源补丁apply检查通过，nuwa Android完成1。
[Risk] 变量运行值和实际拒绝码未观测，BootShim/SEC/XNU仍未验证；没有新镜像、设备模式或board/feed/内存修改。
```

## Q-078 · 相对偏移修正实测与PIL链阻塞取证

```text
[unixnu-nuwa][firmware] 完成相对偏移对照并定位候选自动ABL配置

[Change] R-008只编译新shim复用原FD打包，完成两次授权临时启动及Android核对；保存用户照片和同SM8550源码片段，准备取消AUTO ABL的源码候选并列R-009。
[Evidence] 源码910ee079，新包8b420abe与旧包仅4106/4107不同；两次15样本fastboot均false，照片PIL加载失败，候选RAW带AUTO ABL；Android完成1且三分区hash不变。
[Risk] 候选/原厂日志精确归属及SEC/BDS/XNU阶段未确认；空AUTO解析与新FD待审批验收，未改board/feed/内存或生成R-009镜像。
```

关联固件提交910ee079（codex/nuwa-relative-offset，已发布）：

```text
[unixnu-nuwa][firmware] 修正BootShim头的相对装载偏移

[Change] text_offset从绝对FD_BASE改0，FD复制地址和全部指令保持。
[Evidence] 同机ABL变量分支会将该字段加到KernelBaseAddr；补丁7409eecd的apply检查通过。
[Risk] R-008 A已获批准，实际变量及SEC执行待对照试验；此提交只改源码。
```

## Q-079 · R-009固定源码和新FD构建门

```text
[unixnu-nuwa][build] 固定取消AUTO ABL源码并接入独立固件CI

[Change] 记录R-009 A批准及PILDxe空列表控制流，新增33输入profile和workflow选项，CI/检查器区分相对头与FD目标并核对实际RAW及原PIL驱动。
[Evidence] 固件2ab6827d仅两配置路径且等同发布，PILDxe89e030af的零计数跳转静态核对，profile检查及旧R-007产物回归通过。
[Risk] 新FD编译、空AUTO真实分派及BDS仍待验收；未打包或操作设备，board/feed/内存图保持。
```

关联固件提交2ab6827d（已等同发布）：

```text
[unixnu-nuwa][firmware] 保留PIL驱动并取消自动ABL链载

[Change] RAW配置切到nuwa本地副本，仅注释AUTO ABL；RETAIL与全部镜像定义和数值保留。
[Evidence] 实际PILDxe89e030af静态空列表路径跳过加载循环，补丁0007应用检查通过，用户批准R-009 A。
[Risk] 空AUTO的真实分派及BDS尚未验证；待独立CI产物检查和临时试启动，未改内存图。
```

## Q-080 · 新FD CI调度与受限试启动门

```text
[unixnu-nuwa][build] 启动取消AUTO ABL固件CI并备妥受限打包试启动门

[Change] 保存固定6af9701的CI39819452729调度状态，新增R-009打包器及试启动配置门，核对设备与原Android恢复源。
[Evidence] 两个负路径拒绝旧R-007产物且未生成包，实际nuwa/kalama Android完成1，恢复源ef558db2；CI输入2ab6827d已固定。
[Risk] 新FD真实编译与实机结果待取证；未下发新镜像，board/feed及内存图不变，不以CI排队代替构建成功。
```

## Q-081 · APT超时取证及换源覆盖修正

```text
[unixnu-nuwa][build] 修正固件CI遗漏APT源导致的Azure下载超时

[Change] 保存39819452729失败终态与首错日志，换源由单个ubuntu.sources扩展至所有活跃list/sources并检查无Azure地址残留。
[Evidence] 安装步骤6分钟超时124，末项cpp-13-aarch64下载仍走Azure；构建未开始且无固件产物，固件2ab6827d和包清单不变。
[Risk] 新runner实际下载与编译待重试，尚未执行本轮实机；维持用户要求的本次试验后停止边界。
```

## Q-082 · R-009实机结果、Android恢复与停工收尾

```text
[unixnu-nuwa][device] 记录取消AUTO ABL后的DXE断言并恢复Android后停止

[Change] 保存39820752081成功产物与665项核验、唯一一次临时启动照片和采样，保留初次恢复超时及按键后独立恢复成功；R-009/H-004收尾并按用户要求停止。
[Evidence] 新包b60f96c0、FD5ad08040、实际空AUTO/PILDxe89e030af；照片候选GUID确认DXE但分配失败/架构协议缺失，01:25:30实际nuwa Android完成1且三分区hash与试前相同。
[Risk] 分配器/内存图根因及BDS/XNU仍未验证，未扩heap或改ADT/board/feed，未继续修复、生成镜像或第二次试验；下一轮起点仅记文档。
```

## Q-083 · DXE资源静态审查及同SoC评估规则

```text
[unixnu-nuwa][firmware] 审查DXE分配限制并准备不改内存图的诊断候选

[Change] 固化遇难题评估同SoC UniXNU/UEFI来源的仓库约定，记录69MiB与原厂Heap差异及分配器搜索路径，准备首次失败和断言前快照源码，R-010列两方案待审。
[Evidence] 固定Mu cfb93724与R-009子模块一致，0008严格apply检查通过；sheng0eb4514d/fuxibb25ad75固定源码及适用性已评估，运行空闲量仍TODO。
[Risk] 源码草案未编译/执行，69MiB差异不是实测根因；帧缓冲时序/锁内打印影响待验收，未生成镜像、操作设备或改board/feed/内存图。
```

## Q-084 · R-010诊断CI接线及硬停规则修订

```text
[unixnu-nuwa][firmware] 接入不改内存图的DXE诊断构建并更新设备日志恢复门

[Change] R-010 A获批，新增dxe-allocation配置和实际核心标记检查，两个Mu目标按raw哈希保留CRLF；按用户修订取消镜像生成硬停，设备缺日志或恢复路径前硬停。
[Evidence] 35项固定输入及0008严格apply检查通过，旧39820752081产物回归检查通过；AGENTS第3节与D-021记录用户明确规则，用户确认可录像。
[Risk] 新固件尚未编译或试启动，锁内日志时序影响未验证；原内存图、board/feed和所有_verified保持，设备前仍需在线核对。
```

## Q-085 · 临时启动日志与恢复前置门

```text
[unixnu-nuwa][device] 在临时启动前强制核对具体日志采集和恢复证据

[Change] R-010试启动接入15分钟内状态、当前包哈希和已有原boot恢复证据门；新增只读状态/分区摘要记录，恢复等待可接管晚出现的fastboot。
[Evidence] 无preflight时明确在设备命令前拒绝；本轮唯一nuwa/kalama Android完成1、三分区SHA与R-009相同，用户已确认可录像；CI39826580758编译中。
[Risk] 新固件和晚出现fastboot恢复分支实际运行未验证；屏幕是当前唯一阶段日志通道，需启动前通知用户录像，未执行候选启动或刷写。
```

## Q-086 · R-010嵌套依赖修复

```text
[unixnu-nuwa][build] 在修改Mu源码前初始化其固定嵌套依赖

[Change] R-010 CI补丁前显式递归初始化Mu gitlink，保存首轮实际失败及下载证据核验。
[Evidence] 39826580758实际首错MdePkg.dec(33)缺mipisyst/include，嵌套子模块前导减号；0008应用/后哈希通过，DeviceBuild契约要求Mu递归初始化。
[Risk] 重试完整编译未验证，未生成FD或执行候选；来源版本、诊断补丁、board/feed及内存图不变。
```

## Q-087 · DXE诊断私有锁调用修复

```text
[unixnu-nuwa][firmware] 将诊断快照加锁包装保留在Mu内存实现上下文

[Change] Page.c提供取锁快照包装，DxeMain只调用该包装，更新两文件诊断补丁及前后哈希，保留旧版编译错误证据。
[Evidence] 39827372451实际DxeMain.c:575/577报私有锁未声明；Imem.h:106/115和Page.c:90/102为真实原型实现，修订bb8bf3ec严格apply及35项静态检查通过。
[Risk] 修订版完整编译和设备执行未验证；保持原锁语义、内存图、board/feed和断言，不跳过错误或新增驱动替身。
```

## Q-088 · 间接APT镜像源修复

```text
[unixnu-nuwa][build] 修复runner的mirror文件间接选择Azure导致安装超时

[Change] 精确替换已观测mirror+file入口并拒绝未处理间接源，保留签名和原超时；纠正锁包装注释，包证据增加设备提交与诊断patch SHA。
[Evidence] 39828647170实际URIs为mirror+file且下载仍落Azure，安装360秒124、编译跳过；安装脚本WSL bash -n和35项输入/严格补丁检查通过。
[Risk] 当前4a859ab6仅注释变更，私有锁修订尚无完整编译结果；新runner下载待验收，未启动设备、改board/feed或内存图。
```

## Q-089 · R-010固件构建与包验收

```text
[unixnu-nuwa][firmware] 验收包含真实DXE分配诊断的固件与临时启动包

[Change] 保存39829943950成功运行与产物核验，生成仅shim加FD的v4包；保持全部来源和内存图。
[Evidence] CI6m51s成功，666项核验通过；实际核心c0135047含首失败/断言前标记，FDd9c3eaa0、包9197fed2，原PIL与空AUTO、相对shim保持。
[Risk] 当前仅编译和静态验收通过，未试启动或进入XNU；日志时序影响和运行分配状态待本轮唯一一次实测。
```

## Q-090 · R-010临时加载和恢复等待证据

```text
[unixnu-nuwa][device] 记录分配诊断临时加载并等待实体键恢复通道

[Change] 完成唯一一次包9197fed2临时加载，保留D-021前置记录和15次采样，H-005记按键回fastboot，原Android恢复等待中。
[Evidence] 试前实际nuwa/kalama Android完成1及三个原分区SHA；Sending3080KB和Booting均OKAY，15次nuwa fastboot均false，阶段画面尚待用户。
[Risk] ACK不证明DXE或XNU通过，实际分配数值和本次Android恢复完成1尚未确认；未继续新试验或修改内存图。
```

## Q-091 · 清晰实机资源快照、恢复与下一范围审阅

```text
[unixnu-nuwa][device] 确认DXE资源耗尽并恢复Android后提交原厂Heap候选审阅

[Change] 保存最新清晰原图和精确数值，记录本次恢复及三分区对比，关闭H-005；只读准备原厂Heap单行diff/区间审查，R-011列两方案。
[Evidence] 实机missing-arch-before-assert为27次失败、25页/100KiB空闲、最大8页/32KiB、5段，DxeMain.c(586) Not Found；02:30:04 nuwa Android完成1且三分区SHA不变。
[Risk] BDS/XNU未到，第一请求type/guard等缺失，未定位全部开销或SPSS错误；单行Heap候选只有静态无重叠/apply检查，未应用、编译或实机验收，超出R-010内存图范围待批。
```

## FW-011 · 已执行独立固件提交 1ccf760d667b9eec6dd3491c90cc04ebb7c58340

```text
[unixnu-nuwa][firmware] 恢复同机原厂DXE Heap以对照已确认的资源耗尽

[Change] 按R-011 A仅将MemoryMapLib的DXE Heap恢复为BAB00000/0D1C0000，保留其他区域和属性、PIL空AUTO及正确BootShim。
[Evidence] 同机原厂配置表SHA2adc494b包含相同一行；R-010实机最终仅25页空闲、最大8页，候选区间静态审查和严格apply检查通过。
[Risk] 原厂范围恢复尚未编译或实机验证；历史Android DT非实际候选ABL x0，SPSS和后续协议问题仍未解决，不改XNU窗口或宣称进入XNU。
```

## Q-092 · R-011源码及CI配置

```text
[unixnu-nuwa][firmware] 固定获批的原厂Heap源码并接入实际SEC描述符验收

[Change] R-011 A获同意，独立固件1ccf760只恢复Heap一行，新增factory-heap构建/打包/试启动配置，保留R-010诊断和日志恢复门。
[Evidence] 源码完整Git对象发布且旧分支保持，35项输入和严格诊断补丁检查通过；旧实际SEC读取69MiB，要求新SEC精确读出同机209.75MiB。
[Risk] 新固件尚未编译/试启动，实际ABL x0及扩展范围运行所有权未验证；保留其他内存行、board/feed/ADT及所有_verified。
```

## Q-093 · 原厂Heap实际固件验收

```text
[unixnu-nuwa][firmware] 验收实际209.75MiB Heap与仅单行变化的SEC内存表

[Change] 保存39835052901成功产物与严格核验，新增实际新旧SEC内存表逐字节比较，准备v4临时包和新鲜设备前置记录。
[Evidence] CI6m51s成功，666项检查通过；实际SEC Heap为BAB00000/209.75MiB，41条描述符仅Heap地址/长度变化；包8e852150，试前nuwa Android完成1。
[Risk] 当前仅编译及静态产物通过，R-011尚未启动，实际所有权、分配/协议和BDS/XNU均待运行证据。
```

## Q-094 · 原厂Heap实机菜单与恢复结果

```text
[unixnu-nuwa][device] 实机观察到UniXNU菜单并恢复Android后转入系统卷接线

[Change] 记录用户先见三项UniXNU菜单后BDS无OS的明确观察，区分NoBootOS图形与应用执行；保存唯一临时加载及恢复，关闭H-006。
[Evidence] 8e852150命令接受，用户确认Return to firmware/Restart/Power off菜单；Config.c与BootManager.c/NoBootOS.bmp对应；09:14:28 nuwa Android完成1、三分区SHA不变。
[Risk] 无本轮完整分配计数/照片日志，不保证所有SPSS问题消失；未执行XNU，当前包无FAT或系统负载，实际initrd和系统卷链路仍待验证。
```

## Q-095 · 系统卷发现与v4输入契约

```text
[unixnu-nuwa][loader] 固定系统卷发现契约并区分Android与候选initrd证据

[Change] 保存只读Android启动头、vendor fragment table和DT摘要，记录配置查找及整段512B BlockIo限制，明确菜单后BDS无OS的阶段归属。
[Evidence] 固定AOSP头SHA276f565d；Android initrd33870292B模512余468，vendor单fragment30899943B，当前R-011包无FAT/XNU；命令与摘要见system-volume-audit。
[Risk] 候选实际x0/chosen和安装ABL临时v4拼接未验证；不据Android地址构造板值，系统卷、Apple ADT及XNU执行仍待验证；无新增设备启动。
```

## Q-096 · 离线ABL拼接与系统卷探针

```text
[unixnu-nuwa][loader] 固定ABL拼接指令并离线制成只含配置的FAT32探针

[Change] 增加不覆盖旧证据的定向反汇编输出，记录同SoC发布器适用性；用固定UniXNU制卷方法生成标记菜单探针，登记中午录像待办。
[Evidence] 安装版ABL38a837fa/PEb489faff固定，14处复制及bootconfig指令核对通过；WSL FAT32 64MiB/bc0b3eae，配置逐字节读回和fsck.fat -n退出0。
[Risk] 只有离线静态检查，探针未接入固件/完整启动包，候选chosen和UEFI挂载未验证；无设备命令、板值/feed变更或XNU运行结论。
```

## Q-097 · 文件发现链路与描述符布局审查

```text
[unixnu-nuwa][loader] 核验实际FD的文件系统链路并纠正内存描述符字段解释

[Change] 固定驱动绑定与预连接源码，核验实际FD六个模块；修正ResourceAttribute宽度说明及字段解码，记录候选内存保留边界。
[Evidence] 八项静态链路检查通过，Fat/DiskIo/Partition/English实际PE存在；Mu PiHob.h定义UINT32，实际SEC41行MemoryType均匹配源码，原始表字节回归仍只差获批Heap字段。
[Risk] 未执行设备命令；二进制存在和源码路径不证明实际绑定、候选映射或FAT挂载；DarwinBoot及XNU运行仍未验证，未改固件/board/feed。
```

## Q-098 · Darwin22入口输入离线检查

```text
[unixnu-nuwa][loader] 验证固定加载器解析当前内核并固定ADT条件输入与CPU来源

[Change] 在WSL主机执行原样纯解析函数，核对当前内核真实符号和编译驱动来源；从缓存nuwa FDT提取CPU/GIC/timer/PSCI，展开官方逐输入占位符契约。
[Evidence] 20个正反例全部符合预期且UBSan无报错；77742999内核ParseKernel接受、10个映射段、零未解析外部符号；FDT e7217b15记录8个affinity、stride0x40000、声明19.2MHz和smc。
[Risk] 主机解析不等于EFI或XNU执行；目标ADT、完整NativePrelink ABI、CPU编号及硬件中断/PSCI均未验证；13回调和早期timer仍关闭，未操作设备或修改board/feed。
```

## Q-099 · 同包复测SEC停点与恢复

```text
[unixnu-nuwa][device] 记录同包复测SEC末屏并确认原Android完整恢复

[Change] 保存一次R-011原包定向复测、用户原照片及SEC banner关联，区分上午菜单到达与本次SEC停点，关闭本轮按键恢复待办。
[Evidence] 候选8e852150及前置身份/恢复输入核对通过；原照片47637c0e最后为platform-hobs Success/x0 B5DB1000，实际SEC含同一日期时间；12:18:42 Android完成1、三分区SHA未变。
[Risk] 未取得本轮DXE或SHENGMEM证据，具体阻塞函数及同包差异未定位；无XNU运行结论，无flash/erase/改槽，下一步只离线审查。
```

## FW-012 · SEC handoff边界诊断源码

```text
[unixnu-nuwa][firmware] 细化入口参数HOB和库构造前后诊断

[Change] 仅在SEC的入口参数HOB与库构造前后加四处ERROR级日志，保持调用顺序和所有内存表、PIL及BootShim。
[Evidence] 中午原包照片末行为platform-hobs Success；实际SEC与固定Mu库审查尚不能定位唯一函数，同SoC也采用相同调用顺序。
[Risk] 诊断不是修复，新二进制编译及运行未验证；不操作设备，不改板值、ADT或验证标志。
```

## Q-100 · SEC handoff边界诊断与离线构建准备

```text
[unixnu-nuwa][firmware] 固定SEC真实调用链并准备HOB与库构造边界诊断

[Change] 新增四条SEC日志的独立固件来源与CI profile，保持工厂Heap及PIL/shim；检查器核验新日志实际入TE，保存同SoC顺序及Mu依赖证据。
[Evidence] firmware ddd794fc单文件变更，35项固定输入静态检查通过；旧R-011实际FD回归通过，实际TE与link-map核对表明最后画面不能唯一定位故障。
[Risk] 新构建和实机执行待验证，原帧缓冲通道仍可能失效；本轮无设备动作，晚上刷新日志/恢复门后再试，不改board/feed或验证标志。
```

## Q-101 · SEC诊断构建与晚间包准备

```text
[unixnu-nuwa][firmware] 构建并核验SEC边界诊断固件且备妥晚间临时包

[Change] 保存CI39915967862实际日志，新增41行内存表回归及离线打包，接入严格候选/原头校验并延长观察至120秒，保留晚上录像和恢复门。
[Evidence] CI abe4be9/firmware ddd794fc成功；666个下载清单文件核验通过，四条新日志入SEC、2952B表完全一致、shim及PIL保持；v4包3153920B/SHA2d833461。
[Risk] 新包未实机启动，不含系统卷/ADT/XNU；严格scope不替代晚间新鲜日志/恢复门，USB采样不算过程日志；未操作设备或修改board/feed/验证标志。
```

## Q-102 · iOS16系统卷及启动载荷预研

```text
[unixnu-nuwa][docs] 固定iOS16启动载荷与系统根卷后续路线和版本缺口

[Change] 记录FAT载荷、预链接内核/ADT、OS/SystemOS和Data的分层接线，新增只读来源/组件/符号审计和就绪矩阵。
[Evidence] 当前77742999无NativeUfs/NativeRamBlock/PMGR对应导出；既定donor七组件在本机，两trust模块重新哈希且v2格式检查通过；固定loader逻辑上限2GiB，参考prelink输入89d8ff86不同。
[Risk] 大DMG未重新全文件哈希，raw大小/UUID、当前prelink及硬件运行均未验收；官网本轮404用固定缓存，不改board/feed或镜像，不操作设备，晚间包2d833461保持。
```

## Q-103 · 晚间SEC构造边界实测

```text
[unixnu-nuwa][device] 实测入口HOB返回并收窄至库构造边界后确认Android恢复

[Change] 保存晚间唯一2d833461临时启动、120秒USB采样和更正原图，旧误发图片排除；关闭拍摄待办并更新下一步构造链审查。
[Evidence] 新图f3cf9558显示list BAB00000/data BAB013B8及before-library-constructors，后标记未见；18:30:39实际nuwa完成1，三分区SHA与试前一致。
[Risk] 具体构造函数/运行PC和日志失效未区分，视频未交付，未到DXE/SHENGMEM或XNU；本次恢复仅检测Android，不宣称发送原boot，无flash/改槽/板值变更。
```

## Q-104 · 四构造日志候选

```text
[unixnu-nuwa][firmware] 审查实际构造依赖并准备逐库进入返回诊断

[Change] 添加四个Mu库构造的8条日志候选与独立CI profile，保留调用顺序/返回值/错误分支；记录共享库影响范围及实测目标。
[Evidence] 固定帧缓冲SerialPortInitialize仅返回成功；39项源码输入和去除日志后的原调用/返回检查通过，内存严格补丁应用一致。
[Risk] 新构建与运行未验证，共享库修改不限SEC且可能影响时序/日志；本轮不操作设备，不改内存表/board/feed或验证标志。
```

## Q-105 · 构造诊断包编译与检查

```text
[unixnu-nuwa][firmware] 构建并核验逐构造诊断包供下一轮实测

[Change] 保存CI39943865806实际日志和下载证据，准备530f56b4临时包，接入严格scope与原头重建校验，补实际日志xref和后续实测清单。
[Evidence] 666项清单核验、实际SEC8条CTOR及4条HANDOFF、41行2952B表不变检查通过；shim/PIL保持，实际DXE核心45570d70保留分配诊断，两包纯文件回归通过。
[Risk] 新包未实机启动，共享日志改变其他模块及时序；下次仍须刷新日志/恢复门，本轮无设备命令或板值/feed修改，无XNU执行结论。
```

## Q-106 · MMU构造边界实测

```text
[unixnu-nuwa][device] 实测Debug与Extract成功返回并定位至MMU构造可见边界

[Change] 保存530f56b4唯一临时启动、120秒采样和原图，更新MMU内部HOB/cache离线检查及可靠通知方式。
[Evidence] 原图520bdded显示Debug/Extract leave Success、最后Mmu enter；19:46:21实际Android完成1、三分区SHA与试前相同，无原boot发送或flash/改槽。
[Risk] Mmu内具体分支/运行PC未取得，缓存与日志故障仍待区分；未见DXE/SHENGMEM或XNU，不改board/feed/验证标志，不继续第二包。
```

## Q-107 · MMU分支离线审查

```text
[unixnu-nuwa][firmware] 核验MMU实际helper和缓存循环并准备分支日志候选

[Change] 保存HOB/cache/helper实际反汇编与固定Mu来源，准备五条查询/读取/cache分支日志，不改调用返回。
[Evidence] 实际helper240B/SHAf615b9f4，行步长4左移字段；0012内存应用通过，去除日志逐字节还原父源码。
[Risk] 运行PC/寄存器/具体分支未知，新候选未编译；无设备/板值/feed修改，前一提交API推送401未解决。
```

## Q-108 · 晚间主线交接

```text
[unixnu-nuwa][docs] 固化MMU停点和下一轮分支诊断的完整交接

[Change] 编写主线交接入口并重写STATUS，列明产物、补丁未完成状态、恢复门和下一轮文件入口。
[Evidence] 实测原图及postcondition确认Mmu enter边界和Android恢复；branch-proposal标记未编译，gh远端ref确认d056fb9已发布。
[Risk] 未定位具体故障指令，新分支日志未编译或实测；本轮仅文档，无新设备状态采样或镜像生成。
```

## Q-109 · MMU分支日志集成

```text
[unixnu-nuwa][firmware] 接入0012独立MMU分支profile和CI产物检查

[Change] 新增mmu-branches profile、五条日志实际SEC检查、独立打包scope和新鲜录像确认门。
[Evidence] 39项固定输入通过；0012删日志精确还原父源码，post pin704ba022；旧constructor包严格验证通过。
[Risk] 新固件尚待CI及实际产物验收；共享库日志影响时序，实机前须通知用户并刷新恢复门。
```

## Q-110 · MMU分支诊断包就绪

```text
[unixnu-nuwa][firmware] 完成MMU分支CI构建及诊断包静态验收

[Change] 保存CI39958974666、实际产物/全表/容器证据与五项离线测试；补齐新鲜录像确认兼容。
[Evidence] 包2b203afa/3153920B，实际SEC五MMU八CTOR四HANDOFF；41行2952B与R-011一致；整头载荷填充严格重建通过。
[Risk] ready_to_execute=false，无设备操作；运行分支与故障指令未验证，实机前通知用户并刷新日志恢复门。
```

## Q-111 · MMU分支实测与恢复

```text
[unixnu-nuwa][device] 实测MMU分支包可见边界并恢复Android

[Change] 保存2b203afa启动、120秒USB观察、用户原图及恢复证据，说明固定源码时间戳不是诊断包版本。
[Evidence] 新包实际发送成功；原图e1bc997f最后Mmu enter，无MMU新日志；原厂boot恢复后Android完成1和三分区SHA一致。
[Risk] 单张照片非连续录像；查询或输出路径尚未区分，无故障PC证据，未启动第二包。
```

## Q-112 · HOB查询诊断

```text
[unixnu-nuwa][firmware] 加入有界HOB查询日志以区分MMU入口后的路径

[Change] 新增0013 PrePi HOB诊断与hob-query独立profile、CI及严格scope，保留前序日志。
[Evidence] 实际SEC查询/SerialPortWrite反汇编；40项固定输入和完整补丁链通过，删除诊断后遍历返回表达式一致。
[Risk] 新日志额外读取header length并影响时序；新固件未编译或实测，不改cache/HOB返回与板值。
```

## Q-113 · HOB日志覆盖与人工恢复规则

```text
[unixnu-nuwa][firmware] 扩展HOB日志覆盖并落实人工恢复期间持续离线工作

[Change] 将查询日志上限由64提高128并更新补丁后哈希；加入旧MMU固件冒充HOB包的反向检查；落实用户人工恢复不硬停要求。
[Evidence] 首版CI39961551151成功；静态条目构造包括资源、页表分配及平台HOB，64可能截断；完整补丁链继续核验。
[Risk] 扩大日志量影响时间；首版未实测，新版本待CI。人工恢复待办不阻塞分析和构建，但不替代新启动前的恢复日志门。
```

## Q-114 · HOB诊断包就绪

```text
[unixnu-nuwa][firmware] 核验HOB查询诊断固件并生成47b5c4b1临时包

[Change] 保存CI39962464061及实际产物、全表和严格容器校验，准备用户录像试验。
[Evidence] 实际SEC九条HOB和前序日志齐备，41行2952B全表相同；包3153920B/SHA47b5c4b1。
[Risk] 编译静态检查不代表运行通过，HOB链与打印路径仍待实机区分。
```

## Q-115 · HOB实机进入DXE

```text
[unixnu-nuwa][device] 保存HOB查询返回及DXE加载的实机证据

[Change] 保存47b5c4b1临时启动、原图、保守日志转录及恢复等待超时记录，更新当前状态。
[Evidence] 原图6cddd1c1显示row93至99、matched、query-leave、FV解压成功与DxeCore加载；用户报告UniXNU菜单后无OS。
[Risk] 未取得SHENGMEM日志或XNU入口；Android恢复及三分区哈希待补齐；日志改变进展不能证明MMU根因已修复。
```

## Q-116 · initrd发布拒绝证据

```text
[unixnu-nuwa][device] 确认initrd发布拒绝及UniXNU加载的屏幕证据

[Change] 保存两张原图及保守转录，更新SHENGMEM取证完成状态。
[Evidence] NuwaBootMemoryDxe打印not a whole number of sectors；后续DXE MMU leave Success；UniXNU.efi与四条FAT挂载日志可见。
[Risk] 地址未可靠转录，拒绝条件包含逆序或非整扇区长度；四个FAT来源未确定，无XNU入口或本轮恢复完成证据。
```

## Q-117 · 有界系统卷传输构建

```text
[unixnu-nuwa][firmware] 接入独立固件仓的有界卷传输profile

[Change] 固定uefi-nuwa@150b5ec的封装接收驱动，接入volume-envelope CI和实际驱动标记检查。
[Evidence] 41项输入、5个补丁、9项补丁后哈希通过；旧HOB二进制冒充profile被拒绝；固件仓7项C主机测试通过。
[Risk] 完整固件待构建；当前仅传输实现，ABL载荷选择与实机映射仍未验证，无XNU入口。
```

## Q-118 · 卷探针容器与恢复闭环

```text
[unixnu-nuwa][build] 完成卷探针严格打包并补齐HOB试验恢复

[Change] 新增限定固定FAT的v4封装生成及逐字节复验，补录Android恢复与三分区哈希。
[Evidence] 实际64MiB FAT在模拟非对齐前缀后由固件同一C解析器正确识别；原五项MMU和HOB反向检查仍通过。
[Risk] CI39966008923尚未完成，新容器尚未生成或实测；没有XNU入口证据。
```

## Q-119 · 有界卷探针实机启动

```text
[unixnu-nuwa][device] 核验并临时启动有界卷配置探针

[Change] 接入严格探针scope和新鲜录像门，保存包与完整内存表比较及实测前检查。
[Evidence] CI39966008923成功，包ae9a445a/70266880B逐字节复验通过；41行2952B相同；用户确认录像后通知并临时启动，ACK成功。
[Risk] 屏幕结果与本轮恢复尚待补齐，不宣称系统卷或XNU运行通过。
```

## Q-120 · 零长度HOB定位

```text
[unixnu-nuwa][firmware] 针对实测零长度HOB加入查询边界诊断

[Change] 保存循环原图及恢复闭环，新增0014与hob-integrity独立profile，异常长度打印后停在现场。
[Evidence] 原图BAB00718 type0 len0重复；原遍历不推进；41输入6补丁9后哈希检查通过，Android完成1及三分区不变。
[Risk] 尚未定位零条目的来源；新行为只诊断不修复，待完整构建和实机。
```

## Q-121 · 硬停落档与交接更新

```text
[unixnu-nuwa][docs] 落实硬停时同步进度与交接的用户要求

[Change] 将落档规则写入AGENTS，重写过期主线交接，记录真实设备恢复和新CI及续接步骤。
[Evidence] postcondition确认Android及三分区；CI39973030321 success，产物尚未本地验收。
[Risk] 交接记录不替代新一轮日志/恢复门，XNU尚未进入。
```

## Q-122 · HOB完整性包就绪

```text
[unixnu-nuwa][firmware] 核验HOB完整性诊断并接入独立试验scope

[Change] 实际SEC强制新标记检查，扩展严格探针容器和设备门，更新交接及进度。
[Evidence] dd1ef825完整容器逐字节校验，41行2952B表一致，5项MMU门回归通过；新鲜用户录像确认及nuwa Android门通过。
[Risk] 新包未实测；HOB异常起因未知，诊断停在异常现场不修复链。
```

## Q-123 · HOB实测及交接落档

```text
[unixnu-nuwa][docs] 落实同链多次HOB查询和内置菜单实测交接

[Change] 保存原图/录像摘要及关键帧，重写STATUS与交接，明确待恢复及卷发现续接步骤。
[Evidence] 两处list同为BAB00000、目标GUID不同；BAB00718 type3 len0x30；35秒内置菜单无启动项；恢复等待超时。
[Risk] 无XNU入口或目标卷发现证据；HOB间歇异常根因未定位，本轮Android和分区postcondition待补。
```

## Q-124 · 卷发布状态诊断

```text
[unixnu-nuwa][firmware] 修正卷发布错误传播并补齐上轮恢复

[Change] 固定bc38be0发布器和独立volume-status诊断profile，补Android恢复与三分区核验。
[Evidence] 8项C主机测试、41输入7补丁10后哈希通过；postcondition确认Android完成1且三分区不变。
[Risk] 完整构建和实机诊断待完成；目标卷及XNU未确认，下一设备动作须新鲜录像门。
```

## Q-125 · 卷状态试验门与CI

```text
[unixnu-nuwa][build] 接入卷状态诊断的严格试验门

[Change] 新scope复用包逐字节校验和新鲜录像/恢复门，记录CI39985245383。
[Evidence] 2项旧产物冒充/空录像拒绝及5项MMU门回归通过。
[Risk] 构建及实际FD/镜像验收未完成，未操作设备。
```

## Q-126 · 卷状态包就绪

```text
[unixnu-nuwa][firmware] 验收卷状态诊断包与完整内存表

[Change] 归档CI39985245383实际产物检查和严格容器复验，记录本轮用户录像确认。
[Evidence] a22e9a44/70266880B逐字节复验，41行2952B内存表相同；实际包缺日志门时设备子进程前拒绝。
[Risk] 新包尚未实测；无目标卷或XNU执行证据，下一步刷新门后临时试验及恢复。
```

## Q-127 · 卷状态试验

```text
[unixnu-nuwa][device] 临时启动卷状态包并保存120秒USB观察

[Change] 本轮新鲜录像确认与通知后试启动a22e9a44，接入原Android恢复流程。
[Evidence] preflight身份/恢复门通过；fastboot boot exit0，launch记录120秒观察。
[Risk] 屏幕结果和本轮恢复尚待，USB不替代卷发现或XNU执行证据。
```

## Q-128 · 实测归因与FV探针

```text
[unixnu-nuwa][firmware] 明确chosen封装缺失并接入独立FV配置探针

[Change] 归档原图/恢复/错误审查，固定00a37d9嵌入探针驱动和确定性FAT16生成及独立profile。
[Evidence] chosen范围与历史Android一致且result0，Android完成1及三分区不变；9项C测试、mtype精确路径、43输入8补丁12后哈希通过。
[Risk] ABL选择仅静态支持，FV完整构建/实机待验；无真实XNU负载，CPU Vectors等独立问题未修。
```

## Q-129 · 内嵌卷探针就绪

```text
[unixnu-nuwa][firmware] 验收内嵌FAT资源与严格临时启动包

[Change] 完成FV资源/新驱动/容器核验，接入独立scope严格录像与恢复门。
[Evidence] CI39988591973成功，87b14624/3153920B逐字节复验，41行内存表一致；缺门在设备子进程前拒绝，用户已本轮确认录像。
[Risk] 尚无新包实机结果；无XNU/ADT，不将小探针发现当完整系统运输成功。
```

## Q-130 · 内嵌配置发现实机通过

```text
[unixnu-nuwa][device] 以原图确认FV配置卷发现链实机通过

[Change] 归档87b14624的发布Success和目标菜单原图，区分60秒退出探针与真实系统输入，更新决策/交接。
[Evidence] 4MiB BlockIo Success、config路径和唯一Volume config loaded项；120秒USB记录完成。
[Risk] 尚无XNU/ADT或完整运输验收；本轮Android恢复/三分区postcondition待补。
```

## Q-131 · FV探针恢复闭环

```text
[unixnu-nuwa][device] 完成配置卷实测后的Android恢复与分区核验

[Change] 补齐87b14624本轮恢复证据，关闭人工恢复待办并同步当前状态和交接。
[Evidence] recovery确认Android完成1；postcondition确认nuwa/kalama与三分区SHA和本轮preflight一致。
[Risk] 已通过的是小配置卷发现，真实XNU/ADT/NativePrelink及大负载运输仍待完成。
```

## Q-132 · 当前内核预链接分析

```text
[unixnu-nuwa][kernel] 生成当前内核的严格常量池预链接分析候选

[Change] 固定完整Libm常量区指纹与原工具补丁，生成当前native分析候选并复验所有绑定，扩展显式候选解析入口。
[Evidence] 65348重定位逐项读回、30段组件/native代码保持；4项拒绝测试和20项ADT回归通过，固定ParseKernel接受5a128fb2。
[Risk] 早期安全initializer为空，完整ABI/目标ADT/运行内存和运输未完成；loadable=false，未操作设备。
```

## Q-133 · 启动输入快照候选

```text
[unixnu-nuwa][firmware] 接入独立ReadyToBoot内存与CPU只读诊断

[Change] 固定6176a82诊断驱动并接入独立构建、实际模块检查与严格打包/录像门。
[Evidence] 46输入9补丁12后哈希校验通过；共享C汇总函数宿主UBSan通过，正常固件选择不变。
[Risk] 完整CI与实机尚待；快照不代表XNU窗口分配或所有权，不含XNU/ADT。
```

## Q-134 · 验收与暂停交接

```text
[unixnu-nuwa][docs] 落实启动输入包验收并按用户要求暂停

[Change] 归档CI39995937843实际模块、SEC表、包及缺门拒绝证据，重写状态/交接和新鲜录像续接步骤。
[Evidence] a2dc8195/3153920B逐字节复验；41行2952B表相同，缺preflight设备子进程0；用户原话先停下落实文档。
[Risk] 新模块与内存/CPU快照未实测；历史Android完成1不当作当前查询，主线暂停且无设备动作。
```

## Q-135 · 启动输入实测与恢复

```text
[unixnu-nuwa][device] 归档早期HOB异常及本轮Android恢复闭环

[Change] 新鲜录像通知后单次试启动a2dc8195，保存HOB坏长度原图/120秒观察/恢复；加入实际SEC差分审查并更新状态交接。
[Evidence] BAB00118 type4 len0，未到新DXE；Android完成1及三分区SHA不变；旧成功SEC与本轮掩蔽构建时间后逐字节一致。
[Risk] HOB首次异常时机与根因未知；ReadyToBoot输入未取得，未修改缓存/Heap或跳过检查，未执行XNU。
```

## Q-136 · HOB阶段诊断候选

```text
[unixnu-nuwa][firmware] 增加有界HOB创建与MMU阶段失败定位

[Change] 独立profile追加0018诊断可信arena、PHIT和HOB链，记录首次检测与上次有效阶段，接入CI/严格打包及录像门。
[Evidence] 47输入10补丁14后哈希通过；精确C主机保护页/ASan/UBSan覆盖336截断、原图零长及边界失败；旧FD冒充/空录像拒绝通过。
[Risk] 诊断影响时序，首次检测不等于写坏者；完整CI/实机未验，不改缓存/Heap，不绕过HOB检查。
```

## Q-137 · HOB阶段包离线验收

```text
[unixnu-nuwa][firmware] 验收有界HOB阶段诊断实际SEC与严格启动包

[Change] 归档CI40000310916、实际检查调用与失败分支审查、SEC表及严格包复验，落实可直接执行的录像/恢复交接。
[Evidence] 2273bdec/3153920B逐字节重建一致，CreateHob2次/查询1次调用和CpuDeadLoop存在，41行2952B表一致；缺preflight设备子进程0。
[Risk] 新包未实测，诊断可能改变时序；首次检测区间不等于写坏者，未取得本轮录像确认，未操作设备。
```

## Q-138 · HOB首次异常区间与根因判断

```text
[unixnu-nuwa][device] 定位MMU切换后首次坏链并完成恢复及缓存机制审查

[Change] 归档2273bdec原图/120秒观察/恢复，核对缓存控制实际指令与公开主来源，明确首嫌及单变量证伪路径。
[Evidence] before-mmu56条/末次create84条有效，返回Success后off718/type0/len0；Android完成1/三分区不变；关闭缓存函数无DC维护指令。
[Risk] 缓存交接是首要工作假设，运行寄存器/映射未测；未实施修复或新增启动，未执行XNU。
```

## Q-139 · HOB缓存交接修复候选

```text
[unixnu-nuwa][firmware] 准备保持Heap和坏条目保护的HOB缓存交接候选

[Change] 独立0019在建表完成后按完整cache行失效已拥有HOB，保持原MMU ABI和默认路径、一次性回调及M/C关闭守卫。
[Evidence] 51输入11补丁15后哈希通过，原保护块保留及MMU去钩子等价；精确C主机8192对齐/拒绝/屏障顺序/字节不变/一次性消费通过。
[Risk] 主机不执行真实cache操作，完整CI/实际包/实机待验；缓存假设未闭环，无设备动作。
```

## Q-140 · 缓存交接包验收

```text
[unixnu-nuwa][firmware] 验收HOB范围IVAC交接实际指令与严格启动包

[Change] 归档CI40005057158、实际维护序列/IVAC行操作/保护/内存表及新包复验，更新录像与恢复交接。
[Evidence] 26ef8efd/3153920B逐字节重建，实际DSB/IVAC/DSB/ISB与原坏条目保护通过；41行2952B表相同，缺门设备子进程0。
[Risk] 尚未实测缓存效果或闭环根因；回调/日志影响布局时序，新包录像未确认，无设备动作。
```

## Q-141 · 缓存交接候选实测与恢复

```text
[unixnu-nuwa][device] 记录缓存候选进入菜单的用户观察并闭环Android恢复

[Change] 新鲜录像确认后单次临时启动26ef8efd，归档120秒USB记录、用户菜单观察及本轮Android恢复核验。
[Evidence] preflight/launch/recovery/postcondition完整；用户报告进入UniXNU菜单，Android完成1且三分区SHA一致。
[Risk] 缓存阶段原图未收，EL/SCTLR/after-mmu仍待核对；单次菜单观察不等于根因证明或XNU执行。
```

## Q-142 · 本轮全量文档对齐

```text
[unixnu-nuwa][docs] 落实缓存候选实测状态决策及安全续接文档

[Change] 对齐README、候选及基线后续、当前状态/交接/人工待办，补D-025；历史时间线保留，已执行命令改为独立新轮次模板。
[Evidence] 747d8fc及本轮preflight/launch/recovery/postcondition，用户菜单文字；文档一致性审计记录原始证据哈希和阶段缺项。
[Risk] 本轮缓存阶段原图与重复性仍缺，未确认根因或XNU执行；仅文档整理，无新增设备动作。
```

## Q-143 · 五原图与故障判断规则

```text
[unixnu-nuwa][device] 归档缓存后HOB与ReadyToBoot通过原图并落实原因判断规则

[Change] 保存五原图和SHA，更新阶段通过及无OS原因，AGENTS增加公开资料结合实况主动排序判断要求。
[Evidence] after-mmu ok/count84、memory Success、ReadyToBoot和唯一菜单；探针exit/无OS，既有恢复完成1/分区SHA一致。
[Risk] 单次对照存在布局时序混杂，缓存唯一根因和稳定性未闭环；9GiB仅快照，未执行XNU，无新设备动作。
```

## Q-144 · OS入口分配与运输离线续接

```text
[unixnu-nuwa][loader] 执行固定分配选择主机验证并明确真实负载运输缺口

[Change] 原函数内存提取并校验当前补丁文本，新增主机分配记录适配器及OS入口合同审计，更新状态和续接。
[Evidence] ASan/UBSan12项通过，真实分析内核VA偏移0x1c8000，高地址选择0x8c01c8000；4MiB卷小于58MB候选。
[Risk] 主机服务不执行UEFI分配，照片范围为子集；loadable=false/ADT/ABI/运输待落实，无手机或板值修改。
```

## Q-145 · 上游驱动更新审查

```text
[unixnu-nuwa][docs] 固定核对最新独立驱动及nuwa适用性保留当前基线

[Change] 记录主仓/12模块/同SoC最新提交、文件差异及许可哈希，核对Darwin22补丁并给出配套引入顺序。
[Evidence] GPU/HID/显示实质更新，CPU/平台/Prelink代码blob不变；0005对DarwinBoot d099354d严格内存apply通过。
[Risk] 主仓分叉，未整仓升级或变更任何源码pin；新驱动未构建/实测，ST FTS不能套Novatek，无手机操作。
```

## Q-146 · 全部上游更新接入

```text
[unixnu-nuwa][build] 接入完整上游合并与21模块并迁移Darwin22补丁

[Change] 基座真实merge e553e46已推送；新增继承缓存保护的upstream-merged固件profile、kernel新源与三新增补丁及完整GpuAddon移植。
[Evidence] 合并树等于完整上游+3工作流，21固定模块；63补丁词法序列与固件51输入11补丁15后哈希通过。
[Risk] 固件/内核完整CI待验，新驱动不等于已激活硬件；未改板值/Heap/身份/验证标志，无手机动作。
```

## Q-147 · 固件验收与内核前置依赖修复

```text
[unixnu-nuwa][build] 验收更新固件并补齐内核sandbox辅助函数的真实前置补丁

[Change] 补入zzw原实现固定SHA；默认固件切新profile，新增解析/原指令审计接入与完整证据。
[Evidence] 固件40014018074成功/697项、SEC与实测旧包字节一致；24解析/packed/SMMU夹具通过，64项补丁包含辅助函数唯一实现。
[Risk] 首轮内核链接失败，新轮待构建；GPU完整主机因AArch64指令未执行，无新实机或板值变化。
```

## Q-148 · 全量更新构建验证闭环

```text
[unixnu-nuwa][build] 闭环更新后的iOS16内核固件及软件夹具并迁移预链接工具入口

[Change] NativePrelink接合并源固定模块，归档内核成功和独立二进制/平台检查，GPU用户QEMU夹具通过，全文更新状态交接。
[Evidence] CI40015845083成功/bf14e530/iOS16/零未定义及平台归档一致；固件2d606985的SEC与实测旧包字节相同；24解析/4池/9grant通过。
[Risk] 可选硬件/root/hash-cache分支未全部激活/编译；新FD/内核未实测，新内核预链接/ADT/窗口/运输尚待资格，无设备动作。
```

## Q-149 · 合并后新内核预链接与AMFI入口定位

```text
[unixnu-nuwa][loader] 生成bf14分析预链接并追踪AMFI注册入口与局部ABI

[Change] 新profile/可选输入支持、原始donor有界审计；保留历史分析，定位旧reference地址已slide风险。
[Evidence] eb66542c/65348绑定逐项读回/30 donor可执行范围不变/24解析；真实mac_policy_register导入和native dSYM80B策略结构偏移对应。
[Risk] 初始化DATA_CONST可写期、完整ABI/ADT/运输/窗口未验，未采用initializer映射，loadable=false；无手机动作。
```

## Q-150 · AMFI可写阶段修正及实际策略槽位核对

```text
[unixnu-nuwa][loader] 核对早期安全加载顺序和AMFI回调槽位并修正保护风险排序

[Change] 新增只读固定补丁阶段审计及donor常量写入到实际native DWARF槽位审计，同步无OTG条件和主线交接。
[Evidence] 与成功CI相同64补丁/12项源码顺序检查通过；335项native策略槽、23项AMFI常量写入和RX目标对应；公开Apple同版本实现支持。
[Risk] 完整CFG/回调及C++ABI、真实ADT/分配窗口/大文件运输仍未资格；初始化映射为空/loadable=false，无设备动作或新实测包。
```

## Q-151 · USB数据线v3 ramdisk运输诊断包

```text
[unixnu-nuwa][loader] 构建USB内存ramdisk的v3候选与匹配v4离线对照

[Change] 复用固定合并固件和64MiB有界探针，严格新scope包验收/录像恢复门；补ABL版本来源和真实选择门字节夹具。
[Evidence] v3 8177783e/v4 91e86ce4仅头部offset20/40不同，70266880B全包回读；7项新测试/10历史门控、16项AArch64用户QEMU分支夹具通过。
[Risk] v3容器接受/实际context/ramdisk拼接和64MiB发布未实测，菜单fallback不算运输成功；无XNU/ADT、无手机或分区动作。
```

## Q-152 · USB v3运输探针实机与恢复闭环

```text
[unixnu-nuwa][device] 确认v3独立64MiB ramdisk发布及FAT挂载并完成Android恢复

[Change] 归档单次8177783e试验的两张原图/转录/完整执行恢复证据，更新状态决策交接；修正未来控制台容器版本提示。
[Evidence] 原图envelope result=1/0x4000000块Success及先于embedded的FAT挂载；offset-64=30899943精确匹配vendor ramdisk；120秒观察，postcondition完成1/三分区SHA不变。
[Risk] 仅此运输阶段实机通过，非运行时SHA/真实大文件读取/XNU或iOS通过；同固件v4对照与重复性未验，无第二候选启动。
```

## Q-153 · 58MiB文件只读SHA应用与USB候选

```text
[unixnu-nuwa][loader] 构建独立EFI大文件SHA探针并通过完整UEFI QEMU文件读取

[Change] 固件不变，通过type=efi执行只读校验app；复用固定MIT SHA实现，分析MachO仅作READTEST数据，新增严格数据用途scope/完整包校验。
[Evidence] app def33a4a/6144B；最终包18ebd838/70266880B；13协议场景/3SHA向量/15门控通过，完整UEFI QEMU从最终FAT读58335232B和SHA通过后返回。
[Risk] nuwa实际EFI加载/分配/文件SHA待实测；分析文件loadable=false，未执行内核/ADT/OS；本轮无新手机动作，Heap/HOB/板值不变。
```

## Q-154 · 文件探针Access Denied与恢复闭环

```text
[unixnu-nuwa][device] 归档外部EFI拒绝画面并定位验签策略差异及完成恢复

[Change] 归档18ebd838单次实测/原图/恢复，纠正等待Enter判断，审查实际构建镜像验证policy和PE签名。
[Evidence] 原图returned Access Denied；实际SecurityStub链接验证库/介质policy0x04、app证书表0；postcondition UTC08:14:06完成1/A槽/三SHA不变。
[Risk] 精确拒绝API/runtime SecureBoot值未捕获，认证拒绝为首因推断；无文件SHA实机成功，不重复同包或关闭验签，新固件候选尚未实现。
```

## Q-155 · 固件内文件SHA诊断profile与CI接入

```text
[unixnu-nuwa][firmware] 接入保留验签策略的ReadyToBoot文件SHA诊断与严格产物检查

[Change] 固定固件a155c495及独立模块selection，新profile/CI保持默认和认证策略；显式沿用旧epoch避免无关SEC变化。
[Evidence] 57输入/12补丁/15后哈希静态通过，原11guard补丁和原保护post-image相同；实际C源AArch64 QEMU 19场景加一次性回调通过。
[Risk] 实际固件编译/SEC逐字节/目标crypto链接和nuwa执行待验，新包未生成，无新手机动作。
```

## Q-156 · 实际SHA链接审计与无外部应用数据包

```text
[unixnu-nuwa][build] 按实际LTO调用验证FV诊断SHA并接入纯数据包和设备门控

[Change] 修正包装函数内联后的实际PE调用审计，加入真实模块crypto链接和拒绝stub回归；构建纯数据FAT及严格新scope包。
[Evidence] 初轮40078257763编译成功/原检查失败留档；下载FD52ab071e独立全检查通过，SEC7192fd3f完全相同，Ready四次调用真实572B SHA体，原认证策略保持。
[Risk] 修正检查后的完整CI重跑待验；实际诊断调度/目标文件SHA尚未nuwa实测，不借旧录像或关闭验证策略。
```

## Q-157 · FV文件诊断绿色CI与最终包验收

```text
[unixnu-nuwa][build] 完成FV文件SHA候选完整CI和独立下载验收并固定6b3e5bfd包

[Change] 归档第二轮40080439083绿色状态/实际产物及完整最终包元数据，更新当前状态、交接和录像待办。
[Evidence] 710实际inventory/7模块，FD52ab071e与首轮相同，SEC7192fd3f与已实测固件全字节一致；真实crypto四BL/原认证0x04保留，70266880B包逐字节复验。
[Risk] NuwaFileAuditDxe实机调度/文件SHA未验，下一轮需新录像/恢复门；数据仍不执行，未改Heap/HOB/板值或验签策略。
```

## Q-158 · FV文件SHA实机与恢复闭环

```text
[unixnu-nuwa][device] 记录6b3e5bfd实机文件SHA通过并完成Android恢复核验

[Change] 保存本轮preflight/单次启动/三原图/屏幕事实和原厂恢复证据，同步当前状态、决策和交接。
[Evidence] 原图PASS exact length EOF SHA256及exit Success；18:09:48 Android完成1、槽_a、三个启动分区SHA与试前一致。
[Risk] 单次文件数据链通过不等于内核或iOS执行，未收到完整连续视频；实际OS窗口、ADT及初始化/完整ABI仍未资格化。
```

## Q-159 · 本轮归档（已完成）

- 代码与证据：`597baed`，v21语义修复/v22跨TTBR诊断映射/实机pmap入口/恢复闭环/音视频忽略/报告Git字节绑定。
- 文档：紧随其后的`[unixnu-nuwa][docs]`提交，包含本轮README与交接、官网QR/DT panic区/Format2复核。
- 发布状态：仅本地commit，未push。与本轮无关的历史未跟踪材料和原始截图未纳入。
- 下一实现：优先移植固定版本DT panic区补丁并验证8796；QR日志作为固件独立接入，Format2迁移另行冻结输入。
