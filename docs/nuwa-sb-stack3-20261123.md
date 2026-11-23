# sb-stack arguments: restart probes removed (2026-11-23)

Host-only packaging change. The kernel, the CHMH rebind and the outer readback are
self-checked here; nothing was written to a device. Reviewer re-review is requested for
exactly one thing: the arguments below (and that the fail-safe defaults still hold).
Authentication **NOT REACHED**.

Branch `display/20h392-dsp-diag`, base `2e94473`.

## What changed relative to `2e94473`

The kernel binary is **bit-identical**; only the boot arguments changed. Comparing the
two packages' `outer-readback/.../unixnu.toml`, the sole difference is the removal of
two tokens:

```text
before: ... nuwa-mg-reset=1 nuwa-sb-restart=400 nuwa-sb-restart-every=180 nuwa-hid-standin=1 nuwa-sb-stack=360
after:  ... nuwa-mg-reset=1                                          nuwa-hid-standin=1 nuwa-sb-stack=360
```

That is a contiguous 46-byte removal (`" nuwa-sb-restart=400 nuwa-sb-restart-every=180"`),
checked byte for byte: the new config equals the old one with that substring deleted
exactly once, and the new token list equals the old list minus those two tokens.

Both arguments are simply **absent**, not set to `0`. The kernel's own parser
(`PE_parse_boot_argn("nuwa-sb-restart", …)` / `"nuwa-sb-restart-every"`) leaves its
zero initialisers when the arguments are missing, and zero is "off" there, so the
one-shot and periodic `psignal` paths stay disabled with exactly the same code path as
a build that never had the probe.

**Reason:** this run is to let the system keep running undisturbed and see what happens
after 360 s. A periodic `SIGKILL` of `SpringBoard` cancels any progress the run is
trying to observe, so the restart probes must not fire at all.

Everything else is unchanged: `nuwa-hid-standin=1`, `nuwa-sb-stack=360`,
`nuwa-mg-reset=1`, `sheng-data-persist=2`, `nuwa-lite=1`, `boot-progress=2`, the eight
`offline-*` tokens, no `sheng-data-reset`, `/chosen/display-scale` `03000000`,
`/chosen/text-fixups` absent, seed unchanged.

## Arguments (extracted from the new `vendor_boot.img`)

```text
-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1 build-tag=nuwa-r35 boot-progress-scale=3 sheng-data-persist=2 sheng-log-reserve=1024 offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1 offline-legacy-transfer=1 offline-legacy-cpu-present=1 nuwa-lite=1 nuwa-mg-reset=1 nuwa-hid-standin=1 nuwa-sb-stack=360
```

**507 bytes, 26 tokens**, SHA-256
`58dc839e9a1a06528ed53304a594d1732cbe85da533af2bb48a51662dabf0d5e`.

## Extraction evidence

Read straight from `vendor_boot.img` (the FAT is sliced out of the image at
`page_size=4096`, length `67108864`, and the members are copied out with `mtools`; the
ADT is parsed with the repository's own ADT module, not with a re-derived tree):

| Check | Result |
| --- | --- |
| `vendor_boot.img` | 100,663,296 B, SHA-256 `2335fd6c79965698f8e89eaa1cd1980f557b85ef6465037e0ab0d826cd85b492` |
| `xnu` args | 507 B, 26 tokens, full text above; no token whose key starts with `nuwa-sb-restart`; no `sheng-data-reset` |
| `/chosen/display-scale` | `03000000` |
| `/chosen/text-fixups` | **absent** (22 `/chosen` properties, none named `text-fixups`) |
| embedded seed `Payloads/scratch-data.img` | 2,121,888 B, SHA-256 `692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247` |
| `/chosen/boot-manifest-hash` | `9bc2b45259ff246b7d64b8795fade88481dffe6e0d1c368f40391b38d3f343b2ca2da92031e8aa360b01edfab338cc28` |

The packager's own `--audit` re-extraction of the package agrees: `outer_sha256`
`2335fd6c…` , `ramdisk_sha256` `1085973c…`, member kernel `64a97b23…`,
`avb_authentication_claimed: false`, status `self-checked`.

## Results

Kernel reused bit for bit from the `2e94473` build (`out/nuwa-sb-stack2-20261123-build`):
boot arguments are not compiled into the kernel, so rebuilding would only introduce
noise. The CHMH and the outer necessarily change because the arguments are part of the
manifest.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 (52,187,136 B) | `64a97b23eb26870f05e57173f507fd2724e5f2afbd1785da634543becf8b5e35` |
| Outer SHA-256 | `2335fd6c79965698f8e89eaa1cd1980f557b85ef6465037e0ab0d826cd85b492` |
| CHMH SHA-384 | `9bc2b45259ff246b7d64b8795fade88481dffe6e0d1c368f40391b38d3f343b2ca2da92031e8aa360b01edfab338cc28` |
| Outer-readback FAT SHA-256 | `1085973cf15071ef6955c1848395b254be85da62145dd6d126f5bccc87462383` |

`fsck.fat -vn`: 9 files, 106,239 of 129,022 clusters; `mdir`: **11,664,896 B free**
(above 8 MiB). `payload.img` and `outer-audit/actual-vendor-ramdisk.img` both hash to
the FAT value. Product:
`out/nuwa-systemgroup-seed-20261122/vendor-boot-sb-stack3/vendor_boot.img`.

## What the reviewer must check

1. The 46-byte argument removal is the only difference from `2e94473` (byte-level
   comparison is in `out/nuwa-systemgroup-seed-20261122/repack-sb-stack3.py`).
2. The fail-safe still holds with the arguments absent: `nuwa-sb-restart*` stay at their
   zero initialisers, so no one-shot and no periodic signal is issued, and
   `nuwa-sb-stack=360` is unaffected by their absence.
3. Nothing else in the payload depends on those two tokens.

Independent verifier should rerun `repack-sb-stack3.py` with fresh paths (it pins the
baseline outer, the kernel, the seed and the exact argument transformation), then repeat
the extraction checks above, `fsck.fat -vn`, `mdir` and the CHMH comparison. Device
behaviour remains unobserved; the stackshot probe itself is unchanged from
`docs/nuwa-sb-stack-20261123.md`.
