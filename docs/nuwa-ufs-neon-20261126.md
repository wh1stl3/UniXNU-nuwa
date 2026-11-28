# nuwa retained UFS NEON · 2026-11-26

Host-only candidate based on `a03370a80cc362c63c76c4b47d2930060613c100`;
no device access or release. `nuwa-ufs-neon=1` is the sole new opt-in.
`cid=N261126A` is a candidate label, not a hardware ID or a per-boot nonce.

## Evidence contract

- `s=1`: setup claimed; no HC claim yet. `s=2`: the existing pre-first-write
  prerequisite expression ran. The `HC` fields, in order, are CAP/HCE/HCS/
  transfer DB/task DB/IS. `?` means short-circuited, not zero. Old bases and
  RSR are not read there; neither the values nor queue ownership are inferred.
- `s=3`: attributed Slot0 Device and LU0 descriptor replies and MODE SENSE
  outcomes are cached. Rows show selected raw descriptor fields and compare
  LU0's enabled/count/block size to this retained session's READ CAPACITY.
  `MS` is DPOFUA/WCE; neither bit proves durability.
- `s=4`: survey finished or stopped. Primary and backup GPT header/table
  CRCs are checked separately against the pinned 4 KiB LUN0 geometry; `id`
  also checks matching tables, userdata identity and overlaps. Only after
  those checks, descriptor/READ CAPACITY agreement, and the placement/reserve
  predicate pass do reads enter the proposed Data window. The window is
  `57393401 + 4195074` blocks, entirely below the existing 262144-block
  reserve. Four anchors are relative pages `0, 1, 640, 2097857`; the
  `A` nonzero mask uses that order. `M(part)` covers 10 of the 768 map/ring
  pages (`2,65,66,129,130,193,194,257,258,769`); it does not certify the
  remainder, identify a valid overlay, or authorize initialization.
- At most 3 query/SCSI commands and 18 one-block READ(10)s. The existing
  retained latch stops all subsequent submissions on ownership loss or
  timeout; the media walk also stops on the first failed read. Nothing
  here allocates a new MMIO mapping, changes DMA, adds UIC/reset, submits a
  hardware Data write/flush, or changes volatile Data behavior.
- Both renderers use the same cached formatter. The early page reserves
  rows 37–42 when enabled; the live banner reserves up to six of its
  existing rows before the crash budget. Publishing acquires no render lock
  and never paints. Host fixture checks 66-column rows, both consumer
  call sites and a 1440×3200 scale-3 budget; actual visibility, panics
  clearing the page, and timing/behavior on device were not measured.

## Host artifacts (self-checked)

Final source re-linked as `out/nuwa-ufs-neon-20261126-build-r3`; its kernel
digest matches r2, used to produce `out/nuwa-ufs-neon-20261126-package`.
The 96 MiB outer retains the stock header/tail. Exactly three FAT files
changed (kernel, ADT, TOML); boot args are 561 → 577 bytes with only the
new token appended. CHMH is freshly bound, not authentication. FAT free
space is 11,021,824 B; linked Data/log write and sync entry points never
call hardware. UniXNU HEAD pin is `693f5d9cae8a408dd18b39f3f9fdc4228c934241`;
remote HEAD before/after was `e7bddb9a7eecdcf81f36da9fa38bd9d4d3f155c2`.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `48637103823e84726de1654c07629118d6b63021340cc88d58a8d15d62196f72` |
| Outer SHA-256 | `18fa4941696667d1813442022ea71fc48e4c414b1abadb1caf73774fcc76202a` |
| CHMH SHA-384 | `e78df504dfaad23a15627d2651ce9c2bce7a1790e652dcfb2df24413ba3e37e96c4623008b8201a984d2ce43efccbc43` |
| FAT readback SHA-256 | `f863982b0003ff9eda34aee9381ceae688938286e46f1c8d215a39a68b7e59c3` |
| Seed SHA-256 (unchanged) | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |
| Trust bundle SHA-256 (unchanged) | `eb1475f643f45a974ebd40596f6e2b1cdf40205d2ca3c6094d774886099399c3` |
| PIX template SHA-256 | `28d45ab6c3d7c5ec79cf14543af4836dadf04de7eddaa91fd876b36bc831dbcc` |

## Reproduction and rollback

Use the [MODE SENSE candidate's build inputs](nuwa-ufs-modeprobe-20261126.md)
with fresh `B` and `P` under this worktree's `out/`; the build options are
unchanged. Package and audit using `--data-persist-diag --ufs-neon` instead of
`--ufs-desc`. Run:

```sh
"$PY" -B tests/test-nuwa-retained-entry.py "$B" "$BASE"
"$PY" -B tests/test-nuwa-ufs-neon.py "$B" "$BASE"
"$PY" -B tests/test-nuwa-crashcap.py "$B/kernel.macho"
llvm-objdump -d --disassemble-symbols=_native_ufs_store_write,_native_ufs_store_sync,_native_ufs_log_write,_native_ufs_export_write,_native_ufs_log_sync "$B/kernel.macho"
"$PY" -B scripts/package-nuwa-crashcap.py --audit-only --base "$BASE" --kernel "$B/kernel.macho" --data-persist-diag --ufs-neon --out "$P"
fsck.fat -vn "$P/readback-fat.img"
mdir -i "$P/readback-fat.img" ::/EFI/UniXNU/Payloads
```

Source rollback: use the unchanged `a03370a` worktree. Package rollback for
comparison: keep the unmodified PIX template and MODE SENSE candidate
(`932c01bd957c6bb8c1b227a672aae32526bc904b2eb8ad7cac4fae954add4fb6`);
neither is a claim about what is installed. Device rollback remains the
existing separately authorized procedure in
[the launchd handoff](nuwa-launchd-reached-20261115.md); it was not exercised.
The retained setup splice and terminal isolation must be reviewed before
any device authorization.
