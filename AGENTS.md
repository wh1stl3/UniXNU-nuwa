# AGENTS.md — UniXNU-nuwa

长期规则见共享治理文档：`D:/Code/PortingiOS/docs/governance-2026-11-06.md`（12 条，v2 对齐官方 format 2）。本文件只写 nuwa 专属约定。

## 目标
小米 13 Pro（nuwa / SM8550）通过 UniXNU 运行 iOS 16（donor: iPhone10,3 / 16.7.16 / 20H392，xnu-8796 线）。

## 基线
- 基座：`D:/Code/PortingiOS/UniXNU`（上游 main `e2fdae4` + 本地 `af9d099`（submodule pin：ArmCpu=93a5030、XnuPrelink=f1d80d3）与 `693f5d9cae8a408dd18b39f3f9fdc4228c934241`（iOS 16.7.16-20H392 profile））。
- **已是官方 format 2 骨架**：`schema_version = 2`、`feeds.toml`（钉 `UniXNU-sm8550-common@a9f45dc6…`）、`dts/nuwa.dts`、`configs/nuwa_defconfig`、`patches/xnu/series`、`porting.toml`、`scripts/package.sh`、`.github/workflows/*`。
- 当前（2026-11-10）：官方第 7 步；旧 stage5 实测 AppleImage4 `failed to get mix-n-match policy: 2`，显示后 park，无自动复位，不证明 stage5。`.cache/media/stage5-panic-20261110-183907/execution.log` 18:54:23 历史实查回 A/TWRP current/active=0；本轮未新查设备。
- AMNM-only chosen u32=0 是已批准的非 Apple bring-up 软件策略；本地主机产物仅 self-checked，未独立 verifier、未上机，禁止设备放行。BNCH 缺失+level0 下一 panic 已闭环，当前证据不批准任何 BNCH 运行候选。用户要求的 Deep 复核已完成：此前“必须源码/等待外部 provider”的绝对裁定撤回，仅作历史；完整 Apple 生产安全链不是官方 bring-up 阶段 5 前提，可研究明确实验软件域，以受限消费者闭环及充分认证负例证据解除门禁，不一定需闭源源码。不将任意值称真实硬件/donor nonce，不把初始化成功当认证成功；不改 level、不替换指针/跳 init。无新证据时不重复 BNCH 猜值、无效候选构建和上机，本地修复/分析/主机验证继续，适用审查门禁不变，上机前须用户确认。证据见 `docs/mix-n-match-host-20261110.md`。
- 最新主机里程碑：BNCH 四矩阵+26 evidence robustness 独立 verifier PASS，静态 review 限构造初态；consumer-parse 静态 review/独立 verifier PASS，真实注册一次 version18→index1/apin→畸形 manifest parser3→mapper92→wrapper92，仅三纯 log stub。nonce/认证、firmware 构造/execute/auth callback/PMAP install NOT REACHED；trst 非 apin 阳性、无签名正例。下一本地主机动作确认可解析 manifest/对应 apin payload/真实状态，缺则明确输入/接口边界，不猜值、不虚报认证通过。见 `docs/image4-bnch-offline-20261110.md`。公开仅只读、不外发；general 发布取消，未发 comment/issue。PR187 仅传输，不解除门禁，完整证据仍保留。
- 固件提交 `719afa67e3aebbf058c2a8beff4c801057fb2b20` 仅 DEBUG 组件 mask `0x8007EE4F`，静态 review+机械 PASS；旧 edksetup 缺失，完整 EDKII 解析/AutoGen/编译/设备未验证，3 脏子模块保留。本会话不改固件。菜单下移仅观察，OEM SDAM/Reset 候选不变；mask 修复不证明其因果。另 general 正执行已授权恢复 Android/清 userdata，最终结果待回报；上行 A/TWRP 仅最后已知历史快照，不代表当前设备状态。多设备规则以根 AGENTS 为准。
- crypto 事实：`CONFIG_XNU_CRYPTO_BOOTSTRAP="prelinked"`；`prng_random.o` 最终 `-U XNU_SOURCE_CORECRYPTO14`，当前 prelink 无 `_source_corecrypto14_bootstrap`，不能声称 console 后必经 source corecrypto EARLY_BOOT。不切换 crypto 模式。
- 仍未验收：正常启动、平台服务发布、存储与用户态；内存所有权问题不因探针阳性自动关闭。ADT 身份/种子约定不变，root UUID 留待根卷阶段。`scripts/` 历史审计工具不再充当 ADT 生成器。

## 目录约定（官方布局）
- 板级文件：`board.toml`、`porting.toml`、`feeds.toml`、`configs/`、`dts/`、`patches/xnu/series`、`package/`、`scripts/package.sh`、`proprietary-files.txt`、`local.toml.example`。
- `drivers/`、`kits/` 不是设备仓目录——驱动与库来自组件仓，共享资源来自 SM8550 仓；设备 `package/` 在构建树内成为 `kits/nuwa`。
- 本机覆盖写 Git 忽略的 `local.toml`；设备输入写 `unixnu.local.toml`（基座检出处）。

## 硬边界
- flash/erase/改槽等设备写入动作：须用户当轮明确授权。
- 唯一 ECID（`--unique-chip-id`）等设备种子只经命令行或 Git 忽略的配置传入，不入库（治理 §6）。
- 含 Apple 组件的产物（`kernel.macho`、`boot.img` 等）只留本地 out/，不上传 GitHub（治理 §7）。
- 不照抄 sheng 板值（MMIO/IRQ/面板/电源/chip_id 均须 nuwa 证据）；组件一律用规范 ID。

## 记录纪律
`porting.toml` 是唯一权威记录：改代码同步对应区域的 findings/evidence，并跑 `python3 scripts/porting-record.py check --device .`。

## 关联文档
- AI 分工与调度：`../../docs/ai-orchestration-2026-11-06.md`。
- 路线背景：`../../docs/nuwa-ios17-sheng-migration-2026-11-06.md`。
