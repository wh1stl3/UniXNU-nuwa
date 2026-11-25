# Display counters — 2026-11-25

Host-only diagnostic; no device access or flash. This version only adds
observations and does not change ABI calls, validation, transfer, vsync,
timeouts or delays. Runtime display behavior is not established.

## Hooks and interpretation

The counters are `volatile uint32_t`, incremented using relaxed atomic
fetch-add; independent samples need not form a consistent snapshot.

- `reg`: board `package/NuwaLegacyDisplay.cpp:286–287`, registration callback:
  the component calls it immediately after the **void**
  `IOService::registerService` returns (`UniXNU/drivers/GopFramebuffer/NativeLegacyDisplay.cpp:524–531`).
  This is a registration call returning, not proof of matching or of an
  independently reported success status.
- `cli`: board `package/NuwaLegacyDisplay.cpp:316–318`, only when its `IOReturn`
  equals `kIOReturnSuccess`; component call at `NativeLegacyDisplay.cpp:857–860`.
- `vo`, `vb`: board `package/NuwaLegacyDisplay.cpp:329–330`, separate
  accepted and rejected callbacks at the end of `validateSwap`
  (`NativeLegacyDisplay.cpp:785–837`).
- `ret`: board `package/NuwaLegacyDisplay.cpp:338–339`, after
  `completeCurrentSwap` returns (`NativeLegacyDisplay.cpp:743–753`).
  This is not a panel vblank or hardware fence.
- `co`, `cb`: board `package/NuwaLegacyDisplay.cpp:333–335`, success and failure
  status respectively. These are **transfer callback outcomes**, not exact
  copy counts: `NativeLegacyDisplay.cpp:583–604` also reports successful
  blank fills and `:590–596` reports failures before a copy starts.
- `vy`: board `package/NuwaLegacyDisplay.cpp:342–343`, event 1 after the sender returns
  (`NativeLegacyDisplay.cpp:412–418`). The current build compiles the sender
  and this callback out, so `vy=0` does not establish that a client waited.
- `ve`: 0 from `package/NuwaLegacyDisplay.cpp:283–285` under the
  `NUWA_DISPLAY_HOST_NO_SOFTWARE_VSYNC` compile-time
  configuration for this build, regardless of boot arguments. Other builds
  lacking this specific state export display `?`, not a guessed enabled bit.

`vs` is omitted: the accessible validation callback runs at exit, not entry;
it cannot establish that every entered invocation returned. It must not be
called submit either. `pr` is omitted: the available scanout preparation
bridge is not a present-attempt hook. `vq` is omitted: no board callback
reports client registration or request. If a future qualified `vq` hook shows
`vq>0 && vy=0`, clients requested vsync and no notification was observed:
that is a direct possible explanation for backboardd not submitting frames,
not proof that a client remained waiting or that this caused the stall.
`native_legacy_swap_stage(1)` is on GPU/direct-flip paths and is not a CPU
swap count.

The generated banner uses two rows, `DSP reg=%u cli=%u vo=%u vb=%u`
and `DSP+ co=%u cb=%u ret=%u vy=%u ve=%u`, both at `PROC` priority;
zero-event rows are emitted. The selection budget keeps or drops both rows
together. Existing yield checks between row paints remain unchanged, so a
yield or scanout handoff can still interrupt a physical paint between them.
The whole group can be dropped if higher/equal-priority rows fill the budget.

## Host fixture

`tests/test-nuwa-dspcount.py` self-checked zero, partial, all counters nonzero,
and synthetic `ve=1 vy=2`: maximum widths 61 and 66 columns. It checks the
actual generated formatter, 78-column limit, `PROC` priority and group budget
against the actual selector. A `vq>0` combination cannot be represented
because the field is unreachable. `tests/test-nuwa-peer-probe.py` and
`tests/test-nuwa-crashcap.py` also self-checked.

Rollback outer SHA-256:
`4a83a8e4b5ba6feeef761dd6cfa65697a5e8325e71694057857d7e15f784b4d9`.

## Package and audit

`out/nuwa-dspcount-20261125-package/vendor_boot.img`; single-core build,
no `sheng-smp`, 561-byte args and seed unchanged from stack900. Outer readback
and pure-Python FAT audit checked the complete file set and CHMH rebinding;
only kernel and its ADT differ from stack900, which retains the same args and
seed as the rollback outer. FAT free **11,025,920 bytes** (at least 8 MiB);
`fsck.fat -vn` and `mdir` also self-checked. The CHMH is experimental and
authentication remains NOT REACHED.

| Artifact | Digest |
|---|---|
| Kernel SHA-256 | `cbd508fead33ca9f43f23d890432578642fc86d857258f20b490adf052213631` |
| Outer SHA-256 | `7c8ee0d61e61951a6115e955dd650461848a0ab16111a89ce2816d6b2e7aba73` |
| CHMH SHA-384 | `54ea450840ba0cd9ba4f2a02b7f2686653e459993f9822edc7a5df093ee71f2ad66bf5b97309134fdf6bbb58339b2ea2` |
| Outer-readback FAT SHA-256 | `3469d6b8048fd07cc7b907a0a65bfd9232efc8ac9df66e6f3529ed3bde3d0985` |
| Seed SHA-256 | `3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e` |

Independent verifier should rerun `tests/test-nuwa-dspcount.py`,
`tests/test-nuwa-peer-probe.py`, `tests/test-nuwa-crashcap.py` with the
candidate kernel, the single-core build recipe in
`docs/nuwa-crashcap-20261125.md` with a fresh output, then
`scripts/package-nuwa-crashcap.py --audit-only` against this package and
`fsck.fat -vn` on `readback-fat.img`. The final build and tests have not
been rerun by an independent verifier.
