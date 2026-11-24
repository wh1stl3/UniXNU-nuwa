# lsd stackshot — host candidate, 2026-11-24

Based on `2b56562f7d27f7548fee9cdfff2f1da74b068d20`: only the
stackshot target changes from SpringBoard to exact `lsd` p_comm, with the
summary labelled `SHOT lsd`. The census, capture mechanism and parsing
logic are unchanged. `sb` is now the **lsd main binary** first LOADINFO64
load address, not SpringBoard's. Details and presence semantics remain in
`nuwa-sb-stack-detail-20261124.md`.

Flags remain KCDATA_FORMAT|TRYLOCK|SAVE_LOADINFO, buffer 1 MiB, and
`nuwa-sb-stack=360`. SHOT*/T* remain temporary priority 0. Success uses
five rows, optionally six with SHOT2; an error uses one. `r=` and presence
bits are unchanged. Pending remains `SHOT pending <seq>`. Example:

```
SHOT lsd n=2 w=2 r=0 ks=23456789 sc=31323334 sb=04123000
T0 C=fffffff00700cafe U=104123450,18123abcd,192340008,11234000c f=5!
T1 K=f007123456,f007abcdef U=104dead00,104dead04 f=2!
T2 -
T3 -
```

Host fixtures measured summary 42–59 columns, thread rows 4–78, SHOT2
31–65, and r=52 error 36. Maximum measured width 78; physical panel not
observed. Build, tests and package readback are self-checked; no device
access. Authentication NOT REACHED.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `ed31ea23b4d65458c2ceac63af93398eabc498f8bc8907da6772f4e173c0f397` |
| Outer SHA-256 | `92494535a871f8406606cd711e2a8d76a01eb82a53ccc6365d2fa0fedb4157dc` |
| CHMH SHA-384 | `4ec26976a9fdf3123c844325d949199f044ef6b71964a7383cb09a8e5133fa3d65b67afd892134f835411303ac9020ca` |
| Readback FAT SHA-256 | `adc6d441672a81db0c7ca5a7de06ff05bc6252f8c792d8c4427ea16aabaf229d` |

Outer readback FAT is 67,108,864 bytes with 11,648,512 bytes free;
`fsck.fat -vn` and `mdir` ran. Seed SHA-256
`692355638b31d347ced5983a5910491f0556156f79675c2e371ebe9987683247`
is unchanged. Repack audit checked the 507-byte args against the baseline
byte-for-byte, SHA-256 `58dc839e9a1a06528ed53304a594d1732cbe85da533af2bb48a51662dabf0d5e`;
includes `nuwa-hid-standin=1`, `nuwa-sb-stack=360`, no sheng-smp,
restart or sheng-data-reset. Upstream UniXNU main before and after build
`8542980d02b4d2cc5c32ee3542de1760b2562aac`, not adopted.

Package: `out/nuwa-lsd-stack-20261124-package/vendor_boot.img`.
Verifier: rerun the commands in `nuwa-sb-stack-detail-20261124.md` with
fresh output paths and this kernel SHA, then `fsck.fat -vn` and `mdir`
on the new audit's `actual-vendor-ramdisk.img`. The executed build used
the same flags as that record and output `out/nuwa-lsd-stack-20261124-build2`.
