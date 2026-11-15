# PMAP 正常 RET continuation profile：主机 FAT 与相对布局

2026-11-11，**仅 self-checked；无设备授权、无新镜像重建、不 commit/push**。
主控转述 reviewer `ses_e3978fb51ffeFzituOGp94unZo` 对本增量 **PASS WITH CONDITIONS**；
本轮只实现该窄主机包装，不重新构建 native/prelink/renderer，不重跑旧矩阵/22 native/完整 build，
不新增 probe/console 研究。设备命令仍须另获当轮明确授权。

## 冻结输入与两处逆差分

| 项 | 路径 / 绑定 |
|---|---|
| 目标 continuation kernel（profile 固定） | SHA256 `7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4`，55386112 B，即已验 `renderer-baseline.macho` |
| 已验 diagnostic 来源 | `kernel-pmap-ret-stop.macho`，SHA256 `6671eafeab4e1ad73ba73f8c85728f6f7f2fc78a7db9398721b911e1b613f269`，55386112 B |
| 实际文件位置 | `/root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/`（`renderer-baseline.macho`、`kernel-pmap-ret-stop.macho`、`pristine.macho`） |
| 唯一差分 | 2 个 4-byte word / 实际 8 bytes，见下表 |

| fileoff | VA | diagnostic word（已验） | continuation word（恢复） |
|---|---|---|---|
| `0x19acf00` | `0xfffffff0046e9f00` | `0x14ca9d0e`（B→observer） | `0xd65f03c0`（原 PMAP RET） |
| `0x98d340` | `0xfffffff007991340` | `0x17e984a0`（observer slot→renderer） | `0x14000000`（自环） |

generator 实际核对：两文件等长，仅上述 8 字节不同；renderer 区间
`fileoff 0x3ee5c0..+2607` 逐字节相同。因此 `execution_mode=continue-original`、
`pmap_ret_restored=true`、`observer_unhooked=true`、`renderer_retained=true`。
本轮**不**重建 native、**不**再次 renderer/entry patch、**不**改写任何既有镜像；
continuation kernel 直接取报告目录中的已冻结文件，逆差分只作为准入证明复核。
observer 无 init 注册，恢复唯一新增入口后不在正常调用图可达；正常链接组件保留，无需删除/重链。

## 显式 profile 与参数

`build-owner-payload.py --profile pmap-ret-continue-20261111-r1` 为独立显式 profile；
默认仍是 `baseline-prepared-fb1e`。新 profile 只接受上述 `7fd3…`/55386112 B，
任意用户 `--kernel-sha256`、diag `6671…`、pristine `3a38…`、二次改写字或大小不符均拒绝。
`--continuation-reference` 仅该 profile 必需，只读 frozen diagnostic 源。

有效 bootargs 固定为 `-v serial=3`，显式去掉旧 `sheng-platform-stage=5`：
`ArmDTPlatform.cpp:200-209` 在 `registerService` 返回后主动 reset stage，stage5 提示只掩盖状态。
该改动仅是运行态 board 覆盖（`kernel_args.before` 为旧 board 三元组，`after` 为两项），
`overrides` 与 `runtime-board.json` 准确记录；正式 `board.toml`、旧 diagnostic profile、
基线 profile 和默认 defconfig 均未改。无 panic/stage/reset/sheng-smp 追加参数。
旧 diagnostic 严格分支仍保留；新 profile 走同一 `check_profile_arguments` 严格门禁，
不会落入普通宽松路径。

## 记录、token 与 FAT 产物

owner schema2 `input_binding.artifact` 绑定 profile/实际 kernel/大小；历史
`generator_validation_baseline_kernel_sha256` 仍固定 `fb1e…`，旧 initializer checker 不放宽。
新 artifact 在新 ignored 目录预留后仅抽一次 48-byte BNCH，未传 `--reuse-record`；
跨 profile/跨 kernel/旧 schema 记录均按实际输入绑定拒绝。

根 `out/owner-pmap-ret-continuation-20261111-final/`：

| 项目 | 路径 / SHA256 |
|---|---|
| FAT | `build/nuwa/ios-16.7.16-20H392/nuwa/payload/payload.img`，67108864 B，`3e98ba12f13df9a776af5de85e254ff3b95fc94a7bc38eb53edd1aca774521f1` |
| ADT | `adt-generation/final.adt`，13256 B，`a296706d390447319c11a9db7b691f9d4ecc3276bac6424ad9e04598c16aab7a` |
| schema2 owner 记录 | `adt-generation/record.json`，1077 B，`fb326d3441b0d9a552463c84d0b4d240e68937c54342097acbb28f78992c97a5`（BNCH 48 B，未复用） |
| continuation 证据 | `continuation.json`，994 B，`12271c990b417c65ecef994d1f93f9ad31e7d57553d5cf8f6e58cbeacffaeefa` |
| 回读/输入/覆盖 | `extracted/EFI/UniXNU/`、`extract-command.json`、`inputs/`、`runtime-board.json`、`overrides.json`、`../payload-record.json` |
| 独立重提取布局 | `out/owner-pmap-ret-continuation-20261111-final-layout/layout.json` |

真实 mcopy 回读：FAT 内 kernel 逐字节等于 `7fd3…`，ADT 等于本次 bridge/record，
trustcache 等于本次输入；`unixnu.toml` 唯一 xnu entry，args 精确 `-v serial=3`，
无 `sheng-platform-stage=5`、无 `sheng-smp`。chosen 无 `boot-manifest-hash`，
manifest-properties 仅 name+BNCH48，无 love/CHMH；**memory-map/DeviceTree 实际不存在**，
按冻结生成器如实留档，不伪造。仅 trust sidecar，无 data/addon/root-policy。
`payload-record.json`：`readback_complete=true`、`bridge_calls=1`、
`device_release=false`、`new_kernel_initializer_validated=false`、`authentication=NOT REACHED`。

## 重新量测的相对布局（静态，非 runtime 映射）

从本 FAT 内实际 kernel/ADT 重新测量，并复用已验固定 r4 loader 公式与来源绑定
（镜像 `692cfcca…dc2e5`、DarwinBoot `3c757340…`、去 CR 源码 `f3815791…b8cf`）：

| 项目 | 实际值 |
|---|---|
| root VM base/end/span | `0xfffffff003dc8000` / `0xfffffff0081b7000` / `0x43ef000`（71233536 B；文件 55386112 B，二者不同） |
| Args | `0x43f0000`（4096 B 页） |
| Tree | `0x43f1000`，ADT 13256 B |
| Ramdisk/TrustCache | `0x43f5000`，RamdiskBytes=0，trust 66272 B |
| Addon/Policy/Top/Used | `0x4408000` |
| window / limit | `0x40000000` / `0x3fe00000`；Used 未超限 |
| 已知低区间 | UEFI stack、Display Reserved、DXE Heap 与 ADT 高 DRAM 机械不相交 |

W 的实际物理基址未观测（仅 `W mod 2MiB=0x1c8000` 已证）；`absolute_conflicts_cleared=false`，
2 MiB guard 不是已证 stack 保留。「live native/bootstrap stack/SP 与 pool 回收时序未建立」
**指本审计未重新证明**，不撤销既有独立读取期保留/回收不重叠结论；该结论仍以既有独立证据为准，
见 `out/pmap-ret-memory-ranges-verifier-20261111/correction.json`、同目录
`native-flow/result.json` 及[范围说明](owner-pmap-ret-range-acceptance-20261111.md)。
实际 W/SP/GOP 未观测**不是新增的、上机前必须取得的地址门禁**；EFI map/GOP 契约条件仍保留。
**不声称 runtime 映射或 RET 执行通过**。

## 本方案判读合同（随本轮交付）

1. 目标：恢复原 PMAP RET + 去 stage5 主动 reset，**暴露首个自然 panic 或可见原生里程碑**；
   不预设一定到达任何后续阶段。
2. panic 可读时：按冻结 baseline 的 caller/文本定位**首个实际失败**，不扩散到无关后续行。
3. 若看到 `MAC Framework successfully initialized`：只能证明到
   `mac_policy_initbsd` 的 printf（BSD MAC 入口，callback 循环之前）；不是 MAC 回调、
   AMFI 或认证通过证明。
4. 普通日志**只有实际看到**才作证据；console 屏幕是否可见另由 scout 核对，本任务不加 hook、
   不用 noreturn renderer 伪装 nonstop logger。此前 panic renderer 显示过 `DIAG` 行，
   不代表全部 panic/printf 路径可见。
5. 停菜单、重启、画面变化**不自动归因** PMAP/watchdog/stage5；无新输出是多义的，
   **不等于“未到达”**，不自动重试、不批量增加停点。
6. 若真实后续仅无输出，再单独做一次
   `BootArgs.Video → PE_state.video → PE_create_console → console_write` 的有限补查，
   不预先扩张范围。
7. 用户口述/录像/照片分别标注来源；设备未获新授权，本轮不执行任何设备命令。

## 实际自检命令与结果

Windows cwd `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`；WSL Ubuntu-22.04/root，
子命令 cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`，现有 Python3.11/dtc/mtools，
无安装/下载/设备命令。

```powershell
# 增量 5 项测试：实际 exit0，22.630s；只新增此 profile，未重跑旧 BNCH/22 native/完整 build。
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/test-owner-pmap-ret-continuation.py --base /mnt/d/Code/PortingiOS/UniXNU --soc /mnt/d/Code/PortingiOS/nuwa/UniXNU-sm8550-common --continuation-kernel /root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/renderer-baseline.macho --continuation-reference /root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/kernel-pmap-ret-stop.macho --diagnostic-pristine /root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/pristine.macho --identity-file out/owner-payload-verifier-20261111/explicit-identity.json --trust-cache out/mix-n-match-20261110/audit-final/new/kernel.macho.trustcache --loader-image .cache/boot-stage12-v4-r4.img --output out/owner-pmap-ret-continuation-20261111-selfcheck-r2

# 唯一显式主机包装：实际 exit0；新 token/新 record，未传 reuse。
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/build-owner-payload.py --base /mnt/d/Code/PortingiOS/UniXNU --soc /mnt/d/Code/PortingiOS/nuwa/UniXNU-sm8550-common --kernel /root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/renderer-baseline.macho --kernel-sha256 7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4 --profile pmap-ret-continue-20261111-r1 --continuation-reference /root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/kernel-pmap-ret-stop.macho --enable-owner-bnch --identity-file out/owner-payload-verifier-20261111/explicit-identity.json --trust-cache out/mix-n-match-20261110/audit-final/new/kernel.macho.trustcache --output out/owner-pmap-ret-continuation-20261111-final

# 新窄 profile-aware 审计：实际 exit0；旧 diagnostic 审计未改且仍拒绝本包。
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/audit-owner-pmap-ret-continuation-package.py --candidate out/owner-pmap-ret-continuation-20261111-final --base /mnt/d/Code/PortingiOS/UniXNU --loader-image .cache/boot-stage12-v4-r4.img --continuation-reference /root/nuwa-pmap-ret-native-20261111/diagnostic-20261111-r1/kernel-pmap-ret-stop.macho --output out/owner-pmap-ret-continuation-20261111-final-layout
```

`tests.json`：5/0 errors/0 failures，`device_commands=0`。覆盖：profile 默认关闭/强制 BNCH；
只接受 `7fd3…`/55386112 B（diag/pristine/任意 hash/大小/二次 patch 拒绝）；
8B 精确逆差分且其余 bytes 不变、renderer 区间不变；旧 `sheng-platform-stage=5`
与额外 args 拒绝；真实 DTB/Context/FAT 构建、有效 args 与 FAT kernel/ADT/trust/toml 回读；
跨 profile/kernel/大小/旧 schema 记录拒绝；新审计拒绝旧 diagnostic 包、旧审计拒绝本包；
FAT kernel 篡改/报表 profile 篡改拒绝。旧 5/22/BNCH 套件未重跑。

新审计同时重测 VMspan/ADT 长度/Args/Tree/Top。本 continuation kernel 与已验 diagnostic 仅
RET/observer 两处 8B 不同，segment 布局与 ADT 长度相同且为 trust-only 固定布局，
故可复用既有 r4 loader/读取期证据（见上）。脚本
`audit-owner-pmap-ret-continuation-package.py` 中 gaps 段（约 125-137 行）的 stack/lifetime
相关文字是「本审计未重新证明」的措辞，不是新的地址门禁；历史 JSON 保持原样，待 verifier
完成后再按需仅更正未来报告的 metadata 措辞（本任务不动脚本，避免版本竞态）。
`runtime_ret_executed=not observed`，不把静态 RET word 当已执行。

## 未决项与下一步

- 仅主机 FAT+layout；**未生成外层 vendor_boot**（待审查），`device_release=false`，
  无设备授权、未上机、无 device-ready 结论。
- 旧 diagnostic 包审计不会被静默当 continuation 合格：两个审计各自 profile-aware 互拒。
- wrapper 未改正式 board/defconfig/旧 profile/现有镜像；base pin、native/prelink、
  renderer 历史产物未动；不 commit/push。
- 下一观察点由主控/reviewer 决定；若按上述合同上机，先看首个自然 panic 或
  `MAC Framework successfully initialized`（仅 printf 位置证明），无输出按多义处理。
- 独立 verifier 仍需按本文命令在新 ignored 输出复跑 5 项测试、CLI 与审计，
  并复核 kernel/ADT/record/layout hash；本轮所有结果均只标 self-checked。
