# r35 exit-ring selection — host only

The generator accepts only `out/nuwa-r35-20261119/BootProgress.c` with SHA-256
`c6e5655257e708a0b304b12fded80b81e38c10fc20f4c8119bfef58d91a45a35`.
It creates a new file exclusively and changes only `if(status || ns)` to
`if(signal || ns)` inside the real `boot_progress_exit`. Here `signal` is
the existing `status & 127`; a normal exit(1) has status `0x100`. Thus a
signal or nonzero reason namespace enters the existing four-slot ring, but
ordinary exit(1) does not. No locking, renderer, other exit records, or
authentication code is changed. The comment describing abnormal exits in
the generated source is inherited from r35.

Example, from this worktree (output directory must already exist):

```
python3 -B scripts/generate-r35-exit-selection.py ../UniXNU-nuwa/out/nuwa-r35-20261119/BootProgress.c out/BootProgress-exit-selection.c
python3 -B scripts/test-r35-exit-selection.py ../UniXNU-nuwa/out/nuwa-r35-20261119/BootProgress.c
```

The test compiles the actual generated exit function and row-formatting loop
with host stubs, not a Python ring model. Two SIGTRAP records survive 200
ordinary exit(1)s; after a reason record and another signal fill the ring,
another 200 ordinary exits leave all four intact. Four maximum-width rendered
records occupy 71 characters in the 80-byte row. A subsequent signal evicts
the oldest record: a signal/reason storm can still displace the targets.
The existing try-lock can drop concurrent events; this test does not exercise
concurrency. Replay uses stubs for other kernel behavior and is self-checked,
not an independent verifier run, kernel build, or device observation.
The generated source is an input for a future isolated build, not a
packaged or authorised device image; r35 remains unchanged.

## r35b isolated kernel, 2026-11-20 (self-checked)

The entry `scripts/build-r35b-kernel.py` pins the r35 build script and original
renderer, generates and pins the new renderer, and runs the original recipe
with only its in-memory ring assertion changed to require the new predicate
and reject the old predicate. All other recipe assertions remain in place.
It creates a new sibling directory exclusively; it does not edit r35 inputs.
The recipe's compilation and link commands are in that directory's
`commands.json`. It uses the original checkout's pinned inputs and scripts,
not this diagnostic worktree's versions.

Exact command (WSL Ubuntu-22.04, root, from this worktree):

```
/home/wh1stl3/.local/bin/python3.11 -B scripts/build-r35b-kernel.py ../UniXNU-nuwa/out/nuwa-r35-20261119 ../UniXNU-nuwa/out/nuwa-r35b-exit-selection-20261120
/home/wh1stl3/.local/bin/python3.11 -B scripts/test-r35-exit-selection.py ../UniXNU-nuwa/out/nuwa-r35-20261119/BootProgress.c
```

The recipe completed, including its source, object, symbol and link assertions.
Linked `_boot_progress_exit` disassembly has `and w24,w22,#0x7f` at
`fffffff0079ac4c0` and `orr w8,w24,w20; cbz w8,...` at
`fffffff0079ac590`: the ring guard uses the masked signal and namespace.
The separate existing status-or-namespace condition at `fffffff0079ac544`
is not the ring guard. Host replay completed; it does not test concurrency.

SHA-256 before and after build matched for original r35 build script
`c2e8bcc0aae8a6736592079b4f0bd1fba9032490ddfa432f30df9e6fbc619979`,
renderer `c6e5655257e708a0b304b12fded80b81e38c10fc20f4c8119bfef58d91a45a35`,
display header `86311631e7cf66881bd6d1a57a927c78db9ea9bb579deb025136252e3e218c72`,
kernel `787610183dc7f772e2d01aa183f72f2fcc52245fc44407e6c815ced614412464`,
and original `vendor_boot.img`
`c6e64820cc46c1a54e65d3640994ad7acf0e7aa807dfd3765eac82f483a4a7ed`.
Only these original files were compared, not the entire package directory.

New renderer SHA-256
`a4163ecd10ecfd6bb429f2ce9c919f9a67a6dab85c936beeabb8f7fba2fe89be`;
native 17646656 bytes
`f4648bcfd02bbbabb7d2a5ac4719d62c9c62d5eb6c79f3a2b61770eda53bd668`;
kernel 55721984 bytes
`ad7e70f7e615494c6162cec1a72610e119e897414bb89e4e038075244442da2f`.

Stopped at kernel: `scripts/build-ufs-apfs-root-chmh-r35.py` pins the original
kernel and its inherited `check_inputs` requires the fixed CHMH digest. No
supported r35b new-kernel packaging entry was identified; no digest binding,
authentication bypass, image or device operation was attempted. The inherited
build tag remains r35. Runtime and authentication remain unverified.
