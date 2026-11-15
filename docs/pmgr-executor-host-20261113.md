# PMGR mode-2 executor — self-checked

Parent reports kernel directed deep review PASS WITH CONDITIONS and independent
verifier PASS, and PMGR CHMH packaging ordinary review and independent verifier
PASS. The executor itself is self-checked only; independent review and verifier
are pending. No device commands or actual run/claim were issued.

Explicit profile `pmgr-mode2-20261113-r1` freezes r4 outer
`ad74c1cb7beee59b60bc0fbb446a7439e8a21a39a3f956ea574b6a62410efd45`, FAT
`a9697c46d775e722d902cceea32070518ea2e8e5cfce8af8abc4eccd25afe701`, kernel
`81b85228316574782f9d5390956c3ce3d8c97e4b345a9ea1631feacf3280b5d1`, derived ADT
`59e78384804830a981e894451c66301c873afbb1da5d768220e538db2a4c8fff`, record
`be10c1a9c113e84ad3ac9d29f26e453c3ea01a02c0b7bbc75987f4208b1dd3c4` and
exact args `-v serial=3 nuwa-pmgr=2`. The outer audit member `parent-adt` denotes
the derived ADT; the original parent `885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4`
is separately bound in material and input record. Run identity binds the full
frozen mapping. Prepare/boot gate host inputs before claim/device; restore uses
the current run identity and backup, not candidate/evidence.

Windows WorkBuddy Python and WSL Ubuntu-22.04 root Python 3.11 each ran the real
`host_inputs` once, subprocess trapped: both exit 0, zero device calls and no run
directory. The WSL command is `/home/wh1stl3/.local/bin/python3.11 -B
out/pmgr-executor-hostcheck-20261113.py` from the device repo; the same helper
is portable to WorkBuddy Python. The single Windows `-B
scripts/run-pmap-ret-once.py --self-check` produced 115 synthetic test groups
in `out/pmgr-executor-selfcheck-20261113.json`: synthetic runners only, including
mode/args, evidence/source, path, identity/cross-profile and restore without
candidate/evidence. It does not perform actual device commands.

Windows `-B out/pmgr-executor-dry-20261113.py` made 18 actual CLI invocations
(six enumerated profiles × three phases), all without authorization; all exit 0,
report zero device commands, and create no run directory. Results are in
`out/pmgr-executor-dry-20261113.json`. These 18 real CLI invocations are distinct
from the self-check's synthetic calls and the two real host-input checks.

SHA256: executor `dea70f7018ccef56bc2d2d3c4449179b3173504e2edaf613845c8a8b205c0027`;
self-check JSON `918c0d52b78996e4a445b49c1add1685f78884cdb79d55d9a2625aad0a1a658c`;
dry JSON `1c7f6e1e6cfcc8e58b3cd70b81dfab990f1da74c2ca3684d780d59b32d37cddd`.
Windows AST parse and tracked `git diff --check` exited 0. Correct-base WSL
`scripts/porting-record.py check --device /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa
--base origin/feat/step7-kernel-patches-8796` reported 14 structured areas.

Observe real PMGR publication and AMFI consumption; disappearance of an old
panic does not establish pthread runtime. CHMH identity is experimental and
unauthenticated; authentication NOT REACHED. The three future device phases each
need new phase-specific authorization. No backup reuse is implemented.

Verifier should independently rerun both interpreter host-input checks, the
single self-check, the 18-call matrix and the correct-base porting-record check;
use fresh output names for evidence and do not invoke any device tool.
