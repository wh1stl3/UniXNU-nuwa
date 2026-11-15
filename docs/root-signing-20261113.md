# nuwa real root policy input — 2026-11-13

Host-only, self-checked; no kernel link, payload packaging, device operation or
Apple authentication. The parent supplied ordinary reviewer PASS WITH CONDITIONS
for the selected volume identity; its independent mechanical verifier was still
running when signing began. System volume UUID is
`DADD93F8-DBBF-4B17-A1DF-0F11E64172F7` (`SydneyUpdate20H392.D22D221OS`, role 1),
not container UUID `0E25F331-6279-458A-9CFE-F39598DA17AA`.

Input is the complete `out/root-inputs-20261113/os-window.raw`, 5635081728 B,
SHA256 `6e87bfcaa8eca952e00b719f333d1f1060715a63566112267ad8730e1ed98906`;
not the smaller partition span, DMG container or whole userdata. Existing
userdata image SHA256 `2c2aca3feb7585c91b80ec6b50cc1888ac9315f4c77d981566de5dd902eabefa`
was not modified. Input and anchor SHA256 were rechecked before signing.

Reused `UniXNU/VerifiedRoot@974f043d0c71ba2e60331483a41c6c6d35274ee3`,
BSD-2-Clause-Patent, `tools/manifest.py`, `tools/verify_image.py`, and the
unchanged real C verifier with its OpenSSL test adapter. Const-table layout
follows `UniXNU/scripts/build-verified-root-probe.py:106-118`; RootAnchor.c
follows `scripts/build-sheng-source-storage.py:164-166`.

Existing nuwa owner key was reused, never printed or overwritten. Public DER
SHA256 is `717c2e0323dd356862829180a026f825fab1650d9eadaa3e5a301a513bf9fb43`;
395-byte anchor SHA256 is
`6546a28755f44ab823c70f2da5e7e556b01a1fffe75275e02a26ab6e80625043`.
This is an experimental software owner trust domain, not Apple trust. Generation
1 and minimum 1 are not persistent anti-rollback enforcement.

Official manifest generation exited 0, signed UUID and input SHA as above,
1375753 blocks, generation 1. The 44024640-byte manifest SHA256 is
`349efb16d2aa56b82317bfa0535d0036afa1067b810d664413fba73ce55da594`;
44024096-byte block table SHA256 is
`0ad98b1447ccd5326326fa264554a8ed4a74d5f5d3f66c588d1413d2fff6e24e`.
The first signing wrapper failed before signing due to shell quoting; corrected
invocation completed. The first host-library compile failed from PowerShell
variable interpolation; corrected compile completed.

`out/root-signing-20261113/libNuwaRootInputs.a` is 44026480 B, SHA256
`24a0499d5de6c8ae0cad70e1f22af0f6b8e4b91c519e8a8379d147e0a5752d29`.
It contains `RootAnchor.o` (872 B, SHA256 `fa7cccfb60d02b7c75157739f0bfd64725412c82433e6774be859ee3f2409532`)
and `RootPolicies.o` (44025240 B, SHA256 `8ed331c2e4c61453f52ba8cd3c19c194c793bc1b4e5e52154871c527c086077d`).
The latter contains one full manifest, one const `{pointer, length}` record and
count 1; llvm-objdump shows the pointer relocation in `__DATA_CONST,__const`.
It is a host input object, not a linked or runtime-qualified kernel. Build
commands are in `build-commands.json`; `build-inputs.py` and `negative.py` are
retained with the ignored output.

Negative checks using the C verifier returned status 2 for one-bit modified
structurally shaped public anchor, 3 for signature mutation and 5 for modified
block. This wrong-anchor control is not a second independently generated RSA key.
The official verifier with the container UUID instead of the system UUID exited 1.
An initial wrapper printed a misleading `exit=0` due to shell interpolation;
the direct invocation's actual exit 1 and rejection message were captured.
Official `verify_image.py` exited 0 after real RSA verification and all 1375753
original blocks, and confirmed the signed full-image SHA256 and system UUID.
The host-only result is `out/root-signing-20261113/verification.json`.

Capacity: the current FAT is 67108864 B. The 44024640 B manifest plus the existing
r5 kernel 55451648 B totals 99476288 B, exceeding the entire FAT by 32367424 B
even before FAT metadata or other files. The actual final linked kernel and its
memory window were not built or measured. No capacity, check or policy was reduced.

Independent verifier can reproduce from the device repository under WSL:

```sh
python3 /mnt/d/Code/PortingiOS/UniXNU/kits/VerifiedRoot/tools/verify_image.py --library out/root-signing-20261113/libvr-host.so --manifest out/root-signing-20261113/signed/manifest.bin --trusted-key out/root-inputs-20261113/owner/trusted-key.bin --image out/root-inputs-20261113/os-window.raw --volume-uuid DADD93F8-DBBF-4B17-A1DF-0F11E64172F7 --minimum-generation 1 --output out/root-signing-20261113/verifier-verification.json
python3 out/root-signing-20261113/negative.py
sha256sum out/root-signing-20261113/signed/manifest.bin out/root-signing-20261113/libNuwaRootInputs.a
git diff --check
```

The verification output path is separate; no private key access is needed. The
negative script writes its own existing ignored `negative.json`; run a copy in a
fresh directory if preserving that record is required. Independent verification
and integration acceptance remain with the parent.
