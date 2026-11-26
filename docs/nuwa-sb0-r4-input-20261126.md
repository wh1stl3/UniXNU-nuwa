# Exact r4 physical input — no-grant, no-storage EFI probe

**Host self-checked.** Neither r4 nor W has been modified or run on a
device. No startup/deployment change. This application reports an input
observation, not an authorization or a receipt that W can consume.

## What r4 provides

Rehashed `boot-stage12-v4-r4.img` (`692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5`),
decompressed the pinned slice (offset 4096, length 1,483,112) and compared
the result to the prior independent extraction. Its 192-byte shim precedes
the FD SHA-256 `85bb651a746304343f5baf0d2e1f158405b4054e7886a2815e568fde59fd9256`,
which also byte-matches the retained build FD. FFS GUIDs and PE SHA-256:

| Module | FFS GUID | PE SHA-256 |
| --- | --- | --- |
| ButtonsDxe | `5bd181db-0487-4f1a-ae73-820e165611b3` | `9e176cf82aecb6fed29aa96768ac1eaec79d88d03357d164b799f19632477f1c` |
| ConSplitterDxe | `408edcec-cf6d-477c-a5a8-b4844e3de281` | `6b48fcc4ab0817bfcacf567dd101b830dbb2c9a7f46ae14325ac359fe8527bda` |
| SimpleTextInOutSerial | `6696936d-3637-467c-87cb-14ea8248948c` | `cfe18c628a4c903ca69a91edc6a15410737f292453fd88ca5b8c3b90126108d2` |
| PmicDxe | `5776232e-082d-4b75-9a0e-fe1d13f7a5d9` | `c130806b51f668f54c0498d757e6713739ac636ac70f1fe6c463d62f94c51671` |
| RngDxe | `b0d3689e-11f8-43c6-8ece-023a29cec35b` | `d02252fe6dfa37af22c9daffb988839308e5049acb0e47199796a3ce5beb6935` |

Fresh host decompression of the r4 guided section and FFS extraction
byte-compared all five PEs plus BdsDxe and UFSDxe to the retained files.

- **Dedicated handle exists, but TextIn/Ex is not physical-state proof.**
  ButtonsDxe `0x2018–0x2054` installs SimpleTextIn, TextInEx, and the
  hardware vendor device path `d7f58a0e-bed2-4b5a-bb43-8ab23dd0e2b0` on
  its image handle. BDS also contains that device path. `ReadKeyStroke`
  `0x14c0` and `ReadKeyStrokeEx` `0x15a4` return 4-byte scan/Unicode
  queue entries; the Ex state flags neither identify a VOL+ release nor
  date the entry. `WaitForKey` (`0x1cdc`) indicates queued/available
  input, not physical key-up. Initialization `0x1e38–0x1ef0` can read
  PMIC SDAM key data, and `0x1b4c–0x1b78` can use its cached transform
  (`0x1ac4`) before queueing. An empty queue or Reset is not evidence of
  release. The exact FD also contains a separate serial SimpleTextIn
  implementation. ConSplitter (`ConSplitter.c:3338–3395,3448–3488,3605–3702`
  in the retained BaseCore workspace) returns saved keys or polls the
  underlying devices; it does not propagate source identity to the caller.
  Exact live membership of ConIn is not claimed. Do not use it for admission.
- **Independent physical source: VOL+ current level.** ButtonsDxe
  `0x3cc8–0x3ce8` locates GPIO GUID `4bc5c6d7-4ca4-8835-d1bc-d29cc2025d4a`.
  Its VOL+ `ReadGpioStatus` `0x3928–0x396c` invokes slot `+0x38` with
  `EFI_STATUS EFIAPI (UINT32 pmic=1, UINT32 gpio=5, UINT32 type=0,
  BOOLEAN *out)`, without a `This` argument, and treats raw 0 as pressed.
  These values are from the button table at `0x684e/0x6856`, not copied
  from another device. PmicDxe `0x1740–0x1754` publishes that GUID with
  interface RVA `0x2f3b0`, revision `0x30000`; its `+0x38` slot points to
  `0x1b50` → `0xb65c`. Selector 0 takes the real-time branch via
  jump table `0x2a540`, then reads a masked current bit via `0xa054`
  and writes one Boolean; it does not drain a queue or clear a latch.
  The historical nuwa FDT describes VOL+ as active-low GPIO6 on
  `qcom,pm8550-gpio` (`phandle 0x5b9`), consistent with zero-based index 5.
  This is static evidence of a release/press distinction; hardware
  availability, polarity over an actual press and display remain untested.
- **Do not substitute PON.** The r4 `GetPonRtStatus` call in ButtonsDxe
  `0x3e0c` locates `9ba45b66-efa4-441c-a3e4-ed2224786be2`, not the older
  open header's `97044b58-…`. Exact PmicDxe's published interface at
  `0x2f360` has slot `+0x18` pointing to `0x1914`, a constant
  `EFI_UNSUPPORTED` return. The probe does not call it or use VOL-/power.

## No-write executable and launch contract

`out/sb0-r4-input-build-r2/SB0-INPUT-NO-GRANT.efi` (AArch64, 5,632 B),
SHA-256 `c1f9eb03f124a6a2e0e5395ee7e2de442aa00177b43bc17def8abd227a06c9d6`.
This standalone EFI application must be explicitly started before EBS under
the exact r4 FD after ButtonsDxe, PmicDxe, RngDxe and output are available.
It needs an independently approved volatile EFI launch path; no FD, boot
entry, package, partition, shell or launcher was built or altered here.
Do not auto-start it on normal reboot. It returns to the caller, never
loads W and never calls EBS.

It requires the exact dedicated button path, not `ConsoleInHandle`, with
both input protocols on the same FFS image handle; it never calls their
key methods. It checks unique PMIC/RNG handles, FFS image identity and
the pinned interface/function RVAs. These checks are not firmware
authentication. Output names the exact W outer, LU0 LBA 57393401,
4096-byte length, logical seed identity and payload hash. The attempt ID
is 32 bytes returned by the exact `EFI_RNG_PROTOCOL` provider, with no
timer/serial fallback. The final `NO-GRANT RELEASE-PRESS-RELEASE`
line repeats that ID. An external observer correlates BEGIN and result;
the application never ingests a previous record and does not attest that W
was actually loaded. No nonce, key, result or grant is persisted or sent to W.

Then, after the prompt: three released samples, three pressed samples after
READY, three released samples, at nominal 20 ms spacing. Any initially held
sample refuses, bogus status refuses, ordinary idle and a continuous hold
expire after the bounded 1,500 samples, and cached/serial keys are not read.
Freshness is per invocation; actual RNG behavior across reboots remains
untested. A bare copied console result cannot authorize anything.

## Old firmware UFS producers

The exact r4 FD extracted UFSDxe PE SHA-256 is
`2194af1a049bac42e3ea205d8fa22c24f8de34b2363ca4a3e66f8d42390ce802`,
the **same binary** as the prior accepted retained-route residual in
`out/nuwa-ufs-ownership-trace-20261114/TRACE.md` (original device worktree).
That establishes static registration and the `0x369c` EBS callback's
command/timer paths, not live callback completion, final SFS/BlockIO
activity, producer cessation, old descriptor lifetimes or SID/domain
exclusion. The standalone probe leaves this issue unchanged: it has no
storage protocol or handoff, adds no UFS producer, and does not run a new
W handoff. A later launch or authorization changes timing and does not
inherit live evidence from that static trace. A local lock or fresh button
sequence is not a fence for these producers.

## Reproduce on host

`out/audit-r4-button-input.sh` verifies the FD and selected retained PEs;
`out/sb0-r4-input-audit/` contains the input disassemblies and GUID census.
Build the application from this worktree:

```sh
python3 -B scripts/build-nuwa-sb0-input.py \
  --r4-boot ../UniXNU-nuwa/.cache/boot-stage12-v4-r4.img \
  --w-outer out/W-package-r8/vendor_boot.img \
  --sb0 out/sb0-generator-check/commit-sb0.bin \
  --basecore /home/wh1stl3/nuwa-fw/mu_basecore --out out/<fresh-dir>
cc -std=c11 -O2 -Wall -Wextra -Werror -fsanitize=address,undefined \
  -fno-sanitize-recover=all -no-pie tests/test-nuwa-sb0-input.c -o out/<fixture>
out/<fixture>
```

The build reuses Mu BaseCore MdePkg protocol headers from the local r4
build workspace (nuwa BaseCore submodule pin `cfb93724…`, BSD-2-Clause-Patent);
it links no external library. Host checks ran: five state fixtures,
ARM64 EFI header/import/unsigned audit, no media protocol GUID, no SB0
payload, and unchanged W input hash. Evidence in the build `audit.json`
and disassembly. Host results only; independent reviewer/verifier pending.
