# Display property readback — host self-checked

## Follow-up: held property references and scanout bridge counters

The board obtains `width` and `refresh` with `copyProperty`, casts and checks
while each reference is held, then releases each exactly once. Other presence
checks use `getProperty` without dereferencing the result. `PROP 0000` does not
distinguish an unrun sample from a completed sample with all properties absent.
The `copyProperty(const char *)` call is virtual: the board introduces no
direct symbol import; the host ABI audit asserts the existing vtable import and
leaves it in the strict unresolved fingerprint.

The following row is `SC n=%u r=%u o=%u` (at most 41 characters for three
32-bit counters). It replaces row 11's second history entry or trace line;
the separate `stg`, EX, X1, DSP and CLI lines are unchanged. Counters are
relaxed atomic samples, independently read, and wrap at 2^32. `calls` counts
bridge entries; `rejects` counts failed display/console/interrupt/renderer
checks; `ok` counts successful bridge returns.

The upstream `kickOnce()` can reject requests before reaching this bridge:
`calls=0` means no bridge entry, not necessarily no incoming swap.
`calls>0, ok=0` means no successful bridge return observed (subject to
independent sample timing), not a diagnosis of earlier request validation.
`ok>0` means handoff succeeded, not that a CPU copy happened: the call sites
include blank fill and a path before GPU/CPU selection, and further checks can
fail. Successful handoff may stop diagnostic page repaint before the increment
can be shown. The counters do not prove a completed frame.

**deep_reviewer must re-review property lifetime and atomic access**, including
the three independently sampled counters, before runtime use. No device
operation performed.

| Follow-up artifact | Digest |
| --- | --- |
| kernel SHA-256 | `a6f2218eb2ee544390d344c1b555c9d5b226f70d7d702e971079af79f24525a5` |
| outer SHA-256 | `9b1620e2b41c38e55f32ef406b9205f6032e753791c998ec1f9b18142daeb708` |
| FAT from outer SHA-256 | `fa98a4fb360c419b2f19a34bda7f8b08e5277f5dc1b77ad3bca5b25c790072e1` |
| experimental CHMH SHA-384 | `7e1b83593cab2c146b39e83e99ab46d597354859eccb5871bd68d85037eb5b629eed94c07362e30b049b0ebc2d69ab29` |

Build `out/nuwa-prop-sc-resume-build-r2-20261122`, package
`out/nuwa-prop-sc-resume-package-20261122`, separate audit
`out/nuwa-prop-sc-resume-audit-20261122`. Outer config is byte-identical to
the prior resume-only config; `fsck.fat -vn` and `mdir` report 11,898,368 B
free. Self-checks: property/FDR/scanout source test and linked exception,
register and IRQ-guard tests. Independent verifier should rerun those tests,
the `--mg-reset` compact build and the resume-only package/audit commands from
the previous candidate using the new kernel hash and fresh output paths.

## Previous candidate

The registration-return path reads existing properties only, then publishes one
16-bit relaxed atomic sample. No registration, property publication, 329 guard
or HID logic changes. A zero mask before this path is indistinguishable from
all properties absent; `DSP s=4` is an independent relaxed sample and does
not provide an acquire/release ordering guarantee.

| Bit | Observation |
| --- | --- |
| 0–2 | nub: `canvas-width`, `canvas-height`, `device_type` present |
| 3–7 | display: `IOMFBNumLayers`, `IOMFBDisplayRefresh`, `NormalModeEnable`, `ADCLLoadAll`, `IOFBRotation` present |
| 8 | refresh present but not an `OSDictionary` |
| 9 | width is `OSData` and its length is not 4 |

Bit 9 does not diagnose a non-OSData width; the publication path constructs
OSData. No property value, client matching, frame presentation or runtime
success is established by this host build.

The existing FDR row is `PROP %04x FDR %us st=%u sig=%u`, or
`PROP %04x FDR no exit seen`. The worst representable formatted line is
42 characters; other page rows are unchanged. Screen geometry and whether the
page remains visible are runtime observations.

| Artifact | Digest |
| --- | --- |
| ON kernel SHA-256 | `591957c24f510e5e77c43936fe6480cd874dce49fb0b3b48b09db51b3ebbb1f9` |
| outer SHA-256 | `16e34f9e461ce32125c6d694cd74bbb6681551148ec9381a367f13f080babedb` |
| FAT read from outer SHA-256 | `cdc51a8099ccc9144a65bb50850ee8b8d0f47fbaae87e7e8ec7bfb3fba7a28f2` |
| experimental CHMH SHA-384 | `63f206be925cfc06e18ec83de6c555b9f6a0a462ed160f45f38c4d7c9d46b2430f9880e2bc3fcabfc6a52a01654db345` |

Build `out/nuwa-prop-resume-build-r2-20261122`, package
`out/nuwa-prop-resume-package-20261122`, separate outer audit
`out/nuwa-prop-resume-audit-20261122`. Outer readback contains
`nuwa-lite=1 nuwa-mg-reset=1`, no `sheng-data-reset`, and otherwise the
documented resume-only arguments. `fsck.fat -vn` and `mdir` report
11,898,368 bytes free (minimum 8,388,608). Audit re-extracts outer content
and checks rebound CHMH. Upstream main was `8542980d02b4d2cc5c32ee3542de1760b2562aac`
both before and after build; local base stays pinned `693f5d9cae8a408dd18b39f3f9fdc4228c934241`.

Self-check: FDR/property source test, MG syscall model, and linked
`test-r35g-ux-linked.py`, `test-r35k-regs-linked.py`,
`test-r35e-irqguard-linked.py`. Initial archive audit failed its strict
unresolved fingerprint because new type-check imports were not inventoried;
the checker now verifies their exact owners before preserving the old
fingerprint. Initial packager rejected the new kernel pin; the exact new hash
was added without removing the previous pin.

Reviewer must re-review read-only sampling and row width. **deep_reviewer must
review the relaxed atomic usage, property object lifetime and the exact
packager pin change before runtime use.** Independent verifier should repeat
the build and package/audit using the commands in
`docs/nuwa-r35l-display-dsp-20261122-observation.md` and
`docs/nuwa-mg-reset-20261122.md`, adding `--mg-reset`, and rerun the tests
listed above. No device operation was performed; authentication NOT REACHED.
