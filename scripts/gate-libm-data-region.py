#!/usr/bin/env python3
"""Read-only word-level inbound-reference gate for the 20H392 Libm region."""
import argparse
import hashlib
import json
import struct
import sys

START, END = 0xfffffff005b8c054, 0xfffffff005b8c51c
DONOR_SHA = "2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221"
MASK = (1 << 64) - 1


def decode(word, pc):
    if word & 0x7c000000 == 0x14000000:
        kind, bits, imm = ("BL" if word & 0x80000000 else "B"), 26, word & 0x3ffffff
    elif word & 0xff000010 == 0x54000000:
        kind, bits, imm = "B.cond", 19, (word >> 5) & 0x7ffff
    elif word & 0x7e000000 == 0x34000000:
        kind, bits, imm = "CBZ/CBNZ", 19, (word >> 5) & 0x7ffff
    elif word & 0x7e000000 == 0x36000000:
        kind, bits, imm = "TBZ/TBNZ", 14, (word >> 5) & 0x3fff
    elif word & 0x9f000000 in (0x10000000, 0x90000000):
        kind = "ADRP" if word & 0x80000000 else "ADR"
        bits, imm = 21, ((word >> 5) & 0x7ffff) * 4 + ((word >> 29) & 3)
    elif word & 0x3b000000 == 0x18000000:
        kind, bits, imm = "literal", 19, (word >> 5) & 0x7ffff
    else:
        return None
    if imm & (1 << (bits - 1)):
        imm -= 1 << bits
    target = ((pc & ~4095) + (imm << 12) if kind == "ADRP"
              else pc + imm * (1 if kind == "ADR" else 4)) & MASK
    return kind, target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    args = ap.parse_args()
    from pathlib import Path
    base = Path(args.base)
    parser = base / "kits/XnuPrelink/native_prelink.py"
    if hashlib.sha256(parser.read_bytes()).hexdigest() != "a2da7ea8a4431f6c26418ecab9be718c0fbd2f0aa2334ba8d32c2270d2ac81dc":
        raise ValueError("native_prelink.py SHA256 mismatch")
    sys.path.insert(0, str(base / "kits/XnuPrelink"))
    import native_prelink as n
    donor = (base / "out/ipsw/20H392/kernelcache.decompressed").read_bytes()
    if hashlib.sha256(donor).hexdigest() != DONOR_SHA:
        raise ValueError("donor SHA256 mismatch")
    parent = n.macho(donor)
    segments = parent["segments"]

    def offset(va, size):
        return n.backed_offset(segments, va, size, len(donor))

    info = next(s for s in segments if s["name"] == "__PRELINK_INFO")
    at = offset(info["va"], info["filesize"])
    entries = n.unserialize_xml(donor[at:at + info["filesize"]])["_PrelinkInfoDictionary"]
    images = []
    for entry in entries:
        va = entry.get("_PrelinkExecutableLoadAddr")
        if va is not None and entry.get("_PrelinkExecutableSize") and entry.get("OSKernelResource") is not True:
            images.append((entry["CFBundleIdentifier"], n.macho(donor, offset(va, 32))))
    if len(images) != 221:
        raise ValueError("expected 221 parsable kexts")
    external, inside, refs = [], [], {"ADR": 0, "ADRP": 0, "literal": 0}
    for name, image in [("kernel", parent), *images]:
        for seg in image["segments"]:
            if seg["name"] != "__TEXT_EXEC" or not seg["filesize"]:
                continue
            pos = offset(seg["va"], seg["filesize"])
            for i in range(0, seg["filesize"] - 3, 4):
                pc = seg["va"] + i
                word = struct.unpack_from("<I", donor, pos + i)[0]
                item = decode(word, pc)
                if item is None:
                    continue
                kind, target = item
                row = dict(module=name, pc=hex(pc), word=f"0x{word:08x}", target=hex(target), kind=kind)
                if START <= pc < END and kind not in refs:
                    inside.append(row)
                elif not START <= pc < END and START <= target < END:
                    if kind in refs:
                        refs[kind] += 1
                    else:
                        external.append(row)
    libm = next(e for e in entries if e.get("CFBundleIdentifier") == "com.apple.kec.Libm")
    at = offset(libm["_PrelinkExecutableLoadAddr"], 32)
    ncmds = struct.unpack_from("<I", donor, at + 16)[0]
    pos = at + 32
    commands = {}
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", donor, pos)
        if size < 8:
            raise ValueError("invalid load command")
        if cmd in (2, 0x26):
            commands[cmd] = struct.unpack_from("<" + "I" * (size // 4), donor, pos)
        pos += size
    if 0x26 in commands:
        raise ValueError("unexpected LC_FUNCTION_STARTS: implement parsing before qualifying")
    if 2 not in commands or commands[2][3] != 0:
        raise ValueError("unexpected symbols: inspect all N_SECT before qualifying")
    print(json.dumps(dict(donor_sha256=DONOR_SHA, kexts=len(images),
                          external_branch_count=len(external), external_branches=external,
                          outside_reference_counts=refs, inside_branch_decodes=inside,
                          function_starts="absent", symtab="nsyms=0"), indent=2))
    if external:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
