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
