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

- 2026-10-22 16:24 · Q-041已发布ff8abe1，第十三轮39747264803使用60项补丁和平台声明/风格诊断修复启动，继续取真实archive及VFS导出结果 · 提交号：ff8abe1；本项待定Q-042 · reports/kernel-ci/39747264803/

- 2026-10-22 16:33 · 只读复现官方指令拒绝并清点12项Libm外部编码（4ADRP），9常量池完整hash匹配，参考候选30段4,201,824字节保持；更正先前原因计数为6窗口外/6入口oracle，未知项仍未验收，无新镜像 · 提交号：Q-042已发布382cce5；本项待定Q-043 · reports/donor-compat/pc-relative-inventory.json，docs/operations/2026-10-22-donor-pc-relative-inventory.md

- 2026-10-22 16:47 · 只读核对并行boot及过程文档，实际容器hash匹配但loader接线未验证；CI13源内核成功、ArmCpu archive生成，donor65348绑定零缺失和119段plan通过；最小noreturn声明待重跑 · 提交号：Q-043已发布939967c；本项待定Q-044 · reports/parallel-progress-review/boot-*，reports/kernel-ci/39747264803/，reports/donor-compat/ci13-*

- 2026-10-22 16:49 · 参考boot/过程审查与CI13真实证据、最小noreturn声明已提交发布2b02285；第十四轮39750542014已触发，最终结果待取证 · 提交号：2b02285；本项待定Q-045 · reports/kernel-ci/39750542014/

2026-10-22 17:29 · CI14源内核与三平台库成功取证；固定开源复用路线并准备两库真实重链接，7项测试通过 · 本提交（Q-046） · reports/kernel-ci/39750542014/；reports/driver-reuse/；docs/operations/2026-10-22-driver-reuse-and-platform-link.md

2026-10-22 17:34 · ca8db30已发布；第十五轮两库重链接验证已启动，最终结果待取证 · 本提交（Q-047） · reports/kernel-ci/39755850870/

2026-10-22 17:37 · 只读ADB确认ST FTS SPI、活跃m2面板、Adreno740v2与KIOXIA UFS；固定MiCode DT和LineageOS匹配触控来源，Android仍boot_completed=1 · 本提交（Q-048） · reports/android-driver-evidence/20261022T092529Z/；docs/operations/2026-10-22-android-driver-evidence.md

2026-10-22 17:49 · CI15两平台库真实重链接成功，下载五导出/零undefined核对，65348 donor绑定零失败；运行配置和硬件仍待验证 · 本提交（Q-049） · reports/kernel-ci/39755850870/；reports/donor-compat/ci15-kernel-bindings.json

2026-10-22 18:04 · 固定CI15内核并完成四模块加载器/只读initrd源码接线与BootShim修正，独立提取原厂cfg；75项静态检查和两来源apply检查通过，停于R-004固件产物生成门 · 本提交（Q-050） · reports/loader-integration/；docs/operations/2026-10-22-loader-source-integration.md

2026-10-22 18:10 · R-004 A获批，准备只构建EFI/FD/BootShim的独立Actions流程及固定输入闸门；实际构建待启动 · 本提交（Q-051） · .github/workflows/firmware-candidate.yml；scripts/ci/build-firmware-candidate.py；config/firmware-ci-inputs.json

2026-10-22 18:22 · 首轮固件39761427579取证：BootShim编译/下载机器码检查通过，EDK首错为入口HOB GUID缺失；固定来源补齐SEC生产链，83项静态检查通过并准备第二轮 · 本提交（Q-052） · reports/firmware-ci/39761427579/；docs/operations/2026-10-22-firmware-candidate-build.md

2026-10-22 18:32 · 第二轮39762744079依赖安装及输入检查通过，SEC补丁因上游CRLF未应用；仅云端精确目标归一化并保留严格apply与前后hash，准备第三轮 · 本提交（Q-053） · reports/firmware-ci/39762744079/；docs/operations/2026-10-22-firmware-candidate-build.md

2026-10-22 18:48 · 第三轮固件39764322744成功，四EFI/FD/BootShim下载静态检查通过；修正检查器遗漏的Mu PCD库DEPEX并验证四项负向检查，R-004 A完成；追加记录条件性实机授权 · 本提交（Q-054） · reports/firmware-ci/39764322744/；docs/operations/2026-10-22-firmware-candidate-build.md

2026-10-22 19:06 · 区分enuma与nuwa，核对fastboot解锁/A槽异常后临时原厂boot恢复nuwa Android=1；完成DT/initrd静态核对并准备3153920B v4固件入口包，候选未执行 · 本提交（Q-055） · reports/trial-boot-preflight/；docs/operations/2026-10-22-trial-boot-preflight.md

2026-10-22 19:26 · 只读复核外部驱动报告，纠正ST/FocalTech、sheng GPU、feeds必要性和直接复用判据；保留开源来源索引，主线顺序不变 · 本提交（Q-056） · docs/operations/2026-10-22-driver-source-report-review.md；reports/driver-source-report-review.json

2026-10-22 19:33 · 只读审查r6重打包脚本并在RAM复现gzip OS/ID差异，确认v1 SHA规则；识别原FAT旧内核/6GiB/自动启动风险，未采用混合镜像 · 本提交（Q-057） · reports/repack-reference-review.json；docs/operations/2026-10-22-reference-repack-review.md

2026-10-22 20:22 · 获批临时启动v4候选，命令OKAY/屏幕黑屏/fastboot持续可见，SEC与DXE未验证；原厂恢复先失败，重进bootloader后成功回nuwa Android=1，建立D-016状态隔离规则 · 本提交（Q-058） · reports/v4-firmware-trial/；docs/operations/2026-10-22-v4-firmware-trial.md

2026-10-22 20:27 · 用户告知另一轮开始推送镜像，暂停本仓全部ADB/fastboot/USB查询；Q-058证据已同步，无运行中的设备命令，设备当前状态不再轮询 · 本提交（Q-059） · docs/STATUS.md实机操作暂停；上一轮reports/v4-firmware-trial/

2026-10-22 20:53 · 离线完成ARM64头/BootShim/FD→SEC与日志路由核对，33项静态断言通过；确认屏幕独占日志及SMMU前置盲区，实际ABL交接/cache条件仍TODO，设备暂停不变 · 本提交（Q-060） · reports/arm64-sec-entry-audit/audit.json；docs/operations/2026-10-22-arm64-sec-entry-audit.md

2026-10-22 21:04 · 完成USB/RAM/UART/文件日志出口离线评估：现有高通设备栈可作为DXE导出基础，早期挂死仍需独立记录与回收；Mu日志框架列为复用候选，未实现或实机验证 · 本提交（Q-061） · docs/operations/2026-10-22-log-export-options.md

2026-10-22 21:23 · 遍历官方72中文页并核对144路由，发现Darwin22 boot_args源定义偏移差异，补充SM8550 CDC与sheng持久日志来源；保持4KiB/iPhone主线，未升级上游/生成镜像或访问设备 · 本提交（Q-062） · reports/official-site-audit/；docs/operations/2026-10-22-official-site-route-review.md

2026-10-22 21:40 · 合并上游5fdbd5d到UniXNU fork 76dd641，完整树/3份工作流/28份patch和feed核对通过；CI15实际DWARF确认608B boot_args，用户撤销实机暂停，未访问设备或生成镜像 · 本提交（Q-063） · reports/upstream-merge/；reports/official-site-audit/ci15-boot-args-dwarf.json

2026-10-22 21:52 · 接入Darwin22加载器608B结构/缓冲区补丁及前后哈希门；AArch64布局编译、88项接线检查和两版各10例宿主边界测试通过，保留PIE一次139失败，未生成固件或访问设备 · 本提交（Q-064） · reports/darwin22-loader/；docs/operations/2026-10-22-darwin22-loader-fix.md

2026-10-22 21:54 · 追加核对既有原厂表逐字节证据，接线检查增至89项；复用历史原文避免重复提交，原始空白未修改 · 本提交（Q-064） · reports/darwin22-loader/integration/audit.json

2026-10-22 22:07 · 准备76dd合并版独立内核CI profile，原48项序列重验通过，两份变化挂载patch保留8796字节；60项适配输入/语法和旧基线回归检查通过，待真实CI编译 · 本提交（Q-065） · reports/upstream-merge/kernel-input-review.json；docs/operations/2026-10-22-merged-kernel-profile.md

2026-10-22 22:14 · 合并版内核CI39793231214已触发，当前排队未执行；两版完整DarwinBoot C翻译单元AArch64语法检查通过，未链接/生成固件或访问设备 · 本提交（Q-066） · reports/kernel-ci/39793231214/dispatch.json；reports/darwin22-loader/checks.json

2026-10-22 22:30 · 创建公开独立uefi-nuwa并关闭Actions；同网络enuma保持，准备仅导入Git历史的临时云任务及已有源码接线脚本，尚未导入或生成镜像 · 本提交（Q-067） · reports/uefi-nuwa/repository-created.json；docs/operations/2026-10-22-dedicated-uefi-repository.md

2026-10-22 22:42 · 独立uefi-nuwa发布既有BootShim/SEC/DSC/FDF和只读发布器，2256条树与内存/配置/子模块保护通过，main和enuma保持 · 0a3a51af229eabe76bcc9dcb90d3ce985223b125 · reports/uefi-nuwa/result.json

2026-10-22 23:05 · 完成独立固件profile与本地D:/Code/uefi-nuwa，31项输入/接线检查和完整Git fsck通过，移除共享缓存依赖；source-import成功且secret已删除，新内核CI成功但两次产物下载EOF待核验，未生成镜像或访问设备 · 本提交（Q-068） · reports/uefi-nuwa/；reports/kernel-ci/39793231214/

2026-10-22 23:18 · 分块取回合并版内核及三archive，实际SHA/五导出/零undefined/65348项donor指针检查通过；调度独立固件CI39802617878，尚无设备执行 · 本提交（Q-069） · reports/kernel-ci/39793231214/；reports/firmware-ci/39802617878/

2026-10-22 23:27 · nuwa Android=1只读FDT确认splash/initrd与ramoops-FD重叠；固件CI因Azure依赖下载阻塞取消，补有限超时和镜像替换，未进入固件编译 · 本提交（Q-070） · reports/firmware-ci/39802617878/

2026-10-22 23:38 · 对照实际内核catalogue与精确驱动源码，核对nuwa八CPU/PSCI/GIC/timer的FDT→ADT契约；固件重跑39805110487安装成功进入编译 · 本提交（Q-071） · reports/runtime-platform/live-dt-contract.json；reports/firmware-ci/39805110487/dispatch.json

2026-10-22 23:47 · 独立固件39805110487编译及665项产物静态检查通过，FD7f6f16c8/shim9346a527；SEC诊断源patch已可审查，生成新诊断镜像前按R-007硬停，未操作设备 · 本提交（Q-072） · reports/firmware-ci/39805110487/；docs/NEED-REVIEW.md

2026-10-22 23:56 · R-007 A获批，SEC诊断源码在独立固件分支发布且仅一文件，稳定分支不变 · 5e4a8c814b89f62a4ba2bc145249314fed5db787 · reports/sec-trace/source-publish.json

2026-10-22 23:56 · 接入sec-trace profile并通过31项输入检查；补齐发布器改名后HOB/DEPEX与PE一致性审查，稳定产物补查通过；待调度诊断构建 · 本提交（Q-073） · reports/sec-trace/

2026-10-23 00:00 · 调度SEC诊断CI39809636575，工具安装48秒通过进入编译；接好严格v4打包与D-016试启动/原厂恢复脚本，尚未生成包或操作设备 · 本提交（Q-074） · reports/sec-trace/39809636575/dispatch.json；scripts/prepare-sec-trace-boot.py

2026-10-23 00:06 · SEC诊断CI39809636575成功，665项实际产物及阶段字符串静态检查通过；生成3153920B受限v4包SHAfbb7940a，完成恢复/身份只读前置，尚未试启动 · 本提交（Q-075） · reports/sec-trace/39809636575/

2026-10-23 00:11 · R-007 A诊断包fbb7940a临时Sending/Booting OKAY，用户FASTBOOT后黑屏、15样本fastboot持续；按D-016恢复nuwa Android=1，三分区hash不变，SEC/DXE/XNU未验证 · 本提交（Q-076） · reports/sec-trace/39809636575/launch.json、recovery.json、trial-summary.json

2026-10-23 00:36 · 本机ABL/UEFI静态交叉核对发现BootShim相对text_offset误用，准备源码单字段修正；实际运行拒绝未验证，R-008待审批，nuwa Android=1 · Q-077（本条提交） · docs/operations/2026-10-23-abl-handoff-and-relative-offset.md；reports/abl-handoff/

2026-10-23 00:55 · R-008新shim只改两字节，同FD包两次试启动见日志并恢复Android=1；照片PIL/ABL失败与候选AUTO ABL一致，同SM8550源码核对后准备0007，R-009待审批 · Q-078（本条提交） · docs/operations/2026-10-23-relative-offset-trial-and-pil-stop.md；reports/relative-offset/

2026-10-23 01:05 · R-009 A获批，空AUTO路径静态通过；固件2ab6827d仅替换PIL配置，33输入profile与CI新头/RAW门准备完成，尚无新产物 · Q-079（本条提交） · docs/operations/2026-10-23-pil-no-auto-build-trial.md；reports/pil-no-auto/

2026-10-23 01:07 · 固定6af9701触发CI39819452729，新profile打包/试启动门及拒绝旧产物的负路径通过，设备只读前置Android=1 · Q-080（本条提交） · reports/pil-no-auto/39819452729/run-initial.json；reports/pil-no-auto/reject-old-profile.json

2026-10-23 01:12 · CI39819452729工具安装超时124且未编译；据真实Azure下载日志将换源覆盖扩至全部APT源，固件输入不变，准备重试以完成获批单次实机 · Q-081（本条提交） · reports/pil-no-auto/39819452729/run-final.json；failure-selected.log

2026-10-23 01:30 · R-009 A重试CI成功及665项检查后完成唯一一次实机，候选DXE页分配/协议缺失断言；按键回fastboot后原Android备份临时恢复，01:25:30完成1且三分区hash不变，按用户要求停止 · Q-082（本条提交） · docs/operations/2026-10-23-pil-no-auto-build-trial.md；reports/pil-no-auto/39820752081/

2026-10-23 01:44 · 恢复主线审查DXE页搜索及69MiB/原厂209.75MiB差异，评估同SoC固定来源；不改map的0008诊断源码apply检查通过，R-010待审批，用户同SoC评估规则持久化至AGENTS · Q-083（本条提交） · docs/operations/2026-10-23-dxe-allocation-source-audit.md；reports/dxe-allocation-audit/

2026-10-23T01:53:08+08:00 · 批准R-010 A并按用户修订日志/恢复硬停门，35项输入及旧产物回归静态检查通过，接入分配器诊断CI · Q-084（提交后以git log定位） · reports/dxe-allocation-audit/profile-check.json；docs/operations/2026-10-23-dxe-allocation-build-trial.md

2026-10-23T01:55:48+08:00 · CI39826580758编译中，落实D-021设备前置门并只读确认nuwa Android完成1及三分区摘要 · Q-085（提交后以git log定位） · reports/dxe-allocation-audit/gate-check.json；android-online-before-build.json

2026-10-23T01:58:43+08:00 · 39826580758首错为Mu嵌套依赖缺失，取包逐项验hash，补丁前递归初始化固定gitlink后重试 · Q-086（提交后以git log定位） · reports/dxe-allocation/39826580758/

2026-10-23T02:07:20+08:00 · 39827372451真实编译首错为私有锁声明不可见，将加锁包装留在Page.c，35项静态检查重过后重跑 · Q-087（提交后以git log定位） · reports/dxe-allocation/39827372451/compile-errors.json

2026-10-23T02:16:49+08:00 · 39828647170工具安装超时，按实际mirror+file入口修复Azure间接选源，保留签名/限时；35项与Bash语法通过 · Q-088（提交后以git log定位） · reports/dxe-allocation/39828647170/

2026-10-23T02:26:32+08:00 · 39829943950固件编译成功，666项及实际DXE核心日志标记静态检查通过，v4包9197fed2准备完成 · Q-089（提交后以git log定位） · reports/dxe-allocation/39829943950/

2026-10-23T02:29:17+08:00 · R-010唯一临时加载ACK通过、15次nuwa fastboot均false；阶段日志待用户，恢复等待端点/实体键H-005 · Q-090（提交后以git log定位） · reports/dxe-allocation/39829943950/launch.json；preflight.json；trial-summary.json

2026-10-23T02:39:24+08:00 · 最新清晰实机图确认DXE最终25页空闲/最大8页/27次失败，原Android恢复完成1且三分区未变；准备单行原厂Heap候选，R-011待审 · Q-091（提交后以git log定位） · reports/dxe-allocation/39829943950/screen-observation.json；postcondition.json；reports/dxe-allocation-audit/factory-heap-proposal.json

2026-10-23T02:51:01+08:00 · 用户同意R-011 A，独立固件仅恢复同机原厂Heap一行并发布 · 1ccf760d667b（固件） · reports/factory-heap/source-publish.json
2026-10-23T02:51:01+08:00 · 接入factory-heap CI与实际SEC Heap描述符验收，35项输入及旧FD回归静态检查通过 · Q-092（提交后以git log定位） · reports/factory-heap/profile-check.json；docs/operations/2026-10-23-factory-heap-build-trial.md

2026-10-23T09:08:42+08:00 · CI39835052901成功，实际SEC确认209.75MiB，41条表仅获批字段变化，临时包8e852150及试前门检查通过 · Q-093（提交后以git log定位） · reports/factory-heap/39835052901/

2026-10-23T09:22:59+08:00 · R-011用户实机确认UniXNU三项菜单后BDS无OS，已恢复Android完成1且三分区未变；转入系统卷发现审查 · Q-094（提交后以git log定位） · reports/factory-heap/39835052901/user-observation.json；recovery.json；postcondition.json

2026-10-23T09:31:37+08:00 · 完成系统卷发现契约及Android v4头只读审查；33870292B initrd非整扇区，候选实际映射仍TODO，未再启动 · Q-095（提交后以git log定位） · docs/operations/2026-10-23-system-volume-discovery.md；reports/system-volume-audit/inputs.json

2026-10-23T09:56:34+08:00 · 离线固定ABL前置段/generic/bootconfig复制路径及14处指令；WSL制成仅配置FAT32探针，读回/fsck通过，未接入固件或操作设备 · Q-096（提交后以git log定位） · docs/operations/2026-10-23-offline-initrd-and-volume-probe.md；reports/system-volume-audit/volume-probe.json

2026-10-23T10:23:00+08:00 · 核验实际FD文件系统驱动与预连接源码，修正32位ResourceAttribute布局并核对41行类型；原始内存表差分回归通过，无设备动作 · Q-097（提交后以git log定位） · docs/operations/2026-10-23-volume-discovery-chain.md；reports/system-volume-audit/discovery-chain.json

2026-10-23T11:20:07+08:00 · 固定DarwinBoot纯解析函数主机20项检查通过，当前内核格式被接受；复查符号闭包并从缓存DT提取CPU/GIC/PSCI输入，未生成目标ADT或操作设备 · Q-098（提交后以git log定位） · docs/operations/2026-10-23-darwin22-entry-input-contracts.md；reports/darwin22-input-contracts/

2026-10-23T14:16:46+08:00 · R-011同包复测照片停于SEC平台HOB成功，未取得SHENGMEM；12:18:42恢复Android完成1且三分区未变，转离线HOB/构造审查 · Q-099（提交后以git log定位） · reports/initrd-retest/2026-10-23-noon/；docs/operations/2026-10-23-initrd-retest-sec-stop.md

2026-10-23T15:02:06+08:00 · SEC真实调用与同SoC顺序审查完成，四条边界日志源码ddd794fc已发布，35项输入与旧FD静态回归通过；新构建待执行，本轮无设备动作 · Q-100（提交后以git log定位）；FW-012 ddd794fc · docs/operations/2026-10-23-sec-handoff-diagnostic.md；reports/sec-handoff/

2026-10-23T15:26:32+08:00 · CI39915967862编译和下载静态检查通过，四条新日志入SEC、41行表2952B不变；v4包2d833461离线就绪，晚间刷新日志/恢复门后试，未操作设备 · Q-101（提交后以git log定位） · docs/operations/2026-10-23-sec-handoff-build-ready.md；reports/sec-handoff/39915967862/

2026-10-23T15:50:31+08:00 · 晚间新包严格scope与原头逐字节校验接线完成，观察默认120秒并记录相对时刻；仅纯文件/语法/CLI帮助检查，无设备命令 · Q-101（同一里程碑，提交后以git log定位） · reports/sec-handoff/39915967862/trial-scope-integration.json

2026-10-23T17:03:32+08:00 · 完成系统卷/启动载荷/内核/iOS16预研，固定donor七组件、v2 trust及当前根卷后端缺口；确认packed 2GiB限制与参考native不匹配，无镜像/设备/板值变化 · Q-102（提交后以git log定位） · docs/operations/2026-10-23-ios16-system-payload-research.md；reports/ios16-payload-research/

2026-10-23T18:36:32+08:00 · 晚间唯一诊断包实测新图确认入口HOB已返回，最后构造前日志；18:30:39 Android完成1、三分区不变，无第二次启动 · Q-103（提交后以git log定位） · docs/operations/2026-10-23-sec-handoff-evening-trial.md；reports/sec-handoff-trial/2026-10-23-evening/

2026-10-23T18:59:02+08:00 · 四构造源码审查，Debug初始化为无重置实现；39项静态检查通过，8条共享库日志候选待CI，不操作设备 · Q-104（提交后以git log定位） · docs/operations/2026-10-23-constructor-trace.md；reports/constructor-trace/

2026-10-23T19:26:45+08:00 · CI39943865806成功，实际SEC8条构造日志和2952B全表回归通过，530f56b4包及严格scope就绪；无设备操作 · Q-105（提交后以git log定位） · docs/operations/2026-10-23-constructor-trace-ready.md；reports/constructor-trace/39943865806/

2026-10-23T19:50:49+08:00 · 530f56b4原图确认Debug/Extract成功、最后Mmu enter；19:46:21实际Android完成1且三分区未变，转MMU内部离线审查 · Q-106（提交后以git log定位） · docs/operations/2026-10-23-constructor-trace-trial.md；reports/constructor-trace-trial/2026-10-23-evening/

2026-10-23T20:34:35+08:00 · 实际helper240B与非零行步长核验，五条分支日志候选内存检查通过，未编译或操作设备 · Q-107（提交后以git log定位） · docs/operations/2026-10-23-mmu-constructor-audit.md；reports/mmu-constructor/

2026-10-23T21:00:52+08:00 · 完成MMU停点主线交接，核对d056fb9远端已同步；明确0012未编译和下一轮入口，本轮无设备操作 · Q-108（提交后以git log定位） · docs/operations/2026-10-23-mainline-handoff.md

2026-10-23T21:10:16.214254+08:00 · 接入0012独立profile/CI/打包scope，39输入及日志还原通过；新构建待执行 · Q-109（提交后git log定位） · reports/mmu-branches/profile-check.json；docs/operations/2026-10-23-mmu-branches-build.md

2026-10-23T21:18:05.100423+08:00 · CI39958974666成功，新包2b203afa静态核验通过，41行全表一致、五项离线测试通过，无设备操作 · Q-110（提交后git log定位） · reports/mmu-branches/39958974666/；docs/operations/2026-10-23-mmu-branches-build.md

2026-10-23T21:23:58.332786+08:00 · 新包2b203afa实测最后Mmu enter，无新增MMU；解释固定编译时间；原厂boot恢复Android完成1及三分区一致 · Q-111（提交后git log定位） · reports/mmu-branches-trial/2026-10-23-evening/

2026-10-23T21:28:57.597878+08:00 · 实际SEC HOB查询/日志尾部核对，0013独立profile40输入及完整补丁链通过，待CI · Q-112（git log定位） · reports/hob-query/；docs/operations/2026-10-23-hob-query-trace.md

2026-10-23T21:35:31.355085+08:00 · 首版HOB CI39961551151成功未实测，日志上限提高128避免过早截断；更新人工恢复不阻塞离线工作约定 · Q-113（git log定位） · docs/operations/2026-10-23-hob-query-trace.md；AGENTS.md

2026-10-23T21:44:02.567733+08:00 · HOB CI39962464061成功，47b5c4b1静态包验收通过，待实测 · Q-114（git log定位） · reports/hob-query/39962464061/

2026-10-23晚 · HOB诊断包实机到DXE，用户报告UniXNU菜单无OS；原图6cddd1c1已保存，恢复仍待确认，不推断MMU根因已修复 · Q-115 · reports/hob-query-trial/2026-10-23-evening/screen-observation.json

2026-10-23晚 · 用户两张照片确认NuwaBootMemoryDxe拒绝initrd范围、DXE MMU返回Success及UniXNU加载/FAT挂载；原图地址未可靠转录，不宣称XNU或系统卷发现通过 · Q-116 · reports/hob-query-trial/2026-10-23-evening/initrd-observation.json

2026-10-23晚 · 在独立固件仓实现有界卷封装接收，接入volume-envelope profile；主机C测试及完整输入补丁链通过 · Q-117 · reports/volume-envelope/

2026-10-23晚 · 补齐HOB实测恢复，完成严格卷探针打包脚本与真实64MiB FAT的C主机解析；新固件CI39966008923运行中 · Q-118 · reports/volume-envelope/full-size-host-parser.json

2026-10-23晚 · CI39966008923成功，ae9a445a完整卷探针核验并通知录像后临时启动；等待屏幕结果，未宣称卷发现或XNU通过 · Q-119 · reports/volume-envelope-trial/2026-10-23-evening/

2026-10-23晚 · 卷探针实测发现BAB00718零长度HOB原地循环，恢复Android及哈希闭环；加入0014查询GUID/PHIT及异常长度停止诊断，独立profile静态通过 · Q-120 · reports/hob-integrity/

2026-10-23晚 · 落实每次硬停同步交接/进度要求，重写主线交接并明确CI39973030321成功及未完成本地验收 · Q-121 · docs/operations/2026-10-23-mainline-handoff.md

2026-10-23晚 · dd1ef825新诊断包全表/新标记/容器核验通过，独立scope接入并刷新录像及设备门 · Q-122 · reports/hob-integrity/39973030321/

2026-10-23晚 · 归档dd1ef825录像摘要/两原图/菜单关键帧，记录同链不同GUID查询及BAB00718正常推进；重写进度和交接，本轮恢复未闭环 · Q-123 · docs/operations/2026-10-23-hob-integrity-trial.md

2026-10-24T00:15:19.951531+08:00 · 接手并补齐dd1ef825恢复闭环；修正卷发布错误传播，8项主机测试/新profile静态通过，准备CI · Q-124（提交后git log定位） · docs/operations/2026-10-24-volume-publisher-status.md；reports/volume-status/profile-check.json

2026-10-24T00:17:00.937798+08:00 · 启动CI39985245383，接入新scope严格试验门，2项新反向检查及5项原MMU门回归通过 · Q-125（提交后git log定位） · tests/test_volume_status_gate.py；docs/operations/2026-10-24-volume-publisher-status.md

2026-10-24T00:23:43.134759+08:00 · CI39985245383成功，新包a22e9a44/70266880B完整复验，41行内存表相同，用户已本轮确认录像，准备试验 · Q-126（git log定位） · reports/volume-status/39985245383/

2026-10-24T00:27:22.419670+08:00 · a22e9a44在新鲜录像门后临时启动ACK成功，120秒USB观察完成，屏幕与本轮恢复待补 · Q-127（git log定位） · reports/volume-status-trial/2026-10-24/

2026-10-24T00:39:15.327331+08:00 · 六原图确认chosen封装缺失、补init_boot静态选择证据与错误分级，恢复闭环；FV小探针源码/生成及主机检查通过 · Q-128（git log定位） · docs/operations/2026-10-24-error-triage-and-initboot.md；reports/embedded-probe/

2026-10-24T00:48:14.773032+08:00 · CI39988591973成功，内嵌探针包87b14624完整复验/41行内存一致，新scope门通过且用户本轮录像确认 · Q-129（git log定位） · reports/embedded-probe/39988591973/

2026-10-24T00:56:02.341592+08:00 · 87b14624原图确认4MiB发布Success及唯一探针配置菜单，FV→FAT→配置发现实机通过，恢复待闭环 · Q-130（git log定位） · docs/operations/2026-10-24-embedded-volume-trial.md；reports/embedded-probe-trial/2026-10-24/

2026-10-24T00:57:15.571203+08:00 · 87b14624本轮原Android恢复完成1及三分区SHA一致，FV配置发现里程碑收尾，转真实XNU/ADT输入 · Q-131（git log定位） · reports/embedded-probe-trial/2026-10-24/{recovery,postcondition}.json

2026-10-24T01:21:43.762242+08:00 · 当前源内核生成分析预链接5a128fb2，Libm完整常量池识别及65348重定位读回/代码保持/主机ParseKernel通过 · Q-132（git log定位） · docs/operations/2026-10-24-current-native-prelink.md；reports/native-prelink-current/

2026-10-24 · 接入独立ReadyToBoot只读启动输入审计，46输入/9补丁/12后哈希静态通过，完整构建待验 · Q-133 · reports/boot-input-audit/profile-check.json

2026-10-24T01:41:52.750228+08:00 · 启动输入诊断CI39995937843成功，a2dc8195/3153920B完成实际模块/内存表/严格容器与缺门拒绝校验；用户明确暂停，未操作设备，已落实交接 · Q-134 · reports/boot-input-audit/39995937843/

2026-10-24T01:44:39.161097+08:00 · 用户恢复并明确本轮录像许可；a2dc8195包/Android身份/恢复门复验后通知并单次临时启动ACK0，120秒USB观察中，阶段与恢复待验 · Q-135 · reports/boot-input-audit-trial/2026-10-24/

2026-10-24T01:54:51.259229+08:00 · a2dc8195本轮原图确认BAB00118/type4/len0保护性停点，未到ReadyToBoot；120秒观察后Android完成1/三分区不变；实际SEC与旧成功包仅构建时间4字节差异，根因未定 · Q-135 · reports/boot-input-audit-trial/2026-10-24/

2026-10-24T02:01:55.720812+08:00 · 离线加入可信arena的HOB创建/MMU/构造阶段诊断，47输入10补丁14后哈希及精确C主机保护页/ASan/UBSan通过，完整CI待验，无设备动作 · Q-136 · reports/hob-stage-audit/

2026-10-24T02:14:14.358409+08:00 · HOB阶段包CI40000310916成功，2273bdec/3153920B完成实际SEC检查调用/失败分支、41行内存表及严格容器复验，缺门设备子进程0；未操作设备，待通知录像 · Q-137 · reports/hob-stage-audit/40000310916/

2026-10-24T02:17:23.691609+08:00 · 用户新鲜录像确认后preflight通过，已即时通知并单次临时启动2273bdec/ACK0，120秒USB观察中；阶段与恢复待验 · Q-138 · reports/hob-stage-audit-trial/2026-10-24/

2026-10-24T02:26:06.995875+08:00 · 2273bdec原图定位last-create有效到after-mmu坏链，off718/type0/len0；Android完成1/三分区不变；公开资料+源码/实际指令支持首嫌HOB缓存交接，尚未实施修复 · Q-138 · reports/hob-stage-audit-trial/2026-10-24/

2026-10-24T02:38:56.760611+08:00 · 准备HOB使用范围IVAC交接0019，保留Heap/坏条目保护；51输入11补丁15后哈希和精确C主机边界/顺序/字节不变验证通过，完整CI待验，无设备动作 · Q-139 · reports/hob-cache-handoff/

2026-10-24T02:48:52.565741+08:00 · 缓存交接候选CI40005057158成功，26ef8efd/3153920B实际DSB/IVAC/DSB/ISB与坏条目保护、41行表及严格容器通过；缺门设备子进程0，无设备动作，待录像 · Q-140 · reports/hob-cache-handoff/40005057158/

2026-10-24T02:56:24.080562+08:00 · 26ef8efd用户确认录像后单次临时启动/120秒观察，用户报告进入UniXNU菜单；原Android恢复完成1/三分区SHA不变；缓存阶段原图待补，未宣布根因或iOS执行 · Q-141 · reports/hob-cache-handoff-trial/2026-10-24/

2026-10-24T02:58:55.763501+08:00 · 用户要求落实所有文档：同步README/STATUS/主线交接/候选说明/基线后续/实测/PENDING及D-025；历史原始证据保留，移除当前交接的重复启动命令，菜单文字与阶段原图区分；无新增设备动作 · Q-142（续接747d8fc） · docs/operations/2026-10-24-hob-cache-handoff-trial.md

2026-10-24T03:08:47.513216+08:00 · 五原图确认HOB维护后after-mmu与ReadyToBoot/菜单阶段实机通过；无OS符合exit探针，末尾充电为用户报告；补强缓存首因判断并将公开资料/明确排序要求写AGENTS第8节，无新设备动作 · Q-143（续接772465b） · reports/hob-cache-handoff-trial/2026-10-24/screen-observation.json

2026-10-24T03:17:12.549163+08:00 · OS入口离线续接：固定分配函数主机ASan/UBSan12项通过/高PA不截断，核对分析内核真实同余偏移；4MiB运输容量不足及prelink资格/ADT缺口明确，无板值或设备动作 · Q-144 · reports/loader-window-host/results.json、reports/os-entry-next-step/continuation.json

2026-10-24T03:28:17.252417+08:00 · 查最新上游主仓1a01c2af/12模块及同SoC：GPU/HID/显示实质更新，CPU/平台/Prelink实现未变；0005对新DarwinBoot内存apply通过，未采用或构建，无设备动作 · Q-145 · reports/upstream-review/2026-10-24/review.json

2026-10-24T03:46:17.280839+08:00 · 用户授权全部合并：基座e553e46真实merge推送，54冲突落实完整上游+3工作流，21模块固定；设备接入新固件/内核profile，63补丁/固件整链静态通过，CI待验 · Q-146 · reports/upstream-integration/2026-10-24/

2026-10-24T04:00:31.761882+08:00 · 固件40014018074成功，SEC与26ef8efd字节一致；主机解析24/packed/SMMU通过。内核首轮因漏前置zzw授权辅助函数链接失败，补真实实现并核验64项序列，待重建；GPU主机架构限制未验 · Q-147 · reports/upstream-integration/2026-10-24/

2026-10-24T04:19:54.495058+08:00 · 全量上游合并闭环：固件40014018074/FD2d606985、内核40015845083/bf14e530均成功并独立产物检查；64补丁、平台归档/零未定义、24解析/4常量池/9grant与GPU用户QEMU夹具通过；21源码纳入与可选功能激活分开，无手机动作 · Q-148（续接6070627） · reports/upstream-integration/2026-10-24/integration-result.json

2026-10-24T15:04:24.918562+08:00 · bf14新内核生成eb66542c分析预链接：65348绑定读回/30 donor代码范围不变/24解析；AMFI旧地址逆slide后定位真实注册调用，native dSYM局部策略结构一致，写入/调用时序未验仍loadable=false，无设备动作 · Q-149 · reports/native-prelink-merged/

2026-10-24T15:16:00+08:00 · AMFI时序和回调槽位：实际CI同64补丁重建/12源码检查通过，native dSYM335槽与原AMFI23项指针写入对应；DATA_CONST文件只读不等于早期页表只读，风险排序已修正。用户暂无OTG，问项关闭；完整初始化/ABI及运输仍待资格，无新包或设备动作 · Q-150 · reports/native-prelink-merged/init-phase-final.json、amfi-ops-slots.json

2026-10-24 · 按用户USB数据线方向构建v3运输候选8177783e与v4匹配离线对照91e86ce4，70266880B仅头部20/40两字节不同，固件/Heap/HOB/地址不变；7新测试/10历史门控、16原始ABL门字节QEMU夹具通过，版本来源补证；新包需独立封装64MiB发布证据，不以fallback菜单判成功，待本轮录像确认，无设备动作 · Q-151 · reports/usb-ramdisk/40014018074/、docs/operations/2026-10-24-usb-ramdisk-v3.md

2026-10-24T15:41:49+08:00 · 8177783e单次v3临时实测：原图独立envelope result=1/64MiB块Success/FAT先于embedded挂载，运输阶段实机通过；offset-64=vendor30899943B。120秒观察后固定原厂v4恢复，Android完成1/A槽及三分区SHA不变；无第二候选/OTG/flash。真实大文件SHA及XNU/ADT/ABI仍待资格 · Q-152（准备9cfaacd） · reports/usb-ramdisk-trial/2026-10-24-v3-01/、docs/operations/2026-10-24-usb-v3-trial.md

2026-10-24 · 运输实测已提交8de7b98；新独立EFI文件SHA app def33a4a/6KiB，复用固定MIT SHA、28项UEFI头pin；最终USB v3包18ebd838/70266880B含58,335,232B分析数据但无XNU执行项。13协议场景/3向量/15门控通过，完整UEFI QEMU从最终FAT实际读完/哈希匹配并返回。nuwa文件阶段待本包新录像，无新手机操作，原FD/Heap/HOB保护不变 · Q-153 · reports/file-read-audit/、docs/operations/2026-10-24-file-read-audit.md

2026-10-24T16:14:06+08:00 · 18ebd838单次实测：新菜单原图returned Access Denied，纠正等Enter判断；实际构建镜像验证库/0x04拒绝policy和PE无签名支持认证拒绝首因，文件SHA未实机通过。120秒观察后原厂v4恢复完成1/A槽/三SHA不变，无第二候选或策略改动；下一步离线保留认证入口诊断 · Q-154（包准备ab7e4b9） · reports/file-read-audit-trial/2026-10-24-01/、docs/operations/2026-10-24-file-audit-access-denied.md

2026-10-24 · 固件内NuwaFileAuditDxe源a155c495推送，新独立fv-file-audit profile及CI/模块和SEC/认证policy检查接入；57输入/12补丁/15后哈希通过，原guard保持，19实际C源AArch64 QEMU场景及一次性回调通过。实际固件CI/目标crypto/SEC同字节待验，无新手机动作或新试验包 · Q-155 · reports/fv-file-audit/、docs/operations/2026-10-24-fv-file-audit.md

2026-10-24 · CI40078257763固件编译成功但原包装符号检查因LTO失败，保留原日志；按实际Ready四次BL→572B SHA体和模块真实crypto链接修正并独立验收FD52ab071e/SEC7192fd3f逐字节相同及全部原保护/认证策略。纯数据FAT5ea19e90与首轮离线包6b3e5bfd已验收，待完整CI重跑，不启动手机 · Q-156（首轮源2b7328b） · reports/fv-file-audit/40078257763/

2026-10-24 · 第二轮40080439083/source dbbdc02完整成功；独立710项产物/7模块检查通过，FD52ab071e与首轮相同、SEC7192fd3f与已实测固件全同；原认证库/0x04和真实crypto调用保留。最终包6b3e5bfd/70266880B完整复验，23门控/19软件场景已有证据，待本包新录像，不要求Enter/键盘/OTG，本轮无新设备动作 · Q-157 · reports/fv-file-audit/40080439083/acceptance.json

2026-10-24 18:09 北京时间 · 6b3e5bfd单次实机58MB精确长度/EOF/SHA256 PASS，原厂恢复Android1及三分区SHA不变 · Q-158（本里程碑提交） · reports/fv-file-audit-trial/2026-10-24-01/。

2026-10-24 · 设备仓ADT生成器落地：make-nuwa-adt.py按基座契约补齐--gpu-addon/--text-fixup/--persistent-data，check-nuwa-adt.py独立解码最小12节点/20检查与完整21节点/35检查全通过，audit-nuwa-adt-inputs.py对实机FDT 14项对照10项精确相等0项不符，test-nuwa-adt.py正负例8用例全部符合预期（3生成/4违约树/1参数拒绝）；根compatible采用实机值并说明ArmDTPlatform不匹配该属性，iomem较FDT只少最后4KiB页而非55MiB；dram_size/owned_memory_size属受审字段未写入，提R-012待批，board仍example=true；无设备动作 · Q-159（本里程碑提交） · reports/adt-nuwa/2026-10-24/、docs/operations/2026-10-24-nuwa-adt.md

2026-10-24 · R-012批准A：board写入dram_size=0x240000000（实机FDT /memory最大连续段，与D-001吻合）与owned_memory_size=0x40000000（D-002上界），example=true/其余TODO/所有_verified未动；新增check-nuwa-adt-board.py按payload.py:149-170规则离线重放参数组装，board-only 21节点/31检查、带sidecar 21节点/34检查0失败；修正旧实现--unique-chip-id与--chip-id强制成对的契约不兼容（基座分别独立传参，board的chip_id仍TODO，成对会让payload exit 2），test增至10用例全过；窗口能否被固件满足仍未验证，无设备动作 · Q-160（本里程碑提交） · reports/adt-nuwa/2026-10-24/board.json、docs/NEED-REVIEW.md R-012

2026-10-24 · 早期安全初始化器通路打通：全内核38MB字节级交叉引用证明228个kext的kmod_start均为跳转桩且AMFI槽静态为0（空槽=无start，对照corecrypto已填），三个__mod_init_func仅做OSMetaClass静态注册，初始化由early_security_init驱动；native bf14e530导出_native_prelink_security_init_version=1，配置后emit前置检查全过并记录0xfffffff004703c54（原VA+slide）；根因为emit-current-prelink-analysis.py:18,43硬编码空映射；新候选1aeebf13与eb66542c差异全在__PRELINK_INFO、三可执行段零差异；修正全段capstone.disasm静默截断导致的假阴性结论；loadable仍false，调用ABI未资格化，无设备动作 · Q-161（本里程碑提交） · reports/native-prelink-merged/{amfi-callgraph,early-security-init,earlysec-diff}.json、docs/operations/2026-10-24-early-security-init.md

2026-10-24 · 注册调用ABI静态核对通过：0x5703fa4调_mac_policy_register，x0=&mac_policy_conf(0x6cb78a0)/x1=&handle(0x6cb6e1c)/x2=0，与security/mac_policy.h:6225三参数签名一致；conf的8个字段(0x00..0x38)偏移逐个对上mac_policy.h:6205-6216，mpc_ops@+0x20=0x6cb6e28与amfi-ops-slots的original_ops_address互证；native导出mac_policy_register(0x790a66c)，返回值按int判。修正两处脚本缺陷：参数寄存器反扫取最早adrp（改正向模拟）、stp的mem操作数下标为2（改查找）。blocker1静态部分基本清空，运行时仍未验证，无设备动作 · Q-162（本里程碑提交） · reports/native-prelink-merged/amfi-register-call.json

2026-10-24 19:2x · **首次内核进入试验（实机）**：fastboot boot 临时启动内核候选1aeebf13（带early_security_init），DarwinBoot打印Exiting boot services并出现绿色横条，XNU输出AppleARMPlatform/IODTNVRAM、SecurityLock::LockType=SOFTWARE_LOCK(Module 42B57F0A-…)、LockCapsuleInterface、App Log Flush 0 ms；约235秒后设备自动重启回Android，无需人工按键，恢复闭环三分区SHA未变。确切读数：kernel va 0xfffffff003DC8000 pa 0x8C01C8000、args pa 0x4C408000 window 0x40000000 bytes（1GiB窗口申请成功，blocker3得肯定答案）、TCR_EL1 0x28003518(4KiB granule，与D-003一致)、CurrentEL 1。菜单单条目高亮+1s倒计时自动启动，按电源键非Enter(Menu.c:219-236无电源键分支)。失败点判断置信中高：内核在Apple启动链安全锁阶段终止，缺SEP/硬件信任链；反证空白是这些字面串在XNU源码树/基座/donor/native/预链接产物中均不存在，主机无9008串口故无panic串志 · Q-163（本里程碑提交） · reports/xnu-first-entry-trial/2026-10-24/、docs/operations/2026-10-24-xnu-first-entry.md

2026-10-24 20:1x · **首次内核进入录像取证（实机）**：用户拍摄完整录像2d932cb8b5db1c97cde5eba6e4991325_raw.mp4（2分50.43秒，HEVC 59.97fps），本地按1fps抽170帧做像素统计（新增scripts/analyze-first-entry-video.py）重建完整时间线。**关闭上一轮唯一空缺：App Log Flush : 0 ms之后内核静默退出，19秒黑屏，无panic文本**（124s转黑，167s回到Android桌面）；退出口即"无输出"。**更正上一轮记录：绿条只存在于118-123秒共6秒，不是235秒**——绿条只是ExitBootServices瞬时标记，不代表内核存活时长；Module UUID首字符判读有误，应为42857F0A-13F2-4821-8A23-53D3F714B…（上轮读作42B57F0A）。**新证据两块**：①UEFI内存图日志[NUWA-BOOT-AUDIT]（源码uefi-nuwa/Platforms/Xiaomi/nuwaPkg/Drivers/NuwaBootAuditDxe/NuwaBootAuditDxe.c）读出largest base=0x8C0000000 bytes=0x240000000、descriptors=129 conventional=16 merged=16，与D-001主bank及R-012批准的dram_size独立吻合；②DarwinBoot逐个加载kext每行leave status=Success，装载阶段无失败点。**Si splash 定位（两次误判后定论）**：第45帧"Si/Project Silicon/28.085"标志先误判为另一台Apple Silicon设备屏幕、再误判为nuwa机身背面印刷图案，实为**画在nuwa屏幕上的Mu-Silicium boot splash**（uefi-nuwa即Project-Silicium/Mu-Silicium fork，docs/nuwa-unixnu.md:3记录baseline 6c67550，图案逐元素等同Silicon/Silicium/SiliciumPkg/Include/Resources/BootLogo.bmp）；判据是该区域第36-42秒高亮像素为0、第43秒随屏幕点亮突然出现2444个亮像素，机身印刷不可能如此；第60秒被UniXNU logo覆盖，全程只有nuwa一台。下一轮取证改走fastboot getvar与UEFI变量（adb为user build无su，读不到uefi_a分区） · Q-164（本里程碑提交） · reports/xnu-first-entry-video/2026-10-24/、docs/operations/2026-10-24-first-entry-video-forensics.md
