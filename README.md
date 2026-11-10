# UniXNU-nuwa

**当前（2026-11-10，self-checked）：官方第 7 步 / bring-up 内核入口至 platform expert 诊断。**
旧 stage5 `998d284a…` 已测：照片确认 AppleImage4 panic `failed to get mix-n-match policy: 2`，
未自动复位；panic 显示后 park 符合预期，不证明 stage5。既有日志记录 18:54:23 已回 A/TWRP current/active=0，未新查设备。
本轮仅新增 `/chosen/mix-n-match-prevention-status` u32=0（AMNM=true，非 Apple 启动链 bring-up 软件策略，非 donor/熔丝事实；放宽反重放令牌/chained-manifest-hash 约束，不关闭 AMFI、不宣称 Apple secure boot）。
既有 stage5/panic/kernel/prelink/crypto/trust 保持，仅组装一次 payload/vendor_boot，增量自检 exit 0，**self-checked，未独立验证、未上机**；本轮仅配置/文档一次本地提交，不 push/merge。
**最终阻塞：外部 provider 接口支持缺失，AMNM-only 禁止设备放行。** BNCH 缺失且当前 secure-boot-level=0 会触发下一 panic；Deep 最终裁定固定 donor 无已证明的无 AP-token/no-shadow 入口，XNU nonce wrapper/custom runtime 不能替代内建初始化/PMAP_CS。需要 provider 源码或受支持兼容实现；不填假 BNCH、不改 level、不替换指针或跳 init，不再重复分析/构建/上机。
下一动作：审阅[本地英文上游问题草稿](docs/appleimage4-provider-question-draft-20261110.md)，经用户许可发送或提供接口资料；草稿未发送。
菜单自动下移仍仅用户观察；OEM SDAM/Reset 只是候选机制；日志级别过滤已确证但未修。多设备规则见根 AGENTS，身份/定向/回读门禁不变。
见 [本轮证据、完整 hash 与增量验证命令](docs/mix-n-match-host-20261110.md)。阶段验收等级不提升。

Crypto 更正：`nuwa_defconfig` 为 `CRYPTO_BOOTSTRAP="prelinked"`，`prng_random.o` 最终
`-U XNU_SOURCE_CORECRYPTO14`，当前 prelink 无 `_source_corecrypto14_bootstrap`；不能声称 console 后必经
source corecrypto EARLY_BOOT。不切换 crypto 模式。PAN/volatile fallback 事实见 [b 轮证据](docs/panic-fallback-host-20261110.md)。

## 历史快照（以下进度、未完成项与“下一步”仅代表当日，不是当前状态）

**最新探针（2026-11-09）**：用户观察到 `07e176761020d3d7f01fb086d9a89af3e3531eb9` 的 `_ml_parse_cpu_topology` 后置探针约 6 秒复位，说明该调用已返回。下一候选改为 `_arm_init` 内第一次 `_arm_vm_init` 返回后复位（delay 6，panic_screen=false）；复位表示该调用已返回，不复位不能区分未到达、未返回或探针失败。主机检查仅 self-checked；新候选尚未上机。旧进度段保留作历史，最新配置与产物以 `porting.toml` 为准。

Xiaomi 13 Pro（nuwa，SM8550）的 UniXNU 设备仓。目标：iOS 16.7.16 / 20H392，donor 身份 iPhone10,3（D22AP）。

**最新进展（2026-11-07）**：官方 bring-up **阶段 1（UEFI）已通过、阶段 2（UniXNU 菜单）菜单已出现**。四次 `fastboot boot`（不写分区）：header v1 未交接；header v4 后固件跑起来；清空 `uefipil.cfg` 的 `[AUTO]` 消除 PIL panic；DXE Heap 改为 `0xBAB00000+0x0D1C0000`（`uefi-nuwa` `d7c97a7`）后 `DxeMain.c(581)` 断言消失，UniXNU 内置配置菜单出现（倒计时 10 s，默认 `Return to firmware`）。Tools → Advanced Logger 以 24 个 OneSend 二维码导出日志，主机已解码（179 行）：RamManager 映射了高 9 GiB，UniXNURamDisk 发布了 initrd 块设备。所有区域仍为 `planned`。详见 `docs/step5-firmware.md` 的 "First hardware runs" 与 "Run 4"。**第 7 步（内核）进展（2026-11-08，仅主机构建）**：8796 内核已能在 Linux 工具链上完整编译并链接（`patches/xnu/series` 26 项：13 个 arch 引用 + 本地 8796 移植/修补；归档只留阶段 5 所需的 4 项）。预链接已通过规划器（`board.toml` 的 `[kernel.prelink] roots` 去掉 `apfs` 和 `Libm`），现停在 `emit_prelink.py` 的 `External PC-relative encoding at 0xfffffff005b8c1cc`；尚无预链接内核、payload、DarwinBoot 与内核入口证据。分支 `feat/step7-kernel-patches-8796`（未合并 main）。详见 `porting.toml` 的 packaging 区域与 `../../docs/SESSION-HANDOFF.md`。

**阶段 3（负载）进展（2026-11-08）**：payload 必须随 `vendor_boot` 送入 ABL 的 initrd（GKI 布局，官方 `guide/boot`）。已用空闲的 B 槽 `vendor_boot_b` 验证：菜单读到 `\EFI\UniXNU\unixnu.toml` 并列出 `xnu` 项（占位文件，无内核），A 槽与 TWRP 未动；原厂 vendor_boot 备份在 `.cache/stock/`。详见 `docs/step5-firmware.md` 的 "Payload delivery through vendor_boot"。**下一步**：构建内核（阶段 3 另一半——payload 哈希与 ADT 需要真内核；先清点 8796 补丁与 profile TODO），并把 payload 卷缩到 `vendor_boot` 分区（96 MiB）能容纳的大小；每次写设备或上机前须用户当轮授权并检查槽位。

**此前阶段**：官方 `porting/steps` **第 5 步（准备硬件描述与固件）的固件配置已能构建，并由独立 Verifier 复跑（PASS）**。第 4 步已完成并留证：`defconfig` → `fetch` → `status --json` → `tree` 对本地 iOS 16.7.16-20H392 profile 解析通过，`unixnu.lock` 已提交。OS profile 在本地基座 `UniXNU` 的 `693f5d9cae8a408dd18b39f3f9fdc4228c934241`（xnu 8796.141.3 / `1b191cb58250d0705d8a51287127505aa4bc0789`）；本仓记录基线 `279c990a0c7a238aa0a5818493c6cd6a46528749`。第 5 步 `uefi-nuwa` 的 `nuwaPkg` DSC/FDF 集成（UniXNU、UniXNUDxe、UniXNURamDiskDxe、DarwinBoot、AdvancedLogDxe）构建退出码 0，产出 `SILICIUM_UEFI.fd` 3145728 字节（= `0x300000`，与 `nuwa.toml` 的 `uefi_fd.size` 一致），构建步骤见 `docs/step5-firmware.md`。**Advanced Logger 已接线**（`uefi-nuwa` `e494c01b`：DXE_CORE 用 DxeCore 版 `AdvancedLoggerLib` 安装 `gAdvancedLoggerProtocolGuid`，驱动用 Dxe/Runtime 实例，构建通过），但**仍未上机**。ADT 身份已定：`chip_id = 4acab8db` 已写入 `board.toml`；`unique-chip-id` 种子只存在于基座检出里被 git 忽略的 `unixnu.local.toml`（每次构建沿用同一值，需用户自行备份）；`root_match_volume_uuid` 已注释掉，待 userdata 镜像构建后、阶段 6 前补。仍缺：运行时验证（Tools→Advanced Logger 页与 dispatch）、内存所有权证据（`0xbe000000-0xd4c00000` 的现行所有者、`0xafffff000-0xb00000000` 尾部）。启动链常规审查已出结论——**APPROVE WITH CONDITIONS**（仅针对首次 `fastboot boot`；未升级 Deep Reviewer，因无候选满足 `ai-orchestration` §2.3）。静态对账另有两条约束：`MemoryMapLib` 未描述 6 个 live `no-map` 保留区；不要调小 `owned_memory_size`（低于约 925 MiB 窗口会落到 ADT `dram-base` 之外）。**下一步**：首次 `fastboot boot` 的放行条件还剩 RamPartition 协议生产者确认、SEC HOB 写入确认与用户当轮明确授权（**尚未放行**）；上机验证 Tools→Advanced Logger 与运行时 dispatch，内存门禁取证，root UUID 补齐后再进入第 6 步驱动选型。

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

治理规则见 `../../docs/governance-2026-11-06.md`（12 条）。Apple 派生产物（`kernel.macho`、`boot.img`、IPSW 组件）只留本地 `out/`，不上传 GitHub；ECID 等设备种子只经命令行或 Git 忽略的 `unixnu.local.toml` 传入。
