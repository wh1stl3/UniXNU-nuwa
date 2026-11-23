# SMP entry observations, default off (2026-11-23)

Local candidate: `out/nuwa-smp-observe-20261123-package/vendor_boot.img`.
Host self-checked, not flashed or booted. Branch `display/20h392-dsp-diag`,
base `1afa867`. No admission or reset-vector change relative to `917f3ea`;
the packaged args are byte-identical to `b02007f7…5999`, **without `sheng-smp`**.
Authentication remains NOT REACHED.

## How to read it

Startup page row 38:
`SMP 0/0/0 c1=step0 n=0 t=- rc=- aff=-`. The first three numbers are
`req/run/cond` (run is hex, cond `1` = SMC, `2` = HVC). `!fail` is printed
only for a nonzero existing failure. The live post-handoff title repeats
`rc` and `aff` (`C`/`E` are the existing crash/failed-exit totals). It does
not consume a body slot or change the body row selector or repaint gate.

| Field | Can tell | Cannot tell |
| --- | --- | --- |
| `n`, `t` | CPU_ON dispatch attempts, and target operand of the latest attempt (both hex; `t=100` expected). The count increments immediately before PSCI. `n=0 t=-` means no dispatch reached that point. | `n=1` alone does not establish firmware return or secondary entry. |
| `rc=-` | No firmware result or no-conduit result published yet. This includes local helper-start failure (`-1000`), which is not a PSCI return. | Cannot tell why no result was published; use `n` and `step`. |
| `rc=nc` | Driver failed to find a conduit (local `-1001`); no SMC/HVC was issued for that request. | Not a firmware rejection. A numeric `rc=-1001`, if returned by firmware, is not the driver's `nc`. |
| Numeric `rc` | Signed PSCI `CPU_ON` return. Interpret each nonzero value by its PSCI meaning; `-4` (`ALREADY_ON`) and `-5` (`ON_PENDING`) do **not** mean rejection. `rc=0 aff=-` means the call returned success but the secondary has not reported at the sampling point in this frame. | Success does not show that reset, scheduler entry, or IPI delivery worked. A single frame cannot distinguish delayed arrival from no arrival. |
| `aff` | Secondary's real `MPIDR_EL1` affinity fields (`& 0xff00ffffff`, hex). `-` is unpublished; `0` is a valid observation. Any value other than `100` (`0x100`) is an affinity alias/mismatch for this gate. | Does not show the stack address or reset instructions run before `initCPU`; a mismatch only in AFF2/AFF3 will not set the existing AFF1:AFF0 `!fail1` check. |
| `c1=step…`, `!fail…`, `run` | Existing progression, failure and running count. `step7` is written before `run++`; a single `step7 run=0` frame must **not** be classified as boot-core takeover. | A frame is not an atomic snapshot across all fields. No claim of sustained scheduling, timer or IPI stability. |

## Collection and display sites

Line numbers below are for the staged files from this build. ArmCpu base is
`UniXNU/ArmCpu@93a5030c5d983d0ef90f0fca93879d6e36ad1ba8`; the device patch
applies only with `--smp-observe`, after the existing one-secondary patch.

- `drivers/ArmCpu/ArmCpu.cpp:829–831`: publish separate no-conduit state.
- `drivers/ArmCpu/ArmCpu.cpp:841–847`: publish the actual target and increment
  the attempt counter immediately before the unchanged PSCI call; publish
  the signed return and firmware-result state immediately after it.
- `drivers/ArmCpu/ArmCpu.cpp:571–575`: at the existing secondary-only
  `initCPU` MRS, store affinity then publish its independent valid flag,
  before the existing affinity check/park. `step7`/`run++` are at 587–588.
- Generated `BootProgress.c:896` (page) and `:1894` (post-handoff title).
  The new flags/counter use release/acquire publication for diagnostic data
  only; no changes to secondary dispatch decisions, locks or scheduling.
  With SMP off none of these ArmCpu writes run. The binary and displayed
  text do change; this is not a claim of image identity or measured
  equivalence on hardware.

The host C formatter replay measured **78 / 80 columns** for page/title at
the tested maxima (bounded by `t=100`, the current gate's target), **37 / 61**
with default-off fields (title counters maxed), and **41 / 63** for the
simulated successful entry. The generator comparison found the other page
rows and live body byte-identical (including `DSP`/`CLI`/`PROP`/`SC`/`LOAD`/
`UFS`/`SCHED`/`PC` and the banner budget). No physical display was measured.
If rendering stops before a paint, these fields are not independently
visible; the live path retains the existing repaint cadence.

## Package evidence (self-checked)

| Artifact | Hash |
| --- | --- |
| Kernel SHA-256 (52,187,136 B) | `825eaa8ffdb12fde9f57d7f5bd3cb66fe2d9ac234ffa0955d1038bcbe633332d` |
| Outer SHA-256 (100,663,296 B) | `9db3c82bd36b6953d3eb35e17a418053a192d78d5d18442a38372ad50e20f599` |
| Rebound CHMH SHA-384 | `1b283bfae35c2a11b59f38b1cf0703e1bf06c0b6c3bdb8b15efdc649be299e7a2a52520b2229c5fdd8efeb5c45373325` |
| FAT SHA-256 | `a97c187c477a578c2721dd13f0e463b6a1716f9537e327cfa6ec80f62202068c` |
| Seed SHA-256 (unchanged on outer readback) | `692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247` |

Outer audit re-extracted the kernel, seed and FAT; FAT has 11,664,896 B
free (≥8 MiB). Direct extraction from both the pinned `b02007f7…5999`
outer and this outer confirmed the same 489 argument bytes / 25 tokens,
SHA-256 `0c33efc81150bfe14f3fe3872c81666af99f20d9d7bf4089a6cce1bb380cef83`.
`start.o` is byte-identical to the existing gate build. The linked gate
test confirmed the existing reset mask, probe guard and prelink inventory
counts (65,443 bindings / 31 components / 7 interfaces).

Independent verifier should rerun the [gate build recipe](nuwa-smp-gate-20261123.md#results-self-checked-host-only)
with `--smp-observe` and fresh output directories, then run:

```sh
H=825eaa8ffdb12fde9f57d7f5bd3cb66fe2d9ac234ffa0955d1038bcbe633332d
$PY -B scripts/test-nuwa-smp-gate-kernel.py --build "$BUILD" --kernel-sha256 "$H"
$PY -B scripts/repack-nuwa-smp-gate.py --kernel "$BUILD/kernel.macho" \
  --kernel-sha256 "$H" --output "$PACKAGE" --audit "$AUDIT"
$PY -B scripts/test-nuwa-smp-observe.py --package "$PACKAGE"
```

`reviewer` re-review pending: collection point and validity publication,
default-off CPU-path equivalence, page/title widths and existing row retention,
and local `-1001` versus firmware `rc`. `deep_reviewer` should confirm the
observational stores do not change the secondary entry contract. This record
is not a device-write authorization.
