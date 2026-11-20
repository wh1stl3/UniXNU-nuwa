# FAT capacity correction and ON outer pin — self-checked

The previous `fat_clusters()` counted non-data sectors as FAT entries.
It reported 65,536 B too much free in each fixed FAT. The 8 MiB
minimum is unchanged. The original r35 OFF package's real free space is
below that minimum; this is a pre-existing image fact, not a regression
introduced by this correction. OFF is **rejected**, not repacked or released.

| Fixed FAT | Old free | Correct free | Difference vs 8 MiB | Correct result |
| --- | ---: | ---: | ---: | --- |
| split-off / original r35 | 8,420,864 B | 8,355,328 B | −33,280 B | FAIL |
| split-on | 11,996,672 B | 11,931,136 B | +3,542,528 B | PASS |

FAT BPB: 512 B per sector/cluster, 131,072 total sectors, 32 reserved
sectors, 2 FATs of 1,009 sectors. Data starts at sector 2,050;
`N=(131072-32-2*1009)/1=129022` data clusters, numbered 2..129023
inclusive. The corrected loop scans precisely this range. The
`fsck.fat -vn` read-only walk of directory chains also checked for unused
clusters and the free cluster summary; FSInfo separately agrees.

WSL root, working directory device checkout:

```text
$ /home/wh1stl3/.local/bin/python3.11 -B scripts/test-r35-display-fat.py
off: clusters=129022 used=112703 FSInfo=16319 old=8420864 corrected=8355328 threshold=FAIL
on: clusters=129022 used=105719 FSInfo=23303 old=11996672 corrected=11931136 threshold=PASS
on outer SHA256=09d11016b7710a29f8aba936fe397aae79bf7ec01cef5ef27b760ec37b967efa; outer readback FAT SHA256=3d8ed2bd8009d704c570adda524aa3b378165c243feb61d044fda66a4a620664
```

The test invokes `fsck.fat -vn out/nuwa-r35-display-split-{off,on}/payload.img`
individually and compares its used/total cluster output with the scanner and
FSInfo. For ON, it also hashes the actual outer image and the FAT extracted
from it. The `mdir -i out/nuwa-r35-display-split-on/payload.img -/ ::`
read-only directory listing reported `11 931 136 bytes free`. No FAT image
or kernel was rewritten.

Both fixed packages were also audited through the real corrected packager:

```bash
PY=/home/wh1stl3/.local/bin/python3.11
S=scripts/build-ufs-apfs-root-chmh-r35-display.py
"$PY" -B "$S" --kernel out/nuwa-r35-display-budget-compact/kernel.macho \
  --kernel-sha256 89355aa4e0dc0f3d2e9ef1971e94d45f6584f66d4ae318e6ac2bdc832fce4b39 \
  --enable-display --output out/nuwa-r35-display-fat-fixed-on \
  --audit out/nuwa-r35-display-split-on
"$PY" -B "$S" --kernel out/nuwa-r35-20261119/kernel.macho \
  --kernel-sha256 787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464 \
  --output out/nuwa-r35-display-fat-fixed-off --audit out/nuwa-r35-display-split-off
```

The ON command exited 0; extracted FAT hash was the value above and
`audit.json` SHA-256 was
`40549bc2b80e752079124960f7e64e55e0d62a331942c68c2d43a02edf86ce5a`.
The OFF command exited 1 at `verify_fat` with
`ValueError: FAT free space below 8 MiB`. Output directories shown are
existing: use new names on rerun.

## Release identity and limits

**Pinned ON outer SHA-256**:
`09d11016b7710a29f8aba936fe397aae79bf7ec01cef5ef27b760ec37b967efa`.
The complete image and retained audit agree. The previously relayed suffix
`efa0` was incorrect; `7efa` is the correct ending. This pin and the FAT
check are host-side identity and capacity checks, not authentication or
device release. The original r35 OFF image remains unchanged and is not a
valid fallback under the corrected 8 MiB gate. ON awaits the required
independent reviewer and verifier rerun, as well as explicit device
authorization; 329 remains an expected diagnostic panic if reached.
Authentication remains NOT REACHED.

The r35 packager and its display wrapper pin the corrected r14 source.
Older historical r16–r34 wrappers and the historical executor retain their
original r14 source pin; they fail closed against the corrected file until
separately updated and requalified. No historical profile or executor pin
was silently repointed.
