# r35i experimental display scale

Host-only diagnostic; no device operation. The r35h layout and X1 source are
unchanged. The r35i package adds `/chosen/display-scale` as little-endian u32
3, matching the existing `/product/artwork-scale-factor` in the r35h ADT.
The packager rejects an existing `display-scale` rather than replacing it,
and rejects a different artwork scale. This is an experimental value, not a
measurement of the nuwa panel.

UniXNU `docs/zh/guide/mobilegestalt.md` at checkout
`693f5d9cae8a408dd18b39f3f9fdc4228c934241`, lines 14–32, lists
`/chosen/display-scale` with an example of 2, not a nuwa value. It gives no
values for `/chosen/display-scale-factor` or `/chosen/display-rotation`;
neither is added.

Experiment / cost / exit: missing display scale / set 3 to match existing
artwork metadata / logical display scaling may not match the actual panel /
replace or remove after panel and consumer behavior are measured and reviewed.
Reviewer and deep_reviewer review, independent verifier rerun and device
validation remain pending. Authentication remains NOT REACHED.

## Host results (self-checked)

Artifacts in `UniXNU-nuwa/out/nuwa-r35i-*-r2-20261121`:

| Artifact | Hash |
| --- | --- |
| full kernel SHA-256 | `882a66fd7e5f45df98c106aff2abab322d834c973f970c0359266f95b8e41a8e` |
| compact kernel SHA-256 | `19d16ca35c356fa5e45b7c0191d13f399327db82c6ce05cdb4b0492dd5711c42` |
| derived ADT SHA-256 | `2108edcacebf51fb19b94c8c7be2a76d5d4907efc821ce821ab595f894f8f509` |
| CHMH SHA-384 | `3a6580d9b72156f35d4fc1e83415830e1ab997260305a6f4db27ba4a37c1232581014e8ce663c7b63574ac459b084cdc` |
| FAT SHA-256 | `6f566f9ce41ca9c6e2b3c251d09677c7082256dfbd10774e1c9644464e74d792` |
| outer SHA-256 | `db5517bd3fb0735a8e550ffa53269513bd4cf6caedb0be1a15ece22b50c6141b` |

The ADT parser reports both scale values as flags 0, four bytes `03000000`.
Removing the new entry produces the r35h **tag** ADT byte-for-byte. The older
r35h **final** ADT has a different CHMH; it is not the tag baseline. The
compact kernel and rebound CHMH match the tag baseline because the compact
kernel is byte-identical; CHMH is recomputed, not copied as an assertion.
The r35h source layout model, exception linked checks for both kernels,
and compact IRQ linked check completed. Outer readback audit completed.
The same-source compact audit and linked audit completed; the linked audit
reports ALL PASS and 49,615 preserved non-STAB symbols. FAT scan and fsck
report 12,070,400 bytes free, exceeding the 8,388,608-byte floor; the
independent outer audit read back the packaged FAT hash above.

## Reproduction

Follow `docs/nuwa-r35h-layout-20261121.md` using fresh output paths and its
referenced r35g commands. Replace both r35b packager invocations with
`scripts/build-ufs-apfs-root-chmh-r35i.py`; keep the same `NUWA_DETAIL_*`
environment and `NUWA_LAYOUT_R35H=1` for the compact package test. Parse the
result with `scripts/nuwa_launch_context.py`, verify the chosen and product
four-byte entries, remove only chosen display-scale, and compare the remaining
ADT bytes against the r35h tag package if using the same pinned inputs.
