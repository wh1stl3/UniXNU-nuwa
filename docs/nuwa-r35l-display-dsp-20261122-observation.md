# r35l display ON bring-up probe — host self-checked

The isolated `display/20h392-dsp-diag` branch merges
`display/20h392-abi@d5d1df5ca36022ad20f6203b1991759719ed3f98` and
`diag/r35g-ux-exception@b7c117720f986d2e5b4eb51e5b5c68fc2a90137f`.
Only `AGENTS.md`, `README.md` and `porting.toml` conflicted; both sets of
records were kept. The diagnostic generators and tests come unchanged
from the latter parent, including the r35l overlay at `6dcecf1`. The ON
build verifies a replay of the pinned r35l full native link, applies
the existing two display hooks to its byte-identical `bsd_init.c`,
substitutes the DSP renderer archive, and force-loads the CPU-only display
archive. Donor pins, r35 final-render recipe and 329 guard are unchanged.

## Decode

The board reports its 13 existing failure sites and two success points via
`boot_progress_diag_set(uint8_t stage, uint8_t reason)`. Stage and reason
are separate relaxed byte samples, not a synchronized pair. `0/0` means no
result; `2/0` means early init completed; `4/0` means the registration call
returned, not that a client matched or a frame was presented.

| Stage | Reason | Existing refusal |
| --- | --- | --- |
| 1 | 1–5 | preModLoad, postModLoad, console, allocation, metaCast/init, respectively |
| 0 | 6 | late hook found no early object and no prior early failure; otherwise preserve reason 1–5 |
| 3 | 7–13 | IOSurface load, matching/console, nub setup, nub attach/start, DT parent/property, attachment, probe/start, respectively |

The normal page shows `DSP s=<n> r=<n>` on zero-based row 9 (max 15
columns). This uses the short DATA summary's slot; detailed DATA rendering
is unchanged. EX1–EX4, X1–X3 and the prior conditional `stg` block are
byte-identical. At scale 3, row 9 is just outside the fully panic-safe
rows 0–8; an immediate panic or scanout handoff can prevent a readable
sample. The setter does not trigger a repaint or change any return path.

## Results

| Artifact | Digest |
| --- | --- |
| Full kernel SHA-256 (55,857,152 B) | `f04cca991dce965d8b67bf622f0ec3e29b72ff394fa15314a5b112503c15022c` |
| Compact kernel SHA-256 (52,146,176 B) | `7ae5623c8a82ddbbcef1da905de3e39fb4c5e4ec4d5f35e7b9bb3348e062674f` |
| Compact outer SHA-256 (100,663,296 B) | `193c95868a8b10a51bd41bd2db55b1772909dd7b4aa7ae532cba226a334612a0` |
| FAT SHA-256 (outer readback identical) | `40574af5a6b063ca741609be1b9c4cc2974a7514491401a0d5bddd1bb4ea00a1` |
| Rebound CHMH SHA-384 | `7d5aef09505cbf27fab6c0d5df0c904369a1af85205fe4856a959f9ff040e6d23a202379d9903f8abc68f0e631c152bf` |

Full/compact native audit: mapped bytes and 50,047 non-STAB symbol tuples
matched; 128,848 STABS removed. Prelink inventories agreed on 65,443
bindings and the linked Legacy slot reports matched. The compact kernel
passed the r35g exception-site, r35k saved-register and r35e IRQ guard
linked tests. Separate packager `--audit` re-extracted FAT, kernel, ADT,
trust and config and checked CHMH; SHA-384 of the recorded material matched.
`fsck.fat -vn` reported 105,719 of 129,022 clusters used; `mdir` reported
**11,931,136 B free**, above 8 MiB. Only compact was packaged.

The extracted `outer-readback/EFI/UniXNU/unixnu.toml` args matched the
record in full and contained exactly one of each offline token:

```text
offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1
offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1
offline-legacy-transfer=1 offline-legacy-cpu-present=1
```

## Independent verifier rerun

Use WSL Ubuntu-22.04 as the owner of the existing root-owned compile tree.
Keep the base at `693f5d9cae8a408dd18b39f3f9fdc4228c934241` (read only).
Initially point the isolated checkout's `out` at the original device
checkout's `out` for replay. Use fresh output names. The `PY`, `BASE` and
`CPO` paths are in the [original display build](nuwa-r35-display-20261120-observation.md#host-checks-and-limits).

```sh
build() {
  "$PY" -B scripts/build-nuwa-display-native.py --base "$BASE" --cpo "$CPO" \
    --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
    --r35-dir out/nuwa-r35-20261119 --r35l-dir out/nuwa-r35l-regs-full-20261121 \
    --cpu-only --no-software-vsync --candidate "$@"
}
build --out out/nuwa-r35l-dsp-on-full --keep-link-debug
build --out out/nuwa-r35l-dsp-on-compact
```

Run `audit_debug_strip` on the two `native.macho` blobs via the display
build module with `kits/XnuPrelink` on `PYTHONPATH`; compare `prelink.json`
bindings and `linked-original-slots.json`. Run `test-r35g-ux-linked.py`,
`test-r35k-regs-linked.py` and `test-r35e-irqguard-linked.py` on compact.
For packaging use a **real**, Git-ignored `out/` in the isolated checkout.
Link historical inputs from the original `out/`, copy the compact kernel
into the real `out/`, and make its existing `.cache/boot-stage12-v4-r4.img`
and `.cache/stock/vendor_boot_b.img` inputs available read-only.

```sh
S=scripts/build-ufs-apfs-root-chmh-r35-display.py
K=out/nuwa-r35l-dsp-on-compact/kernel.macho
H=7ae5623c8a82ddbbcef1da905de3e39fb4c5e4ec4d5f35e7b9bb3348e062674f
P=out/nuwa-r35l-dsp-on-package-r2
A=out/nuwa-r35l-dsp-on-outer-audit
"$PY" -B "$S" --kernel "$K" --kernel-sha256 "$H" --enable-display --output "$P" </dev/null
"$PY" -B "$S" --kernel "$K" --kernel-sha256 "$H" --enable-display --output "$A" --audit "$P" </dev/null
fsck.fat -vn "$A/actual-vendor-ramdisk.img"
mdir -i "$A/actual-vendor-ramdisk.img" ::
```

The probe and merge resolution require reviewer re-review; the build/package
await independent verifier. No device action or release. Actual probe result,
readable capture, service matching and presentation require runtime observation.
Authentication **NOT REACHED**.
