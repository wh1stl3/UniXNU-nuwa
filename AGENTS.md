# AGENTS.md — UniXNU-nuwa

长期规则见 `D:/Code/PortingiOS/docs/context-brief.md`（目标/卡点策略/硬边界）；路由见 `docs/routing.md`，决策见 `docs/decisions.md`。本文件只写 nuwa 专属约定。

## 目标
小米 13 Pro（nuwa / SM8550）通过 UniXNU 运行 iOS 16（donor: iPhone10,3 / 16.7.16 / 20H392，xnu-8796 线）。

## 基线
- **显示官方验收尚未通过**：以 `UniXNU/docs/zh/porting/display.md:30–56` 为准：XNU 发布显示服务；CPU 路径确认像素布局、行跨度、分配大小及缓存处理并实际显示已知画面；交换完成；IOSurface 生命周期与交换完成通知闭合；分别记录请求刷新率及实测帧时序；全部完成后才启用 GPU 呈现。
- 当前仅传输链路冒烟（主控转述 / self-checked：`reg=2 cli=4 vo=6 vb=0 co=6 cb=0 ret=6`）；`co` 可能含清屏，缺已知画面显示、IOSurface 生命周期/通知闭环及请求刷新率/实测帧时序证据；`bk/so/PIX` 仅诊断拆分，不是验收标准。
- 2026-11-25 PIX 源像素签名候选，仅主机 self-checked，未刷写：[记录](docs/nuwa-pixsig-20261125.md)。
- 2026-11-25 lsd 异常帧链候选仅主机 self-checked、未刷写、待深审：[记录](docs/nuwa-crashframes-20261125.md)。
- 2026-11-25 DSP 回调计数候选仅主机 self-checked、未刷写：[记录](docs/nuwa-dspcount-20261125.md)。
- 2026-11-25 lsd 异常寄存器采集候选仅主机 self-checked，未刷写、待深审：[记录](docs/nuwa-crashcap-20261125.md)。
- 2026-11-25 lsd 900 秒采样候选仅主机 self-checked，未刷写、待启动链深审：[记录](docs/nuwa-stack900-20261125.md)。
- 2026-11-25 IconServices 禁用项后 lsd 观察（主控转述 / self-checked）：[记录](docs/nuwa-icondisabled-20261125-observation.md)。
- 2026-11-25 显式禁用 IconServices job 候选主机包 self-checked、待深审：[打包记录](docs/nuwa-icondisabled-20261125.md)，[本轮观察](docs/nuwa-icondisabled-20261125-observation.md)。
- 2026-11-25 full seed + candidate disable + PEER 仅主机 self-checked，未上机、待深审：[记录](docs/nuwa-final-20261125.md)。
- 2026-11-24 8 目录 seed + lsd 探针包仅主机 self-checked，未上机、待 deep review：[记录](docs/nuwa-seed-containers-20261124.md)。
- 2026-11-24 lsd 深帧优先级修订主机包 self-checked、未上机：[记录](docs/nuwa-lsd-deep-20261124.md)。
- 2026-11-23 **SMP 入口关候选：观测版仅追加 `sheng-smp=1`，未上机**。判据、止损与复跑见 [记录](docs/nuwa-smp-observe-entry-20261123.md)；需 `deep_reviewer` 复审启用后的失败面与可观测性。
- 2026-11-23 **SMP 入口观测包：默认关闭、未上机**。启动页和交接后横幅的字段、回读与复审见 [记录](docs/nuwa-smp-observe-20261123.md)。
- 2026-11-23 **SMP 入口门：默认关闭、仅主机、未上机**。`reset_vector` 在 BCM2837 改用 AFF1:AFF0（`0xFF→0xFFFF`，已入 device series），`ArmCpu::probe` 只在 `sheng-smp` 非零时准入 `reg 0x100` 一个次核；未新增 boot arg。kernel `6af982c3…`、outer `b02007f7…`、CHMH `1f9c8fef…`、FAT 剩余 11,664,896 B；入口关/运行关未验，需 `deep_reviewer` 复审。见 [记录](docs/nuwa-smp-gate-20261123.md)。
- 2026-11-23 **nuwa-sb-stack rev3 参数版：去掉两个 restart 参数、kernel 不变（仅主机打包，未上机；待复审 args 差异）**：[记录](docs/nuwa-sb-stack3-20261123.md)；探针本体见 [rev2](docs/nuwa-sb-stack-20261123.md)。
- 2026-11-23 **SpringBoard 重启后仍无新帧，原因未证，交互未达**（主控转述 / self-checked）：[记录](docs/nuwa-sb-stall-20261123.md)。
- 2026-11-22 **六进程在场，mobileactivationd 迁移失败候选待查，交互未达**（主控转述 / self-checked）：[观察](docs/nuwa-mobileactivation-migration-20261122.md)。
- 2026-11-22 **Apple logo 里程碑**（主控转述实机、self-checked；持久交互未达成）：见 [记录](docs/nuwa-logo-milestone-20261122.md)。
- 2026-11-20 **FAT 计数更正（主机 self-checked，未上机）**：ON 通过，原 r35 OFF 低于原门槛；见 [本轮记录](docs/nuwa-r35-display-fat-correction-20261120-observation.md)。
- 2026-11-21 **r35f 首次实机观察（用户录像及 vision 转录，非独立 verifier）**：见 [本轮记录](docs/nuwa-r35f-first-boot-20261121-observation.md)；主机构建及深审见 [原记录](docs/nuwa-r35f-thread-ready-20261121-observation.md)。
- 2026-11-20 **r35e IRQ 绘制门禁（仅主机，未上机，待复审）**：见 [本轮记录](docs/nuwa-r35e-irqguard-20261120-observation.md)。
- 2026-11-20 **r35d 快照修复（仅主机，未上机，待复审）**：见 [本轮记录](docs/nuwa-r35d-snapshot-20261120-observation.md)。
- 2026-11-20 **r35c 退出诊断候选（仅主机，未上机，复审待完成）**：见 [本轮记录](docs/nuwa-r35c-exit-detail-20261120-observation.md)。
- 2026-11-20 **r35b 瘦身候选（仅主机，未上机）**：见 [本轮记录](docs/nuwa-r35b-compact-20261120-observation.md)；旧 r35b 未达到 FAT 门槛。
- 2026-11-20 **时基已核对、r35 主机复现一致，第一阻塞不变（交互目标仍未达成）**：r34 页面 CLK 行 `cntfrq=19200000 dt=19200000 dv=6143960ms cv=6143960ms`，`cntfrq_readback` 缺口闭合（仅 boot CPU、6144 s 零漂移）；r35 主机复现逐字节一致但**仍未上机**（上机授权在写入前由用户取消，槽位状态待确认），设备仍跑 r34（`vendor_boot_a` `46aa4fd9…891e`），第一阻塞仍是 SpringBoard/mobileactivationd 的 SIGTRAP 读数缺失。见 `docs/nuwa-r34-page-evidence-20261120.md`；逐轮细节见 `docs/nuwa-userspace-20261119-observation.md`。
- 2026-11-19 **用户态推进 r16–r35（交互目标仍未达成）**：r34 上 SpringBoard 与 mobileactivationd 以 **SIGTRAP** 退出，为当前第一阻塞；显示服务（`GopFramebuffer`）未接、SMP 未开启、认证仍 **NOT REACHED**；r35（异常退出环）已构建**未上机**，设备现跑 r34（`vendor_boot_a` `46aa4fd9…891e`）。逐轮载荷/内核/seed 哈希、设备读数、八项关键发现与证据路径见 `docs/nuwa-userspace-20261119-observation.md`（主机侧 self-checked，设备侧主控转述）。
- 2026-11-15 **原生 UFS 根卷 → launchd 用户态**（交互目标仍未达成）：`userdata` 前 8446279680 B 写入并整镜像回读 `da429da6…68d7`，根卷 `boot-uuid=DADD93F8-…-0F11E64172F7`、`native-ufs-root=1`、无 ramdisk；主控转述用户实机观测到青带 3（initproc exec 完成）与橙带 15（initproc 回到内核）。启动载荷已写入 `boot_a`(`692cfcca…`) 与 `vendor_boot_a`(r7 `24258f44…`/r8 `8e09fae2…`/r9 `37b665da…`)。主机侧一律 self-checked；认证 NOT REACHED；launchd 之后、显示服务、断电重启仍回同系统均未验证。详见 `docs/nuwa-launchd-reached-20261115.md`。
- 2026-11-15 启动链绕行台账（现象 / 绕过 / 代价 / 解除条件）：
  - root 卷挂载后 `rootvp not authenticated` 致 panic → `8796-nuwa-root-auth-skip` 记录 errno 继续 / 代价：认证未做、NOT REACHED / 解除：真实 trust cache 与 IPSW 认证链可用。
  - `query_trust_cache()` 在 `lck_rw_lock_shared` 上 panic（`trust_cache_rt_lock` 零锁）→ `8796-nuwa-trust-cache-init` 在 `machine_lockdown()` 前恢复 `trust_cache_runtime_init()`+`load_static_trust_cache()` / 代价：ADT `TrustCache` 条目为 `{0,0}`，加载为空操作 / 解除：memory-map 指向真实打包 trust cache。
  - launchd exec 被 AMFI 拒（EXEC/8）致死 initproc → `8796-nuwa-exec-policy-skip` 仅对 initproc 忽略 `ip_mac_return` / 代价：initproc 首 exec 不受签名策略约束；`amfi_get_out_of_my_way=1` 实测无效 / 解除：非空运行时 trust cache。
  - 显示服务缺失 → `deferred`，只有 `vinfo` 观测带 / 代价：无 UI / 解除：接 `GopFramebuffer` 与 launchd 显示服务。
  - 三个绕过补丁为 opt-in（`-DXNU_NUWA_*=1`），按既有约定不列入 `patches/xnu/series`；观测补丁保持未跟踪。
- 2026-11-14 `ufs-queue-five-20261114-01`：主控转述用户两照片显示五次队列观察完成；最终 binary reviewer 的加载合同及画面/栈与产物一致，非认证。旧队列地址是 DMA 地址，RSR=1 未停、DB=0 仅瞬时，不证明 ownership；恢复独立 host verifier 18/18 PASS，A 无镜像级回读、serial 未重新硬件关联，不称当前 live/长期稳定。下一 host 有界 SID `0x60` 域只读候选已启动，TPL 支线 deferred，无新设备授权。详见 `docs/nuwa-ufs-queue-five-run-20261114.md`。
- 2026-11-14 `ufs-hc-observe-20261114-01`：四读完成后预设 inspect panic；vision 终止画面约 2.5–13.27 秒无重启，最终 binary reviewer PASS WITH CONDITIONS。UFSHCI 4.0、32 transfer/8 task 仅为瞬时 HC 状态，不证 DMA/transport/root。恢复独立 verifier PASS，A 无镜像级回读，restore exit 原日志已清理且无 runid，整体 exit 未独立确认；不称当前 live/长期稳定。下一 host 单次 NOP 先处理 ownership、producer exclusion、SMMU 域；下一设备操作未授权。见 `docs/nuwa-ufs-hc-observe-20261114.md`。
- 2026-11-13 PMGR：主控转述 kernel directed deep PASS WITH CONDITIONS / 独立 verifier PASS，mode2 CHMH 包装普通 review / 独立 verifier PASS；执行器新增 profile 仅 self-checked，待独立 review/verifier。观察真实 nub 发布和 AMFI 消费，不以旧 panic 消失证明 pthread 已过；三阶段均需新授权。见 `docs/pmgr-executor-host-20261113.md`。
- 2026-11-13 PMGR：主控补 ordinary review PASS WITH CONDITIONS 的显式 root-parent 路线，撤回初始硬阻塞；已产隔离 kernel `81b85228…3280b5d1`/55451648 B，8 绑定重定、325 最终虚槽、10 项有界真实代码检查 self-checked。完整 IOKit 生命周期/pthread runtime 未证，实际启动链 ABI 待 deep_reviewer/独立 verifier；新 kernel 未来须 CHMH 重绑。集中证据 `docs/nuwa-platform-power-kernel-20261113.md`。r2 archive 及旧产物保留；此前恢复独立 host PASS 不代表当前 live。
- 2026-11-12 主控转述：CHMH-only `chmh-20261112-01` 四帧经 reviewer 确认 `bsd_init`→`pthread_init` NULL 表 panic；备份及 restore-readback 100663296 B、SHA256 `493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad` 独立 verifier PASS，原始 serial 关联限制不消除。donor pthread prelink、renderer 和 pthread+CHMH FAT/outer 均已获普通 review/独立 verifier PASS；静态启动链闭合但 runtime 未证。新执行器 profile 仅 self-checked；见 `docs/pthread-executor-host-20261112.md`。
- 基座：`D:/Code/PortingiOS/UniXNU`（上游 main `e2fdae4` + 本地 `af9d099`（submodule pin：ArmCpu=93a5030、XnuPrelink=f1d80d3）与 `693f5d9cae8a408dd18b39f3f9fdc4228c934241`（iOS 16.7.16-20H392 profile））。
- **已是官方 format 2 骨架**：`schema_version = 2`、`feeds.toml`（钉 `UniXNU-sm8550-common@a9f45dc6…`）、`dts/nuwa.dts`、`configs/nuwa_defconfig`、`patches/xnu/series`、`porting.toml`、`scripts/package.sh`、`.github/workflows/*`。
- 当前（2026-11-10）：官方第 7 步；旧 stage5 实测 AppleImage4 `failed to get mix-n-match policy: 2`，显示后 park，无自动复位，不证明 stage5。`.cache/media/stage5-panic-20261110-183907/execution.log` 18:54:23 历史实查回 A/TWRP current/active=0；本轮未新查设备。
- AMNM-only chosen u32=0 是已批准的非 Apple bring-up 软件策略；本地主机产物仅 self-checked，未独立 verifier、未上机，禁止设备放行。BNCH 缺失+level0 下一 panic 已闭环，当前证据不批准任何 BNCH 运行候选。用户要求的 Deep 复核已完成：此前“必须源码/等待外部 provider”的绝对裁定撤回，仅作历史；完整 Apple 生产安全链不是官方 bring-up 阶段 5 前提，可研究明确实验软件域，以受限消费者闭环及充分认证负例证据解除门禁，不一定需闭源源码。不将任意值称真实硬件/donor nonce，不把初始化成功当认证成功；不改 level、不替换指针/跳 init。无新证据时不重复 BNCH 猜值、无效候选构建和上机，本地修复/分析/主机验证继续，适用审查门禁不变，上机前须用户确认。证据见 `docs/mix-n-match-host-20261110.md`。
- 最新主机里程碑：BNCH 四矩阵+26 evidence robustness 独立 verifier PASS，静态 review 限构造初态；consumer-parse 静态 review/独立 verifier PASS，真实注册一次 version18→index1/apin→畸形 manifest parser3→mapper92→wrapper92，仅三纯 log stub。nonce/认证、firmware 构造/execute/auth callback/PMAP install NOT REACHED；trst 非 apin 阳性、无签名正例。下一本地主机动作确认可解析 manifest/对应 apin payload/真实状态，缺则明确输入/接口边界，不猜值、不虚报认证通过。见 `docs/image4-bnch-offline-20261110.md`。公开仅只读、不外发；general 发布取消，未发 comment/issue。PR187 仅传输，不解除门禁，完整证据仍保留。
- 固件提交 `719afa67e3aebbf058c2a8beff4c801057fb2b20` 仅 DEBUG 组件 mask `0x8007EE4F`，静态 review+机械 PASS；旧 edksetup 缺失，完整 EDKII 解析/AutoGen/编译/设备未验证，3 脏子模块保留。本次文档更新未改固件，不限制其他已授权固件构建。菜单下移仅观察，OEM SDAM/Reset 候选不变；mask 修复不证明其因果。多设备规则以根 AGENTS 为准。
- 最新研究记录：`docs/image4-firmware-evaluate-20261110.md` helper/issuer 独立复跑，ledger 独立机械执行/schema 核验完成：2584 bzero/clear各全覆盖、free零/size闭合，后5152来源 BLOCKED；OOM原-13→evaluate80无成功alloc/free，13隔离模型负例PASS。首次JSON错误字段KeyError后仅修正核验exit0；非认证证据，static review因服务端cyber_policy未完成，不集成研究代码、不扩大门禁。
- 最新设备状态：Launcher 后锁屏反复重启，非稳定恢复；旧 exec-in EIO退出未知、完整super回读不符仍保留，不定案尾部截断。`.cache/super-window-v1` 原25tests/manifest独立PASS不代表新兼容修正已完成：当前0 byte停于bootmode unknown，无后台writer，general在修复工具，非分窗写进行中。用户本轮RAM smoke→super-only分窗写回读授权不撤销，身份/回读门禁不变。userdata已清Android，iOS UFS不在，未来iOS恢复需新授权。主机提交 `8ae344cc05879a27cf77b5103e30b2ca51a6d41d` 不变，本轮记录未提交。本次文档更新未运行研究/设备命令、未改脚本或恢复工具；其他已授权任务仍按各自边界推进。本地主机实现/验证继续，上机前确认，super恢复另有本轮授权。公开资料只读，不对外发消息。
- crypto 事实：`CONFIG_XNU_CRYPTO_BOOTSTRAP="prelinked"`；`prng_random.o` 最终 `-U XNU_SOURCE_CORECRYPTO14`，当前 prelink 无 `_source_corecrypto14_bootstrap`，不能声称 console 后必经 source corecrypto EARLY_BOOT。不切换 crypto 模式。
- 仍未验收：正常启动、平台服务发布、存储与用户态；内存所有权问题不因探针阳性自动关闭。ADT 身份/种子约定不变，root UUID 留待根卷阶段。`scripts/` 历史审计工具不再充当 ADT 生成器。

## 下一步
- 2026-11-25：lsd 崩溃分析冻结，主线转显示接线；下一版用已审的 pixsig 探针（outer `28d45ab6c3d7c5ec79cf14543af4836dadf04de7eddaa91fd876b36bc831dbcc`）区分 `bk` 清屏与 `so` 真 surface，再按结果决定是否处理 CA 软件后端、转换/扫描输出或 vsync。

## 阻塞
- 卡点优先查 [已知差异与跨项目关停手段清单](docs/nuwa-open-deltas-20261125.md)。
- 2026-11-22：持久 Data 与显示/交互仍受阻，认证 NOT REACHED；主控转述实机与深审、主机 self-checked，详见 [本轮结论](docs/nuwa-session-20261122-findings.md)。
- CPU-only 显示 ON 候选按 329 止损条件冻结，OFF 诊断路径保留，329 guard 不动；这是 deferral，非绕过。三项止损均未闭合，解除条件及证据见 [329 决策记录](docs/nuwa-329-stop-20261121.md)；ON 产物保留分支、不上机。self-checked。

## 目录约定（官方布局）
- 板级文件：`board.toml`、`porting.toml`、`feeds.toml`、`configs/`、`dts/`、`patches/xnu/series`、`package/`、`scripts/package.sh`、`proprietary-files.txt`、`local.toml.example`。
- `drivers/`、`kits/` 不是设备仓目录——驱动与库来自组件仓，共享资源来自 SM8550 仓；设备 `package/` 在构建树内成为 `kits/nuwa`。
- 本机覆盖写 Git 忽略的 `local.toml`；设备输入写 `unixnu.local.toml`（基座检出处）。

## 硬边界
- flash/erase/改槽等设备写入动作：须用户当轮明确授权。
- 唯一 ECID（`--unique-chip-id`）等设备种子只经命令行或 Git 忽略的配置传入，不入库（见 context-brief 硬约束）。
- 含 Apple 组件的产物（`kernel.macho`、`boot.img` 等）只留本地 out/，不上传 GitHub（见 context-brief 硬约束）。
- 不照抄 sheng 板值（MMIO/IRQ/面板/电源/chip_id 均须 nuwa 证据）；组件一律用规范 ID。

## 记录纪律
`porting.toml` 是唯一权威记录：改代码同步对应区域的 findings/evidence，并跑 `python3 scripts/porting-record.py check --device .`。

## 关联文档
- AI 分工与调度：`../../docs/routing.md`。
- 路线背景：`../../docs/decisions.md`。
