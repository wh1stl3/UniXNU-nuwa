# SMP entry gate: one secondary, default off (2026-11-23)

Host-only package. Nothing was written to a device and nothing was booted; the
kernel, the CHMH rebind, the outer readback and the FAT are self-checked here.
Authentication stays **NOT REACHED**.

Branch `display/20h392-dsp-diag`, base `d780165` (the sb-stack3 packaging
commit). This round changes the kernel, so it is *not* an argument-only repack:
the device-facing argument set is the current one unchanged.

## Scope and acceptance

This version tests **one** thing: whether the second core (cpu1, ADT `reg`
`0x100`) can enter XNU and report there with the expected affinity on its own
stack. It does **not** test multi-core scheduling stability; that is a later
gate.

Two gates, in order:

- **Entry gate** (the next device round): exactly one `PSCI CPU_ON`, the new
  core reaches `ArmCpu::initCPU` with `MPIDR_EL1[15:0] == 0x100`, gets its own
  `cpu_data`, GIC redistributor and time base, and the banner row 38 reports
  `SMP req=1 run=1 cond=1 ... c1=step7` with no `!fail`. Stop conditions: no
  `c1=` report at all, `!fail1` (affinity alias), or the boot nub being taken
  over (`run` stays 0 while `c1` advances) — then stop, do not retry, and keep
  the single sample.
- **Run gate** (later): sustained scheduler/IPI/timer behaviour with the
  secondary up. Not attempted here.

Why `c1=step7` is the entry proof: `ArmCpu` writes step 5 on the new core at
`initCPU` entry, step 6 after its redistributor, step 7 after the GIC, time
base and CPU state are up. The affinity check happens between 5 and 6
(`(mpidr & 0xffff) != (affinity & 0xffff)` → `armcpu_smp_fail=1` and
`parkCore`), so a wrong or aliased decode cannot reach 6/7.

## Changes

### 1. `osfmk/arm64/start.s` — reset-vector affinity mask

Added to the device series as `patches/xnu/8796-nuwa-smp-affinity.patch`
(`patches/xnu/series`, directly after `8796-apple-only-cpu-tunables.patch`).
The hunk is the upstream SM8550 condition
(`UniXNU-sm8550-common@a9f45dc6 patches/xnu/native-smp-secondary.patch`):

| Line | Original | New |
| --- | --- | --- |
| 148 | `#if HAS_CLUSTER` | `#if HAS_CLUSTER \|\| defined(BCM2837)` |
| 151 (`#else` arm) | `and x0, x15, #0xFF` | unchanged text, no longer selected on this board; the `0xFFFF` arm above now applies |

So the mask applied on BCM2837 changes from `0xFF` to `0xFFFF`: the physical id
becomes `AFF1:AFF0`, which is how the SM8550 device tree numbers the cores
(cpu0 `0x000`, cpu1 `0x100`, … cpu7 `0x700`). `HAS_CLUSTER` is only defined by
`H14.h`/`H13.h`; the BCM2837 board config (`MAX_CPU_CLUSTERS 1`) leaves it
unset, which is why the old mask zeroed cpu1 to `0x000` and matched the boot
core's `cpu_data` entry. `ml_get_cpu_number()` already masks `AFF1:AFF0`, and
`MAX_CPUS` (4) / `MAX_CPU_CLUSTERS` (1) are unchanged.

### 2. `drivers/ArmCpu/ArmCpu.cpp` — one admitted secondary

Component patch `patches/armcpu/nuwa-smp-one-secondary.patch`, applied by the
kernel recipe (it is not an XNU series entry). In `ArmCpu::probe`, inside the
existing `sheng-smp != 0` branch only:

```c
if (id != 0x100) {
  return nullptr;
}
```

Every other cpu node stays unprobed, i.e. the device tree keeps it `waiting`
and no `CPU_ON` is issued for it. With `sheng-smp` absent the branch is not
reached and `probe` returns `nullptr` for every secondary exactly as before.

### 3. Build recipe

`scripts/build-nuwa-display-native.py --smp-gate` stages both sources, applies
the two patches, compiles them with the recorded commands and replaces
`start.o` in the link file list and the ArmCpu archive on the link command
line. The unmodified recipes reproduce the recorded objects **bit for bit**
(`start.o` `c6429a8e…`, `ArmCpu.o` `c18059c1…`), so the recorded inputs stay
pinned while the new objects are traceable to the two hunks:

- `start.o`: exactly one word changes, at `0x420`: `and x0, x15, #0xff` →
  `and x0, x15, #0xffff`. Symbol table identical.
- `ArmCpu.o`: `cmp w22, #256; b.ne` added in `probe` (`0x4b8/0x4bc`), function
  sizes after it shift by 8 bytes, and the assert line-number immediates in
  other functions move by +6 (360→366, 448→454, 453→459, 460→466) because the
  patch inserts six source lines. Symbol table identical.
- The ArmCpu checkout is CRLF on this host; the staged copy is normalised to
  LF before patching, and `-ffile-prefix-map` keeps the embedded `__FILE__` at
  the upstream path. Two `-Wno-*` flags (missing-designated-field-initializers,
  unused-but-set-global) are needed because clang-24 raises warnings that the
  recorded machine did not enable; the unmodified compile is bit-identical
  with them added, so they change no code.

## Default off — what is and is not identical

No boot argument is added or removed: `sheng-smp` is absent, so:

- `ArmCpu::probe` behaviour, CPU registration, pmap/time-base initialisation
  and the boot path are the same decisions as the current kernel;
- the boot core enters at `_start`, never `reset_vector`, so the changed word
  is not executed;
- the probe gate is behind `sheng-smp != 0`.

The image is not byte-identical, and this must not be claimed: `reset_vector`
contains one different immediate word, `ArmCpu.o` is 8 bytes larger, and the
link layout after it shifts. The next section states exactly what was compared.

## Results (self-checked, host only)

Baseline reproduced first: the same builder without `--smp-gate` rebuilt the
current kernel bit for bit (`64a97b23…`, 52,187,136 B), so the builder change
does not perturb the default path.

| Artifact | Value |
| --- | --- |
| Kernel | `6af982c35ba95de30ac33d68f040cae384878b78236d40d2f9d9c8a0f7dc683f`, 52,187,136 B |
| Outer `vendor_boot.img` | `b02007f707302915ec62516dff21bec5d1dd4e0dbaa95ccfe5440d18b3655999`, 100,663,296 B |
| CHMH SHA-384 | `1f9c8fef99eaa2c4e508f8ae2e37a314c804cecbf816cacc92519a0b550331b132534e60516c86ff064a0f4b7d730f94` |
| FAT (`payload.img`, outer readback identical) | `194b6c9a21a0a9819906cfad4a7dd695282b4650ef9446ac367471f235e31ec2`, 67,108,864 B |
| Derived ADT | `f2f940632c3cb76885f8f064021b24130c3427bcd4def4679426586033e9abd7`, 13,680 B |
| Seed (`scratch-data.img`, unchanged) | `692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247` |

FAT: `fsck.fat -vn` reports 9 files, 106,239/129,022 clusters; `mdir` reports
**11,664,896 B free** (above the 8 MiB floor). The separate `--audit` pass
re-extracts the outer and agrees on `outer_sha256` and the FAT.

Linked checks: `_LowResetVectorBase` = `0xfffffff007404000` and the mask at
`0xfffffff007404420` is `and x0, x15, #0xffff`; `ArmCpu::probe` contains the
unique `cmp w22, #256; b.ne` guard at `0xfffffff0079a6090`. Prelink inventory
shape is unchanged: 65,443 bindings, 31 components, 7 kernel interfaces; the
binding *addresses* shift because `ArmCpu.o` grew 8 bytes.

Reproduction (WSL Ubuntu-22.04 root, from this worktree):

```sh
PY=/home/wh1stl3/.local/bin/python3.11
BASE=/mnt/d/Code/PortingiOS/UniXNU
CPO=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json
$PY -B scripts/build-nuwa-display-native.py --base "$BASE" --cpo "$CPO" \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 --r35l-dir out/nuwa-r35l-regs-full-20261121 \
  --cpu-only --no-software-vsync --candidate --hid-standin --mg-reset --smp-gate \
  --out out/nuwa-smp-gate-20261123-build
$PY -B scripts/test-nuwa-smp-gate-kernel.py --build out/nuwa-smp-gate-20261123-build \
  --kernel-sha256 6af982c35ba95de30ac33d68f040cae384878b78236d40d2f9d9c8a0f7dc683f --objects
$PY -B scripts/repack-nuwa-smp-gate.py \
  --kernel out/nuwa-smp-gate-20261123-build/kernel.macho \
  --kernel-sha256 6af982c35ba95de30ac33d68f040cae384878b78236d40d2f9d9c8a0f7dc683f \
  --output out/nuwa-smp-gate-20261123-package --audit out/nuwa-smp-gate-20261123-audit
```

## Arguments (re-extracted from the new `vendor_boot.img`)

489 bytes, 25 tokens, SHA-256
`0c33efc81150bfe14f3fe3872c81666af99f20d9d7bf4089a6cce1bb380cef83`:

```text
-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1 build-tag=nuwa-r35 boot-progress-scale=3 sheng-data-persist=2 sheng-log-reserve=1024 offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1 offline-legacy-transfer=1 offline-legacy-cpu-present=1 nuwa-lite=1 nuwa-mg-reset=1 nuwa-hid-standin=1
```

Proof that no token was added or dropped:

- byte-identical to the previous package with this exact set, outer
  `d6de71fcb7caa4c210f2d40e4729fe98611e5336b267eba301fdc8595b723769`
  (`worktree-textfixup` final4), token for token;
- identical to outer `2335fd6c…b492` (`sb-stack3`) with ` nuwa-sb-stack=360`
  removed;
- identical to the current device package (`vendor-boot-hid-stage`, outer
  `01e6e1c7…`) with ` nuwa-sb-restart=400 nuwa-sb-restart-every=180` removed;
- no `sheng-smp`, no `nuwa-sb-restart*`, no `nuwa-sb-stack`, no
  `sheng-data-reset`; `/chosen/display-scale` `03000000`.

The next device round that exercises the entry gate must add exactly one token,
`sheng-smp=1`, to this set; that is a boot-argument change and needs its own
authorisation. This package does not carry it.

## Gaps found (stop-loss) and what is still unproven

The mask fix is necessary but the entry gate is not proven by it:

- `CpuDataEntries[cpu1]` exists only after `ml_processor_register` ran for
  cpu1 on the boot core (`finishSecondary`), which is what sets
  `cpu_phys_id = 0x100` and `cpu_reset_handler = start_cpu`; that path is
  unchanged and untested here.
- `MAX_CPUS` 4 means the topology keeps cpu0..cpu3; only cpu1 is admitted, so
  `startThread` never reaches `ml_get_topology_info()->num_cpus` and
  `ml_cpu_init_completed()` is not called (it is gated by `armcpu-edge`,
  default 0). No cluster-edge or per-CPU pmap change was made.
- GIC redistributor discovery, time base, IPI delivery and the secondary's
  scheduler entry are existing code and have never run on this board.

If the entry gate fails, the failure mode recorded by `armcpu_smp_step/fail`
and `armcpu_smp_seen_mpidr` is the next thing to read; do not widen this
change set in the same round.

## Review request

`deep_reviewer`: boot entry ABI (`reset_vector` / `LowResetVectorBase` /
`start_cpu`), the affinity decode (`AFF1:AFF0` against `ml_get_cpu_number` and
`CPU_PHYS_ID`), and that default-off is genuinely zero-difference in behaviour
(the two decisions above, not image bytes). Ordinary review of the packaging
diff is also wanted. Independent verifier should rerun the three commands
above with fresh output names.
