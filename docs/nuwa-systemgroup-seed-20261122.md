# nuwa SystemGroup Data seed — 2026-11-22

**WSL read-only investigation complete; seed write and packaging deferred (self-checked).** Branch `display/20h392-dsp-diag`, starting HEAD `a2cd623d59a09157e4c7925d2114c0e526dbadf1`. No guest was used in this investigation; no seed, kernel, or device write.

## OS mount and entitlements

Reused the active WSL `apfs-fuse` read-only mount at `/tmp/nuwa-astra-os`; the logical volume root is its `root/` child. The source `UniXNU-nuwa/out/root-inputs-20261113/os-window.raw` is 5,635,081,728 B, SHA-256 `6e87bfcaa8eca952e00b719f333d1f1060715a63566112267ad8730e1ed98906`. `apfsutil` reported System volume UUID `DADD93F8-DBBF-4B17-A1DF-0F11E64172F7`. Both `usr/libexec/mobileactivationd` and `System/Library/LaunchDaemons` are present. To reproduce a new read-only mount, use `~/apfs-work/apfs-fuse-66b86bd525e8cb90f9012543be89b1f092b75cf3/build/apfs-fuse -o ro "$OS_WINDOW" "$EMPTY_MOUNT"`; the existing tool is `sgan81/apfs-fuse` (GPL-2.0).

Parsed 491 launchd plists (48 `RunAtLoad=true`), selecting `Program` or `ProgramArguments[0]`. Resolved 477 signed arm64 Mach-Os in the OS window, including 464 XML/DER-entitled jobs and 13 with neither entitlement slot. Parsed `LC_CODE_SIGNATURE` SuperBlob slots 5 and 7 with Python; cross-checked all `systemgroup.com.apple.*` literals in the decoded XML against DER. One additional XML/DER-entitled job (`com.apple.webkit.adattributiond`) resolved on the read-only SystemOS Cryptex, adding no identifier. Of the 13 remaining unresolved entries, two are jetsam plists without programs and 11 point to unavailable programs (eight App Cryptex entries; `dietapplecamerad`, `dietappleh13camerad`, `sntpd`). `sntpd` is the only unresolved `RunAtLoad` job. Coverage does not include non-LaunchDaemon executables or unavailable jobs.

**Exact requested key `com.apple.security.application-groups`: 0 matching IDs.** The complete union of the two actual MCM SystemGroup keys (`com.apple.security.system-groups` and `com.apple.security.system-group-containers`) is **34**, listed in the runbook heredoc below. Cache `.21` at file offsets `0x1fd7368` and `0x1fd7389` names those keys; `+[MCMEntitlements systemGroupIdentifiersForIdentifier:entitlements:]` is also present. The donor `mobileactivationd` declares `mobileactivationd`, `pisco.suinfo` and `regulatory_images` under `system-group-containers`, not `application-groups`.

**Early-launch proxies (entitled job, not a measured runtime lookup):** 11 IDs with at least one `RunAtLoad=true` consumer, using the common `systemgroup.com.apple.` prefix:

| ID suffix | Example `RunAtLoad` consumer |
| --- | --- |
| `bluetooth` | `bluetoothd` |
| `configurationprofiles` | `imagent`, `sharingd` |
| `icloud.findmydevice.managed` | `mobile.lockdown`, `AppleCredentialManagerDaemon` |
| `installcoordinationd` | `atc` |
| `logd_helper.FTABHarvest` | `bluetoothd` |
| `mobileactivationd` | `amsaccountsd` (the `mobileactivationd` job itself is not `RunAtLoad`) |
| `osanalytics` | `DumpPanic`, `wifid` |
| `pisco.suinfo` | `identityservicesd` |
| `regulatory_images` | `SpringBoard`, `locationd` |
| `sharedpclogging` | `SpringBoard`, `sharingd` |
| `userimagecache` | `SpringBoard` |

`powerlog` additionally has `KeepAlive=true` consumers `aggregated` and `powerd` (no `RunAtLoad=true` consumer). The other entitlements are not evidence of an early request.

## Container evidence and volume recommendation

- The donor OS `/private/var` has no `containers` directory. The existing read-only seed mount has an empty `/containers/Shared/SystemGroup`, parent ownership `0:0` and mode `0755`; this does not establish **child** ownership or mode.
- The matching SystemOS Cryptex cache `.21` contains `containers/Shared/SystemGroup` at file offset `0x1f0543f` and the explicit leaf `/private/var/containers/Shared/SystemGroup/systemgroup.com.apple.installcoordinationd` at `0x1fd2cfe`. An identifier leaf is proven for that group and is the proposed naming for the other groups, including `mobileactivationd`; a general no-UUID rule is not proven. The cache separately names `MCMMetadataIdentifier`, `MCMMetadataUUID`, a metadata plist, ACL setup, and identifier-to-path mapping. An empty directory is not proven sufficient for MCM registration. Do not invent metadata, ACLs, or class numbers.
- `mobileactivationd` strings directly name `Library/ucrt`, `Library/dcrt`, `Library/internal` and other service-specific paths. This supports `Library/ucrt` for the target probe, not blanket creation of those paths for all groups. `dcrt` and `internal` are referenced but not confirmed prerequisites; no target-specific requirement for `Library/Caches` or `tmp` was established.
- **Child owner/mode are unconfirmed.** The launch plist sets `--system-container-owner=root` for global system containers, and the target daemon is `UserName=mobile`. The cache names a creation method taking `mode`, `owner` and protection class, but those strings do not prove the values for SystemGroup. Confirm against a populated donor sample (`stat -f '%u:%g %Lp %N'`, `ls -ledO@`) before claiming donor parity. The separately acknowledged lab fallback is `0:0 / 0755`, matching the observed parent and allowing path traversal, not claiming mobile write access.
- **Use a writable local copy of the original image, not a tree rebuild.** Clone the logical raw image or losslessly expand the original `.dbr`; this preserves the original volume UUID, APFS metadata, and keybag state. Rebuilding from a tree with `newfs_apfs` assigns new APFS identity and does not reconstruct the original filesystem metadata. `asr` is a whole-volume restore tool, not necessary for this delta. `make-data-seed.py:40–74,93–97` creates APFS with `hdiutil`, copies the donor **OS** `/private/var` tree, and packs/grows it; it is not a clone of an installed Data volume. r34/r35 scripts consume a prebuilt keybag seed, and the exact historical guest command that added the keybag is not recorded in the two device checkouts.

## Future macOS procedure — not executed

Copy the original `.dbr` and the pinned official `drivers/DarwinBoot/Test/packed_ramdisk.py` to a **local** Mac directory (not an HGFS mount). Paste the block after setting the two file paths. It starts from the `.dbr`; if the source is already a raw 8 GiB APFS image, make a local sparse clone (`cp -c "$SOURCE_RAW" "$job/edit.raw"` on a clone-capable same-volume APFS filesystem), skip only the first `expand`, and keep the same checks. A standalone directory tree is suitable for donor evidence, not for a claimed seed-only rebuild.

```bash
bash <<'BASH'
set -euo pipefail
BASE="$HOME/nuwa-seed/data-8g-keybag.dbr"
PACKER="$HOME/nuwa-seed/drivers/DarwinBoot/Test/packed_ramdisk.py"
PIN=2c95d15be323eeb336c58aa1d9cc35bc72c0923942e76a702ab24c0a858c8110
UUID=B0E0F71F-A265-4038-8F5C-6D3632859DEF
test "$(shasum -a 256 "$BASE" | awk '{print $1}')" = "$PIN"
job=$(mktemp -d "$HOME/nuwa-systemgroup.XXXXXX")
printf 'Work and output directory: %s\n' "$job"
mnt="$job/mount"
mkdir "$mnt"
cat >"$job/groups.txt" <<'GROUPS'
systemgroup.com.apple.AssetCacheServices.diskCache
systemgroup.com.apple.DeviceActivity
systemgroup.com.apple.ReportMemoryException
systemgroup.com.apple.WiFiAssist
systemgroup.com.apple.appstored
systemgroup.com.apple.bluetooth
systemgroup.com.apple.cfpreferences.managed
systemgroup.com.apple.configurationprofiles
systemgroup.com.apple.coreanalytics
systemgroup.com.apple.dt.previews
systemgroup.com.apple.geod
systemgroup.com.apple.icloud.findmydevice.managed
systemgroup.com.apple.icloud.ifccd
systemgroup.com.apple.icloud.searchpartyd.sharedsettings
systemgroup.com.apple.installcoordinationd
systemgroup.com.apple.logd_helper.FTABHarvest
systemgroup.com.apple.lsd
systemgroup.com.apple.lsd.iconscache
systemgroup.com.apple.lskdrl
systemgroup.com.apple.media.books.managed
systemgroup.com.apple.media.shared.books
systemgroup.com.apple.mobile.installationhelperlogs
systemgroup.com.apple.mobileactivationd
systemgroup.com.apple.mobilegestaltcache
systemgroup.com.apple.mobilestorageproxy
systemgroup.com.apple.nearbyd.datastore
systemgroup.com.apple.nsurlstoragedresources
systemgroup.com.apple.ondemandresources
systemgroup.com.apple.osanalytics
systemgroup.com.apple.pisco.suinfo
systemgroup.com.apple.powerlog
systemgroup.com.apple.regulatory_images
systemgroup.com.apple.sharedpclogging
systemgroup.com.apple.userimagecache
GROUPS

# Lab assumption, NOT verified MCM metadata. Accept explicitly or stop.
printf 'Type LAB-0755 to accept provisional child owner/mode 0:0 / 0755: ' >/dev/tty
IFS= read -r ack </dev/tty
test "$ack" = LAB-0755
sudo -v
expand() {
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$(dirname "$PACKER")" python3 - "$@" <<'PY'
import sys
from pathlib import Path
from packed_ramdisk import regions
src, out = map(Path, sys.argv[1:])
size, extents = regions(src.read_bytes())
assert size == 8 * 1024**3 and extents[0][0] == 0 and bytes(extents[0][1][32:36]) == b'NXSB'
with out.open('xb') as f:
    f.truncate(size)
    for off, data in extents:
        f.seek(off)
        f.write(data)
PY
}
mounted=0
cleanup() { if [ "$mounted" = 1 ]; then hdiutil detach "$mnt"; fi; }
trap cleanup EXIT
attach() {
    hdiutil attach -imagekey diskimage-class=CRawDiskImage -nobrowse \
        -owners on -mountpoint "$mnt" "$@"
    mounted=1
    test "$(diskutil info -plist "$mnt" | plutil -extract VolumeUUID raw -)" = "$UUID"
}
detach() { hdiutil detach "$mnt"; mounted=0; }
inventory() {
    sudo "$(command -v python3)" - "$mnt" >"$1" <<'PY'
import hashlib, json, os, stat, sys
from pathlib import Path
root = Path(sys.argv[1])
rows = {}
for current, dirs, files in os.walk(root, followlinks=False,
        onerror=lambda err: sys.exit(str(err))):
    for name in dirs + files:
        p = Path(current) / name
        s = p.lstat()
        data = (os.readlink(p) if p.is_symlink() else
                hashlib.sha256(p.read_bytes()).hexdigest() if stat.S_ISREG(s.st_mode) else None)
        rows[str(p.relative_to(root))] = [s.st_mode, s.st_uid, s.st_gid, s.st_flags, data,
            {k: hashlib.sha256(os.getxattr(p, k, follow_symlinks=False)).hexdigest()
             for k in sorted(os.listxattr(p, follow_symlinks=False))}]
print(json.dumps(rows, sort_keys=True, indent=2))
PY
}

expand "$BASE" "$job/edit.raw"
attach -readonly "$job/edit.raw"
inventory "$job/before.json"
detach
attach "$job/edit.raw"
sg="$mnt/containers/Shared/SystemGroup" # mounted Data corresponds to /private/var
test -d "$sg" && test -z "$(sudo ls -A "$sg")"
while IFS= read -r id; do
    sudo mkdir "$sg/$id"
    sudo chown 0:0 "$sg/$id"
    sudo chmod 0755 "$sg/$id"
done <"$job/groups.txt"
leaf="$sg/systemgroup.com.apple.mobileactivationd/Library"
sudo mkdir -p "$leaf/ucrt"
sudo chown 0:0 "$leaf" "$leaf/ucrt"
sudo chmod 0755 "$leaf" "$leaf/ucrt"
detach

out="$job/data-8g-keybag-systemgroup.dbr"
python3 "$PACKER" "$job/edit.raw" "$out" | tee "$job/packed.json"
expand "$out" "$job/readback.raw"
attach -readonly "$job/readback.raw"
inventory "$job/after.json"
detach
python3 - "$job" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
a = json.loads((p / 'before.json').read_text())
b = json.loads((p / 'after.json').read_text())
base = 'containers/Shared/SystemGroup/'
added = {base + x for x in (p / 'groups.txt').read_text().splitlines()}
added.update(base + 'systemgroup.com.apple.mobileactivationd/' + x for x in ('Library', 'Library/ucrt'))
assert len(added) == 36 and b.keys() - a.keys() == added and not a.keys() - b.keys()
assert all(a[k] == b[k] for k in a), 'Existing entry content or inspected metadata changed'
assert all(b[k][:3] == [0o40755, 0, 0] for k in added)
print(f'Entries {len(a)} -> {len(b)}; additions only:')
print(*sorted(added), sep='\n')
PY
test "$(shasum -a 256 "$BASE" | awk '{print $1}')" = "$PIN"
shasum -a 256 "$out"
BASH
```

The inventory tests paths, existing regular-file bytes, symlink targets, modes, ownership, flags and xattrs, not independent ACL parity or APFS transaction bytes. Stop on any unexpected entry (including host-created entries); do not silently remove it. If a new stand-alone test image is explicitly wanted instead, the filesystem creation commands are `hdiutil create -size 8g -layout NONE -type UDTO -o "$job/empty"` → `hdiutil attach -nomount "$job/empty.cdr"` → `sudo newfs_apfs -v Data "$SCRATCH_DEVICE"` (only the `/dev/diskN` just printed by that attach). A volume-clone experiment can use `sudo asr restore --source "$SOURCE_DATA_VOLUME" --target "$SCRATCH_DATA_VOLUME" --erase --noprompt` **only on the positively identified disposable target**, then re-inspect UUID/layout. These are alternatives, not steps to run against the original, and neither was tested here.

## Existing baseline, self-checked

| Item | Digest |
| --- | --- |
| Original packed seed SHA-256 (1,896,608 B) | `2c95d15be323eeb336c58aa1d9cc35bc72c0923942e76a702ab24c0a858c8110` |
| Outer SHA-256 | `bf7056634ca116782275432cb75331cbcee07ad03fef52c0917b0826a1c66dd5` |
| FAT SHA-256 | `4a02f97b36c29d521fcfb7a469e66fa8b4630a8f053c5d59c7ea902d321184fc` |
| Kernel SHA-256 | `22af086c04d463f9be74ae302a180fa20c31346ee124a32dcd1791e89595ddc1` |
| ADT `/chosen/boot-manifest-hash` (CHMH SHA-384) | `583b57aefe4a2caac7fffb0555e6f882b4754cb70edf8c119908d4a85860598a9adb2c24ba1d708b148d61e8613fc740` |
| XNU args SHA-256 (470 B) | `3d65e3183ae6e25bfea61aadc4e31941741a378f821a9fb43ba7d6d18c771720` |

Extracted the FAT byte range from the baseline outer and matched it against the existing outer readback; `mdir` reported 11,898,368 B free. From the existing readback tree, `scratch-data.img` matched the original seed byte for byte, and `unixnu.toml` matched the staged config byte for byte. XNU args have no `sheng-data-reset`, contain `sheng-data-persist=2`, `nuwa-lite=1`, `nuwa-mg-reset=1`, `boot-progress=2` and the eight explicit `offline-*` tokens in the display packager. Readback ADT `/chosen/display-scale` is `03000000`. These are baseline results, not candidate comparisons.

## Packaging constraints and stop condition

- Reuse the official seed helper's expand/attach/detach/repack path, not its preference edits. The stock CLI unconditionally calls `merge_pref` at lines 71–86, so running it unchanged would violate the seed-only delta. Do not change the upstream checkout. Preserve the base image and verify the new image by read-only remount. No seed entries were added, removed, or compared this run.
- The display packager delegates through r35 to r14. r35 pins seed encoded bytes, logical identity, size and UUID; r14 repacks and reads back the FAT and requires at least 8 MiB free. r14 also calls `os.utime(SEED, ...)` before insertion, so any build must point that path at a staged candidate copy, not the original. Recompute the CHMH on packaging: `build-chmh-only-payload.py:39–45` binds kernel, loader, trust, args and **parent** ADT, not the seed; identical bound inputs should give the same digest. No kernel rebuild is required for a seed-only candidate.
- With no `sheng-data-reset`, a store tied to the old seed identity is kept and not applied to the new seed. `package/nuwa-ramblock/NativeRamBlock.cpp:85–91,121–125` describes the new Data session as volatile in this case. A seed-only trial does not establish persistent Data; do not change the reset flag to compensate.
- **Stop condition:** after any separately authorized trial, if `mobileactivationd` again traps at the same candidate PC (`0x1bf3bc`, `brk #1`; observed PC low 12 bits `0x3bc`), stop pursuing the migration line. Low bits alone are the existing signature, not a full PC/slide measurement.
