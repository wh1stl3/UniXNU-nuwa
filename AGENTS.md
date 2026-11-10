# AGENTS.md — UniXNU-nuwa

长期规则见共享治理文档：`D:/Code/PortingiOS/docs/governance-2026-11-06.md`（12 条，v2 对齐官方 format 2）。本文件只写 nuwa 专属约定。

## 目标
小米 13 Pro（nuwa / SM8550）通过 UniXNU 运行 iOS 16（donor: iPhone10,3 / 16.7.16 / 20H392，xnu-8796 线）。

## 基线
- 基座：`D:/Code/PortingiOS/UniXNU`（上游 main `e2fdae4` + 本地 `af9d099`（submodule pin：ArmCpu=93a5030、XnuPrelink=f1d80d3）与 `693f5d9cae8a408dd18b39f3f9fdc4228c934241`（iOS 16.7.16-20H392 profile））。
- **已是官方 format 2 骨架**：`schema_version = 2`、`feeds.toml`（钉 `UniXNU-sm8550-common@a9f45dc6…`）、`dts/nuwa.dts`、`configs/nuwa_defconfig`、`patches/xnu/series`、`porting.toml`、`scripts/package.sh`、`.github/workflows/*`。
- 当前（2026-11-10）：官方第 7 步；旧 stage5 实测 AppleImage4 `failed to get mix-n-match policy: 2`，显示后 park，无自动复位，不证明 stage5。`.cache/media/stage5-panic-20261110-183907/execution.log` 18:54:23 历史实查回 A/TWRP current/active=0；本轮未新查设备。
- AMNM-only chosen u32=0 是已批准的非 Apple bring-up 软件策略；本地主机产物仅 self-checked，未独立 verifier、未上机，禁止设备放行。BNCH 缺失+level0 的下一 panic 已闭环；Deep 最终裁定固定 donor 无已证明无 AP-token/no-shadow 入口，需要 provider 源码或受支持兼容实现。XNU wrapper/custom runtime 不能控制前置 BNCH init/内部 shadow 或替换内建 PMAP_CS，interface register 仅一次。不填假 BNCH、不改 level、不替换指针/跳 init；无支持前停止重复分析、构建和上机。证据见 `docs/mix-n-match-host-20261110.md`。
- 下一动作：审阅 `docs/appleimage4-provider-question-draft-20261110.md`，经用户许可发送或提供接口资料；本地草稿未发送。菜单自动下移仅用户观察；OEM SDAM/Reset 只是候选，日志级别过滤已确证未修。多设备规则以根 AGENTS 为准。
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
