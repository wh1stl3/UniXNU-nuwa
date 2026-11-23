# nuwa SMP 入口关候选（2026-11-23）

仅主机 `self-checked`，未上机。基线：`display/20h392-dsp-diag` 的 `917f3ea`，
默认关闭包 `b02007f707302915ec62516dff21bec5d1dd4e0dbaa95ccfe5440d18b3655999`。
重建内核与基线逐字节一致；候选仅追加 `sheng-smp=1`。CHMH 随 args 重绑为实验启动集标识；
认证仍为 NOT REACHED。

## 入口验收与止损

- **只验入口**：一次 PSCI `CPU_ON`，cpu1 以 `MPIDR_EL1[15:0] == 0x100` 和自己的栈进入
  XNU 并报到。不验 IPI、定时器、迁移、TLB 的长期稳定性，也不扩大到更多核。
- 首看 `SMP req=… run=… cond=… boot=…`。预期 `req=1 run=1 cond=1 boot=0`，
  仅 `c1=step7`，无 `!fail`。`cond=1` 是 SMC；`boot` 是主核 MPIDR 低 24 位，
  不是次核 affinity。`step4` 只说明抵达调用点；`step5` 后才检查次核 affinity，
  `!fail1` 表示不匹配，`!fail2` 表示 redistributor 唤醒失败。
  `step7` 间接表明已过 affinity 检查和次核栈路径；页面不直接输出次核 MPIDR、栈地址或
  PSCI 返回码，不能从该行独立量测栈或调用次数。
- 看 `PC` 采样有无新线程或新进程样本，以及 `LOAD` 的 user/sys/idle 与 ticks 变化。
  `PC` 是共享采样且不标核号；`LOAD` 是聚合值。两者只作活动旁证，不替代次核报到，
  缺少新样本也不单独判失败。
- 无报到、报到但 affinity 不是 `0x100`、或注册后立刻 panic/挂死：停在首次观测，
  不重试、不扩大。
- **待 `deep_reviewer` 复审**：只审启用 `sheng-smp=1` 后的失败面与可观测性，
  尤其是页面不刷、最后一步停滞及无法直接量测 affinity／栈的证据边界；
  boot 入口 ABI 和默认关闭等价性另派，不在本轮重审。本记录不授权设备操作。

## 产物与直接回读

产物仅在 `out/nuwa-smp-entry-20261123-{build,package,audit}/`。

| 产物 | 摘要 |
| --- | --- |
| Kernel SHA-256 | `6af982c35ba95de30ac33d68f040cae384878b78236d40d2f9d9c8a0f7dc683f` |
| Outer SHA-256 | `0e70de8ff57b5b240edc33fe2bc1653974ff9ebd1edec9cfc0f9e01dd04f9fde` |
| CHMH SHA-384 | `de8d9f55de56fc2d413d4e04e78b0bd58f5b767f629377f6d4f2a9cb23153f3afc5cfcaea189ab8c8816c6d8c7721cc7` |
| FAT SHA-256 | `96bade875f145451ac58de9281e16814e6e72e02624995800a2c614acfbf49d5` |
| Seed SHA-256 | `692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`（同基线） |

单独 `--audit` 的 outer 回读 FAT 与 `payload.img` 相同；`fsck.fat -vn` 与 `mdir`
确认余量为 **11,664,896 B ≥ 8 MiB**。FAT 外的字节不变；读回文件逐项比对仅
`unixnu.toml`（args 后缀）和 `kernel.macho.adt`（CHMH）变化。
不传 `--enable-smp-entry` 复包，outer SHA-256 仍为基线 `b02007f7…5999`。

从基线与候选的 `vendor_boot.img` 分别切出 FAT 后用 `mcopy` 提取；
候选 `xnu` args 严格等于基线 args 加 ` sheng-smp=1`，其余字节不变。
501 B、26 项，SHA-256 `5ada678b399e74bf9c7b567dc860ae86150af66252df678e9a7a93fbda2d75f9`。
直接读回的 `args` 全文：

```text
-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1 build-tag=nuwa-r35 boot-progress-scale=3 sheng-data-persist=2 sheng-log-reserve=1024 offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1 offline-legacy-transfer=1 offline-legacy-cpu-present=1 nuwa-lite=1 nuwa-mg-reset=1 nuwa-hid-standin=1 sheng-smp=1
```

同一 FAT 直接提取的 ADT 初始状态（不是实机运行状态）：

```text
/cpus/cpu0/state: running
/cpus/cpu1/state: waiting
/cpus/cpu2/state: waiting
/cpus/cpu3/state: waiting
/cpus/cpu4/state: waiting
/cpus/cpu5/state: waiting
/cpus/cpu6/state: waiting
/cpus/cpu7/state: waiting
/psci/method: smc
```

## 复跑

按[默认关记录](nuwa-smp-gate-20261123.md#results-self-checked-host-only)的同一
WSL 构建与 `test-nuwa-smp-gate-kernel.py --objects` 命令，给构建输出换一个新目录。
保持默认关基线目录不变，再执行以下命令（独立 `verifier` 复跑用新输出目录）：

```sh
$PY -B scripts/repack-nuwa-smp-gate.py --enable-smp-entry \
  --kernel out/nuwa-smp-entry-20261123-build/kernel.macho \
  --kernel-sha256 6af982c35ba95de30ac33d68f040cae384878b78236d40d2f9d9c8a0f7dc683f \
  --output out/nuwa-smp-entry-20261123-package --audit out/nuwa-smp-entry-20261123-audit
fsck.fat -vn out/nuwa-smp-entry-20261123-audit/actual-vendor-ramdisk.img
mdir -i out/nuwa-smp-entry-20261123-audit/actual-vendor-ramdisk.img ::/EFI/UniXNU
```
