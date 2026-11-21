# Display ON gate parameters — host self-checked

The ON wrapper appends `offline-legacy-pm=1 offline-legacy-phase=4
offline-legacy-validate=1 offline-legacy-transfer=1
offline-legacy-cpu-present=1` after the existing three display arguments.
OFF and the inherited r35 arguments are unchanged. This is a bounded
diagnostic experiment: reaching donor slot 329 is expected to panic, not
demonstrate a working display.

The first build was attempted in WSL as the ordinary user:

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/build-ufs-apfs-root-chmh-r35-display.py \
  --kernel out/nuwa-r35-display-budget-compact/kernel.macho \
  --kernel-sha256 89355aa4e0dc0f3d2e9ef1971e94d45f6584f66d4ae318e6ac2bdc832fce4b39 \
  --enable-display --output out/nuwa-r35-display-gates-20261122-on
```

It stopped at `scripts/build-nuwa-pmgr-kernel.py:24`: permission denied
reading `/root/nuwa-pmap-ret-native-20261111/build-result.json`. On explicit
authorization the same command succeeded under `wsl -d Ubuntu-22.04 -u root`
using the new output `out/nuwa-r35-display-gates-20261122-root-on`.

| Item | SHA-256 unless specified |
| --- | --- |
| outer | `f7563e66d853b7adaf6e67b8508811b7a9cef74881e423cb888a393ac6e5ab7e` |
| kernel | `89355aa4e0dc0f3d2e9ef1971e94d45f6584f66d4ae318e6ac2bdc832fce4b39` |
| FAT | `39a349e4de100c393d9e10cedf55a3884fb904167c1b8faa184b663777460342` |
| CHMH (SHA-384) | `bd4009069967973496cfb8f55489083cdbbdda1b8fd5dccc648ff3b80ff198bef5c0ca5ced65442e9d947ac9d0a65913` |

The packager's separate `--audit` rerun read back the outer FAT, kernel,
ADT, trust and config, and checked the CHMH against the derived ADT and input
material. The extracted outer config contains each of the eight requested
offline tokens exactly once, as well as native-ufs-root=1, boot-progress=2,
aks=1, disable-watchdogd=1 and build-tag=nuwa-r35; its complete argument
string matches `record.json`, its SHA-256 matches the recorded args hash,
and SHA-384 of the recorded CHMH material matches the recorded CHMH.
`fsck.fat -vn` reported 105719/129022 clusters used; `mdir` reported
11,931,136 bytes free, exceeding 8 MiB. The audit output is
`out/nuwa-r35-display-gates-20261122-root-audit`.

The parameters enable the requested opt-in settings, not proof that the
corresponding runtime transitions succeed: service loading/registration,
power state, phase progress, buffer validation and CPU transfer still need
runtime evidence. Authentication remains NOT REACHED. No device action;
host results self-checked only.
