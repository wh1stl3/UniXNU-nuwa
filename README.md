# UniXNU-nuwa

**当前（2026-11-15）：原生 UFS 根卷挂载成功，launchd 进入用户态；交互目标未达成。**
`userdata` 前 8446279680 B 写入并整镜像回读 `sha256=da429da6…68d7`；根卷
`boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7`、`native-ufs-root=1`、无 ramdisk。
三处启动链绕过（root auth 跳过 / trust cache 在 lockdown 前初始化 / initproc exec
策略跳过）与实机观测带（青 3 = exec 完成，橙 15 = initproc 回到内核）见
[里程碑记录](docs/nuwa-launchd-reached-20261115.md)。启动载荷已写入 `boot_a`
（`692cfcca…`）与 `vendor_boot_a`（r7 `24258f44…`、r8 `8e09fae2…`、r9 `37b665da…`）。
认证仍为 NOT REACHED（未认证 CHMH）；launchd 之后的一切、显示服务、以及
「断电重启仍回到同系统」均未验证。主机侧产物一律 self-checked，设备侧为
主控转述的用户观测。

**用户态推进（2026-11-17 – 11-19，r16–r35）：**SpringBoard 与 mobileactivationd 在 r34 上以 SIGTRAP 退出，
这是当前第一阻塞；显示服务未接、SMP 未开启、认证仍 NOT REACHED，r35（异常退出环）已构建**未上机**。
逐轮载荷哈希、设备读数与关键发现见
[用户态观察记录](docs/nuwa-userspace-20261119-observation.md)。

**PMGR checkpoint (2026-11-13):** root-parent kernel built, SHA256
`81b85228316574782f9d5390956c3ce3d8c97e4b345a9ea1631feacf3280b5d1`,
55451648 B; 8 bindings / 325 final slots / 10 bounded real-code checks self-checked.
[Evidence and commands](docs/nuwa-platform-power-kernel-20261113.md).
Directed deep review and independent verifier pending; full IOKit lifecycle and
pthread runtime unproven. Future CHMH rebind required; prior restore has independent host PASS.

**历史（2026-11-14）：官方第 7 步，交接暂停。** 真实 UFS 持久交互当时未达成；NOP 曾实机成功并恢复。r5 只读 root kernel 和 r2 CHMH 包的主机审查/验证边界、产物 pin 及操作步骤见[userdata 交接](docs/handoff-userdata-20261114.md)。用户已授权无备份安装指定 userdata 前缀，不包括 root 启动或启动分区写；所有本轮尝试均在写前停止，写入 0 字节，无有效备份。最终 CRLF 安装器修复的 10 项定向测试仅 self-checked，独立复跑尚未完成；新会话按最新规则裁定并完成必要验证。目标是真实 UFS 持久可交互并断电重启；[机型进度](../AGENTS.md)。以下旧进度、授权与下一步均为历史快照。
旧 stage5 `998d284a…` 已测：照片确认 AppleImage4 panic `failed to get mix-n-match policy: 2`，
未自动复位；panic 显示后 park 符合预期，不证明 stage5。设备历史：用户手动 TWRP 非 root 卡刷，59/60 回读匹配但 super 不符；知悉后内置 Format Data（userdata F2FS/关联 metadata RC0）再观察进入 Launcher，随后锁屏反复重启，不能称稳定恢复。旧 exec-in 写 super 出现 remote stdin EIO，退出未知；首次完整回读 9663676416 B SHA256 `c1d974966eccdf8eba6685b03833c0635ddf2fa402bcf6e9da498aa8ee25f8b5`，不符目标 `1afda55e0395157ba643070944b7df2c5e504ece48ee89b0edda4e0375ffca7b`。未定案尾部截断，AOSP exec-in 关闭语义仅机制解释。`.cache/super-window-v1` 原144×64MiB local25tests/manifest独立PASS，新兼容修正尚未完成；当前0 byte停于bootmode unknown，general无后台writer、工具修复进行中，非分窗写进行中。用户本轮RAM smoke→super-only分窗写回读授权仍有效，身份/回读门禁不变。userdata已清Android，iOS UFS根不在；未来iOS恢复需新授权，boot_completed/实际版本未机器确认。
此前本地提交 `f660735b72e84331f4ea932b8f4002b745815412` 仅新增 `/chosen/mix-n-match-prevention-status` u32=0（AMNM=true，非 Apple 启动链 bring-up 软件策略，非 donor/熔丝事实；放宽反重放令牌/chained-manifest-hash 约束，不关闭 AMFI、不宣称 Apple secure boot）。
该候选保持既有 stage5/panic/kernel/prelink/crypto/trust，仅组装一次 payload/vendor_boot，增量自检 exit 0，**self-checked，未独立验证、未上机**。本轮本地主机里程碑一次提交三个离线研究脚本及记录，无新镜像构建/设备操作，不 push/merge。
**当前证据不足以批准任何 BNCH 运行候选，AMNM-only 禁止设备放行。** BNCH 缺失且当前 secure-boot-level=0 会触发下一 panic。用户要求的 Deep 复核已完成：此前“必须取得 AppleImage4 源码/等待外部 provider”的绝对裁定已撤回，仅作历史；完整 Apple 生产安全链不是官方 bring-up 阶段 5 前提。可研究明确实验软件域，以受限消费者闭环及充分认证负例证据解除门禁，不一定需闭源源码。不将任意值称真实硬件/donor nonce，不把初始化成功当认证成功；不改 level、不替换指针或跳 init。无新证据时不重复 BNCH 猜值、无效候选构建和上机；本地修复/分析/主机验证继续，适用审查门禁不变，上机前须用户确认。
离线 BNCH 四矩阵+26 evidence robustness 独立 verifier PASS，静态 review 仅认可构造初态；consumer-parse 静态 review/独立 verifier PASS：实际注册一次 version18→index1/apin→畸形 manifest parser3→mapper92→wrapper92，仅三纯 log stub。firmware 构造/execute/auth callback/PMAP install 及 nonce/认证 NOT REACHED；trst 非 apin 阳性，无签名正例。见[证据](docs/image4-bnch-offline-20261110.md)。
最新本地主机 checkpoint：`63769f208783769f7fa4ec5cffc14d3eba37b21a` 已记录 UFS 审计脚本/文档及 ledger 主控静态审查，未 push/merge。[UFS 独立 verifier](docs/nuwa-ufs-input-audit-20261110.md#independent-verification-2026-11-10) self-test 7、audit 32 nodes/59 refs/0 issues、py_compile/diff 均 exit0，输出 `out/verifier-ufs-20261110`；`driver_readiness=BLOCKED`，未启用驱动，区域等级不变。
最新[firmware-evaluate/ledger 证据](docs/image4-firmware-evaluate-20261110.md)：helper/issuer 及 ledger/OOM/13 模型负例已独立机械复跑/schema 核验；首2584 bzero/clear/free闭合，后5152来源 BLOCKED，OOM原-13→evaluate80，无成功alloc/free。主控静态 PASS WITH CONDITIONS 仅限 SHA256 `94d09c6b…` 单脚本的 harness 安全/模型一致性，不是完整依赖或原生 ABI 独立审查；研究脚本仍未集成，不称认证 PASS，不笼统关闭适用门禁。
下一本地主机动作：只读明确完整消费者契约及 apin/IM4M 输入边界；本地基座完整 HEAD/path/行号、单文件 clean 限定及同期搜索范围以[2026-11-11 只读补核](docs/ios-handoff-20261110.md#local-base-readonly-20261111)为准。原 reviewer revision 未记录；本次确认的空 manifest-properties 行段不是全仓无 producer 或最新远端结论。nuwa 已设置 AMNM-only，但 native-trust-cache-runtime/AMFI 属性不能替代缺失契约。资产核查仅覆盖基座 `out/ipsw/20H392` 十二文件、未见 apin/IM4M，其他缓存未查、另行定位中，不推断全机无资产。并行准备 UFS iOS16/8796 ABI 与固件资源/队列交接的只读输入 brief；不扩张 DMA/SMMU 或设备门禁。公开仅只读不外发。
主控已接受主机 checkpoint（2026-11-11）：[owner-defined boot-artifact BNCH](docs/owner-boot-artifact-bnch-plan-20261111.md#independent-host-acceptance) 获 reviewer 主机静态 PASS WITH CONDITIONS；verifier 11项、启用/record复用、原initializer及缺失2/超长84独立失败控制通过，py_compile/record14/diff各0。新独立 ADT `out/owner-bnch-verifier-final-20261111/final.adt`（13256B）SHA256 `269170758882aa3b58c1de9f803a0563e774742ea7d1056ed3d9ff90299ce147`，fresh原始输入checker exit0；fresh报告无failure_controls，沿用独立测试报告控制，不称fresh重跑。仅主机生成及原initializer构造态独立验证，未接入正式payload，不是认证/runtime/stage5/device；固定kernel/base不变，无新设备候选。test08新ignored fixture的init/HEAD/alternates例外获主控批准，无commit/项目仓Git写入，非“零Git写入”；传递依赖新增绑定而非历史hash匹配，详见说明。下一步单独reviewer受限诊断设计→deep→实现/包装/独立核验→申请设备授权；阶段等级不提升。
主控已接受[显式payload窄wrapper](docs/owner-payload-host-20261111.md)：三脚本/board静态review PASS无整改；verifier5测试、追加后新record的实际CLI/FAT回读、正常禁用/旧record拒绝均exit0。独立payload `out/owner-payload-verifier-final-20261111/` 内64MiB SHA256 `cebc736cc8d5f248c7e57887dda94f904a13e0a29b4d45adb664c55235b2a5c3`，提取kernel仍固定`fb1e796d…`；data/addon/root-policy非全组合实测。[固定r4 loader](docs/loader-r4-binding-20261111.md)静态路径review及镜像→FD→PE→PDB→源码独立机器来源链PASS，原commit/blob错误比较FAIL撤回；独立gzip实际exit2（trailing garbage），完整FD比较通过，非exit0或历史review exit1。来源绑定不等于全部语义重新独立执行。新native/prelink/诊断最终布局尚未交付，wrapper新hash消费未完成，不称新诊断候选/认证/stage5/device通过；当前等待单独任务交付及后续layout/新hash门禁，不轮询，阶段等级不升。
最新[冻结PMAP profile离线包装](docs/owner-pmap-ret-package-20261111.md)（**self-checked，待独立review/verifier**）覆盖上述前轮“尚未交付/新hash未完成”快照：仅显式`pmap-ret-stop-20261111-r1`接受final `6671eafeab4e1ad73ba73f8c85728f6f7f2fc78a7db9398721b911e1b613f269`/55386112B，默认仍旧baseline门禁；schema2实际kernel/profile绑定，新artifact仅抽一次BNCH48，旧initializer未改/未验证新kernel。新FAT SHA256 `640830e458b17dc1f554253d776297b34f143bb75de216802e0997a80999c877`，真实回读及5项新增测试exit0。相对布局Used `0x4408000`<=`0x3fe00000`，实际window PA/live栈/回收生命周期仍缺；memory-map/DeviceTree实际缺失不伪造，2MiB非stack证明。无native/renderer再修改、bootimg/vendor_boot/设备release，不称device-ready、不申请上机；外层包装及独立门禁另行安排，阶段等级不升。
最新[冻结主机候选验收完毕](docs/owner-vendor-boot-20261111.md)：外层review PASS WITH CONDITIONS仅状态文字整改，独立verifier official/helper各exit0、两产物及ramdisk cmp0，`out/owner-vendor-boot-verifier-20261111/vendor_boot.img` 100663296B SHA256 `a4d789f06d74d2b8ea1aa9dff3b25556fcfae894454b766d7bf92f072567bfd0`；唯一FAT `500a639b…789797`、kernel `6671…`、r4 `692cfcca…`不变。**最终静态范围PASS**：[更正边界+native-flow A–E](docs/owner-pmap-ret-range-acceptance-20261111.md)闭合，原引用错误FAIL撤回，历史报告/pending文字保留并解释；helper未来记录改用稳定独立证据指引，不重包。当前无设备授权，待当轮授权及设备身份/槽位门禁；实时W/SP/GOP未测、EFI map/GOP条件保留，不称runtime/认证/stage5/设备通过或已设备ready实测。另reviewer准备操作方案，本任务不发起授权，阶段等级不升。
PR187 核查：open 未 merged，3 文件 +5/-2，仅将 typed manifest properties 传入 ADT，无 producer/认证实现；NX769J / 20F66 报告未披露 BNCH 来源与准确配置，与 nuwa / 20H392 不同。公开 profile 缺字段不能否定作者陈述；仅传输线索，不解除运行门禁，初始化成功不等于认证成功。完整 revision/边界见下方证据。
固件独立提交 `719afa67e3aebbf058c2a8beff4c801057fb2b20` 仅修 `nuwa.dsc` DEBUG 组件 mask `0x8007EE4F`，静态 review+机械检查 PASS；隔离环境已取得固定 Mu_Basecore/edksetup，但 brotli fetch rc128 后停止（self-checked），不是仍运行；未执行 BaseTools/EDK 解析、AutoGen 或编译，设备未验证，3 个脏子模块保留。终态见设备仓 `.cache/fw-mask-719afa67-20261110/RESULT.md`；下一步只读核对现有结果，下载重试预算已耗尽，不自行重跑准备。本次记录整改仅 self-checked，未运行研究/设备命令、未改脚本或恢复工具。
菜单自动下移仍仅用户观察；OEM SDAM/Reset 只是候选机制，不能把日志 mask 修复视为已证明该症状因果。多设备规则见根 AGENTS，身份/定向/回读门禁不变。
见 [本轮证据、完整 hash 与增量验证命令](docs/mix-n-match-host-20261110.md)。阶段验收等级不提升。
**最新设备里程碑（2026-11-11）**：冻结候选 `pmap-ret-stop-20261111-r1`（`vendor_boot` 100663296 B SHA256 `a4d789f06d74d2b8ea1aa9dff3b25556fcfae894454b766d7bf92f072567bfd0`，固定 r4 loader `692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5`）经主机验收（外层静态 review PASS WITH CONDITIONS、独立 verifier PASS）后，按当轮授权用 `scripts/run-pmap-ret-once.py` 执行一次三阶段（run `pmap-ret-20261111-r4`）：阶段 2 命令复核 PASS（A→B 实际读回 B；唯一 `fastboot boot` 固定 r4，exit 0），阶段 3 复核 PASS 并经独立重算主机回读（切回 A 读回 A、Android `boot_completed=1`/`_a`/root；B 槽已还原本轮原厂备份 100663296 B SHA256 `493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`，设备整分区 SHA 与 `restore-readback.img` 一致，r4 暂存已清理，原备份与证据保留）。用户观察到上述 `DIAG` 行后设备 STOP；无录像，故不做 RET/认证/stage5 结论，阶段等级不变。本地证据 `out/pmap-ret-run-pmap-ret-20261111-r4/`（`boot-complete.json`、`restore-complete.json`、`restore-readback.img`、`event-0041..0122`）只留本地、不含序列号。
**下一主机候选（2026-11-11，self-checked）**：新增独立显式 profile `pmap-ret-continue-20261111-r1`，从已验 diagnostic `6671…` 仅两处 8B 逆差分恢复原 PMAP RET（`0x19acf00`→`d65f03c0`）并把 observer slot 还回自环（`0x98d340`→`14000000`），renderer 保持；目标 kernel 固定 `7fd3d933…750b6f4`/55386112 B。有效 bootargs 仅 `-v serial=3`（去掉旧 stage5 主动 reset），只做运行态覆盖并记录，正式 board/旧 profile 未改。新 FAT `3e98ba12…21f1`（64 MiB）、ADT `a296706d…6aab7a`（13256B）、schema2 记录 `fb326d34…2c97a5`，5 项增量测试/CLI/新 profile-aware 审计均 exit0；独立 verifier 的 5 项测试/CLI/FAT/layout 也已 exit0（verifier 包 FAT `9ff5c272…d04c`、ADT `885094de…27a4`、record `a7ca5cc8…0b57`）。continuation 外层已主机冻结：`out/owner-continuation-vendor-boot-20261111-final/vendor_boot.img` 100663296 B SHA256 `4a52ddbc…a05618`，ramdisk 精确等于 verifier FAT，DTB/bootconfig/vbmeta/footer 按已审允许集保留，4 项外层增量测试/全链回读 exit0；仍无设备授权/执行器，认证未验证，旧 diag/旧 profile 继续拒绝。上游 pins 不动，影响待定。判读合同见[profile 说明](docs/owner-pmap-ret-continuation-20261111.md)与[外层说明](docs/owner-continuation-vendor-boot-20261111.md)。

Crypto 更正：`nuwa_defconfig` 为 `CRYPTO_BOOTSTRAP="prelinked"`，`prng_random.o` 最终
`-U XNU_SOURCE_CORECRYPTO14`，当前 prelink 无 `_source_corecrypto14_bootstrap`；不能声称 console 后必经
source corecrypto EARLY_BOOT。不切换 crypto 模式。PAN/volatile fallback 事实见 [b 轮证据](docs/panic-fallback-host-20261110.md)。

## 历史快照（以下进度、未完成项与“下一步”仅代表当日，不是当前状态）

**最新探针（2026-11-09）**：用户观察到 `07e176761020d3d7f01fb086d9a89af3e3531eb9` 的 `_ml_parse_cpu_topology` 后置探针约 6 秒复位，说明该调用已返回。下一候选改为 `_arm_init` 内第一次 `_arm_vm_init` 返回后复位（delay 6，panic_screen=false）；复位表示该调用已返回，不复位不能区分未到达、未返回或探针失败。主机检查仅 self-checked；新候选尚未上机。旧进度段保留作历史，最新配置与产物以 `porting.toml` 为准。

Xiaomi 13 Pro（nuwa，SM8550）的 UniXNU 设备仓。目标：iOS 16.7.16 / 20H392，donor 身份 iPhone10,3（D22AP）。

**最新进展（2026-11-07）**：官方 bring-up **阶段 1（UEFI）已通过、阶段 2（UniXNU 菜单）菜单已出现**。四次 `fastboot boot`（不写分区）：header v1 未交接；header v4 后固件跑起来；清空 `uefipil.cfg` 的 `[AUTO]` 消除 PIL panic；DXE Heap 改为 `0xBAB00000+0x0D1C0000`（`uefi-nuwa` `d7c97a7`）后 `DxeMain.c(581)` 断言消失，UniXNU 内置配置菜单出现（倒计时 10 s，默认 `Return to firmware`）。Tools → Advanced Logger 以 24 个 OneSend 二维码导出日志，主机已解码（179 行）：RamManager 映射了高 9 GiB，UniXNURamDisk 发布了 initrd 块设备。所有区域仍为 `planned`。详见 `docs/step5-firmware.md` 的 "First hardware runs" 与 "Run 4"。**第 7 步（内核）进展（2026-11-08，仅主机构建）**：8796 内核已能在 Linux 工具链上完整编译并链接（`patches/xnu/series` 26 项：13 个 arch 引用 + 本地 8796 移植/修补；归档只留阶段 5 所需的 4 项）。预链接已通过规划器（`board.toml` 的 `[kernel.prelink] roots` 去掉 `apfs` 和 `Libm`），现停在 `emit_prelink.py` 的 `External PC-relative encoding at 0xfffffff005b8c1cc`；尚无预链接内核、payload、DarwinBoot 与内核入口证据。分支 `feat/step7-kernel-patches-8796`（未合并 main）。详见 `porting.toml` 的 packaging 区域与 `../../docs/context-brief.md`。

**阶段 3（负载）进展（2026-11-08）**：payload 必须随 `vendor_boot` 送入 ABL 的 initrd（GKI 布局，官方 `guide/boot`）。已用空闲的 B 槽 `vendor_boot_b` 验证：菜单读到 `\EFI\UniXNU\unixnu.toml` 并列出 `xnu` 项（占位文件，无内核），A 槽与 TWRP 未动；原厂 vendor_boot 备份在 `.cache/stock/`。详见 `docs/step5-firmware.md` 的 "Payload delivery through vendor_boot"。**下一步**：构建内核（阶段 3 另一半——payload 哈希与 ADT 需要真内核；先清点 8796 补丁与 profile TODO），并把 payload 卷缩到 `vendor_boot` 分区（96 MiB）能容纳的大小；每次写设备或上机前须用户当轮授权并检查槽位。

**此前阶段**：官方 `porting/steps` **第 5 步（准备硬件描述与固件）的固件配置已能构建，并由独立 Verifier 复跑（PASS）**。第 4 步已完成并留证：`defconfig` → `fetch` → `status --json` → `tree` 对本地 iOS 16.7.16-20H392 profile 解析通过，`unixnu.lock` 已提交。OS profile 在本地基座 `UniXNU` 的 `693f5d9cae8a408dd18b39f3f9fdc4228c934241`（xnu 8796.141.3 / `1b191cb58250d0705d8a51287127505aa4bc0789`）；本仓记录基线 `279c990a0c7a238aa0a5818493c6cd6a46528749`。第 5 步 `uefi-nuwa` 的 `nuwaPkg` DSC/FDF 集成（UniXNU、UniXNUDxe、UniXNURamDiskDxe、DarwinBoot、AdvancedLogDxe）构建退出码 0，产出 `SILICIUM_UEFI.fd` 3145728 字节（= `0x300000`，与 `nuwa.toml` 的 `uefi_fd.size` 一致），构建步骤见 `docs/step5-firmware.md`。**Advanced Logger 已接线**（`uefi-nuwa` `e494c01b`：DXE_CORE 用 DxeCore 版 `AdvancedLoggerLib` 安装 `gAdvancedLoggerProtocolGuid`，驱动用 Dxe/Runtime 实例，构建通过），但**仍未上机**。ADT 身份已定：`chip_id = 4acab8db` 已写入 `board.toml`；`unique-chip-id` 种子只存在于基座检出里被 git 忽略的 `unixnu.local.toml`（每次构建沿用同一值，需用户自行备份）；`root_match_volume_uuid` 已注释掉，待 userdata 镜像构建后、阶段 6 前补。仍缺：运行时验证（Tools→Advanced Logger 页与 dispatch）、内存所有权证据（`0xbe000000-0xd4c00000` 的现行所有者、`0xafffff000-0xb00000000` 尾部）。启动链常规审查已出结论——**APPROVE WITH CONDITIONS**（仅针对首次 `fastboot boot`；未升级 Deep Reviewer，因无候选满足 `../../docs/routing.md` 的升级门槛）。静态对账另有两条约束：`MemoryMapLib` 未描述 6 个 live `no-map` 保留区；不要调小 `owned_memory_size`（低于约 925 MiB 窗口会落到 ADT `dram-base` 之外）。**下一步**：首次 `fastboot boot` 的放行条件还剩 RamPartition 协议生产者确认、SEC HOB 写入确认与用户当轮明确授权（**尚未放行**）；上机验证 Tools→Advanced Logger 与运行时 dispatch，内存门禁取证，root UUID 补齐后再进入第 6 步驱动选型。

## 三仓关系

| 仓 | 作用 | 位置 |
| --- | --- | --- |
| `UniXNU-nuwa`（本仓） | 板级连接、组件选择、镜像与分区策略、记录 | 本目录 |
| `UniXNU-sm8550-common` | SM8550 共享资源、DTSI、SoC 配置与补丁 | `../UniXNU-sm8550-common`（上游 `UniXNU/` 检出，HEAD = `a9f45dc6…`，与 `feeds.toml` 同一 commit） |
| `uefi-nuwa` | Mu-Silicium 固件（nuwaPkg、`Resources/Configs/nuwa.toml`） | `../uefi-nuwa` |
| `UniXNU`（基座） | 解析器、package、DarwinBoot、组件 | `../../UniXNU` |

## 前置条件

- 基座检出：`D:/Code/PortingiOS/UniXNU`（`[package] unixnu` 指向它）。
- Python 3.11+、git、`dtc`、`mtools`；内核与 payload 在 Linux/WSL 构建（`scripts/linux/setup-toolchain.py`）。
- 网络：`unixnu fetch` 需要拉取 feeds 与 Apple 源码参考。

## 构建

在基座检出目录执行：

```sh
./unixnu defconfig nuwa_defconfig -D ../nuwa/UniXNU-nuwa
./unixnu fetch -D ../nuwa/UniXNU-nuwa
./unixnu status --json -D ../nuwa/UniXNU-nuwa
./unixnu tree -D ../nuwa/UniXNU-nuwa
```

或使用设备打包脚本（所有取值来自 `board.toml`）：

```sh
scripts/package.sh --check --os ios-16.7.16-20H392
scripts/package.sh --os ios-16.7.16-20H392 --uefi ../uefi-nuwa
```

第 4 步的 `defconfig` / `fetch` / `status --json` / `tree` 已对 `board.os_profile = ios-16.7.16-20H392` 解析通过，不再停在解析阶段；镜像组装属第 7 步。仍缺：donor `KernelCache` 成员在 `[ipsw.sha256]` 的哈希、`[userdata]` 几何与 `[bootimg]` 实测值——待办见 `porting.toml` 的 `configuration`、`packaging` 区域。

## 记录

`porting.toml` 是唯一权威记录（14 个区域，完成等级 `planned` → `device-verified`）。改动代码后同步对应区域的 findings/evidence，并运行：

```sh
python3 scripts/porting-record.py check --device .
```

## 文档

- 移植流程：<https://unixnu.com/zh/porting/steps>
- 设备仓规范：<https://unixnu.com/zh/porting/device-repository>
- 迁移指南：<https://unixnu.com/zh/porting/migration>
- 组件目录：<https://unixnu.com/zh/reference/components>
- 启动验证：<https://unixnu.com/zh/porting/bring-up>

## 约定

治理规则见 `../../docs/context-brief.md`。Apple 派生产物（`kernel.macho`、`boot.img`、IPSW 组件）只留本地 `out/`，不上传 GitHub；ECID 等设备种子只经命令行或 Git 忽略的 `unixnu.local.toml` 传入。
