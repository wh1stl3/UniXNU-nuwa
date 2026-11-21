# Display nub type change — build blocked

The display nub now uses `IOService` rather than `IOPlatformDevice`, with
the resource-service parent, memory property, device-tree attachment,
display attach/probe/start and failure cleanup unchanged. The requested
motivation is that `IOPlatformDevice::compareName()` and `getResources()`
assume an `IOPlatformExpert` provider, whereas this nub is attached to
`IOResources`; `IOService::getResources()` is the default implementation
without that platform-provider assumption. The provider implementation
assertion was supplied in the brief and has not been independently checked.
Deep review of the initialization change remains required.

The existing eight offline options and `disable-watchdogd=1` are unchanged.
No `sheng-lite` or `sheng-disable-watchdogd` argument was added.
`package/nuwa-watchdog/SOURCE.md:31` says the lite list was not ported;
`package/nuwa-watchdog/nuwa_watchdog_policy.c:118-122` selects the
unprefixed watchdog option first and the prefixed spelling only as fallback.

The first build attempt used WSL Ubuntu-22.04 as root and absolute
`/home/wh1stl3/.local/bin/python3.11`:

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/build-nuwa-display-native.py \
  --base /mnt/d/Code/PortingiOS/UniXNU \
  --cpo /root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/nuwa_pmap_ret/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json \
  --linker-dir /opt/unixnu-linux/CommandLineTools/usr/bin \
  --r35-dir out/nuwa-r35-20261119 --r35l-dir out/nuwa-r35l-regs-full-20261121 \
  --cpu-only --no-software-vsync --candidate \
  --out out/nuwa-r35l-dsp-ioservice-20261122
```

It stopped before compilation at `scripts/build-nuwa-display-native.py:501-502`:
`--r35-dir must be inside device out/ and replaces --link-dir`.
The input resolved to the other checkout's
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa/out/nuwa-r35-20261119`, outside
this worktree's resolved `out/`.

On user direction, both r35 inputs were copied with `cp -aL` into this
worktree's `out/nuwa-r35-ioservice-input-20261122` and
`out/nuwa-r35l-ioservice-input-20261122`. The same build command was rerun
with those two paths substituted. The path check passed and compilation
reached archive validation, which stopped at
`scripts/verify-nuwa-display-host-abi.py:613`:
`unresolved symbol fingerprint changed`. The generated diagnostic is
`out/nuwa-r35l-dsp-ioservice-20261122/archive/archive.json`; no fingerprint
gate was altered and no further build was attempted.

No new kernel or package was produced;
args readback, outer/CHMH/FAT checks and hashes are not available. No device
action. Source edit only; not compiled or independently verified.
