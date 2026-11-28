# nuwa v1 direct build shape — 2026-11-28

**Host-only build-shape validation; this package is not eligible for device
writes.** `KernelPort.inc` instantiates `Provider<CandidatePort, false>`.
`BuildWriteOptIn` is also off, `coldStartEvidenceLocked()` returns no evidence,
and `fuaProvenLocked()` returns false. Thus `nuwa-data-write=1` is a request,
not an authorization; with this provider the real mode-2 store cannot open.
The selected v1 branch is present in the binary but real v1 I/O, FUA,
durability, authentication and device boot have not been demonstrated. No
device connection, flashing or reboot was performed. Review and an independent
`verifier` rerun remain outstanding.

The device worktree is `research/nuwa-ufs-owner-api-20261126` at
`964d7e0`, with the pre-existing uncommitted v1/SBTH changes and this
increment. The UniXNU build input is `693f5d9cae8a408dd18b39f3f9fdc4228c934241`.
Remote main HEADs before and after the build were UniXNU
`e7bddb9a7eecdcf81f36da9fa38bd9d4d3f155c2` and UniXNU-nuwa
`fe6b859367cc7b0641e9ae7dda46d8b5c6fc4fb0`. Existing source reuse:
UniXNU/UniXNU `693f5d9cae8a408dd18b39f3f9fdc4228c934241`,
RamBlock v1 `DirectDisk.h` and `PersistOverlay.h`, BSD-2-Clause-Patent;
the retained provider is the existing device-worktree implementation.

Selected uncommitted build inputs, SHA-256:

| Input | SHA-256 |
| --- | --- |
| `scripts/build-nuwa-display-native.py` | `b991a3fc6d4542f8afbfa3cc81d2e34fa903bb437d8f6a90b51b1ad0c21c2f82` |
| `scripts/generate_nuwa_postevent.py` | `e22ea434067f19b0061be5963bf10ffdfdbaa6a28141d7e56c1968d292bd7a62` |
| `package/nuwa-ramblock/NativeRamBlock.cpp` | `2e9904549a4dee31a17b0fb52924f7baa373c6b5aa7617991d0acd562d6ff64e` |
| `package/nuwa-data-write/KernelPort.inc` | `8db35f5f9ad7328b558928aeb7a51e10733b3c4b8d93a0fefe94cf13c6416ab5` |
| `package/nuwa-data-write/Provider.h` | `b3be16bc83d91ce07867e2c3d753b67f755d19a9a0aa60c026774f9df1474b25` |
| `package/nuwa-data-write/DualBankLogOverlay.h` | `0c2c52f801ec16fed49f73fb8186827014e7d70ea128b41c1d51b7fa61bb5739` |
| staged `nuwa-data-provider/NativeUfs.cpp` | `84a57e15d653578ad467feeb31f16a52b0d97cd0df0c03bdd3d0676ff412eb6d` |
| staged `nuwa-data-provider/CombinedRead.h` | `cf28e51ca9153f708dab1add52dd80f803470f4fc780148cd816945f6c8a6167` |

The v1 baseline commit excludes unrelated SBTH changes from shared source
files while preserving them in the working tree. In particular, the committed
build script and post-event generator differ from the historical inputs hashed
above. The artifact hashes below identify that earlier mixed working-tree
build, not a rebuild of the v1-only commit; the latter has not been rebuilt.

## Build and package

`--data-v1-direct` requires the existing GPT/provider selection and excludes
both disposable switches. It leaves `NUWA_DATA_CANDIDATE`,
`NUWA_DISPOSABLE_DATA` and `NUWA_DISPOSABLE_FUA_PERMISSIVE` undefined for
RamBlock, and does not define `NUWA_DATA_WRITE_OPT_IN`. The linked
`NativeRamBlock.o` contains `directDiskIO` instantiated with `persist::Overlay`;
the linked native image has `_native_ufs_store_{open,write,sync}` and no
disposable counter or `native_ufs_store_order` symbols. `--post-event` omits
`fua=` and `flush=` in this build; they remain available in disposable builds.
The `--v1-data-template` packager rejects disposable and non-disposable v3
kernels; the disposable profile rejects the v1 kernel before creating an output
directory.

Commands run as root in WSL Ubuntu-22.04, from this device worktree:

```sh
p=/home/wh1stl3/.local/bin/python3.11
base=/mnt/d/Code/PortingiOS/UniXNU
b=out/nuwa-v1-shape-20261128-build
pkg=out/nuwa-v1-shape-20261128-package
template=/mnt/d/Code/PortingiOS/nuwa/worktree-ufs-neon-20261126/out/nuwa-ufs-neon-20261126-package/vendor_boot.img
gpt=/mnt/d/Code/PortingiOS/nuwa/.cache/device-evidence/20261107-recovery/gpt-sda.bin
cpo=/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json

$p -B scripts/build-nuwa-display-native.py \
  --base "$base" --cpo "$cpo" --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 --r35l-dir out/nuwa-r35l-regs-full-20261121 \
  --cpu-only --no-software-vsync --candidate --mg-reset --hid-standin \
  --crashcap --pixsig --data-persist-diag --data-candidate-gpt "$gpt" \
  --data-v1-direct --post-event --out "$b"
$p -B scripts/package-nuwa-crashcap.py --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --v1-data-template "$template" --post-event
```

Both exited **0**. The package was created before a later fail-fast refactor of
the packager's kernel-profile checks; the final packager's `--audit-only`
rechecked the resulting bytes and exited **0**. Logs:
`out/nuwa-v1-shape-20261128-{build,package,audit-final}.log`.

| Artifact | Bytes | Hash |
| --- | ---: | --- |
| `out/nuwa-v1-shape-20261128-package/vendor_boot.img` | 100,663,296 | SHA-256 `6511903d471b5d0e6de91045be3e825898069c8547efa8c3e6ef0b40381d26ff` |
| `out/nuwa-v1-shape-20261128-build/kernel.macho` | 52,207,616 | SHA-256 `173795a53c5aca67a54c689e9ce0832048122de32a33ec69f8301cda19da53e8` |
| `out/nuwa-v1-shape-20261128-package/readback-fat.img` | 67,108,864 | SHA-256 `d0fd9f746cda0f8297033d2ff65b77b185e632b828762a94cfa6362bf933ac51` |
| CHMH value, bound to this kernel and args | 48 | SHA-384 `346d16f159959a18dbb830e27780cf250df5fe476aaae8d4c2e9e1a2019e0d71f525d4b324fa3cdd3128412ffbdfe337` |
| `out/nuwa-v1-shape-20261128-package/kernel.macho.adt` | 13,680 | SHA-256 `357643ec73ad7dcb69d10b4df69eb63a4d505eace0e496c1bf434add22eaace0` |

The fixed `18fa4941…` template is rebound using the existing experimental CHMH
procedure. The package audit checks the actual outer/FAT/config/kernel/ADT,
preserved seed and trust, and 11,021,312 bytes of FAT free space. The CHMH is
not an authentication claim.

## Exact args

Extracted from the actual readback FAT: **597 bytes of ASCII text**, **598**
including the terminating NUL. The former 602-byte no-glyph package's full
`unixnu.toml` differs only by replacing `nuwa-disposable-data=1` with
`nuwa-data-write=1`. The text contains one each of `sheng-data-persist=2` and
`sheng-log-reserve=1024`, and no `sheng-data-reset` token:

```text
-v serial=3 native-ufs-root=1 native-ufs-lun=0 nuwa-pmgr=2 rd=uuid boot-uuid=DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 boot-progress=2 aks=1 disable-watchdogd=1 build-tag=data-trial boot-progress-scale=3 sheng-data-persist=2 sheng-log-reserve=1024 offline-mobile-graphics-load=1 offline-legacy-register=1 offline-legacy-gop=1 offline-legacy-pm=1 offline-legacy-phase=4 offline-legacy-validate=1 offline-legacy-transfer=1 offline-legacy-cpu-present=1 nuwa-lite=1 nuwa-mg-reset=1 nuwa-hid-standin=1 nuwa-sb-stack=900 disable-jobs=com.apple.iconservices.iconservicesagent nuwa-ufs-neon=1 nuwa-data-write=1
```

Exact text bytes in hex, without the NUL:

```text
2d762073657269616c3d33206e61746976652d7566732d726f6f743d31206e61746976652d7566732d6c756e3d30206e7577612d706d67723d322072643d7575696420626f6f742d757569643d44414444393346382d444242462d344231372d413144462d30463131453634313732463720626f6f742d70726f67726573733d3220616b733d312064697361626c652d7761746368646f67643d31206275696c642d7461673d646174612d747269616c20626f6f742d70726f67726573732d7363616c653d33207368656e672d646174612d706572736973743d32207368656e672d6c6f672d726573657276653d31303234206f66666c696e652d6d6f62696c652d67726170686963732d6c6f61643d31206f66666c696e652d6c65676163792d72656769737465723d31206f66666c696e652d6c65676163792d676f703d31206f66666c696e652d6c65676163792d706d3d31206f66666c696e652d6c65676163792d70686173653d34206f66666c696e652d6c65676163792d76616c69646174653d31206f66666c696e652d6c65676163792d7472616e736665723d31206f66666c696e652d6c65676163792d6370752d70726573656e743d31206e7577612d6c6974653d31206e7577612d6d672d72657365743d31206e7577612d6869642d7374616e64696e3d31206e7577612d73622d737461636b3d3930302064697361626c652d6a6f62733d636f6d2e6170706c652e69636f6e73657276696365732e69636f6e73657276696365736167656e74206e7577612d7566732d6e656f6e3d31206e7577612d646174612d77726974653d31
```

## Host self-checks

All commands below exited **0**. `test-nuwa-v1-entry.py` supplies a host-only
opt-in file-backed mock port; its FUA observations are file operations, not
hardware FUA evidence. It uses the actual staged v1 `NativeUfs.cpp` and
`CombinedRead.h`, and checks refusal of four v3 images and 13,878 overwrites.
The post-event fixture compiles and executes non-disposable, disposable and
FUA-trial paths, including critical paint, and inspects linked disassembly.
The old no-glyph disposable post-event fixture and package audit also exited 0.

```sh
$p -B tests/test-nuwa-v1-build.py "$b" "$pkg" out/nuwa-no-glyph-20261128-package
$p -B scripts/test-nuwa-postevent.py --renderer "$b/BootProgress.c" --kernel "$b/native-with-stabs.macho"
$p -B tests/test-nuwa-v1-entry.py "$base" "$b/nuwa-data-provider/NativeUfs.cpp" "$b/nuwa-data-provider/CombinedRead.h"
for f in dualbank data-write; do
  c++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined \
    -fno-sanitize-recover=all -no-pie -pthread "tests/test-nuwa-$f.cpp" -o "out/test-nuwa-$f-v1-shape"
  "out/test-nuwa-$f-v1-shape"
done
$p -B scripts/package-nuwa-crashcap.py --base "$base" --kernel "$b/kernel.macho" \
  --out "$pkg" --v1-data-template "$template" --post-event --audit-only
fsck.fat -vn "$pkg/readback-fat.img"
mdir -i "$pkg/readback-fat.img" ::/EFI/UniXNU/Payloads/
$p -B "$base/scripts/porting-record.py" check --device "$PWD"
```

The exact test output is in `out/nuwa-v1-shape-20261128-{shape-test-final,
postevent,postevent-old,entry,regressions,audit-final,disposable-audit-final,fsck,
porting-record-final}.log`. The first record check exited 1 because the newly
added host evidence omitted `revision`; after adding the actual base revision
and marking the working-tree increment, it exited 0. `git diff --check` exited 0.
For an independent rebuild, use fresh `$b` and `$pkg` directories and then
rerun the commands above; the produced artifact hashes must be checked rather
than assumed identical.
