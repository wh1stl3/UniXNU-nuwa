# IconServices candidate disable and PEER probe — 2026-11-25

Host-only work, **self-checked**; independent verifier and deep review pending.
No device access or flash. Disabling this candidate is an experiment, not
proof that the sampled lsd connection targets it or that authentication works.

## Domain and process identity

The OS window of `userdata-root.img` was mounted read-only with apfs-fuse.
`/System/Library/LaunchDaemons/com.apple.iconservices.iconservicesagent.plist`
is a system-domain LaunchDaemon. Its decoded values:

```xml
<key>Label</key><string>com.apple.iconservices.iconservicesagent</string>
<key>UserName</key><string>_iconservices</string>
<key>MachServices</key><dict><key>com.apple.iconservices</key><true/></dict>
<key>RunAtLoad</key><false/>
<key>ProgramArguments</key><array><string>/System/Library/CoreServices/iconservicesagent</string></array>
```

`LimitLoadToSessionType` is absent. The chosen system-domain override is
`/private/var/db/com.apple.xpc.launchd/disabled.plist`, not the per-user
`disabled.501.plist`. This is an on-demand job. A matching service string in
the candidate agent is not proof of the specific sampled XPC connection.

XNU 8796 source under
`UniXNU/out/nuwa/ios-16.7.16-20H392/nuwa/tree/.cache/xnu-work`:

```c
// bsd/sys/param.h:95
#define MAXCOMLEN       16              /* max command name remembered */
// bsd/sys/proc.h:150
char    p_comm[MAXCOMLEN + 1];
// bsd/kern/kern_exec.c:917-923
if (imgp->ip_ndp->ni_cnd.cn_namelen > MAXCOMLEN) {
        imgp->ip_ndp->ni_cnd.cn_namelen = MAXCOMLEN;
}
bcopy((caddr_t)imgp->ip_ndp->ni_cnd.cn_nameptr, (caddr_t)p->p_comm,
    (unsigned)imgp->ip_ndp->ni_cnd.cn_namelen);
p->p_comm[imgp->ip_ndp->ni_cnd.cn_namelen] = '\0';
// bsd/kern/kern_proc.c:1303-1305
if ((p = proc_find(pid)) != PROC_NULL) {
        strlcpy(buf, &p->p_comm[0], size);
        proc_rele(p);
```

The exact 16-byte command is `iconservicesagen` followed by NUL. The existing
`containermanagerd` comparison is `containermanager` (also 16 bytes).

## Seed and probe

The source is `out/seed-full-20261125/seed-edited.raw`, 8,589,934,592 bytes,
SHA-256 `203a34d1c0bf3c82ec0a5b1f7d4864f2afb65aec3f5291af8b4bf909acb0bbfc`,
from `out/seed-full-20261125/HANDOFF.txt`: 8 earlier directories plus 30
new directories. The HANDOFF's source encoded seed SHA-256 is
`c6688cd179c4af965c825fb6bb31b0f71c0c48802e97efe11079e1ccb7043081`.
The two `lsd.iconscache` and `mobilegestaltcache` Library/Caches directories
have ownership 501:501 instead of the specified 0:0; this follows their
existing parents and is not asserted equivalent to the requested ownership.

After HANDOFF, the same-hash VM raw was copied to a distinct file and edited.
`disabled.plist` was absent: before size 0, keys `[]`; after size 90,
keys `["com.apple.iconservices.iconservicesagent"]`, Boolean value `true`.
The binary plist was read back under a read-only VM mount; `fsck_apfs -n`
reported the volume and container OK. Modified raw SHA-256:
`26957263676b0312f3bebe213c2985deb8ce5652ac2ce3e99d59da77aba89584`.
The `.fseventsd/no_log` marker was created then removed; APFS metadata and
mount side effects are not asserted unchanged.

## Final package and readback

The only final deliverable is
`out/nuwa-final-20261125-package/vendor_boot.img`:

| Artifact | Bytes | Digest |
|---|---:|---|
| kernel, SHA-256 | 52,203,520 | `44158f0fea54fc54b48c243aed864ec7567e5c566bafb4bdaeaad1e11184cc94` |
| outer, SHA-256 | 100,663,296 | `01ffdf9b607e1acfbe91867ad5d7a38fec32ea388fd273bf43443939ec13ac5d` |
| CHMH, SHA-384 | 48 | `4c918c49a6f5d3b000b128bd6dffe86b3ee764e1532e58a548d426b57b764bd70f6d86095f1600539b5cefd479a91a1f` |
| outer-readback FAT, SHA-256 | 67,108,864 | `77b48ae0fbb9956d04e10c4096265a469dce8cef113de8c92c07a8b1750dff84` |
| encoded seed, SHA-256 | 2,744,480 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

The previously generated diagnostic staging FAT supplied the already-bound
kernel and CHMH; the seed was replaced before creating the sole final outer.
The 507-byte args compare byte-for-byte to the rollback outer. The pure-Python
FAT/ADT audit checked required and forbidden args, `display-scale=03000000`,
absent `text-fixups`, seed hash and all FAT files against staging; only seed
content differed. FAT free space is **11,025,920 bytes** by Python and `mdir`;
`fsck.fat -vn` returned zero. The Python FAT reader extracted the actual seed
from the final outer; the official Python `regions()` decoded its eight
extents and `cmp` matched the edited 8 GiB raw byte-for-byte. That decoded raw
was mounted using `apfs-fuse -o ro` (`findmnt` confirmed `ro`); Python
`plistlib` read the 90-byte binary plist and confirmed the sole label maps to
Boolean `true`. APFS reading itself used FUSE, not a pure-Python APFS parser.

For an independent verifier, rerun `python3 tests/test-nuwa-peer-probe.py`,
the four `scripts/test-sb-stack-*.py` and `test-banner-*.py` tests named
below, the three linked tests against the final kernel, and
`python3 -B out/seed-full-20261125/final-audit.py`, `fsck.fat -vn` and `mdir`
on the outer-readback FAT. Extract and decode the seed from the final FAT
again, then independently mount that decoded raw read-only and read the plist.
Rebuild and packaging should use fresh output paths; the local helper scripts
and source images under `out/` are ignored host artifacts, not Git evidence.

The existing process census gained an exact-match PID slot; the other three
PIDs reuse existing census slots. The slots are independent best-effort atomic
samples, not an instantaneous coherent census. Stackshot target, time,
flags, 1 MiB buffer and T0 continuation priority were not changed.

Host fixture output (the formatter and selector are compiled from the generator):

```text
PEER icon=4096 cm=4095 lsd=4094 SB=4093
PEER icon=- cm=55 lsd=- SB=88
PEER icon=- cm=- lsd=- SB=-
```

The fixture checks the 78-column bound and required rows against a 24-row
budget. Smaller runtime geometry or a larger priority-0 population is not
proved to retain every row.

The host checks ran `python3 tests/test-nuwa-peer-probe.py`, the existing
`test-sb-stack-row`, `test-sb-stack-paint`, `test-banner-budget` and
`test-banner-short-values` scripts, plus linked r35g UX, r35k registers and
r35e IRQ-guard checks against the candidate kernel. The new fixture includes
the generated census and checks that the untruncated 17-character agent
name does not match. The kernel was built with `taskset -c 0` and
`MAKEFLAGS=-j1`; upstream UniXNU HEAD before and after the build was
`8542980d02b4d2cc5c32ee3542de1760b2562aac` and was not adopted.

## Interpretation for a future authorized run

| Observation | Record as |
|---|---|
| `PEER icon=-` and later-stage evidence | Candidate absent in the census and later progress observed; correlation, not proof of causation. |
| `PEER icon=-` and same lsd stack | Candidate absent in the census; unchanged sampled wait, not proof of a particular peer. |
| `PEER icon=<pid>` | Candidate present; disabling did not establish absence, investigate domain and effective configuration. |
| lsd absent and no later-stage evidence | Inconclusive; neither progress nor resolution established. |

The census only scans PID 1–4096 and can race process lifecycle. A `-` is not
proof of global absence. Rollback outer SHA-256:
`d8d57a241bfbda143b0d6b007a95da7ede1e18ffdc61ad79108f3d5e9e9d1ed6`.
