# nuwa touch ID candidate (2026-11-28)

Status: **host self-checked only; no kernel link, image, device run or
independent verifier**. The archive has no board readiness provider and no
kernel caller. Consequently it cannot currently be enabled on nuwa; neither
the FDT nor this host model proves that power, clocks, pins or ownership are
ready at XNU runtime.

## Sources and licence

- Staged/default-off design reference: `OddlyLabs/unixnu-fuxi@78f30b65`,
  `package/FuxiTouchBoard.h` and `package/FuxiTouchProbe.cpp`, BSD-2-Clause-Patent.
- Actual GENI info/init/PIO code used by the build:
  `UniXNU/QcomGeniSpi@eac47baefe6a5d2368a70351e6ad1b6361bedbe2`,
  `GeniSpi.h` and `GeniSpi.c`, BSD-2-Clause-Patent. The independent builder
  checks the revision and source bytes before compiling them.
- Read-frame and byte-offset **candidate only**:
  `OddlyLabs/FuxiFtsTouch@a9237037`, `FtsProtocol.c` and `FtsProtocol.h`,
  BSD-2-Clause-Patent. Its chip identification, reset, FIFO and ICR routines
  are not called or imported.

## nuwa evidence

The three source records are in `wh1stl3/UniXNU-nuwa` at
`be3cdedb2f17b802a30312ca50613a7ccdab145b`:

- `docs/nuwa-recovery-readonly-20261126-observation.md`: input7 is linked to
  `fts@0`; recovery FDT capture and its limits.
- `docs/nuwa-recovery-final-fields-20261126.md`: declared input slots 0–9 and
  X 0–14399 / Y 0–31999; capabilities are not observed touch events.
- `docs/nuwa-fdt-resources-20261126.md`: `st,spi`, IRQ and supply references.

The locally retained FDT is 938828 bytes with SHA-256
`febcc784a5d9abca32cf383970c5f72b35f80c45d9d933f8a037329864757571`.
Its offline DTS was checked for the following declarations:

| Item | nuwa declaration |
|---|---|
| Controller | `/soc/qcom,qupv3_1_geni_se@ac0000/spi@a90000`, SE `reg=<0xa90000 0x4000>`; wrapper `<0xac0000 0x2000>` |
| Device | `fts@0`, `compatible="st,spi"`, CS 0, max 12 MHz; no `spi-cpol`/`spi-cpha` properties (mode 0 candidate) |
| SPI pins | Named pinctrl nodes: MISO GPIO44 `qup1_se4_l0`, MOSI GPIO45 `qup1_se4_l1`, CLK GPIO46 `qup1_se4_l2`, CS GPIO47 `qup1_se4_l3` |
| Other pins | IRQ GPIO25, reset GPIO24 |
| Rails | AVDD `pm8010m_l6`, 1.8–3.2 V (DT init 3.2 V); VDD `pm_humu_l12`, 1.8 V |
| Identity/config | `fts,tp-vendor=0x38`; `st_fts_m2.ftb`; 10 declared slots, X 0–14399, Y 0–31999 |

The controller's `pinctrl-0` lists the MOSI and MISO phandles in that order;
their roles above come from the named nodes, not the order in the list. The
touch CS node selects pull-up; the generic SE CS node declares pull-down.
This component programs neither, and DT names do not independently measure
electrical direction or active pin state.

## Build and eventual integration

From this worktree in WSL, the independent entry builds a host test and a
freestanding arm64 Mach-O archive (not a kernel or device image):

```sh
python3 -B scripts/build-nuwa-touch-probe.py --self-test --archive
```

The builder defaults to `../../UniXNU/drivers/QcomGeniSpi` relative to the
worktree; `--geni-dir` selects another checkout at the **same** pinned revision,
and `--out` changes the output directory. The archive is
`out/nuwa-touch-probe-20261128/libNuwaTouchProbe.a`. It has not been linked
against an XNU kernel or qualified for its ABI.

The only entry is `nuwa_touch_probe_run(stage, platform, result)`:

- `NUWA_TOUCH_DEFAULT_STAGE` = 0: no callback, log or controller access.
- `NUWA_TOUCH_STAGE_INFO` = 1: a live readiness callback must succeed first;
  read the upstream GENI info and check SPI firmware, FIFO availability and
  geometry, main-sequencer inactivity and existing non-DMA mode. No controller
  writes. Reports `st=1`, which means **info only**, not a successful ID read.
- `NUWA_TOUCH_STAGE_ID` = 2: repeat these checks, initialize the already
  FIFO-capable controller, use its confirmed source clock and mode 0/CS 0,
  and submit at most one 8-byte full-duplex transfer:
  `FB 20 00 00 00 00 00 00`. Its last two received bytes are recorded as-is
  only when the transport reports success.

The limit is **per invocation**, not per boot: there is no automatic retry
inside a call, but another explicitly admitted call can submit another frame.
The caller must not repeat an erroring attempt until the ownership and
quiescence conditions below are met.

There is deliberately no boot argument or automatic caller in this change.
Before either enabled stage, the actual resource owner must already hold
exclusive controller ownership and maintain live readiness until the probe
returns. The board provider's `confirm_ready` callback must certify both rails,
all required clocks, active pinmux, released reset and the source rate and
selector under that ownership. Stage 1, the probe's own MMIO reads, DT constants
and user assertions do not establish readiness or ownership. It must also
supply a log callback and, for stage 2, a microsecond delay callback; an
existing, correctly reviewed caller must select stage 1 or 2 explicitly.

Stage 0 invokes no callback or MMIO. If the owner refuses readiness, the probe
performs no SE/wrapper MMIO; the provider and logging callback must also avoid
all MMIO on that refusal path, buffering the diagnostic for later publication.
This is a provider contract, not something the probe can enforce inside an
arbitrary callback. After readiness is accepted, checks such as FIFO
availability require SE/wrapper reads; their refusal paths perform no
controller writes or transfer, but are **not** zero-MMIO paths. Missing
callback fails before probe MMIO. No provider, argument parsing, logging
backend, readiness measurement or runtime hook is implemented here.

If stage 2 has made, or may have made, controller writes, the owner must retain
exclusivity after return until it has separately established quiescence and a
safe controller configuration, restoring the previous owner's requirements
where needed. If either cannot be established, the controller remains
quarantined and must not be handed to another user or retried. In particular,
the upstream timeout/error recovery attempts cancel/abort, but discards the
final abort-wait result; the probe return alone proves neither quiescence nor
safe restoration. No actual ownership, recovery, restoration or handoff
backend is supplied or validated by this candidate.

The callback receives one line, e.g. `TP id=A57C st=0 phase=2/2`; unavailable
ID is `----`. Status is the underlying GENI error code, including `-110`
timeout and `-5` I/O error; `-95` includes disabled FIFO or pre-existing DMA
mode, `-16` means active main sequencer, and `-19` unsupported FIFO geometry.
`phase=0/2` means the failure precedes completed info checks, while
`phase=1/2` includes initialization/transfer failures. No received byte
pattern, including `3640` or `0000`, is treated as proof of a chip identity.

## Candidate frame, controller writes and open items

The candidate frame is taken from a register-read interpretation on fuxi; its
chip-side effects on nuwa are unverified. This component does not explicitly
request touch reset, event FIFO consumption, ICR writes, sensing or firmware
updates; that is not proof those effects cannot occur. It does not itself
issue power votes or pinmux writes. Stage 2 uses the upstream GENI controller
initialization and PIO path, including known GENI/DMA control and IRQ register
writes; the upstream failure path also reads DMA status. No DMA buffer,
DMA transfer, IOMMU or SMMU mapping is set up here. Disabled FIFO and
already-active DMA mode are rejected before initialization.

Unverified: specific touch IC model; nuwa's interpretation and read-only
semantics of this candidate command; actual pin electrical direction/active
state; rail on-state and power-up order/timing; reset release; live source
clock/rate; controller ownership and prior transactions; upstream PIO behavior
on this SE; XNU logging, kernel linkage and runtime behavior. No read result
has been obtained from nuwa. Driver initialization and its caller require
review before any candidate is built for a device.

The host model exercises the actual pinned GENI PIO implementation, including
the transmitted byte sequence, last-two-byte parsing, arbitrary IDs,
stage-off and owner/readiness refusal with zero mock MMIO, per-call submission
limits across repeated calls, disabled FIFO, pre-existing DMA mode, active
sequencer, unsupported FIFO geometry, timeout and I/O failure. A simulated
owner retains exclusivity after errors and refuses handoff until separately
simulated quiescence and restoration evidence are supplied. This validates
only the test model and caller contract, not an actual provider, safe hardware
handoff or real callback MMIO behavior.
