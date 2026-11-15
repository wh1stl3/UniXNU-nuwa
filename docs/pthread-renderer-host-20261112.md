# Pthread prelink, renderer-only — self-checked

Parent reports the input pthread prelink passed ordinary review with conditions
and independent verifier r4 reproduced `8ffb9f381cebfbfc56dd210901a9b7533b51cc3b95fba0719f4cd2b3972e3f6d` / 55390208 B. Normal OSKext
lifecycle is statically closed, not runtime-proven. The prior reviewer passed a
1324 pc-relative inventory; this run did not repeat it. Full ABI is unqualified,
not a newly demonstrated blocker.

This separate, exact-input profile uses the original renderer/no-reset recipe;
it does not relax the old profile or bind PMAP/observer stop branches. Reused
native SHA256 `4a5bf5cc4f6920409b09fdf11eea21389b52b490e247515ab07ffdd38a7f8aa2`
and map SHA256 `25c892e8a167c448bb1d24853c0420b09b716361f110b17960c90ffcf2ccb460`.
The new image was parsed afresh: object/source/map prove the zero padding after
entry; the full span is file-backed `__TEXT_EXEC,__text`, RX/RX. Symbols,
original instruction bytes, unique SCTLR sequence, branch reach, writable-data
guard and ELF renderer addresses are checked on this image. No Mach-O expansion.

Output `out/pthread-renderer-20261112-r1/renderer-baseline.macho`: 55390208 B,
SHA256 `e0c235f1de499c858d6eb672f989de7692f1d97140e1064da59391642fa11f5d`.
`renderer-manifest.json` SHA256 `96848990e8ff2f6022020be8ab29ac069f557acc941d8b206155cf1c52e682f2`
contains full before/after bytes, source bindings, symbol/layout and tool hashes.
`audit.json` SHA256 `87058eeb866907574167433a0396aa15a9679a36238c82e04d4a9014e7ff9bda`
contains all 301 contiguous changed-byte runs (2321 changed bytes), CFG and
pointer checks. Both artifacts stay under `out/`.

| Patch | VA | file offset | bytes |
| --- | --- | --- | ---: |
| entry bar | `0xfffffff0073f2500` | `0x3ee500` | 64 |
| entry hook | `0xfffffff0073f2488` | `0x3ee488` | 4 |
| MMU bar | `0xfffffff0073f2560` | `0x3ee560` | 68 |
| MMU hook | `0xfffffff0073f4350` | `0x3f0350` | 4 |
| renderer | `0xfffffff0073f25c0` | `0x3ee5c0` | 2607 |
| `_panic` hook | `0xfffffff0079918c8` | `0x98d8c8` | 4 |
| `_panic_trap_to_debugger` hook | `0xfffffff007270174` | `0x26c174` | 4 |

The whole image is independently reconstructed from these seven entries and
actual output binaries; no other byte differs. PMAP initializer RET at
`0xfffffff0046e9f00` remains `d65f03c0` and observer slot at
`0xfffffff007991340` remains `14000000`; entire initializer unchanged. The
original format argument passes unchanged; normal entry uses incoming SP and
common entry dereferences Darwin `va_list *`. Actual emitted hook/entry
instructions were bounded-emulated for both paths up to renderer main; this
does not execute rendering or prove live framebuffer mappings. Existing renderer
source/patcher are checked against pinned base HEAD, and font SHA256
`7749b211129f6f669f53fd9ee16b8e8dc9464aad41ba1bb6f7ce9b45c4eb2f1d`.
Actual new image retains identical pthread metadata, kmod start and all 95
recorded relocated binding values. No old matrix was rerun.

Commands, WSL Ubuntu-22.04 root, cwd
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`, both exit 0:

```sh
unshare -n /home/wh1stl3/.local/bin/python3.11 -B scripts/build-nuwa-pthread-renderer.py --prelink out/pthread-normal-prelink-20261112-r4/work/kernel/kernel.macho --out /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/pthread-renderer-20261112-r1
/home/wh1stl3/.local/bin/python3.11 -B scripts/audit-nuwa-pthread-renderer.py --build out/pthread-renderer-20261112-r1 --python-tools /home/wh1stl3/.local/lib/python3.10/site-packages --output out/pthread-renderer-20261112-r1/audit.json
```

Verifier should rerun with a fresh output directory and audit path, compare
hashes and independently inspect padding, source pins, seven changes and ABI.
`git diff --check` exited 0 in the device repo; record check exited 0 for 14
areas using `/home/wh1stl3/.local/bin/python3.11 -B scripts/porting-record.py
check --device /mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa --base origin/main`
from `/mnt/d/Code/PortingiOS/UniXNU` (both self-checked).
No device, outer, execution profile, native rebuild, old image or pin was
changed. Layout must be reassessed for the next FAT; the final kernel changes
the CHMH experiment digest, which must be freshly derived before packaging.
