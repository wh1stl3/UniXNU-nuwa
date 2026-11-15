# Queue-five executor host profile — self-checked

`ufs-queue-five-20261114-r1` binds outer SHA256
`44205ea9c123afd1a13109c98329f2c8c0d96e9c2a1021ff9b82cc3920248dc9`
(100663296 bytes), FAT `eb30a7d4e2354b4618a80fc6d50becdf4fff2a6820aec7e44a1a27f8d8deaae9`,
kernel `eff66a33a097568e3c44f84fb1a7f3365889613cdcb629583944f2c99022012b`
(55545856 bytes), derived ADT `f5ee7ad8f1b1fd144d984859c1d94597fb449aa765c0c666f4660554ac4012df`
(13340 bytes), package record `9a7e0662564606663f9ad631b046945bd18d313ef3720beee843d74ea3a90a69`
and outer record `ff8221fcfceae6454c9e6923f6c37b5c56552174c6e19a79c9990abdd18479ce`.
Arguments are exactly `-v serial=3 nuwa-pmgr=2 native-ufs-probe=2 native-ufs-root=0`.
The original stock backup is `493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`;
template `5ad2...` is not that backup. This profile freezes the package's
actual empty evidence object, not invented kernel evidence.

Executor source before SHA256 `318a815076f009c1be074b04394dbad2a7be6ab095903c307ec239c83fb19160`
is a historical pin only; new executor SHA256
`b4e34548e1d59bf78b83d00f301faa64ca73fcea3b52f62b4f5f4c3c7b9ff16c`.
Completed old run identities are not rewritten. Kernel review/verifier and
packaging review/verifier PASS (parent report); packaging evidence is
`out/nuwa-ufs-queue-five-package-verifier-20261114/verifier-summary.json`.
Executor independent review/verifier pending.

Commands below ran from `D:/Code/PortingiOS/nuwa/UniXNU-nuwa` (WSL mapped
cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`), with process return codes:

* `C:/Program Files/WorkBuddy/resources/vendor/python/python.exe -B -c "import ast,pathlib; ast.parse(pathlib.Path('scripts/run-pmap-ret-once.py').read_text(encoding='utf-8')); print('AST OK')"`: exit 0.
* Same Windows Python `-B out/queue-five-executor-host-20261114/hostcheck.py`:
  exit 0; actual inputs hashed, process trap, no run directory.
* `wsl -d Ubuntu-22.04 -u root -- /home/wh1stl3/.local/bin/python3.11 -B out/queue-five-executor-host-20261114/hostcheck.py`:
  exit 0; actual inputs hashed, process trap, no run directory.
* Windows Python `-B out/queue-five-executor-host-20261114/selfcheck.py`:
  exit 0, 118 synthetic groups; see `selfcheck.json` alongside helper.
* Windows Python `-B out/queue-five-executor-host-20261114/dry.py`:
  exit 0, 24 actual unauthorized CLI runs (8 profiles × 3 phases), zero
  device commands and run directories; see `dry.json`.
* Windows Python `-B out/queue-five-executor-host-20261114/targeted.py`:
  exit 0, 26 synthetic cases including args, artifact, material, paths,
  cross-run/profile identity, pre-claim gate and restore independent of
  candidate/evidence; see `targeted.json`. Large artifact negatives use
  synthetic metadata; the two host-input checks hash the actual artifacts.
* From `D:/Code/PortingiOS/UniXNU`, WSL root Python3.11
  `-B scripts/porting-record.py check --device ../nuwa/UniXNU-nuwa --base origin/feat/step7-kernel-patches-8796`:
  exit 0, 14 structured areas checked.

Source reuse: existing `wh1stl3/UniXNU-nuwa` HC executor, base
`029a79bb58a403c0f3441ed991ad312ae1102c39` with local changes, repository
licensing applies; no third-party dependency.

Only future separately authorized prepare, boot and restore phases are
requested; there is no current device authorization. Observe
`QUEUE_ONLY_DONE attempt=5 completed=5 hc_read=5` and raw
HCE/UTRLDBR/UTRLRSR/UTRLBA/UTRLBAU. The old `HC_SNAPSHOT_DONE` stage-7 label
alone is not success. Five instantaneous reads do not establish queue
ownership, DMA, SMMU or root. Authentication remains NOT REACHED.

Independent verifier should rerun both hostcheck commands and the Windows
AST, selfcheck, dry and targeted commands above with fresh output paths, plus
the correct-base porting-record check; do not invoke device tools or authorize
any phase. Final acceptance belongs to the parent.
