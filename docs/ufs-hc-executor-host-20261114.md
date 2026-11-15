# UFS HC observation executor — self-checked

Explicit profile `ufs-hc-observe-20261114-r1` freezes the 100663296-byte outer
`6e150640b3780bcd2bc890d007619eecce2ce2fa6e511a451803556c01c54227`, FAT
`48b463403dffe1cb82c11becc0f6f2e8ba83a4f1c269aea33b97370065471475`, and
55545856-byte kernel `134d1a24ca32b91d3f41cfdf2d95831abdd4ec4c5be827e291970723d14ba0f5`.
Exact args: `-v serial=3 nuwa-pmgr=2 native-ufs-probe=2 native-ufs-root=0`.
Derived ADT `58ffccb0f46e4cd47bca352341508e9daefcaed468fef85c9ff7f3ee814a3ea7`
is distinct from material parent ADT
`885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4`.
Record, material, provenance, evidence and wrapper source are frozen in full
in the run identity. Stock and r4 remain the existing fixed values.

Parent reports r7 directed deep PASS WITH CONDITIONS and independent verifier
PASS; packaging ordinary review and verifier PASS, evidence
`out/nuwa-ufs-hc-package-verifier-20261114/verifier-report.json`. Executor
review and independent verifier remain pending. Identity is experimental,
unauthenticated; authentication NOT REACHED.

Windows WorkBuddy default Python and WSL Ubuntu-22.04 root
`/home/wh1stl3/.local/bin/python3.11` each ran
`-B out/ufs-hc-executor-hostcheck-20261114.py`: exit 0, actual host inputs,
subprocess trapped, zero device calls and no run directory. Windows ran:

* `-B scripts/run-pmap-ret-once.py --self-check`: final exit 0, 116 synthetic
  groups in `out/ufs-hc-executor-selfcheck-20261114.json`. The first attempt
  exited 1 at fixture line 1164: HC was omitted from its profile branch;
  the fixture was corrected, not the production gate.
* `-B out/ufs-hc-executor-dry-20261114.py`: exit 0, 21 real unauthorized
  CLI invocations (7 profiles × 3 phases), zero device commands or run dirs.
* `-B out/ufs-hc-executor-targeted-20261114.py`: final exit 0, 20 synthetic
  cases, including exact args, probe 0/3, root 1, outer/r4/kernel/FAT/ADT/config,
  source/derived/provenance, material, path, identity, pre-claim ordering,
  bad backup and restore without candidate/evidence. Large-artifact negative
  checks use synthetic pinned metadata; the separate two real host-input checks
  hash actual artifacts. The first targeted attempt failed on a Windows temp
  path resolution mismatch in the helper, then was fixed.

SHA256 executor `318a815076f009c1be074b04394dbad2a7be6ab095903c307ec239c83fb19160`;
self-check JSON `4a8c4d44e1c63762e6e2a102cc3eb18a3cbb724f1b4ab4cc912bbc6c62157b5c`;
dry JSON `78d1c25009c2b482d660c3b1d32d3525b3300231572932fa8c3461d829155ef5`;
targeted JSON `c7cee71da73f8c5892095254ad56a2200b5a565c5c550ede01799dc0a6da9a90`.

Restore requires this run's full identity and independent backup, not candidate
or evidence; no backup reuse is implemented. Existing default, one-shot,
whitelist and explicit serial behavior are unchanged. No adb/fastboot command,
device authorization or real run claim occurred.

Future phases require separate new authorizations: prepare (backup and B write),
boot (single observation), and restore (return A and restore B from this run's
backup). Observe stage markers and the single raw VER/CAP/HCS/HCE reads; absent
or abnormal output is not a unique diagnosis. No DMA or root/userdata write is
part of this observation. Do not infer authentication or hardware success.

Reuse: `wh1stl3/UniXNU-nuwa` base `029a79bb58a403c0f3441ed991ad312ae1102c39`
plus its existing uncommitted PMGR executor; repository licensing applies. No
new third-party tool or code.

Verifier: rerun both actual host-input commands, the final self-check, dry and
targeted helpers using fresh evidence names, AST/whitespace checks including
untracked files, and the correct-base porting-record check; do not run a device
tool. Final acceptance remains with the parent.
