# Banner budget fallback — host only

Thread enumeration is deferred: this candidate does not provide the required
thread count or state counts, waiting categories, saved PC, wait_event or port
names. `nuwa-sb-dump=360` is inert in this fallback. No claim is made about
thread suspension or the behavior of a future dump interface.

The generated renderer limits its body to 24 rows or the number that fits,
including title and padding, in the lower half of the framebuffer. The existing
whole-banner height guard remains. The top half is not covered by this banner;
actual logo position is not independently established. Displayed text is capped
at 80 columns; source text is not truncated. Actual rendered row count and
longest displayed line have not been measured on a device.

The original banner is built from the pinned r35l renderer using
`scripts/generate_r35_display_diag.py`. Geometry and process-census source
checks were self-checked. This is not independent verification or permission
for a device operation. Review is pending; independent verifier should rerun
both source checks, the documented r35l display build with `--mg-reset`, and
the repack/outer readback, CHMH, seed and FAT free-space checks.

## Host package — self-checked

UniXNU upstream main before and after build: `8542980d02b4d2cc5c32ee3542de1760b2562aac`.
Build output: `out/nuwa-banner-budget-20261123-build-r2/`; the first build
was stopped by an accidentally configured one-second timeout. Repack wrapper:
`out/nuwa-systemgroup-seed-20261122/repack-banner-budget.py`; output:
`out/nuwa-systemgroup-seed-20261122/vendor-boot-banner-budget/`.
The wrapper checks args relative to the pre-restart baseline; relative to
`74f5597` only `nuwa-sb-dump=360` was added. Outer-readback seed SHA-256:
`692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`.
Outer-readback FAT free space: 11,673,088 bytes.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `ee2df2410510e3143dd9358ae3ea4b2b501933fdcc0cb3a8e2933e80df8fc0ce` |
| Outer SHA-256 | `812a39d5f60f33b17e3f3068f507e15a60c387e0a587fcb98083dfb4ad6c8390` |
| CHMH SHA-384 | `21d4196c5671939ec4d258db3b8cab3865903584e76f17b37fb90fe7420e8c5a86304febe231d4d4e1f9f2e88af5212f` |
| Outer-readback FAT SHA-256 | `b4e45aaa022bda2923cf00c3ae6f595dc924754c8649a5df4ed3c8ccf70e3e36` |
