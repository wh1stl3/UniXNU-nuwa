# HID stand-in touchscreen identity

Before this change the first application collection was keyboard (report ID 1);
touch screen (ID 3) came second. Digitizer properties were written only to
the interface and event driver after matching. Consumers filtering on initial
matching could therefore see keyboard identity and miss the digitizer.

The stand-in now sets Built-In and DisplayIntegrated to true and primary usage
page 0x0d / usage 4 on the device itself in init, before attach and start.
HIDDefaultBehavior remains set. The touch screen application is first; the
keyboard remains second to preserve the existing generic keyboard personality
and report ID rather than changing the set of advertised collections. No
reports are generated. The existing post-match child properties remain.

`IOHIDInterface` and `IOHIDEventDriver` are created by the donor HID stack.
The existing checkpoint writes their properties only after registration; this
change does not implement pre-publication injection. If backboardd matches
the child chain rather than the parent device, this change may be insufficient.

The `nuwa-hid-standin=1` gate is unchanged. This is an identity-only software
stand-in, not real touch support: `native_touch_set_sink` and button sink remain
empty, and no input event path is added. Actual initial matching and whether
the family preserves these properties at publication remain unverified.

Reviewer: re-review property timing and publication, descriptor validity and
global item state, and the unchanged opt-in behavior. Independent verifier
and device execution remain pending; authentication remains NOT REACHED.

Host build self-checked with the r35l display recipe, `--mg-reset` and
`--hid-standin`: kernel SHA-256
`27a287d37a964306cf85c0600cf07b471e2069b111bb087f930e22ddb9076bcb`.
The `2169998` outer-readback args contain no `nuwa-hid-standin=1`, so its
stand-in was disabled. This alone does not prove that no other HID device
existed. The user selected appending that token for the next candidate.
Strings attributed to
backboardd suggest a main digitizer wait but do not identify the matched
registry class or prove its complete matching predicate. No device operation
was performed.

## Candidate package — self-checked

Built using the r35l display recipe with `--mg-reset --hid-standin`, then
`out/nuwa-systemgroup-seed-20261122/repack-hid-touch-identity.py` with the
same SystemGroup seed. The wrapper compared the complete outer-readback args
against the `2169998` package: the only addition is `nuwa-hid-standin=1`.
The two restart arguments are retained, with no `nuwa-sb-dump` or
`sheng-data-reset`. The seed read back byte-for-byte unchanged.

| Artifact | Digest |
| --- | --- |
| Kernel SHA-256 | `27a287d37a964306cf85c0600cf07b471e2069b111bb087f930e22ddb9076bcb` |
| Outer SHA-256 | `d8b9677a0fcff868747800a3ee4f4c38fd3be2a5283c50bde19c148721ef441e` |
| CHMH SHA-384 | `dea82bca45b4cde0681147238f2b59d4067c7c0eeb4c3f04a1096968ecd28843e69500791a4ff05b071fe679edddcde2` |
| Outer-readback FAT SHA-256 | `3dfb22b8401b8f94fea35e1688076b1e1151214d3b5cf9ffa4a21bc1b28ca036` |

FAT free space is 11,664,896 bytes (minimum 8,388,608). Readback args
SHA-256 is `f30cc414da9b208176ea0e64a28a2ad477496ac02398681a29d717b7f356e36d`.
The wrapper, staged seed and images remain local under `out/`. Reviewer must
re-review property timing, descriptor order and state, opt-in, single-variable
args and the child limitation. The independent verifier should rebuild using
the r35l recipe with both flags, rerun the wrapper into fresh local paths,
and independently check the CHMH, outer readback, FAT free space and args.
