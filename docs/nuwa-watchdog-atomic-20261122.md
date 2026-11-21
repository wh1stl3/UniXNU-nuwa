# nuwa watchdog atomic policy — host self-checked

The policy is written to an exclusively created same-directory temp, checked,
synced and closed; only after the migration marker is established or its
existing regular root-owned empty file checked does rename replace the plist.
Failures leave the prior plist untouched and attempt temp unlink; unlink
failure is logged, so temp cleanup is not guaranteed if unlink itself fails.
`nuwa_watchdog_policy_committed` distinguishes a successful rename from the
no-policy no-op; Data stage 4 is not evidence of policy success.

`python3 -B scripts/test-nuwa-watchdog-atomic.py` executes the actual policy C
against a fault-injected syscall model. First write failure, intermediate
short write, fsync failure, marker failure and rename failure preserve the old
bytes; successful policy contains all 32 expected keys in 1502 bytes. The
existing policy test also ran. These are host models, not filesystem runtime.

Recorded-argument watchdog compilation and ON link, outer/CHMH/FAT readback
are self-checked. The extracted args match the previous ON profile exactly;
FAT free space is 11,931,136 bytes. The new artifacts are:

* kernel SHA256 `70575178c4f32674630de7da44ebea3224b10a82db005d6e88527e3880002cae`
* outer SHA256 `06f77d8d4ad509877db7aa3d7d852f2c1cd1946411a1ec6c7877ae55e6f8de24`
* FAT SHA256 `f92c4f70bdd77c7b17bb246e4e5ad5500c9e348d6ce8d4192cbc607fab6c311c`
* CHMH SHA384 `1a99eaf03e584886a7e7d359fb3e4d477c2bb9cdd686970d4e16ad390517a31dca432ffd067713829c5ea7bf63f25977`

Local build, package and audit paths are respectively
`out/nuwa-r35l-dsp-atomic-20261122`, `out/nuwa-r35l-dsp-atomic-package-20261122`
and `out/nuwa-r35l-dsp-atomic-audit-20261122`. No device action. Pre-initproc
changes require deep_reviewer re-review; independent verifier and runtime
remain pending.
