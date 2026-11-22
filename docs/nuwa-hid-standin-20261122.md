# 20H392 HID stand-in and DSP attribute readback

This is a default-off enumeration experiment, not touch or button support.
The only HID opt-in is `nuwa-hid-standin=1`; the post-IOBSD hook calls it
independently of the display condition. It does not send input reports, arm a
timer, use a hardware input source, or replace any provider type or vtable.
Whether a missing digitizer causes the SpringBoard assertion is a hypothesis.

The board probe loads `IOHIDFamily` and the codeless `IOHIDEventDriver`
personality, confirms the original classes, waits up to five seconds for
`IOHIDResource`, then registers the owned subclass between `preModLoad` and
`postModLoad`. It calls init/attach/start on that resource. After the owned
device has a registered `IOHIDInterface` with a registered `IOHIDEventDriver`
child, it sets `Built-In`, `DisplayIntegrated`, and primary usage `(0x0d, 4)`
on the driver and its interface. Matching itself uses the keyboard-first
descriptor and the original keyboard personality.

The ABI parser and archive checks reuse nuwa's display helpers. The override
declarations follow `UniXNU/UniXNU@693f5d9`'s HID recipe; descriptor fields
follow `UniXNU/ShengHidInput@71a40e76`, and late classification follows
`UniXNU/UniXNU-sheng@c8f92b2` (BSD-2-Clause-Patent). Only the 20H392 donor
(`2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221`) supplies
binding addresses. The abstract table at `0xfffffff006cbe2c0` has 207
function entries, including 39 beyond the 168 base slots. Slot 180 is the
sole pure slot; `start` calls it with a descriptor output pointer. The
metaclass initializer passes 208 bytes, and the compiled 136-byte
`IOService` base leaves 72 opaque bytes. The compact link and rendered kernel
are checked for the complete derived vtable, original imports and branch
targets, metaclass GOT/storage, and post-IOBSD/manual initializer order.

`NuwaLegacyDisplay.cpp` reads `NormalModeEnable` and `ADCLLoadAll` on the
display object immediately after both `setProperty` calls succeed. Missing
or non-`OSBoolean` readback sets DSP `s=3 r=16`; it does not abort display
startup and is retained as `s=4 r=16` if registration succeeds. An independent
display failure still reports its own reason. `s=4 r=0` means both reads
returned a canonical `OSBoolean` at the probe; this does not establish that
FDR accessed the same object or that it read those values later. With no
readback failure, an FDR exit 1 still needs separate diagnosis.

Do not use this as evidence of hardware input, successful matching at
runtime, or authentication. `deep_reviewer` must review the private ABI
and boot-time registration order; independent verifier and device execution
remain pending.

## ON candidate — host self-checked

Local build: `out/nuwa-hid-standin-20261122-r4/`; package:
`out/nuwa-hid-standin-20261122-package/`; separate outer readback:
`out/nuwa-hid-standin-20261122-outer-audit/`.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `0a17b5fde4264546bbfcb710adb1752252cdbafb184c796342d8ade53e2a5509` |
| Outer SHA-256 | `a33a405871bccf81cdd2e3d626b2346441c019fb849b007bf68fb196c2f74f44` |
| Experimental CHMH SHA-384 | `51cea29be48dedbdf6b33dfce34b36973ba89af6473bb3f9ef50b9cdea8e1798538c8c004ddd40a28bde16409888464a` |
| Outer-extracted FAT SHA-256 | `2041ec8caee5486e4cfce3970dd250ecbf6291fd9b939f979415b052705222e4` |

`fsck.fat -vn` and `mdir` reported 11,906,560 free bytes (minimum
8,388,608). Outer readback matched the kernel, derived ADT and config.
The readback ADT kept the 4.75 GiB window and contained the recomputed CHMH.
The 492-byte readback `args` equalled the 4.75 GiB display ON args plus
exactly one appended token:

```text
-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1 build-tag=nuwa-r35 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024 offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1 offline-legacy-transfer=1 offline-legacy-cpu-present=1 nuwa-lite=1 nuwa-hid-standin=1
```

The ABI audit rejected three in-memory single-site mutations of the final
kernel: zeroed slot 180, zeroed original C2 veneer instruction, and removed
manual initializer call. The OFF packaging regression rejected this
correctly hashed HID kernel. No device operation.

### Independent verifier rerun

Under WSL, rerun the compact [r35l ON build](nuwa-r35l-display-dsp-20261122-observation.md)
with `--hid-standin` and a fresh `--out "$B"`. Then run the following using
fresh `$P` and `$A` paths under `out/`; keep `$PY` as the pinned Python 3.11:

```sh
S=scripts/build-ufs-apfs-root-chmh-r35-display.py
H=0a17b5fde4264546bbfcb710adb1752252cdbafb184c796342d8ade53e2a5509
set -- --kernel "$B/kernel.macho" --kernel-sha256 "$H" \
  --enable-display --enable-hid-standin --board-window
"$PY" -B "$S" "$@" --output "$P" </dev/null
"$PY" -B "$S" "$@" --audit "$P" --output "$A" </dev/null
"$PY" -B scripts/test-nuwa-display-packaging.py --kernel "$B/kernel.macho" --kernel-sha256 "$H"
fsck.fat -vn "$A/actual-vendor-ramdisk.img"
mdir -i "$A/actual-vendor-ramdisk.img" ::
sha256sum "$B/kernel.macho" "$P/vendor_boot.img" "$A/actual-vendor-ramdisk.img"
```
