# Donor pthread prelink — self-checked

Update (parent-reported): ordinary review **PASS WITH CONDITIONS** and
independent verifier r4 reproduced kernel SHA256
`8ffb9f381cebfbfc56dd210901a9b7533b51cc3b95fba0719f4cd2b3972e3f6d`,
55390208 B. Review closes the normal startup lifecycle **statically**;
runtime registration and device behavior remain unproven. The review's
pc-relative 1324-instruction inventory passed; it was not rerun here. Full ABI
is not qualified; this is a limitation, not an additional demonstrated blocker.

Parent reports reviewer confirmed four frames for `chmh-20261112-01` reaching
`bsd_init` → `pthread_init` NULL table panic. Backup and restore-readback were
independently verified at 100663296 B / SHA256
`493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`;
raw serial association remains limited. This is not a current live-state claim.

`board.toml` adds only `com.apple.kec.pthread` to the donor roots. Existing
source pthread remains `n`, source archive absent, crypto remains `prelinked`.
No ASMB, level, null check, manual kmod invocation or constructor change.
Normal prelink reused native after verifying its stored hash, donor, map,
effective config, original board semantics plus observer archive, defconfig,
27 patch hashes, XNU revision and observer source/builder equality. This does
not establish equality of every historical tool/source input. Base pin remains
`693f5d9cae8a408dd18b39f3f9fdc4228c934241`.

Artifacts, all local `out/pthread-normal-prelink-20261112-r3/`:

* `work/kernel/kernel.macho`: 55390208 B SHA256 `8ffb9f381cebfbfc56dd210901a9b7533b51cc3b95fba0719f4cd2b3972e3f6d`.
* `work/kernel/kernel.json`: SHA256 `f07f86d8bcf44401ff65cf809792447053dad484104d0f5a03143db3a9828ca4`.
* `prelink-bindings.json`: SHA256 `befd4bac3196b02983e41bde43bdc030f4b99a6587bf286008567104016290bd`.
* `provenance.json`, `audit.json`, `logs/prelink.log`: commands, input hashes and bounded results. Native map stays at the recorded existing path, SHA256 `25c892e8a167c448bb1d24853c0420b09b716361f110b17960c90ffcf2ccb460`.

Normal builder and audit, WSL Ubuntu-22.04 root, cwd
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`, both exit 0:

```sh
env PYTHONDONTWRITEBYTECODE=1 /home/wh1stl3/.local/bin/python3.11 -B scripts/prelink-nuwa-pthread.py --out /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/pthread-normal-prelink-20261112-r3
env PYTHONPATH=/home/wh1stl3/.local/lib/python3.10/site-packages /usr/bin/python3 -B scripts/audit-nuwa-pthread.py --prelink out/pthread-normal-prelink-20261112-r3/work/kernel/kernel.macho --output out/pthread-normal-prelink-20261112-r3/audit.json
```

The earlier r1 and r2 builders and audits also exited 0 and produced the same
kernel; r2 adds input checks and a bindings map, r3 checks effective config's
last assignment. The emitter itself explicitly reports
`instruction_relocation_complete=false` and `abi_qualified=false`. The audit
finds one donor pthread metadata entry, its six KPI identifiers present, 95
recorded pthread binding values matching actual relocated memory, no undefined
native symbols, and donor executable bytes preserved. This is not a full
instruction-relocation or dependency ABI proof.

Actual source `startup.c:688–698,747,790` calls `PE_init_iokit` before
lockdown and `bsd_init`; `pexpert/arm/pe_init.c:393` calls `InitIOKit`;
`IOStartIOKit.cpp:168–169` conditionally calls the constructor-installed
`record_startup_extensions_function`. `libsa/bootstrap.cpp:161,183–218,608–658,789`
reads prelink info then selects `com.apple.kec.*` entries marked
`AppleKernelExternalComponent=true` and calls `OSKext::loadKextWithIdentifier`.
The reviewed static chain reaches normal kmod start before lockdown and BSD;
it does not show constructor, allocation, dependency loading or kmod lifecycle
actually succeeding at runtime.

Fresh-image Unicorn starts the real donor kmod start directly: it reaches the
native registration routine, returns its callback table, and native wrapper
dispatch reaches the donor init entry. The unregistered NULL and duplicate
registration panic controls also run. Neither OSKext lifecycle nor donor init
body was executed. Normal startup registration is therefore **not proven** at
runtime; static lifecycle review and bounded execution are separate evidence.

This is the pristine prelink, not old `7fd3…` renderer baseline. Renderer and
layout must be independently rebuilt/validated for the new image before any
later packaging. Kernel changed: rederive the CHMH experimental digest binding;
old CHMH cannot be reused. No outer/executor or device work was performed.

Initial record check using Python 3.11 and `--base origin/main` exited 1 because
our new evidence lacked a command; the entry was corrected and moved from the
storage area to diagnostics. Python 3.10 attempt first exited 1 because that
interpreter lacks `tomllib`. Corrected record check with Python 3.11, cwd
`/mnt/d/Code/PortingiOS/UniXNU`, `scripts/porting-record.py check --device
/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa --base origin/main` exited 0 (14 areas;
self-checked).
