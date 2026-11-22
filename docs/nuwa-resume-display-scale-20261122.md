# Resume-only display scale host candidate

The parent reports that outer `426ad39ea6456daa3a9393b4ea43778d7f5087453f64781181eace2eefdaefb1`
omits `/chosen/display-scale` and that the FBS check traps when both scales
are zero. This consumer diagnosis is parent-reported, not independently
established here. The resume-only ADT derivation now appends the r35i
experimental u32 value 3, after rejecting an existing property and checking
that artwork-scale-factor is 3. The scale is not a panel measurement.

## Self-checked host result

The ON kernel was rebuilt with the rotation candidate parameters in
`nuwa-rotation-20261122.md`; its SHA-256 is byte-identical to the kernel
used for packaging. The package freshly recomputes CHMH. An independent
outer extraction by the packaging audit produced an ADT containing exactly
one `/chosen/display-scale`, flags 0, bytes `03000000`. Removing this one
entry and re-encoding produces the rotation outer-readback ADT byte-for-byte:
all other ADT properties including identity and window are unchanged.
The outer readback configuration also compares byte-identical to rotation.
`fsck.fat -vn` and `mdir` reported 11,898,368 bytes free (floor 8,388,608).

| Artifact | Digest |
| --- | --- |
| kernel SHA-256 | `0bf8950fba416b9537782df245c43f8099e0e10f7c93c6f2d3fc35e604f50e5a` |
| outer SHA-256 | `02850b20ceabd842aabd4c05090bc2ec9f42a672359ddb2cd936bac4842bd068` |
| outer-readback FAT SHA-256 | `56e39861cb3a2c83862bd9f000d439013a275e57c0ed73c0d1dffa378bda465f` |
| outer-readback ADT SHA-256 | `ae717c64726d95b0edddf6a3316edc897f2e8a61ca9d3c9c29db2e72f649ec2d` |
| CHMH SHA-384 | `223ded55e0cef5b18930f47e3b64a419f776ea5a402cdff0d4b4675735e4e6b799b45203f236d51f9b8cfc0896645b7b` |

Outputs: `out/nuwa-resume-display-scale-build-20261122/`,
`out/nuwa-resume-display-scale-package-r2-20261122/` and
`out/nuwa-resume-display-scale-audit-20261122/`. First packaging attempt as
the default WSL user failed at `build-nuwa-pmgr-kernel.py:24`: the historical
`/root/nuwa-pmap-ret-native-20261111/build-result.json` is root-only.
The fresh successful package and build used the documented root-owned WSL tree.
UniXNU upstream main was `8542980d02b4d2cc5c32ee3542de1760b2562aac`
before and after the build.

Reviewer and deep_reviewer re-review and independent verifier rerun are
pending; runtime, panel scale, and authentication are not established.
No device operation was performed.

## Verifier rerun

Use the build command in `nuwa-r35l-display-dsp-20261122-observation.md`
with `--mg-reset` and the rotation candidate options; use the package and
audit commands in `nuwa-mg-reset-20261122.md` with fresh output paths. Run
`fsck.fat -vn` and `mdir` on the audit's `actual-vendor-ramdisk.img`; parse
its `outer-readback/EFI/UniXNU/Payloads/kernel.macho.adt`, remove the single
chosen scale, and compare its encoded bytes against the rotation audit ADT.
Compare both `unixnu.toml` files and recompute SHA-384 over the record's
decoded `material_hex`.
