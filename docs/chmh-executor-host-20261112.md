# CHMH-only executor profile: host-only checkpoint

**Self-checked only; independent review/verifier pending.** The explicit
`chmh-only-20261112-r1` profile pins the reviewed outer, verifier FAT/ADT/record,
fixed r4 and stock, plus the repaired outer audit source and output. Prepare and
boot check frozen host inputs before device or claim; restore depends only on
run identity and its own backup. The default stop profile and previous profiles
remain unchanged. This did not create a real run or claim or access a device.

The ordinary 7fd3 renderer has no AMNM snapshot expectation. Disappearance of
the old panic is not success: observe the first natural later milestone or panic.
CHMH is an unauthenticated experiment; ASMB is absent, host selection level 0,
consumer `+0x60` deferred and authentication NOT REACHED. Actual UFS-persistent
interaction and power-cycle acceptance remain unproven. The previous AMNM
restore was independently verified as recorded in the machine AGENTS; that is
not a statement of current live device state.

WSL Ubuntu-22.04 root cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`:

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/run-pmap-ret-once.py --self-check
```

Self-check exit 0: 98 synthetic groups, no real device commands; ignored
`out/chmh-executor-selfcheck-20261112.json` SHA-256
`0f22d31f86240870df13b26c9ea0f70b7c85ad03e1df3f44bff06cdf0f6aa193`.
Actual frozen-file `Run.host_inputs()` also returned normally with no run
directory or device command; a separate four-profile by three-phase CLI matrix
returned 0 with 12 dry runs, zero device commands and no run directories.
For independent rerun use `--self-check` and repeat that dry matrix; never pass
an authorization flag. The test runner traps real subprocess calls during its
synthetic state-machine cases. No device action is authorized by this document.
