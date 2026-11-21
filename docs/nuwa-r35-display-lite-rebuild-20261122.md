# Display ON lite watchdog rebuild — host self-checked

The historical replay kernel did not contain `nuwa-lite`. The r35l ON builder
was changed to replay the recorded `compile-nuwa_watchdog_policy` command with
the current source and a replacement object in the filelist, leaving the
historical control link intact. No compile flags were added or removed.

First attempt, WSL root, `/home/wh1stl3/.local/bin/python3.11`, fresh output
`out/nuwa-r35l-dsp-ioservice-lite-r2-20261122`: compilation stopped at
`package/nuwa-watchdog/nuwa_watchdog_policy.c:80:13`, undeclared `strstr`
under the recorded kernel headers and flags. Full local log:
`out/nuwa-r35l-dsp-ioservice-lite-r2-20261122.log`. No replacement object,
new kernel or package resulted from this attempt.

The policy now uses the existing kernel libkern header and `strnstr` bounded
by the remaining policy buffer; the host policy test uses a bounded host shim.
The same recorded compile arguments then built the replacement. `watchdog-inputs.json`
records source SHA256 `c8bebb6929baa0287e707528c9600f20abd0473fb82e9bad222aaeb76f7e99d0`,
old object `9f658f687761a8b1a460128b9bf46ad09f16e34482b8e1d4d78ffec6b1885a80`,
new object `bfdb909d864a688a98b24657d99633931b8ad2f9f09f960c4d2f610134a37050`.

The fresh `out/nuwa-r35l-dsp-ioservice-lite-r3-20261122` kernel SHA256 is
`d33ef2ccf95478959ada320174f19203d0d7d6d17077ac60e69a00efbda6dfc5`.
The bytes `nuwa-lite` occur once at file offset `0x133781`; this is not
runtime proof. Host policy cases and historical control replay succeeded.

ON packaging and the second `--audit` readback were self-checked:

* outer SHA256 `97804a3b179c51d5d9cc3a7b24c15d5a74431fdfd8c0ef02fd0f49c6315819f8`
* FAT SHA256 `e0a8d2d19e11154989f1d9f30bfd9032648e6e5a33968591faab6ecd8a748cb5`
* CHMH SHA384 `b578b452f168402909f92891c3258b341d8a6446b46d30402925369dbbacc37d2b180bcc305eb25cfe67f4d4960af17a`
* extracted FAT `fsck.fat -vn` succeeded; `mdir` reports 11,931,136 bytes free.
* extracted `unixnu.toml` contains the eight offline arguments and `nuwa-lite=1`,
  with no `sheng-lite`; `--audit` checked the outer, members and CHMH binding.

The ON args also retain the existing `sheng-data-*` arguments. Artifacts and
logs remain under `out/`. No device operation was performed. Pre-initproc and
display changes need deep review; independent verifier and runtime remain pending.
