# Final instrumented AMNM initializer: continuous host execution

**Self-checked only; independent reviewer and verifier pending.** No device,
kernel/component change, relink, repack, commit or push. This is a single-thread
emulator experiment using the existing ADT-backed object fixtures, not live
IORegistry, boot, hardware atomicity, or authentication evidence.

## Inputs and method

- `/root/nuwa-amnm-final-candidate-stage3-20261111/kernel-amnm.macho`:
  SHA-256 `1754a89e8e92e20baafeaf0e1f98361b0d41ddaea8f420dd44d34d1357f2d162`.
  The `out/amnm-observe-20261111-r1/kernel.input` copy has the same hash.
- `out/owner-pmap-ret-continuation-verifier-final-20261111/adt-generation/final.adt`:
  SHA-256 `885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4`.
- Runner `scripts/research-amnm-endtoend-host.py`, SHA-256
  `19762605bef841ee8fa79944bd9846eb02691c07adeb257073b5ecc5e1329f7e`.
- Evidence `out/amnm-endtoend-host-20261112-r1/evidence.json`, SHA-256
  `4127c03ca9333a0a295e9b90b7aea17ee2caece71497a8bae64ad832670be82b`.
  It records full source hashes, input hashes, compiler command, full PC trace,
  fixture events, all reader and helper calls, raw log and all sixteen raw and
  decoded slots. Earlier exploratory output remains in the separate ignored
  `out/amnm-endtoend-host-20261112/` and is not this final runner's evidence.

The existing `Model` maps the actual Mach-O file-backed segments and zero-filled
segment memory, uses the same ADT-backed OS object fixtures and executes real
`SecureDTInit`. Following that, one uninterrupted Unicorn run starts at
`46e98cc` and ends at `46e9b2c` or original panic entry. The log and flag are
not prefilled. Real hooked code, BLR and continuations execute. Exact bytes
`2b01eaf8` alone receive the existing test-style single-thread LDADDAL model:
64-bit old value, add x10 modulo 2^64 to memory at x9, old value into x11,
PC+4, NZCV unchanged. No claim about hardware atomicity or concurrency.
Other object and logging fixtures are described in the earlier initializer
document. Like that runner, this does not enforce admission of every possible
external dependency; unexpected memory/instruction failures are reported.

## Observed original input

- Stop `46e9b2c`; no invalid memory. The five hook types execute in one trace.
- Committed kinds **1,4,4,4,2,3,4,5**, sequence 8. The three earlier STOREs
  are ids 5,6,7, with byte values 0,1,0. No records are filtered.
- Reader id/return: 5/0, 6/0, 7/0, 8/2, 9/2, 13/2, 10/2, 12/0.
  The first seven callers return to `46eb304`; id12 returns to `46e99dc`.
  All helper callers, keys and errnos are retained in evidence; AMNM helper
  returns 0 and missing `boot-manifest-hash` helper returns 2.
- `5cacef0` receives byte 1 from the actual store instruction at `799148c`;
  the later load sees 1, and the original branch-site operand w8 is 1.
- The unmodified `package/diagnostics/amnm-record.c` is compiled for the host
  and called on the complete frozen 1920-byte emulator log, not on selected
  events. Its original `amnm_snapshot_read`, `amnm_associate`, `amnm_summary`
  return snapshot loss 0, association loss 8 (COUNT), summary
  **`C=8/8 L=8 I=0`**. This is a host C call on a frozen snapshot, not execution
  of the ARM panic renderer. Association value fields are zero when loss is set
  and are not inferred input/store/branch values.

This explains how that summary can arise from extra events in this host
fixture, not the device's panic-2 cause. The observed host path continues;
the device photo and its actual runtime state remain unexplained. The optional
AMNM=1 comparison was not run.

## Commands and verification

All commands below used Windows cwd `D:/Code/PortingiOS/nuwa/UniXNU-nuwa`;
the runner used WSL Ubuntu-22.04 root cwd
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`, `/usr/bin/python3` and Unicorn from
`/home/wh1stl3/.local/lib/python3.10/site-packages`.

```powershell
wsl -d Ubuntu-22.04 -u root -- bash -lc "llvm-objdump --mattr=+lse --disassemble --start-address=0xfffffff00799166c --stop-address=0xfffffff007991670 /root/nuwa-amnm-final-candidate-stage3-20261111/kernel-amnm.macho"
wsl -d Ubuntu-22.04 -u root -- bash -c 'cd /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa && PYTHONPATH=/home/wh1stl3/.local/lib/python3.10/site-packages /usr/bin/python3 -B scripts/research-amnm-endtoend-host.py --output-dir out/amnm-endtoend-host-20261112-r1'
```

Both exited 0. Objdump identifies `ldaddal x10, x11, [x9]`. The run itself
compiles the unchanged C source with `/usr/bin/cc -shared -fPIC -O2` into its
fresh ignored output directory (exact command in JSON), then exits 0. A separate
Python assertion check exited 0: boundary/no invalid memory, all 16 slot sizes,
commits and first eight event kinds, eight exact-opcode model invocations,
actual byte store, and unmodified C summary. `git check-ignore` exited 0 for
the evidence. The script refuses an existing output directory.

For independent rerun, use the same runner command with a **new** ignored
`--output-dir out/amnm-endtoend-host-20261112-verifier`; compare all trace,
slots, helper/reader calls, stop and C summary, allowing output-path metadata
and resulting JSON hash to differ. Also rerun the objdump command and inspect
the host-compiled C boundary. No independent verifier has yet rerun these.
