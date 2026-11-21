# r35 FDR console candidates — host self-checked

Both candidates reuse the existing FDR compact kernel, not a new kernel build.
The original FDR candidate remains unchanged. Only `boot-progress=2` is
replaced with `debug=0x14e`; video additionally removes `serial=3`. All eight
offline tokens, UFS, `nuwa-lite=1` and the other arguments remain unchanged.
With the progress renderer disabled, its EX/X1/DSP/FDR page is unavailable.
The aim is video text logging, not an established runtime result.

## 8796 static routing

Source below is the local 8796 work tree
`UniXNU-nuwa/out/nuwa-apfs-host-20261113-a1/xnu-work`.
`osfmk/kern/debug.h:513-520` decodes `0x14e` as DB_NMI (0x4),
DB_KPRT (0x8), DB_ARP (0x40), and obsolete bits 0x2 and 0x100.
No DB_KDB (0x10) or DB_KDP_BP_DIS (0x80) is set. DB_KPRT clears
`disable_serial_output` (`pexpert/arm/pe_kprintf.c:20-26,35-52`);
it does **not** by itself clear `disable_kprintf_output`, which additionally
depends on DEBUG or DEVELOPMENT and `-enable_kprintf_spam` (lines 45–52,
98–105). `PE_kputc` selects serial if `serial_init()` succeeds, otherwise
falls back to console (lines 57–70); kprintf therefore is not guaranteed
on video merely by setting `debug`.

`serial=3` sets output and input (`osfmk/console/serial_protos.h:48-55`).
If `serial_init()` reports a device, `osfmk/arm/arm_init.c:539-550,575-581`
switches ordinary console to serial, and `serial_general.c:99-123` changes
the selected console operations. If no device is detected this switch
does not occur; runtime device enumeration is unverified. Without `serial=3`,
that explicit switch is avoided, though kprintf can still independently use
UART. `IOLog` calls `os_log` and, unless serial IOLog is disabled, writes
to the selected console (`iokit/Kernel/IOLib.cpp:1548-1588`,
`osfmk/console/serial_general.c:143-195`); thus it can reach video when
video is the selected working console, not unconditionally. Ordinary
printf uses that same console (`osfmk/kern/printf.c:867-885`). Screen
visibility, video console initialization and later display handoff remain
unverified. The video variant is the better screen-logging candidate.

## Artifacts

| | Serial | Video |
|---|---|---|
| Kernel SHA256 | `033f1065893aaf489565d732f04672cefa868dd6c71fc80a431ec741d1053c52` | same |
| Outer SHA256 | `1e3cebf2ecf9d6f16e541622d7a65aab18e599508d135889db9c4d9f53861b1e` | `7730fd610fab619cea375d830726b563b718a1d8a0bfbead106717bb3f668cc4` |
| FAT SHA256 | `4fa689b39cfadc5eccbd46275d309e80b0adc38956d7adf3091822ea117fba78` | `1647f83cac59213962fd06f0b81daa1d6c4c90279158973cada24e49a4f66b78` |
| CHMH SHA384 | `54b54fafcb6d3a3d25a57682e14880766485c59431aee1e64e7047b5691d6f852a899b6dcfe1c6565adce1e2c066762c` | `b79320182995c4f6adff6541c85f7172c9c824a08034d93ef684e8b4fc7c27a7d4994645d05db83d823189beb8f531d6` |

Serial extracted args:

```text
-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 debug=0x14e aks=1 disable-watchdogd=1 build-tag=nuwa-r35 boot-progress-scale=3 sheng-data-persist=2 sheng-data-reset=1 sheng-log-reserve=1024 offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1 offline-legacy-transfer=1 offline-legacy-cpu-present=1 nuwa-lite=1
```

Video args are identical except `serial=3` is absent. Separate outer audits
extracted and checked members, arguments and CHMH. `fsck.fat -vn` and
`mdir` on each extracted FAT reported 11,931,136 free bytes, above 8 MiB.
The inherited packager's historical page-description metadata does not
describe these disabled-page candidates; the actual args above control them.
CHMH is an experimental host identity, not authentication.

## Reproduction for independent verifier

From this checkout, with WSL root and the existing pinned local inputs:

```sh
PY=/home/wh1stl3/.local/bin/python3.11
S=scripts/build-ufs-apfs-root-chmh-r35-console.py
for n in serial video; do
  opt=""; [ "$n" = video ] && opt=--no-serial
  "$PY" -B "$S" $opt --output "out/verifier-console-$n"
  "$PY" -B "$S" $opt --output "out/verifier-console-$n-audit" --audit "out/verifier-console-$n"
  fsck.fat -vn "out/verifier-console-$n-audit/actual-vendor-ramdisk.img"
  mdir -i "out/verifier-console-$n-audit/actual-vendor-ramdisk.img" ::
  grep 'args =' "out/verifier-console-$n-audit/outer-readback/EFI/UniXNU/unixnu.toml"
done
```

No device action; deep review of inherited FDR/ON changes and independent
verifier rerun remain pending.
