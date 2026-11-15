# CHMH / ASMB host experiment

**Proposed experimental domain, not authenticated and not an Apple manifest.**
CHMH is SHA-384 over the bytes `Nuwa.HostBootSetIdentity.v1\0`, followed by
five ordered records: `kernel`, `loader`, `trust`, `args`, `parent-adt`.
Each record is one unsigned byte of ASCII label length, the ASCII label, then
the 32 raw bytes of SHA-256 of the corresponding input. `args` is the exact
UTF-8 byte string `-v serial=3`; parent-adt is the unmodified input, never the
derived ADT. The evidence records the complete preimage. This is a proposed
test binding only, pending ordinary reviewer assessment; it is not a candidate
or an assertion of authenticity. BNCH is not used as CHMH.

## Self-checked results

The existing initializer runner and its ADT-backed IOKit fixtures are reused;
the real initializer starts at `46e98cc`, not a fabricated intermediate state.
Both selector calls naturally execute with `x1=0,1`. The first descriptor is
`5cae660`, level 0 in every completed case. The second selector is:

| Fixture | Second descriptor / level | CHMH helper | AMNM | Stop |
| --- | --- | --- | --- | --- |
| baseline | `5cae660` / 0 | 2 | 1 | `46e9b2c` |
| CHMH-only | `5cae660` / 0 | 0 | 1 | `46e9b2c` |
| ASMB-only, both SMB | `5cad510` / 2 | 2 | 1 | `46e9b2c` |
| both, both SMB | `5cad510` / 2 | 0 | 1 | `46e9b2c` |

CHMH-only publishes the 48 test bytes in `5cad030` (length field 48),
whereas baseline leaves the digest object unchanged. Both reach the same old
boundary, so this does not resolve the device block. Empty ASMB stays level 0;
single `lp-smb0` or `lp-smb1` selects `5caefa0` level 1. Dual SMB is a
dangerous **executed isolation control**, rejected by a separate research
fixture admission function, not a real project candidate gate. CHMH wrong
type/49 bytes panic with 96/84; SMB wrong type/5 bytes likewise panic 96/84.
Changing the args material changes the digest and the reader publishes the
changed bytes; it is **not** an authentication rejection test.

The host IOKit objects and type failures remain fixtures, not live IORegistry.
The indirect runtime `+0x60` consumer after `46e9b2c` is deferred. Real
authentication, nonce comparison, device behavior and production manifest
provenance are NOT REACHED. CHMH-only is a compatibility direction for parent
review, not device approval; ASMB is not a candidate recommendation.

## Reproduction

WSL Ubuntu-22.04 root, cwd `/mnt/d/Code/PortingiOS/nuwa/UniXNU-nuwa`:

```sh
PYTHONPATH=/home/wh1stl3/.local/lib/python3.10/site-packages /usr/bin/python3 -B scripts/research-image4-chmh-asmb-host.py --output-dir out/image4-chmh-asmb-host-20261112-verifier
```

Self-check used the same command with fresh output suffix `final`, exit 0;
`git diff --check` and `git check-ignore` exit 0. Evidence
`out/image4-chmh-asmb-host-20261112-final/evidence.json` SHA-256
`f2e5d2a14e6ba85d6fa06c94e93fd37d79cfec2c6cab19462c70eba3ad65e9ba`;
runner SHA-256 `dfff1602117ff659da7d7db4ec9b65f08beb8e0ac05afff9b23d64e2db95a267`.
Evidence records all fixture trace PCs, raw writes, source and input hashes,
the entire preimage and both digests. Earlier exploratory output remains in
`out/image4-chmh-asmb-host-20261112/`. Independent verifier and reviewer are
pending; final integration belongs to the parent.
