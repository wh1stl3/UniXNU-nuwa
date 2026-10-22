# WORKLOG

> 只追加不修改。一行一个里程碑：`时间 · 结论 · 提交号 · 证据路径`

- 2026-10-22 02:55 · S0 仓库就位：git 初始化、`AGENTS.md`（只读边界 / 版本管理 / 五档文档机制 / 硬停四类）、`docs/` 骨架、上一轮探针证据拷入 `docs/inherited/`（P0 报告 + iomem/partitions/meminfo/nuwa-observed）· commit e417c76（bootstrap）· `AGENTS.md`, `docs/`
- 2026-10-22 02:55 · D-001 内存窗口结案：physmap 单窗口是代码硬约束（`arm_vm_init.c:378,1961`），排除 C；低 4 GiB 最大连续块仅 768 MiB，原 A 提案不成立；首选 B（`0x8c0000000`/9216 MiB），PA 位宽 40 位够用（`proc_reg.h:972-974`）· commit e417c76（bootstrap）· `docs/DECISIONS.md`, `docs/inherited/nuwa-observed.json`
- 2026-10-22 03:00 · 接入 UniXNU 官方移植指南（porting/devices 共 5 页 + sheng/fuxi/vermeer 设备页）：确认三仓结构（基座 `UniXNU` + 设备仓 + `uefi-<device>`）、官方栈为 4 KiB XNU、同 SoC 的 fuxi/vermeer 可作对照 · 摘要见 `docs/inherited/unixnu-official-2026-10-22.md`
- 2026-10-22 03:00 · **D-002 推翻 D-001 §5**：内存窗口真实控制点是 ADT `darwinboot-memory-size`，硬上限 8 GiB（不是 9216 MiB）；板级键为 `[payload] dram_size` 与 `[payload.adt] owned_memory_size`（sheng 2 GiB vs 4.75 GiB，不等价）。D-001 的 A/B/C 三选项全部作废 · `docs/DECISIONS.md`
- 2026-10-22 03:00 · D-003（proposed）：内核页大小走 4 KiB 官方主线，16K 不进本仓，等用户点头，不阻塞离线工作 · `docs/DECISIONS.md`, `docs/STATUS.md`
- 2026-10-22 03:02 · 用户拍定 4 KiB（D-003 → accepted），并明确目标身份是 **iOS 而非 iPadOS** → D-004：查基座 `docs/zh/guide/skip-setup.md` 确认 `ipad_identity` 写的是 4 个 `/chosen` 安全属性（`certificate-production-status=0` 等，供 `mobileactivationd` 原生激活），**与平台身份无关，必须保持 true**；真正决定 iOS/iPadOS 的是 `[ipsw]`、ADT `/product`、`[kernel.prelink]`、disable-jobs。donor 沿用旧仓 iPhone10,3/d22ap/iOS 16.7.16/20H392 · `docs/DECISIONS.md`
- 2026-10-22 03:02 · D-005（proposed）：基座 `feeds.toml` 钉 `xnu-10063.141.1`（17.x），iOS 16 是 8796，49 个补丁按 10063 写 → 先做 `git apply --check` 批量试算再选路，判定前不动 xnu 版本 · `docs/DECISIONS.md`, `docs/STATUS.md`

- 2026-10-22 03:12 · 完成 8796.141.3 的 49 补丁独立检查：38 项静态检查通过、11 项失败；普通 pmap 排除缺失 SPTM 路径后检查通过，D-006 选择先适配 8796，feed 未改 · 提交号：本行所属提交（git blame docs/WORKLOG.md 可解析） · docs/operations/2026-10-22-patch-portability-8796.md，reports/patch-portability-8796/

- 2026-10-22 06:30 · 复跑49补丁：38项静态检查通过、11项失败，补丁哈希/结果与初次差异0，源树前后干净；D-006与feed保持 · 提交号：待宿主，COMMIT-QUEUE Q-001 · docs/operations/2026-10-22-patch-portability-8796.md，reports/patch-portability-8796-recheck/results.json
- 2026-10-22 06:32 · 完成本地只读基座集成审查：需显式out，patch整模块覆盖，当前内核入口依赖Xcode；上游远端差异未验证；提交首版board最小占位R-002并依硬停暂停 · 提交号：待宿主，COMMIT-QUEUE Q-002 · docs/operations/2026-10-22-readonly-base-integration.md，docs/NEED-REVIEW.md

- 2026-10-22 09:02 · 用户选择R-002 A，创建与获批代码块一致的最小board.toml，9项赋值，example=true及ipad_identity=true，未知值仅TODO；R-002 approved并落地 · 提交号：待宿主，COMMIT-QUEUE Q-003 · board.toml，docs/NEED-REVIEW.md

- 2026-10-22 09:05 · NativePrelink security-init和sparse-index两项在8796独立静态检查通过，源树前后干净；board通过tomllib语法解析，完整性未验证；原49项统计保持 · 提交号：待宿主，COMMIT-QUEUE Q-004 · docs/operations/2026-10-22-native-prelink-8796.md，reports/native-prelink-8796/results.json

- 2026-10-22 09:12 · 生成五项8796候选且各自静态检查通过，未接入完整补丁模块；识别PGZ probe引用8796缺失aligned API；feed未改 · 提交号：待宿主，COMMIT-QUEUE Q-005 · docs/operations/2026-10-22-8796-context-candidates.md，reports/xnu-8796-candidates/results.json

- 2026-10-22 09:11 · Q-005记录时间校正：前述09:12为误填，五项候选实际已在09:07前生成并检查；以reports/xnu-8796-candidates/results.json的timestamp为精确证据 · 提交号：待宿主，COMMIT-QUEUE Q-006 · reports/xnu-8796-candidates/results.json
- 2026-10-22 09:11 · D-007确定48项8796候选选择；内存顺序模拟全部匹配，51项基线模拟与独立Git结果差异0，合并diff只读检查返回0；基座status识别nuwa EXAMPLE成功；未编译、未改feed · 提交号：待宿主，COMMIT-QUEUE Q-006 · docs/operations/2026-10-22-8796-selected-sequence.md，reports/xnu-8796-sequence/results.json，reports/board-integration/status.log

- 2026-10-22 09:59 · 完成8796接口静态审查，记录unstripped消费错位、Darwin23 archive/编译记录生产者缺口、13项参考回调与watchdog非union scratch覆盖算例；未宣称ABI通过 · 提交号：待宿主，COMMIT-QUEUE Q-007 · docs/operations/2026-10-22-darwin22-interfaces-and-wsl.md，reports/darwin22-audit/interfaces.json
- 2026-10-22 09:59 · WSL经批准只读实查可运行，默认clang14缺三项XNU内建且Xcode/IIG/SDK输入未就绪；当前直接内核构建路径列为不可行，按用户第2项写R-003两条候选并停止 · 提交号：待宿主，COMMIT-QUEUE Q-008 · docs/NEED-REVIEW.md R-003，reports/darwin22-audit/wsl-toolchain.log

- 2026-10-22 10:04 · 用户选择R-003 A，继续WSL工具链预检/适配第一阶段；用户确认无额外clang、IIG或sysroot输入；R-003 approved A，旧暂停解除 · 提交号：待宿主，COMMIT-QUEUE Q-009 · docs/NEED-REVIEW.md R-003，docs/STATUS.md

- 2026-10-22 10:14 · 落地WSL工具清单/严格预检/非执行式8796适配计划；WSL中9项测试通过、MIG后端代码生成与宿主C/C++语法样例通过；clang目标特征缺失及IIG/sysroot TODO使预检exit2，未编译内核；三树status为空、board/feed哈希不变 · 提交号：待宿主，COMMIT-QUEUE Q-010 · docs/operations/2026-10-22-wsl-firststage-adapter.md，reports/wsl-firststage/

- 2026-10-22 10:20 · 用户建议GitHub Actions并询问仓库关系；核实官方要求fork基座运行macOS build、设备仓独立；只读diff确认缓存fb2bb已含archive调度，未称其远端最新、未跟进或触发CI · 提交号：待宿主，COMMIT-QUEUE Q-011 · docs/operations/2026-10-22-official-ci-route.md，reports/official-ci-plan/

- 2026-10-22 10:44 · 核验官方e95b固定提交macOS workflow与完整491项路径/blob差异，生成5-hunk工作流候选并通过内存精确检查；用户指定wh1stl3、确认仓库未创建并解除Git命令限制，GitHub CLI网页授权等待完成；未运行内核CI · 提交号：待定，COMMIT-QUEUE Q-012 · docs/operations/2026-10-22-official-ci-route.md，reports/official-ci-plan/，patches/base-ci-candidates/

- 2026-10-22 11:03 · GitHub登录确认为wh1stl3；按用户公开选择创建基座fork及设备仓；官方8796标签解引用与本地输入同SHA，完成固定75bc的48项源构建入口及bash语法预检，准备依队列发布；无云端构建结果 · 提交号：待定，COMMIT-QUEUE Q-013 · reports/official-ci-plan/repository-setup.json，source-input-check.json，docs/operations/2026-10-22-source-kernel-ci.md

- 2026-10-22 11:12 · Q-001至Q-013已逐项提交并推送main，映射见milestone-commits.json；补充GitHub workflow授权后安装基座workflow 4e4c04a并启动CI 39715232540（device b745021），host/48项预检通过，编译步骤运行中 · 提交号：Q-013 b745021；本项待定Q-014 · reports/official-ci-plan/milestone-commits.json，reports/kernel-ci/39715232540/run.json

- 2026-10-22 11:21 · 首轮云端源构建失败于clang17不识别旧变量初始化启用开关；确认Xcode/IIG/MIG可用及firehose ARM64真实archive已构建；新增保留-ftrivial-auto-var-init=zero的单行兼容补丁，49项172 hunks精确内存顺序与bash预检通过，待重跑；Q-014已提交f8151a9、推送遇连接重置待重试 · 提交号：待定Q-015 · reports/kernel-ci/39715232540/，patches/xnu-8796-ci-candidates/

- 2026-10-22 11:28 · Q-015已提交推送dbbf029（连同Q-014推送重试成功）；启动第二轮39716728005，当前真实编译进行中；三来源树tracked状态为空，board/feed哈希不变；更新公开README当前入口 · 提交号：dbbf029；本项待定Q-016 · reports/kernel-ci/39716728005/run.json，reports/official-ci-plan/post-publish-workspace-check.json

- 2026-10-22 11:43 · 第二轮失败于UIO数组对齐和新IIG的kernelContent；完成纯文本工具检查39717772747，确认deployment-target选项及旧/新模板；新增不改变字节范围/IORPC的候选，50项209 hunks精确检查通过；用户持续授权所有GitHub命令，Q-016已提交推送42c29a6 · 提交号：待定Q-017 · reports/kernel-ci/39716728005/，reports/kernel-ci/39717772747/，patches/xnu-8796-ci-candidates/

- 2026-10-22 11:47 · Q-017已提交推送4be1fb4，第三轮39718507532以该精确设备输入启动，仍在真实编译；基座workflow宿主head a3cacd5但构建源码仍固定75bc，未整体跟进基座 · 提交号：4be1fb4；本项待定Q-018 · reports/kernel-ci/39718507532/run.json

- 2026-10-22 12:32 · 第三轮证据包已下载，实错为IORPC.kernelContent及缺失arm64/kpc.c；五目标真实IIG生成相同，否证deployment-target候选；新增受限内联RPC适配和源CI关闭KPC/KPERF，51项210 hunks及真实样本检查通过；Q-018已提交推送50fd1fd · 提交号：待定Q-019 · reports/kernel-ci/39718507532/，docs/operations/2026-10-22-ci-third-failure.md

- 2026-10-22 12:34 · Q-019提交7d6675e并推送成功；固定该device_ref启动第四轮39723011018，实际主机/依赖/输入检查成功、真实编译进行中；未取得完整内核构建结果 · 提交号：7d6675e；本项待定Q-020 · reports/kernel-ci/39723011018/run.json

- 2026-10-22 12:40 · 第四轮被适配器主动拒绝未知回调模板，下载证据后以短CI取得17文件全集，仅补入精确kernelContent回调赋值规则，432块静态转换通过；Q-020已通过同对象ID、force=false的GitHub API发布7dfa3c1；补充失败模板保留机制 · 提交号：7dfa3c1；本项待定Q-021 · reports/kernel-ci/39723011018/，scripts/publish-main-via-api.py

- 2026-10-22 12:42 · Q-021以相同对象ID经API发布4313f2d，force=false，启动第五轮39723736387；仍固定75bc/8796与既定设备输入，完整内核/ABI结果未验证 · 提交号：4313f2d；本项待定Q-022 · reports/kernel-ci/39723736387/run.json，api-publish.json

- 2026-10-22 14:22 · 第五轮实际12:48失败，下载完整证据；51份IIG输出无kernelContent残留，首错为ast.c无条件引用关闭的KPERF接口；两处条件保护，52项212 hunks和配方静态检查通过，来源/board/feed边界复核通过 · 提交号：待定Q-023 · reports/kernel-ci/39723736387/，docs/operations/2026-10-22-ci-fifth-failure.md

- 2026-10-22 14:25 · Q-023已发布db30d6d，以同一device_ref启动第六轮39733594660，主机/依赖/固定输入检查成功，真实编译进行中；继续取最终证据，不将启动状态写成通过 · 提交号：db30d6d；本项待定Q-024 · reports/kernel-ci/39733594660/

- 2026-10-22 14:35 · 第六轮最终失败并已取证，未再观察到AST旧错；首错为processor.c缺少KPERF定时器表项保护；补齐与枚举相同条件并保留断言，53项213 hunks及配方检查通过，新增下一轮目标对象证据 · 提交号：Q-024已发布a4fa68a；本项待定Q-025 · reports/kernel-ci/39733594660/

- 2026-10-22 14:37 · Q-025已发布484b97c，启动第七轮39734939751；输入包含两处AST guard及定时器表guard，并将记录精确目标对象，最终结果未验证 · 提交号：484b97c；本项待定Q-026 · reports/kernel-ci/39734939751/

- 2026-10-22 14:48 · 第七轮证据确认ast.o/processor.o实际生成，首错为t_kpc初始化缺少KPC guard；另以源码审查补齐scheduler/KTRACE条件，三项候选56项222 hunks及配方静态检查通过；提取器支持链接错误和目标对象证据 · 提交号：Q-026已发布6ea28e0；本项待定Q-027 · reports/kernel-ci/39734939751/

- 2026-10-22 14:50 · Q-027已发布8dd1b52，启动第八轮39736351595，输入为56项及既定IIG适配；记录精确版本，继续取真实结果，不扩大为内核/ABI通过 · 提交号：8dd1b52；本项待定Q-028 · reports/kernel-ci/39736351595/

- 2026-10-22 14:54 · KPC源码审查定位ARM64上下文两处关闭模块后的回调引用；请求取消第八轮以批量合入保护，取消不作验证；57项225 hunks及配方静态检查通过 · 提交号：Q-028已发布820ee2b；本项待定Q-029 · reports/kernel-ci/39736351595/

- 2026-10-22 14:56 · 第八轮服务端已确认cancelled；Q-029已发布4dd55f0，启动含57项候选的第九轮39736926012，取消不作验证，继续取真实结果 · 提交号：4dd55f0；本项待定Q-030 · reports/kernel-ci/39736351595/run.json，reports/kernel-ci/39736926012/

- 2026-10-22 15:07 · 收录用户提供的HackiOS比较报告，读取固定提交原始实现核验真实源码、IIG替代、Linux类型内建降级、PMU不可用实现和返回加载器边界；未执行上游代码或改变主线 · 提交号：待定Q-031 · docs/inherited/hackios-route-comparison-2026-10-22.md，reports/hackios-review/

- 2026-10-22 15:09 · 第九轮首次到达最终链接，唯一缺失native_legacy_display_probe；使调用匹配已有display构建开关，58项226 hunks及配方检查通过；保持完整链接错误检查，新增失败后原始kernel存在性/hash记录 · 提交号：Q-031已提交7bc0b1a待随本项发布；本项待定Q-032 · reports/kernel-ci/39736926012/

- 2026-10-22 15:11 · Q-031/Q-032均已按相同对象发布（7bc0b1a/526651a），启动第十轮39738601892验证可选display引用修复，使用58项精确输入，真实结果待取证 · 提交号：526651a；本项待定Q-033 · reports/kernel-ci/39738601892/

- 2026-10-22 15:28 · 第十轮完整源码编译/链接成功，下载20,136,488字节Mach-O与runner哈希一致；8796.141.3/Darwin22.6.0、未解析符号0和两项NativePrelink标记1静态检查通过；未预链接/QEMU/实机，当前不安排上机，下一步收口Darwin22设备接口 · 提交号：Q-033已发布4bcb017；本项待定Q-034 · reports/kernel-ci/39738601892/，docs/operations/2026-10-22-ci-source-kernel-success.md

- 2026-10-22 15:40 · 补真实编译时逐对象记录生产者，建立同轮Darwin22三项平台archive编译/格式/符号审查；59项228 hunks及3项参数保护测试通过，实际archive待CI · 提交号：Q-034已发布a8665e8；本项待定Q-035 · reports/driver-archives-plan/，docs/operations/2026-10-22-darwin22-archive-build.md

- 2026-10-22 15:43 · Q-035已发布ccaad74，逐字核验后更新base fork workflow，仅增加archive收集路径，启动第十一轮39742250205验证真实记录与三项平台库，最终结果待取证 · 提交号：ccaad74；本项待定Q-036 · reports/kernel-ci/39742250205/，reports/driver-archives-plan/workflow-install.json

- 2026-10-22 15:54 · 只读核验并行仓run24/53MB预链接/3MiB固件及输入hash，独立核对iPhone donor manifest；本仓只读plan首错确认缺VFS符号，可复用桥接实现；记录真实驱动缺口、预链接豁免与固件保留区/加载器门槛及两条路径 · 提交号：Q-036已发布875482a；本项待定Q-037 · reports/parallel-progress-review/，docs/operations/2026-10-22-parallel-three-artifacts-review.md

- 2026-10-22 16:03 · 第十一轮源内核再次构建成功，933份真实编译记录及四项消费者输入已取得；平台首错为不存在libsa搜索目录触发-Werror，仅在其不存在时移除，保留未知目录报错，4项保护测试通过 · 提交号：Q-037已发布e7228be；本项待定Q-038 · reports/kernel-ci/39742250205/，docs/operations/2026-10-22-darwin22-archive-build.md

- 2026-10-22 16:05 · Q-038已发布562c22f，启动第十二轮39744948467，仅验证已确认无效libsa路径的最小修复与平台archive；VFS候选及预链接方案另有只读核验，未改board/feed，最终结果待取证 · 提交号：562c22f；本项待定Q-039 · reports/kernel-ci/39744948467/

- 2026-10-22 16:14 · 完整清点65,348项实际donor绑定，本仓仅APFS的VFS符号缺失、参考run24零缺失且计数一致；准备真实VFS桥接并核对上游及8796锁/引用语义，下一轮60项231 hunks和配方静态检查通过，实际编译待CI · 提交号：待定Q-040 · reports/donor-compat/，docs/operations/2026-10-22-donor-vfs-bridge.md

- 2026-10-22 16:21 · 第十二轮源内核/933份记录再次成功、无效libsa目录修复生效；平台26条诊断分组，补五项匹配真实定义的C声明，仅三类旧头文件风格警告保持可见而不升级error，保留其他检查，4项命令测试通过 · 提交号：Q-040已发布5f118aa；本项待定Q-041 · reports/kernel-ci/39744948467/，include/nuwa/ArmCpuExports.h
