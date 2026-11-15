# Fixed pthread CHMH FAT and outer — self-checked

Update: parent reports ordinary review PASS and independent verifier PASS:
fresh outer/FAT match, 21 negatives, audit-r2 actual four members/zero padding,
AST 2/2, bounded whitespace and correct-base record check. Evidence:
`out/pthread-chmh-verifier-20261112-r1/audit-r2/audit.json`. This is not a
device or authentication result. Its legacy `members_sha256.parent-adt` key
names the **derived** FAT ADT `4099834dedf4e3ee0b20bc9bbbedf7ad1402d1cdd70afe0ddf7c7adf1e40dfe8`,
not the separate parent ADT `885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4`.

Parent reports renderer ordinary review PASS and independent rebuild/audit PASS
for `out/pthread-renderer-verifier-20261112/renderer-baseline.macho`, 55390208 B,
SHA256 `e0c235f1de499c858d6eb672f989de7692f1d97140e1064da59391642fa11f5d`.
Prior pthread prelink `8ffb9f381cebfbfc56dd210901a9b7533b51cc3b95fba0719f4cd2b3972e3f6d`
metadata and 95 bindings were independently checked. Runtime registration is
not proven. Parent reports official upstream HEAD `0e2fb2bc…` for this stage;
no merge, pin change or network lookup was performed here.

Distinct profile `pthread-chmh-only-20261112-r1` leaves old `7fd3…` profile
and record unchanged. The existing reviewed domain/material helper hashes the
new kernel, r4 `692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5`,
trust `367e051548f9f0407fa9fe9d40007fa4e7c5ff27c45f5a7a30cedf344e24d98e`,
args `-v serial=3`, and original parent ADT
`885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4`.
SHA384 CHMH is `e864dc22f22aab99007526d1c02a1f80210dd954c2ca27caefc250f0c5db588d2cf90c4cee5e82a859cd8327835bb6a8`.
It is experimental and unauthenticated, not Apple authentication. The ADT is
exactly parent plus the unique raw 48-byte CHMH, preserving AMNM0, BNCH,
random seed and every other property/order/flag; ASMB is rejected.

Artifacts, local `out/pthread-chmh-20261112-r4/`:

| File | Bytes | SHA256 |
| --- | ---: | --- |
| `kernel.macho` | 55390208 | `e0c235f1de499c858d6eb672f989de7692f1d97140e1064da59391642fa11f5d` |
| `derived.adt` | 13340 | `4099834dedf4e3ee0b20bc9bbbedf7ad1402d1cdd70afe0ddf7c7adf1e40dfe8` |
| `payload.img` | 67108864 | `d2f48bf3244d9571375fcd2b9aaff4a8814935ae6d48bad05b5faf2dc1f9a07b` |
| `vendor_boot.img` | 100663296 | `175258a62cc9543cb2a7387d0b3a1312eeab5fd7443d1614b0038f2928f8ff3a` |
| `record.json` | 3561 | `8c8009146e8d4d0a4abe2caa85f6db9251d847faab2c5928611a2bf7366318df` |
| `layout.json` | 1044 | `a685229f79cb5350a07440e1f005d168bc89173158277baed614f02fe97a18f2` |
| `audit.json` | 1489 | `22715fde9c453deee09598e3ef3652a123a1c228af4b1b988fc5e3ac9ec1398b` |

The new kernel and ADT are both actually replaced in the FAT. Audit reconstructs
that FAT from the fixed parent and separately extracts all four actual outer
ramdisk members, validating content, derived record, config and ADT. It uses
the prior official outer compare for stock fields, capacity, padding and AVB
footer retarget (not authentication). Template `5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23`
and original backup `493ca426964adabb195a00ded4ff49793bc7efd5d7bea2a567bcfd0c970a8dad`
are separate, checked 100663296-byte inputs.

Relative layout is recomputed from the actual kernel: VM span/args `0x43f0000`,
ADT `0x43f1000`, trust `0x43f5000`, used `0x4408000` <= `0x3fe00000`.
Actual W, live stack/GOP and runtime mappings are not proven; the 2 MiB guard
is not a proven stack reservation.

WSL Ubuntu-22.04 root, cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`:

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/build-pthread-chmh.py --output out/pthread-chmh-20261112-r4
/home/wh1stl3/.local/bin/python3.11 -B scripts/build-pthread-chmh.py --audit out/pthread-chmh-20261112-r4 --output out/pthread-chmh-audit-20261112-r2
/home/wh1stl3/.local/bin/python3.11 -B scripts/test-pthread-chmh.py --candidate out/pthread-chmh-20261112-r4 --output out/pthread-chmh-tests-20261112-r2
```

All three exited 0; official `vendor_boot` argv/cwd/exit are in
`official-command.json`. Actual-outer positive, relative selected-record path
and 21 targeted rejection cases are recorded in `tests.json`, including old/new
kernel, profile, record/hash/path, material, ADT/ASMB, args, template/backup
confusion and synchronized outer/report tamper. Independent verifier must rerun
all commands into fresh directories; this is self-checked, not accepted.

First `out/pthread-chmh-20261112-r1` build exited 1 at FAT reconstruction:
`mcopy` used wall-clock directory timestamps (four bytes differed). It was
preserved, not overwritten. r2 added parent timestamp restoration for both
unique directory entries and succeeded; r3 added strict input/evidence gates;
r4 adds fixed selected ADT/FAT/record hash gates. No executor, device,
native rebuild, commit or push occurred.

Self-check: both new Python files compiled in memory; `git diff --check` exited
0. For the three new untracked files, `git diff --no-index --check /dev/null
<file>` each returned 1 (different files) with empty diagnostics; a Python
wrapper checked those statuses and exited 0. The first PowerShell-embedded loop
had expanded its shell variables and did not check the intended files. The
record check from `/mnt/d/Code/PortingiOS/UniXNU` exited 0, 14 areas:

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/porting-record.py check --device /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa --base origin/feat/step7-kernel-patches-8796
```
