# HC observation CHMH host package

**Host packaging independently verified; not device release.** Parent reports
directed deep closure PASS WITH CONDITIONS and independent r7 kernel verifier PASS.
Packaging ordinary review PASS and independent verifier PASS: see
`out/nuwa-ufs-hc-package-verifier-20261114/verifier-report.json`. The verifier
recomputed the actual outer, FAT, record, derived ADT, args and CHMH, rejected
12 negative cases, and recorded no old input modifications. Authentication
remains NOT REACHED. Executor acceptance is separate.

The fixed r7 kernel is 55,545,856 bytes, SHA256
`134d1a24ca32b91d3f41cfdf2d95831abdd4ec4c5be827e291970723d14ba0f5`.
The exact arguments are
`-v serial=3 nuwa-pmgr=2 native-ufs-probe=2 native-ufs-root=0`.
r7 `NativeUfs.cpp:108-114,159-165` parses both numeric values and requires
probe 2 and root zero. The independent legacy owner wrapper rejects *any*
`native-ufs-root=`; it was not modified or used. Official base
`scripts/unixnu/payload.py:56-73` invokes its sheng-pmgr/symbol gate only
when root contains `1`; root 0 does not satisfy that condition. No gate,
symbol or VM was changed.

Output `out/nuwa-ufs-hc-chmh-20261113-r1/`:

* FAT `payload.img` (67,108,864 B): SHA256 `48b463403dffe1cb82c11becc0f6f2e8ba83a4f1c269aea33b97370065471475`.
* Outer `vendor_boot.img`: SHA256 `6e150640b3780bcd2bc890d007619eecce2ce2fa6e511a451803556c01c54227`.
* `record.json`: SHA256 `46644bdb2306c22e22fa03e713c0efb824ea5b8e6b6ae0de500bd0acbfe6e41f`;
  record path is resolved against the device repository, not the process cwd.
* Derived ADT SHA256 `58ffccb0f46e4cd47bca352341508e9daefcaed468fef85c9ff7f3ee814a3ea7`.
  CHMH is `c2b2aa90d7814beb884c17f9bd19727476b9fa3267bb82847e76419e96f15cbeefff1a8e5bed8120e02878d34a45ed29`.
  Material binds this kernel, fixed r4 loader, trust, complete args and parent ADT.
  Derivation permits only CHMH and rejects ASMB. Authentication NOT REACHED.
* `outer-audit/outer-readback/EFI/UniXNU/` contains the actual four extracted
  members; their hashes and actual config are in `outer-record.json`. Trust
  SHA256 `367e051548f9f0407fa9fe9d40007fa4e7c5ff27c45f5a7a30cedf344e24d98e`;
  config SHA256 `30984f0efac472a095e551084c799487537c596db4ba1eeef13c47ab56d4cf81`.
  `layout.json` reports Mach-O VM span 71,561,216 B, used 71,663,616 B and
  1,002,078,208 B remaining inside the 1 GiB window after loader guard. Actual
  allocation base is not captured. Outer capacity is 100,663,296 B.
* Stock template SHA256 `5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23`
  is distinct from backup `493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`.

Reuse: local `wh1stl3/UniXNU-nuwa` base commit
`029a79bb58a403c0f3441ed991ad312ae1102c39` plus uncommitted
`scripts/build-pmgr-mode2-chmh.py`, source SHA256
`3173f69350086a562ffae20e4d1d4d9586c37bfd9a0b022bc3a1e8e6420f7774`;
no third-party code added. Official base `UniXNU` commit
`693f5d9cae8a408dd18b39f3f9fdc4228c934241`; licensing follows the
existing local repositories. The helper is imported unchanged, not AST-edited.
Pins for reconstructed FAT and record are derived from fixed inputs before the
candidate audit. The helper's official outer command, cwd, exit and streams
are in `official-command.json`. From device-repository root in WSL:

```
python3 -B scripts/build-hc-observe-chmh.py --output out/nuwa-ufs-hc-chmh-20261113-r1
python3 -B scripts/test-hc-observe-chmh.py
```

Both exited 0, self-checked. Tests validate the actual outer and reject profile,
kernel, args, probe 0/3, root 1, config, parent/derived ADT, material, record
and outer modifications. A fresh output directory is necessary to rerun build;
negative tests reserve a fresh `negative-tests` directory.

Observation contract: labels are `INIT_ENTER`, `INIT_RETURN`, `START_ENTER`,
`MAP_ATTEMPT` or `MAP_FAILED`, and four ordered `ATTEMPT` / `COMPLETED`
pairs followed by `HC_SNAPSHOT_DONE`; compare the on-screen bytes to the
actual r7 source. Screen publication requires video confirmation. Missing or
refused markers do not establish a hardware cause; the last attempt is not a
unique diagnosis. These four reads are not DMA or root operation. No executor,
device access, signature/policy operation or userdata write/verification ran;
the existing 8 GB userdata image is not part of this package.
