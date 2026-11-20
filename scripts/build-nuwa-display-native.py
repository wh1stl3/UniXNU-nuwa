#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Reproduce the incomplete display archive and attempt an isolated native link.

Host-only: this deliberately does not install hooks, package an image, or
qualify the 329/330 contracts. Outputs must stay in the device out directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import struct
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
DONOR_SHA = "2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221"
FAMILY = "com.apple.iokit.IOMobileGraphicsFamily"
RENDERER_SHA = "acbbf9f569961f4e58947020cd297a16682cddaa096bb6f0e353447ca3b77224"
STARTUP_RECORD_SHA = "8e85399e601ece0259f6e53889adb65fc862d91b638d986dbde06c4cffe8694e"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, cwd=None):
    print("+", shlex.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


def audit_linked_metaclass(blob, meta):
    from emit_prelink import backed_offset, exports, macho, pc_relative_target

    image = macho(blob)
    symbols = {name: va for va, names in exports(blob, image).items() for name in names}
    segments = image["segments"]
    expected = int(meta["linked_address"], 16)

    def pointer(va):
        return struct.unpack_from("<Q", blob, backed_offset(segments, va, 8, len(blob)))[0]

    # As in sheng check-legacy27-binds.py, follow the constructor's x2 GOT load
    # and read the pointer, rather than treating the absolute nlist as proof.
    pc = symbols["__ZN19NativeLegacyDisplay9MetaClassC2Ev"] + 0x10
    adrp, ldr = struct.unpack_from("<II", blob, backed_offset(segments, pc, 8, len(blob)))
    if adrp & 0x9f00001f != 0x90000002 or ldr & 0xffc003ff != 0xf9400042:
        raise SystemExit("native metaclass C2: expected ADRP/LDR into x2")
    got = pc_relative_target(adrp, pc)[0] + ((ldr >> 10) & 0xfff) * 8
    if not any(s["name"] == "__got" and s["va"] <= got <= s["va"] + s["size"] - 8
               for seg in segments for s in seg["sections"]) or pointer(got) != expected:
        raise SystemExit(f"native gMetaClass GOT at {got:#x}: expected {expected:#x}")
    if pointer(symbols["__ZN19NativeLegacyDisplay10superClassE"]) != expected:
        raise SystemExit("native superClass pointer does not name original gMetaClass")
    return got


def audit_linked_originals(blob, original, refs, *, table="__ZTV19NativeLegacyDisplay"):
    from emit_prelink import backed_offset, exports, macho, pc_relative_target

    image = macho(blob)
    segments = image["segments"]
    symbols = {name: va for va, names in exports(blob, image).items() for name in names}
    vptr = symbols[table] + 16
    text = [s for seg in segments if seg["initprot"] == 5 for s in seg["sections"]
            if s["name"] == "__text"]
    if not text:
        raise SystemExit("linked image has no executable __text")
    audited = {}
    for name, entry in original["functions"].items():
        veneer = symbols[name]
        if not any(s["va"] <= veneer <= s["va"] + s["size"] - 4 for s in text):
            raise SystemExit(f"{name}: veneer is not in executable __text")
        op, = struct.unpack_from("<I", blob, backed_offset(segments, veneer, 4, len(blob)))
        want = int(entry["linked_address"], 16)
        if op >> 26 != 5 or pc_relative_target(op, veneer)[0] != want:
            raise SystemExit(f"{name}: veneer at {veneer:#x} does not branch to {want:#x}")
        for ref in refs[name]:
            if "slot" not in ref:
                continue
            slot = ref["slot"]
            at = backed_offset(segments, vptr + slot * 8, 8, len(blob))
            if struct.unpack_from("<Q", blob, at)[0] != veneer:
                raise SystemExit(f"{table}[{slot}]: slot does not point to its own veneer")
            audited[slot] = {"veneer": hex(veneer), "donor": hex(want)}
    if len(set(symbols[name] for name in original["functions"])) != len(original["functions"]):
        raise SystemExit("different original functions share a linked veneer")
    return audited


def audit_emitted_originals(blob, report, abi):
    from emit_prelink import backed_offset, macho

    meta = abi["metaclass"]
    slide = meta["collection_slide"]
    if report["slide"] != slide or FAMILY not in report["components"]:
        raise SystemExit("gMetaClass requires the selected family at the binding's collection slide")
    segments = macho(blob)["segments"]

    def at(va, size):
        return backed_offset(segments, va, size, len(blob))

    family = macho(blob, at(int(abi["family"]["load"], 16) + slide, 32))
    data = next(s for s in family["segments"] if s["name"] == meta["segment"])
    common = next(s for s in data["sections"] if s["name"] == meta["section"])
    parent = next(s for s in segments if s["name"] == meta["parent_segment"])
    obj = int(meta["linked_address"], 16)
    if (data["va"] + int(meta["data_offset"], 16) != obj
            or not common["va"] <= obj <= common["va"] + common["size"] - 8
            or not data["va"] <= obj <= data["va"] + data["filesize"] - 8
            or not parent["va"] <= obj <= parent["va"] + parent["filesize"] - 8
            or data["initprot"] != 3 or parent["initprot"] != 3
            or struct.unpack_from("<Q", blob, at(obj, 8))[0] != 0):
        raise SystemExit("emitted gMetaClass is not at the expected writable family storage")
    site = int(meta["getter_site"], 16) + slide
    if struct.unpack_from("<Q", blob, at(site, 8))[0] != int(meta["getter"], 16) + slide:
        raise SystemExit("emitted original gMetaClass getter pointer was not slid")

    def in_section(segment, section, outer, prot, va, size):
        child = next(s for s in family["segments"] if s["name"] == segment)
        sec = next(s for s in child["sections"] if s["name"] == section)
        parent = next(s for s in segments if s["name"] == outer)
        if (child["initprot"] != prot or parent["initprot"] != prot
                or not sec["va"] <= va <= sec["va"] + sec["size"] - size
                or not child["va"] <= va <= child["va"] + child["filesize"] - size
                or not parent["va"] <= va <= parent["va"] + parent["filesize"] - size):
            raise SystemExit(f"emitted address {va:#x} outside {outer}/{segment},{section}")
        return at(va, size)

    original = abi["original_imports"]
    table = int(original["vtable_linked_address"], 16)
    table_at = in_section("__DATA_CONST", "__const", "__PLK_DATA_CONST", 1,
                          table, 16 + abi["vtable"]["slots"] * 8)
    for entry in original["functions"].values():
        target, slot = int(entry["linked_address"], 16), entry["slot"]
        in_section("__TEXT_EXEC", "__text", "__PLK_TEXT_EXEC", 5, target, 4)
        if slot is not None and struct.unpack_from("<Q", blob, table_at + 16 + slot * 8)[0] != target:
            raise SystemExit(f"emitted donor Legacy slot {slot} was not slid to {target:#x}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, required=True)
    p.add_argument("--cpo", type=Path, required=True)
    p.add_argument("--link-dir", type=Path, required=True,
                   help="8796 mach.development.bcm2837.link directory")
    p.add_argument("--linker-dir", type=Path, required=True,
                   help="directory containing the 8796 Mach-O ld")
    p.add_argument("--renderer", type=Path, required=True,
                   help="pinned real BootProgress.o (not the stub-containing archive)")
    p.add_argument("--out", type=Path, required=True, help="new directory under out/")
    a = p.parse_args()
    base, cpo, link, out = (x.resolve() for x in (a.base, a.cpo, a.link_dir, a.out))
    if not out.is_relative_to((ROOT / "out").resolve()) or out == (ROOT / "out").resolve():
        p.error("--out must be a new directory inside device out/")
    out.mkdir(parents=True, exist_ok=False)
    donor = base / "out/ipsw/20H392/kernelcache.decompressed"
    if digest(donor) != DONOR_SHA:
        raise SystemExit("20H392 donor SHA256 mismatch")
    renderer = a.renderer.resolve()
    if digest(renderer) != RENDERER_SHA:
        raise SystemExit("BootProgress.o SHA256 mismatch")
    if digest(link.parent / "osfmk/DEVELOPMENT/startup.o.json") != STARTUP_RECORD_SHA:
        raise SystemExit("renderer compile record does not match link tree")
    run([sys.executable, "-B", ROOT / "scripts/derive-nuwa-display-abi.py",
         "--base", base, "--kernelcache", donor, "--out", out / "derived"])
    for name in ("OriginalLegacyFramebufferABI.h", "original-bindings.S",
                 "original-addresses.S", "nuwa-display-abi.json"):
        if (out / "derived" / name).read_bytes() != (ROOT / "package" / name).read_bytes():
            raise SystemExit(f"derived {name} differs from device package")
    host = out / "archive"
    run([sys.executable, "-B", ROOT / "scripts/verify-nuwa-display-host-abi.py",
         "--base", base, "--cpo", cpo, "--out", host])
    archive = host / "HOST-ONLY-incomplete-display.a"
    print(f"host-only archive SHA256 {digest(archive)}", flush=True)

    # Replay XNU's exported link inputs, without its historical map output.
    # Force-loading the incomplete archive cannot make it runtime eligible.
    stem = "mach.development.bcm2837"
    flags = shlex.split((link / (stem + ".linkarguments")).read_text())
    libs = shlex.split((link / (stem + ".linkarchives")).read_text())
    libs = [x for x in libs if not x.startswith("-Wl,-map,")]
    record = json.loads(cpo.read_text().strip().rstrip(","))
    native = out / "HOST-ONLY-display-native.unstripped"
    target = [arg for arg in record["arguments"] if arg.startswith("--target=")][-1]
    command = [record["arguments"][0], target, "-B" + str(a.linker_dir.resolve()), *flags,
               "-Wl,-force_load," + str(link / (stem + ".a")),
               "-Wl,-force_load," + str(archive), str(renderer), *libs, "-o", str(native)]
    (out / "link-argv.json").write_text(json.dumps(command, indent=2) + "\n")
    run(command, cwd=record["directory"])
    print(f"host-only native SHA256 {digest(native)}", flush=True)

    sys.path.insert(0, str(base / "kits/XnuPrelink"))
    import emit_prelink
    abi = json.loads((out / "derived/nuwa-display-abi.json").read_text())
    native_bytes = native.read_bytes()
    got = audit_linked_metaclass(native_bytes, abi["metaclass"])
    refs = json.loads((host / "archive.json").read_text())["original_relocations"]
    slots = audit_linked_originals(native_bytes, abi["original_imports"], refs)
    (out / "linked-original-slots.json").write_text(json.dumps(slots, indent=2) + "\n")
    board = tomllib.loads((ROOT / "board.toml").read_text())
    roots = board["os_overrides"]["ios-16.7.16-20H392"]["kernel"]["prelink"]["roots"]
    roots = list(dict.fromkeys([*roots, FAMILY]))
    # Read-only gate: do not persist or package emitted bytes, even if accepted.
    emitted, report = emit_prelink.emit(
        native_bytes, donor.read_bytes(), roots, abi["metaclass"]["collection_slide"])
    audit_emitted_originals(emitted, report, abi)
    if audit_linked_metaclass(emitted, abi["metaclass"]) != got:
        raise SystemExit("prelink emission moved the native gMetaClass GOT entry")
    if audit_linked_originals(emitted, abi["original_imports"], refs) != slots:
        raise SystemExit("prelink emission changed a linked Legacy slot")
    print("strict emitter accepted; output discarded, runtime still ineligible")


if __name__ == "__main__":
    main()
