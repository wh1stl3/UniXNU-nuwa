# nuwa SMP 入口关候选（2026-11-23）

观测版 `e1d8460`，分支 `display/20h392-dsp-diag`；以默认关 outer
`9db3c82bd36b6953d3eb35e17a418053a192d78d5d18442a38372ad50e20f599` 为基线。
本记录不授权设备操作。认证仍为 NOT REACHED。

## 入口关判据与止损

- **通过**：`rc=0`（不是 `nc`）、`n=1`、`t=100`、`aff=100`，且 `c1` 的 `step` 推进到 7、`run` 变为 1。只验一个次核的入口，不验持续调度、IPI 或定时器。
- **固件结果**：数字 `rc != 0` 按 PSCI `CPU_ON` 的具体返回值解释；拒绝类返回判固件拒绝，`-4`（`ALREADY_ON`）和 `-5`（`ON_PENDING`）不是拒绝，也不算本次入口通过。`rc=nc` 是本地无 conduit，未发出 PSCI；`rc=-` 是结果未发布。
- **未报到／别名**：`rc=0` 但 `aff=-` 表示请求已发出并返回成功，但该帧次核未到采集点（不能从单帧判定永不到达）。`aff` 有值但不等于 `100`，判作 affinity 别名／不匹配。
- **立即停**：出现 panic、重启、全屏停止刷新、`!fail` 或出现 `c2..c7`，立即停，不重试、不扩核。
- **不能凭单帧判接管**：`step7` 先于 `run++`，单帧 `step7 run=0` 不算接管；以随后可见的 `run=1` 补齐入口证据，不能补齐则不判通过。

需 `deep_reviewer` 复审：打开后的失败面，以及首屏、交接后横幅与刷新中止
时的可观测性是否足够支撑判读。横幅只重复 `rc`/`aff`，不能补足未看到的
`n`/`t`/`step`/`run`；页面没有完成绘制时，字段缺失不等同于固件拒绝。

## 产物与直接回读

候选：`out/nuwa-smp-observe-entry-20261123-package/vendor_boot.img`。
主机 `self-checked`，未上机、未由独立 verifier 复跑。

| 产物 | 摘要 |
| --- | --- |
| Kernel SHA-256 | `825eaa8ffdb12fde9f57d7f5bd3cb66fe2d9ac234ffa0955d1038bcbe633332d` |
| Outer SHA-256 | `04366e48f04690d0801654aff359605f9dc984eeb3f4fb2a926c559d158ca48a` |
| CHMH SHA-384 | `7201f8459b8c50da29617beb3604af1ec39f3183bf124845731a281e89d9b32eb4ac04efe6971795b19d9965bd0c3533` |
| FAT SHA-256 | `f053644ce53325de19334c8b31f43074c43796e3df9f74cdf2e9b8e2d302e4da` |
| Seed SHA-256（outer 回读） | `692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247` |

重建 kernel 与默认关观测版逐字节相同。CHMH 按新 args 重绑；FAT 外的
outer 字节不变。独立的 `--audit` 步骤回读了同一 FAT；`fsck.fat -vn`
和 `mdir` 确认可用空间为 **11,664,896 B ≥ 8 MiB**。读回文件仅
`unixnu.toml` 与 `Payloads/kernel.macho.adt` 不同；最终脚本复包得到逐字节相同的 outer。

从基线与新 `vendor_boot.img` 各自切出 FAT 后提取 `unixnu.toml`。
新 `xnu` args 逐字节仅追加 ` sheng-smp=1`；保留 `nuwa-hid-standin=1`，
无 `nuwa-sb-restart*`、`nuwa-sb-stack`、`sheng-data-reset`。回读全文
（501 B、26 项，SHA-256 `5ada678b399e74bf9c7b567dc860ae86150af66252df678e9a7a93fbda2d75f9`）：

```text
-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1 build-tag=nuwa-r35 boot-progress-scale=3 sheng-data-persist=2 sheng-log-reserve=1024 offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1 offline-legacy-transfer=1 offline-legacy-cpu-present=1 nuwa-lite=1 nuwa-mg-reset=1 nuwa-hid-standin=1 sheng-smp=1
```

同一 FAT 直接提取的 ADT 配置（非实机运行状态），除 CHMH 外与基线相同：

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

## 独立复跑

按[入口门构建配方](nuwa-smp-gate-20261123.md#results-self-checked-host-only)
在 WSL Ubuntu-22.04 root 中重跑，构建参数保留 `--smp-gate` 并加 `--smp-observe`。
下列 `TAG` 取未使用的路径；默认关观测包保持只读。无观测补丁的旧入口包复跑
应使用 `1afa867` 的打包脚本及旧 pin，不是本轮候选。

```sh
PY=/home/wh1stl3/.local/bin/python3.11
TAG=out/nuwa-smp-observe-entry-20261123-verifier
H=825eaa8ffdb12fde9f57d7f5bd3cb66fe2d9ac234ffa0955d1038bcbe633332d
cmp "$TAG-build/kernel.macho" out/nuwa-smp-observe-20261123-build/kernel.macho
$PY -B scripts/test-nuwa-smp-gate-kernel.py --build "$TAG-build" --kernel-sha256 "$H"
$PY -B scripts/test-nuwa-smp-observe.py --package out/nuwa-smp-observe-20261123-package
$PY -B scripts/repack-nuwa-smp-gate.py --enable-smp-entry \
  --kernel "$TAG-build/kernel.macho" --kernel-sha256 "$H" \
  --output "$TAG-package" --audit "$TAG-audit"
fsck.fat -vn "$TAG-audit/actual-vendor-ramdisk.img"
mdir -i "$TAG-audit/actual-vendor-ramdisk.img" ::/EFI/UniXNU
diff -qr out/nuwa-smp-observe-20261123-package/outer-audit/outer-readback/EFI/UniXNU \
  "$TAG-audit/outer-readback/EFI/UniXNU"
```

最后一条 `diff` 预期仅有 `unixnu.toml` 的参数后缀和
`Payloads/kernel.macho.adt` 的 CHMH 差异（返回码 1）。
