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
