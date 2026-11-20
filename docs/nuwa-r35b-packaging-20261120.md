# r35b packaging — host only, self-checked

The independent entry pins the original r35 script, substitutes only the new
kernel path/hash and profile in memory, and executes its existing r14-derived
packaging and audits. Kernel size and r35 boot arguments remain unchanged.
The generic root packager has kernel arguments, but does not carry r35's seed,
ADT and record adaptations; r35 itself hardcodes the kernel. This entry uses
the original checkout's scripts and inputs, not a modified r35 script.

Before packaging, the r35 and r35b prelink manifests were compared. Their
donor hash, 28 component names, codeless components, KPI list, extents, and
original executable hashes are identical; neither component list contains
`com.apple.kec.Libm` or `IOMobileFramebufferFamily`. Bindings differ (52674
each), as do native and resulting kernel hashes. These are manifest comparisons,
not an independent per-instruction family or ABI audit.

The existing r14 `fixed` computes the digest from the selected kernel and
other inputs before deriving and checking the ADT; it does not reuse the old
digest. Existing root-policy, seed, FAT budget/readback and outer audits ran.
FAT and outer readback contain the new kernel and ADT. The retained build tag is
`nuwa-r35`. AVB authentication is not claimed; existing experimental CHMH is
not authenticated identity. Authentication remains NOT REACHED.

WSL Ubuntu-22.04 root, working directory this worktree:

```
/home/wh1stl3/.local/bin/python3.11 -B scripts/build-ufs-apfs-root-chmh-r35b.py --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/nuwa-ufs-apfs-root-chmh-20261120-r35b
/home/wh1stl3/.local/bin/python3.11 -B scripts/build-ufs-apfs-root-chmh-r35b.py --output /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/nuwa-r35b-package-audit-20261120 --audit /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/nuwa-ufs-apfs-root-chmh-20261120-r35b
```

Both returned zero. SHA-256 of selected outputs in the first output directory:

| File | SHA-256 |
| --- | --- |
| kernel.macho | ad7e70f7e615494c6162cec1a72610e119e897414bb89e4e038075244442da2f |
| derived.adt | 22a9e9f4bc13ccb4b3a020c1bc840e75b09c2e078bc15ce2e5323dd115e0cf3c |
| unixnu.toml | 1b0179e3c2ea83619ddedc4785b82aa517741494a2bb2f174b3ece1fde06b3f8 |
| payload.img | de26794988414ec4280fbe6937f86de5b6fd8868a0a69cc3d25c1f5fffb30afd |
| record.json | 47a92796caf7835e9c3b589e727a03805e1f28873cf45e0f58af010d3d5678fa |
| layout.json | 51f9d246c11ae4db9ca89c66bbe78ec28468e29e55c96309267b857356248c08 |
| provenance.json | fd160d32c3c62cb007b6879ac29c8264b929aa9a4b34aec383f1c6cbdce1bbda |
| vendor_boot.img | 3c5c2df89ff67341af3fdc4a40eef82467a7360389685f4303f241315ecc9388 |
| outer-record.json | a390b61c3f8e098a4c659dd039a146df42eeec0f48f9514ab5f1fdf743641980 |
| audit.json | 4ab4a39c80db1c49664efe3d6b8874f54fffb62f43df8915b7ac1a6fb588c65f |

New CHMH (SHA-384):
`9ea4853ca37f2e59310720d6803a30d39c2a74da60d12c30896d168ed80fafbe246969138120f6b1b512a3d6fc3be0be`.
Original r35 kernel and vendor_boot after the build match their recorded
hashes `787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464`
and `c6e64820cc46c1a54e65d3640994ad7acf0e7aa807dfd3765eac82f483a4a7ed`;
the entire old output directory was not compared.

No device action was performed. Boot-chain deep review and independent
verifier rerun remain pending; no device release or runtime claim.

The required porting-record check was attempted from the WSL UniXNU checkout
with `--device /mnt/d/Code/PortingiOS/nuwa/worktree-r35b-packaging --base
origin/main`. It stopped before checking records: WSL Git cannot resolve the
Windows `D:/...` gitdir in this linked worktree's `.git` file. Commit remains
blocked until the parent resolves that environment mismatch and reruns it.
