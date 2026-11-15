# PMAP continuation 设备执行器 profile 绑定（2026-11-11）

**Status: self-checked host implementation only. No adb/fastboot command ran,
including `version`/`devices`; no device authorization, no commit/push.**
本任务只在既有 `scripts/run-pmap-ret-once.py` 上新增**显式 profile 选择与身份绑定**；
默认仍是旧 stop profile。三阶段流程、白名单、claim、备份/回读、切槽与还原机制未重构；
旧 run 证据（含已消耗的 `pmap-ret-20261111-r4` boot claim）不被迁移、覆盖或重放。

## Profile 与冻结映射

CLI 新增 `--profile`，默认 `pmap-ret-stop-20261111-r1`（旧语义不变）。
新 continuation profile 必须显式选择：

| 项 | stop（默认） | continuation `pmap-ret-continue-20261111-r1` |
|---|---|---|
| outer | `out/owner-vendor-boot-20261111-final/vendor_boot.img`，`a4d789f0…bfd0` | `out/owner-continuation-vendor-boot-20261111-final/vendor_boot.img`，100663296 B，`4a52ddbc2cc06401f76676f480eb1b0e4b1dfafce0a8d07b453dd53967a05618` |
| kernel | 旧 diagnostic | `7fd3d933aae66d8e34a0d3ebfa142137978976d7521e04cef20321109750b6f4` |
| 有效 args | `-v serial=3 sheng-platform-stage=5` | **仅** `-v serial=3` |
| FAT | 旧 verifier FAT | `9ff5c2720a1af341b66e8417a3308fc0a3be9e561c3406e7db157d05e523d04c` |
| ADT | 旧 ADT | `885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4` |
| 独立 outer 证据 | — | `out/owner-continuation-vendor-boot-verifier-20261111/outer-record.json`（其 `profile`/`vendor_boot_sha256`/`vendor_boot_bytes` 必须与上表一致） |
| 固定 r4 | `.cache/boot-stage12-v4-r4.img`，1495040 B，`692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5` | 同左 |
| 期望 B 原厂备份 | 100663296 B，`493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad` | 同左 |

continuation 只接受上述候选 hash/大小；错误 outer、错误 evidence、旧 diag/旧 FAT、
错误 r4 或跨 profile 记录均在设备命令前拒绝。prepare/boot 还会核对 evidence 记录与本
profile/候选 hash/大小一致；restore 不读取 candidate/r4/evidence。

## Run 身份与旧 run 兼容

prepare 成功进入 run 目录时创建 `out/pmap-ret-run-<id>/run-identity.json`（仅主机状态，
不含 serial），绑定：

```text
run_id, profile, candidate (repo-relative path), candidate_sha256, candidate_bytes,
stock_sha256, r4_sha256, r4_bytes
```

`run_id` 参与精确比较：同 profile、不同 run 的 identity 互换会被拒绝；缺失 `run_id` 的
已存在 identity 不会被自动补字段/迁移（当前没有真实 continuation run；旧无 identity 目录
仍走 stop-only 兼容分支）。continuation 另记录 `frozen`（kernel/args/FAT/ADT/evidence），
仅为身份证据，不是本层重新执行 8B 差分；沿用已验固定 baseline hash。boot/restore 在任何
设备命令、active.lock 或 phase claim 之前要求 `run-identity.json` 与当前 profile 配置
完全一致；不一致或跨 profile 直接拒绝。不同 run-id 目录互不复用。

prepare/boot 的 outer evidence 校验还要求顶层 `record` 与 `input_binding` 均为 JSON
object，且 `vendor_ramdisk_sha256` 和 `input_binding.fat_sha256` 都等于冻结 FAT
`9ff5c272…e523d04c`；缺失、错误或混合类型在目录创建/lock/claim/设备访问前拒绝。
restore 不读取 candidate/r4/evidence。

旧 run 目录**没有** `run-identity.json` 时：
- 只允许默认 stop profile 按原严格语义执行（恢复/读取）；不创建 identity，不迁移/覆盖。
- 显式 continuation profile 直接拒绝，不会走到 claim/backup/state。
- 旧 `pmap-ret-20261111-r4` 的 boot claim 已消耗，`boot.claim`/`active.lock` 的独占语义
  仍会拒绝重放；不会因新增 profile 而重置。
- 旧固定常量 `SIZE/STOCK/CANDIDATE/R4/LABEL` 保留，stop profile 直接引用它们，旧 run 的
  备份/恢复路径不变。

restore 仍只使用本轮全量 `vendor_boot_b.stock.img` 和独立 `restore.claim`/writer claim；
候选路径、r4、evidence 缺失不阻止必要还原（测试显式删除 evidence 并确认候选不存在后
restore 成功）。

## 保留的原有门禁（未重构）

真实引号差异（exec-out 的 su -c 原始参数 vs shell 包裹）、`mkdir -m 755`、
候选/restore `chmod 600`、只写 `/dev/block/by-name/vendor_boot_b`、完整备份 + 双回读、
切槽可读时读回、严格 unknown command 降级、单次 boot claim、失败不重试、
restore claim 独立、active.lock 跨阶段互斥、run-id/staging 路径与权限校验均保持原实现。
新增的 profile 检查只发生在这些门禁之前。

## 观察文案与判读（continuation）

boot 返回的提示按 profile 区分，continuation **不期待**旧 `DIAG: PMAP initializer normal
epilogue reached; STOP`，也不声称 park：

- 目标：首个自然 panic 或可见原生里程碑。
- 若看到 `MAC Framework successfully initialized`：只证明到 `mac_policy_initbsd` 的 printf
  （BSD MAC 入口，callbacks 之前），不是回调/AMFI/认证通过。
- 普通日志只有实际看到才作证据；console 是否可见另核；无输出是多义的，不自动判“未到达”。
- 菜单停止、重启或画面变化不自动归因 PMAP/watchdog/stage5。
- 不加 hook，不用 noreturn renderer 作 logger；不自动 retry/continue/reboot。
- 观察结束由用户手动返回 bootloader，再单独授权 restore；后续可能进入等待，
  不自动判成功或失败。

已审差异仅为两个恢复 word（`0x19acf00`→`d65f03c0`、`0x98d340`→`14000000`）及移除
`sheng-platform-stage=5`；renderer 保持，native/prelink/FAT/BNCH 未重生成。

## 自检（全部 mock；真实设备命令 0）

Windows cwd `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`；WSL Ubuntu-22.04/root，子命令 cwd
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`，既有 Python3.11；未调用 adb/fastboot。

```powershell
# 语法：exit0。
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B -m py_compile scripts/run-pmap-ret-once.py

# 脚本内自检（真实 subprocess.run 被 patch 为断言）：exit0，86 test groups，
# real_device_commands=0；输出保存到 ignored 目录。
wsl -d Ubuntu-22.04 -u root --cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa -- /home/wh1stl3/.local/bin/python3.11 -B scripts/run-pmap-ret-once.py --self-check
```

自检新增覆盖：默认 stop profile、未知 profile 拒绝、continuation 冻结映射逐项、
continuation 三阶段单 boot + 无候选/无 evidence 的 restore、跨 profile boot/restore 在
claim 前拒绝、旧无 identity run 仅 stop 且不迁移、旧 r4 consumed boot claim 不复用、
新旧 profile 全部 phase dry-run 0 命令；本轮修复另加：
identity 的 `run_id`/`profile`/`candidate`/`candidate_sha256`/`candidate_bytes`/`stock`/`r4`
及 frozen 各字段逐项篡改拒绝、同 profile 不同 run identity 互换拒绝、缺失 `run_id` 不被
自动补写；evidence 的 `vendor_ramdisk_sha256` 与 `input_binding.fat_sha256` 分别缺失/错误、
`record`/`input_binding` 非 object、混合类型、args/outer hash/outer size、record 与 FAT
成员的 kernel/ADT 错误均在目录创建/lock/claim/设备前拒绝；真实临时文件的
`Run.check_file` 成功/大小错/hash 错三例。

**模拟与真实校验边界**：selfcheck 的 `fake` 只模拟设备返回 hash；其中
`continuation-wrong-candidate` 是“模拟设备上传/B hash 错”，不用于证明 host 候选文件 hash
校验。host 文件校验由真实临时文件 `Run.check_file` 三例单独覆盖，生产 pin 未改；文档与
报告分开表述两类结果。

每 phase dry-run 也通过 import 方式逐一确认（6/6 `device_commands_executed=0`），
另以 6 条实际 CLI dry-run 命令（stop/continuation × prepare/boot/restore）确认 exit0、
`device_commands_executed=0`，未创建 `out/pmap-ret-run-dry-*`。

脚本完整 hash（本轮 review 修复）：
`0be6f1aa9d09b202bb44abc6723b63ed9203f7615d9e56660b6db907fb54f007`（77051 B，修复前，
83 组）→ `9c4540b8d032fba96dde4307f009b19e29dfa09842b24a4df3f9855fbd54eaa5`
（84965 B，修复后，86 组）。
首次实现历史：`89441a227c9919b00832a7aae1a7ef96453e51008721cd60e6bcbb4bcb097cad`
（62115 B）→ `0be6f1aa…54f007`（77051 B）。
证据：`out/pmap-ret-continuation-executor-selfcheck-20261111/`（`selfcheck.json`、
`dryrun.json`、`result.json` 及 `*.exit`；py_compile/selfcheck/dryrun exit 均 0，
`real_device_commands=0`）。verifier 正在跑的旧 83 组结果不属于本修复版。

## 下一轮三阶段命令（模板，尚未授权）

设备未新授权；以下只是候选执行模板，**不得**在未授权时加 `--authorize-*`。
建议 run-id `pmap-ret-continue-20261111-r1`（不预先创建任何 claim/目录）。

```powershell
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' scripts/run-pmap-ret-once.py --profile pmap-ret-continue-20261111-r1 --phase prepare --run-id pmap-ret-continue-20261111-r1
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' scripts/run-pmap-ret-once.py --profile pmap-ret-continue-20261111-r1 --phase boot --run-id pmap-ret-continue-20261111-r1
& 'C:/Program Files/WorkBuddy/resources/vendor/python/python.exe' scripts/run-pmap-ret-once.py --profile pmap-ret-continue-20261111-r1 --phase restore --run-id pmap-ret-continue-20261111-r1
```

无 flag 时为 dry-run，只打印模板、0 设备命令、不创建 run 目录。实际执行仍须：
用户当轮明确授权、prepare/boot/restore 分别加对应 `--authorize-*`、真实身份/容量/前后
hash 核对、单次 boot claim、失败不重试；restore 使用本轮全量备份与独立 claim。

## 剩余步骤

1. 主控独立 review / verifier 复核本增量（脚本 hash、self-check/dry-run、profile 常量、
   旧 run 兼容与 restore 独立性）。
2. 通过后才向用户申请新设备授权；本任务不创建真实 run、不执行任何设备命令。
3. 若授权，按上表三阶段执行；观察按 continuation 文案，用户手动返回 bootloader 后 restore。
