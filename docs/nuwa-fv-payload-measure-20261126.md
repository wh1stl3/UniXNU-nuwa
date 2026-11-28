# nuwa FV payload size measurement — 2026-11-26

Host-only, self-checked; no firmware build, FV repack or device operation.

The source is `out/nuwa-disposable-data-package-r2/`: the outer SHA-256 is
`6695da9842f4da4d26c1f028adc48f3ffb8f6f369420653492028a74bf362fa5`;
the audited readback FAT SHA-256 is
`087c692478cd3060f34b62d3eb9575bde8f045816eccac52aa74edc51da5ab52`.
The existing `audit.json` identifies the following three changed files.
They were extracted directly from that FAT with `mcopy`:

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| `EFI/UniXNU/Payloads/kernel.macho` | 52,207,616 | `28e87a12b55067d442c2a7bd1de5a9e4a5790057464f3e40282398903f48cc34` |
| `EFI/UniXNU/Payloads/kernel.macho.adt` | 13,680 | `09ffbcc58c2c4fde573f32fde4eb4d83940cbaafd59c8f3e4eca445dbbc4f43c` |
| `EFI/UniXNU/unixnu.toml` | 1,030 | `f088b9eff558b8e48a3c31e1fec698ff5cda56f0ff09170a2c525ddc227e6dec` |

`uefi-nuwa/Platforms/Xiaomi/nuwaPkg/nuwa.fdf` uses GUIDED
`EE4E5898-3914-4259-9D6E-DC7BD79403CF`; the existing build's
`GuidedSectionTools.txt` maps it to `LzmaCompress`. Concatenate the three
files in the table order and run the existing nuwa host build tool
`~/nuwa-fw/mu_basecore/BaseTools/Source/C/bin/LzmaCompress -e -o payload.lzma payload.concat`,
with no tuning flags. Tool SHA-256:
`06f02d72b2de0ed82b881f1f5617af6ce6ade9e71f6d988aae289b9fb021ed98`.
The encoded header is `5d 00 00 00 01 76 d9 1c 03 00 00 00 00`
(LZMA properties lc=3, lp=0, pb=2, dictionary 16 MiB and original size
52,222,326). Decoding with the same tool and `cmp` reproduced the input.
Local files are under `out/nuwa-fv-payload-measure-20261126/`.

The 52,222,326-byte concatenation compressed to **5,970,182 bytes**, SHA-256
`1ba4ebab978664609a32c35c8b139200d7f1c9100e142bfd18d2ccb06186d16c`.
Against the supplied 0x300000 FD remaining capacity of 1,756,072 bytes,
this standalone result exceeds the capacity by **4,214,110 bytes** (3.40x).
The supplied capacity was not independently recalculated here.

This is one standalone compressed concatenation, **not** the actual incremental
size of a repacked FV: adding FFS/section framing, compression alongside the
existing FV contents and changed alignment can alter the result. No such repack
was performed. The large excess is evidence against fitting this actual payload
by the measured standalone LZMA route, not a mathematical proof of every
possible shared-stream FV layout or a claim about omitted payload files.
