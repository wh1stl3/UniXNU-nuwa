# AMNM observer host-only derived package r1

**Self-checked only; independent review/verifier and a new device authorization
are required.** No device command, commit, push, old-package overwrite, pin
change or kernel relink. This is neither the old STOP profile nor the old
continuation profile. The existing schema2 owner record remains unchanged; a
separate `amnm-derived-input-v1` record binds it as parent.

`out/amnm-observe-20261111-r1/` is an exclusive new output. The FAT starts as a
copy of the pinned independent continuation FAT; only the already-instrumented
kernel member is replaced via mtools. The old continuation validation and
schema2 artifact binding are checked first. Its exact ADT/BNCH/random seed,
trust bytes and `-v serial=3` args are retained to control input variables;
no fresh generator invocation or owner patch is claimed. Both the new FAT and
the FAT re-extracted from the actual outer were completely extracted and
checked with the existing `verify_extracted` semantics.

| Input/output | Bytes | SHA-256 |
| --- | ---: | --- |
| AMNM kernel | 55402496 | `1754a89e8e92e20baafeaf0e1f98361b0d41ddaea8f420dd44d34d1357f2d162` |
| Parent schema2 record | 1077 | `a7ca5cc8a15353a9dee8882a1f89e0633a44ff950514ebe6ad58c4567ac20b57` |
| Exact parent ADT | 13256 | `885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4` |
| Trustcache | 66272 | `367e051548f9f0407fa9fe9d40007fa4e7c5ff27c45f5a7a30cedf344e24d98e` |
| FAT `payload.img` | 67108864 | `7074311dc2e2d3e0e71432b150a4bbef557625e27412a98b1464a7736f11c1fa` |
| outer `vendor_boot.img` | 100663296 | `c5784135e3bb03e371808510dc0031fe3641782fd5fedf852fd7401783c0ddef` |

Readback configuration hash is
`7b2ac4be356c5b6070b887057aa734219e45b70767a6d6faf1307b712576e931`;
one XNU entry, three actions and default `xnu` were checked. No CHMH/love or
memory-map/DeviceTree property is fabricated. The fixed r4 loader remains
`692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5`.
The outer uses the existing historical stock template `5ad2a9dc...ad68cc23`,
not the different current backup `493ca426...970a8dad`. The official outer
command and exit are in `official-command.json`; the existing comparison
checks header/table/footer preservation, DTB, bootconfig, vbmeta, padding,
ramdisk identity and 100663296-byte GPT capacity. No AVB authentication is
claimed.

`report.json` and `amnm-provenance.json` bind the final manifest, native map,
verifier audit, audit script hash, parent record and exact output hashes.
Recomputed final Mach-O root VM span is `0x43f7000`; relative r4 offsets are
Args `0x43f8000`, Tree `0x43f9000`, Trust `0x43fd000`, Top `0x4410000`.
Root load ranges and all three AMNM zero-fill objects were checked; the actual
physical allocation/window, page tables and runtime stack are not observed.

## Commands actually run

WSL Ubuntu-22.04 root cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`, all exit 0:

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/build-owner-amnm-observe.py
/home/wh1stl3/.local/bin/python3.11 -B scripts/test-owner-amnm-observe.py
/home/wh1stl3/.local/bin/python3.11 -B scripts/audit-owner-amnm-observe.py
/home/wh1stl3/.local/bin/python3.11 -B scripts/audit-owner-amnm-observe.py --output out/amnm-observe-20261111-r1/amnm-provenance-selfcheck-r2.json
/home/wh1stl3/.local/bin/python3.11 -B /mnt/d/Code/PortingiOS/UniXNU/scripts/porting-record.py check --device .
```

AST syntax checks and `git diff --check` also exited 0. The eight negative
checks reject wrong profile/type/parent/kernel/args, changed ADT and two outer
tamper cases. They are self-checks, not an independent run. Source SHA-256:
`build-owner-amnm-observe.py` `822e96cc447b771d830ff99ee2bafa21282245f807ba47cfef666bcdf0c237f5`;
`test-owner-amnm-observe.py` `aea2e78e19b2944f5cf7ca543db0a994c590a44793a7aa41d1883e5a0e352566`;
`audit-owner-amnm-observe.py` `57603d44bd87ab88a4ebb99622aac92df8d1e1089b1dcd09df8fa2e541b4cff5`
(the first invocation preceded the addition of the `--output` option; the r2
invocation used the stated final source).

Expected observation is original panic text followed by an AMNM snapshot
summary when display and space permit. `associated=0`, lost or absent output
does not establish causality. Renderer uses a local text buffer; boot-progress
banner integration and real display remain unverified. No executor profile or
device run was created. Final integration and device authorization are the
parent's responsibility.

## Packaging audit r2 — self-checked, independent rerun pending

Review requested stronger evidence binding; no image was rebuilt or changed.
The revised audit parses the actual outer, requires its ramdisk to equal the
actual pinned FAT byte-for-byte, reuses the reviewed stock/outer comparison,
then extracts and checks all four members against the fixed kernel and the
parent's ADT, trust, configuration and schema2 record. The derived record
continues to be checked separately. It rejects matching changes to payload or
outer and the report hash, and independently pins the manifest, verifier audit,
native build result and map; a changed winner address inside DATA is not
accepted just because it remains within the range.

These four digest pins match the existing **self-checked packaging-time**
`amnm-provenance.json`: manifest
`640d5d9602b1aa5a5c438e4b190b829e8b6fe8494fb1e8ca2c879ce35028f53a`,
verifier audit `b316df8ab1a17c48a6b948aac8e4e5f2b4986b818959e96aedd0c5f9035d4109`,
build result `04f1db2246b5ebe03a826c7751816bf3963f1ea8c097c4aaf2a21fa4bb2d8fca`,
and map `237499b08b36b4f0cb16465dbabd18cf0d949ce1243e6927d3561091996d00f9`.
The verifier audit is the actual independent report named in the brief. The
available earlier record does **not** establish an independently witnessed
historical hash for each of these four files; their digest freeze here is based
on that earlier self-checked provenance and actual bytes, not a claim of such
historical independent witnessing. The parent/verifier must resolve that
evidence boundary if an independently recorded historical digest is required.

Audit source before/after SHA-256: `57603d44bd87ab88a4ebb99622aac92df8d1e1089b1dcd09df8fa2e541b4cff5`
→ `e72189593cf1e8a742aabdd7c538d7e1adcd80cee77b99e1f27572fb5f72dc7a`.
Test source before/after: `aea2e78e19b2944f5cf7ca543db0a994c590a44793a7aa41d1883e5a0e352566`
→ `ac8531e7870e7881f6ce1e0cd23072d069a01154b667addc8320b8fd2cb717be`.
The unchanged builder hash above matches its packaging-time value. Current
dependency hashes are preserved in
`out/amnm-package-audit-r2-20261111/source-dependency-hashes.txt`; earlier
before-edit hashes were not captured for every dependency, so no unsupported
before/after equality is claimed for them.

Actual WSL root cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`, both exit 0:

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/audit-owner-amnm-observe.py --output out/amnm-package-audit-r2-20261111/audit.json
/home/wh1stl3/.local/bin/python3.11 -B scripts/test-owner-amnm-observe.py
```

The audit's own `mcopy` exited 0. Original eight negatives and four targeted
synchronized-mutation negatives were rejected. The old verifier run does not
verify this revised audit; use a new output path for the required independent
rerun. Runtime/device conclusions remain unchanged.

### r2 resumed: explicit parent member pins

The r2 implementation above survived the cancelled task. A resumed inspection
found that `validate_inputs` pins the parent FAT and record, but the separate
parent trust/config files used as extraction expectations were not themselves
compared to fixed digests. The audit now pins their full hashes to the values
in the table and configuration paragraph above before comparing outer members.
Two isolated in-memory parent-member mutations are rejected. This is a new
self-check, not an independent verification or a new image build.

Final audit source SHA-256 `283507b2cc44dc9c678c0a64d4d3f4def548681b6a9270e3b9dd88d206d42e48`;
test source SHA-256 `a55a97235fe21f8969467cf7fa8de9b721aa298128192697bb875f620938f09a`.
The unchanged dependency digests and test output are in the exclusive
`out/amnm-package-audit-r2-resume-20261111/`; this does not overwrite r1 or
the earlier r2 evidence. WSL Ubuntu-22.04 root cwd
`/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`, both exit 0:

```sh
/home/wh1stl3/.local/bin/python3.11 -B scripts/test-owner-amnm-observe.py
/home/wh1stl3/.local/bin/python3.11 -B scripts/audit-owner-amnm-observe.py --output out/amnm-package-audit-r2-resume-20261111/audit.json
```

Independent reviewer and verifier must use these final sources and a fresh
output path. The four evidence-file historical witness limitation above remains;
no device action or release is authorized by this host-only check.
