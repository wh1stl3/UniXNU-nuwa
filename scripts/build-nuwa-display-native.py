#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Reproduce the incomplete display archive and attempt an r35 or isolated native link.

Host-only: this deliberately does not install hooks, package an image, or
qualify the 329/330 contracts. Outputs must stay in the device out directory.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
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
R35_PINS = {
    "commands.json": "1e3b9dee1cce2592043e821c5f860d0f778b06644adfa2ef3090c8de5b556518",
    "link.filelist": "0974ae0405b7c53261c7520e5ea5fc024240d5dea3d93b375bd30bfea525e978",
    "native-link.map": "36abd5e601fbf9e6de89a61333f63b93468bb81111d9c2909ed3e47152ee5c0f",
    "native.macho": "a9fd5e43d647384626dcd64ce480ca4dd3918a710b0fb8f8d11e8505828932cb",
    "libBootProgress.a": "44a0f124dd5db234cd8f19d2d59d36cabf70cfba8a560ddd6cd9e3c389454fd1",
}
R35_CPO_SHA = "d390eb4440c6854e0243d041f0cd329be419a10ef78facf9a90102f3822e0c70"
R35_RENDERER_SHA = "491aa302b627be782abcd2991f3e723e559904a641689105efabb79e592fc144"
LINKER_SHA = "4f8a881dd4e4c1ff29c217a67bfd265582c1fb3bfebf989fdf5a3a4d9ba390a9"
EARLY_COUNTERS = ("_native_legacy_early_failures", "_native_legacy_early_retires")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, cwd=None):
    print("+", shlex.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


def require_pin(path, expected):
    if digest(path) != expected:
        raise SystemExit(f"{path}: SHA256 mismatch (expected {expected})")


def without_uuid(blob):
    # Apple's ld hashes the output basename into LC_UUID. Only mask its payload.
    if blob[:4] != b"\xcf\xfa\xed\xfe":
        raise SystemExit("r35 native output is not a 64-bit little endian Mach-O")
    offset = 32
    uuids = []
    for _ in range(struct.unpack_from("<I", blob, 16)[0]):
        cmd, size = struct.unpack_from("<II", blob, offset)
        if (cmd, size) == (0x1b, 24):
            uuids.append(offset + 8)
        offset += size
    if len(uuids) != 1:
        raise SystemExit("r35 native output must have one LC_UUID")
    at, = uuids
    return blob[:at] + bytes(16) + blob[at + 16:]


def nm_rows(path):
    return [tuple(line.split()) for line in subprocess.check_output(
        ["llvm-nm", "-P", "-g", str(path)], text=True).splitlines()
        if line and not line.endswith(":")]


def definitions(path):
    return Counter(row[0] for row in nm_rows(path) if row[1] != "U")


def replay_r35(r35, linker, cpo, out, archive, native, *, cpu_only):
    for name, pin in R35_PINS.items():
        require_pin(r35 / name, pin)
    require_pin(cpo, R35_CPO_SHA)
    require_pin(linker / "ld", LINKER_SHA)
    records = json.loads((r35 / "commands.json").read_text())
    record, = [r for r in records if r["label"] == "native-link" and r["exit"] == 0]
    argv = record["argv"]
    cwd = Path(record["cwd"])
    require_pin(cwd / "osfmk/DEVELOPMENT/startup.o.json", STARTUP_RECORD_SHA)
    if (Path(argv[0]).parent != linker
            or argv[argv.index("-filelist") + 1] != str(r35 / "link.filelist")):
        raise SystemExit("r35 replay requires the recorded linker and filelist locations")
    original_map = r35 / "native-link.map"
    renderer = r35 / "libBootProgress.a"
    map_at = argv.index(f"-Wl,-map,{original_map}")
    force_at = argv.index(f"-Wl,-force_load,{renderer}")
    output_at = argv.index("-o") + 1
    # r35 build.py's run_factory env; clang++ is the CLT wrapper, not host clang.
    env = dict(os.environ, DARWIN_TRIPLE="arm64-apple-ios17.0",
               CROSS_CLANG=str(linker.parents[2] / "llvm/bin/clang"),
               CROSS_EXTRA_FLAGS="-mllvm -disable-atexit-based-global-dtor-lowering",
               PYTHONDONTWRITEBYTECODE="1")
    env["PATH"] = f"{linker}:{linker.parents[2] / 'bin'}:" + env["PATH"]

    def link(label, dest, inputs):
        mapfile = out / (label + ".map")
        command = list(inputs)
        command[output_at] = str(dest)
        command[map_at] = f"-Wl,-map,{mapfile}"
        (out / (label + "-argv.json")).write_text(json.dumps(command, indent=2) + "\n")
        logfile = out / (label + ".log")
        with logfile.open("wb") as log:
            status = subprocess.run(command, cwd=cwd, env=env, stdout=log,
                                    stderr=subprocess.STDOUT).returncode
        print(logfile.read_text(errors="replace"), end="", flush=True)
        if status:
            raise SystemExit(status)
        return mapfile

    control = out / "HOST-ONLY-r35-control.unstripped"
    control_map = link("r35-control", control, argv)
    if (without_uuid(control.read_bytes()) != without_uuid((r35 / "native.macho").read_bytes())
            or control_map.read_bytes().partition(b"\n")[2] !=
            original_map.read_bytes().partition(b"\n")[2]):
        raise SystemExit("r35 link replay differs beyond LC_UUID or map output path")
    print("r35 control matches native and map except output UUID/path", flush=True)

    display = definitions(archive)
    baseline = definitions(control)
    overlap = set() if cpu_only else set(EARLY_COUNTERS)
    if (set(baseline) & set(display) != overlap
            or any(baseline[name] != 1 for name in (*EARLY_COUNTERS, "_boot_progress_prepare_scanout"))
            or any(display[name] != 1 for name in overlap)):
        raise SystemExit("r35/display definition inventory changed")
    if cpu_only:
        # No early GPU retire in the board TU: use the original r35 renderer
        # archive byte for byte, including its observation counter aliases.
        link("native-link", native, [*argv, f"-Wl,-force_load,{archive}"])
        return

    # The historical display TU owns both early GPU counters. Localize only
    # the shadowing absolute-zero aliases in a copy of the renderer archive.
    staging = out / "renderer"
    staging.mkdir()
    members = ["BootProgress.o", "nuwa_boot_progress_stubs.o"]
    if subprocess.check_output(["llvm-ar", "t", renderer], text=True).splitlines() != members:
        raise SystemExit("r35 renderer member order changed")
    run(["llvm-ar", "x", renderer], cwd=staging)
    require_pin(staging / members[0], R35_RENDERER_SHA)
    companion = staging / members[1]
    original = companion.rename(staging / "companion.original.o")
    before = nm_rows(original)
    aliases = [row for row in before if row[0] in EARLY_COUNTERS]
    if ({row[0] for row in aliases} != set(EARLY_COUNTERS)
            or any(row[1:3] != ("A", "0") for row in aliases)):
        raise SystemExit("r35 renderer overlaps are not the two expected zero aliases")
    localize = staging / "localize.txt"
    localize.write_text("\n".join(EARLY_COUNTERS) + "\n")
    run([linker / "nmedit", "-R", localize, "-o", companion, original])
    if Counter(nm_rows(companion)) != Counter(before) - Counter(aliases):
        raise SystemExit("r35 renderer companion changed beyond the two external aliases")
    staged = staging / renderer.name
    run(["llvm-ar", "rcs", staged, *members], cwd=staging)
    print("r35 renderer retains one prepare_scanout; display owns both early counters", flush=True)
    command = list(argv)
    command[force_at] = f"-Wl,-force_load,{staged}"
    link("native-link", native, [*command, f"-Wl,-force_load,{archive}"])
    linked = definitions(native)
    if any(linked[name] != 1 for name in (*EARLY_COUNTERS, "_boot_progress_prepare_scanout")):
        raise SystemExit("linked renderer/display symbols are not single definitions")


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
    p.add_argument("--link-dir", type=Path,
                   help="8796 mach.development.bcm2837.link directory for the isolated path")
    p.add_argument("--linker-dir", type=Path, required=True,
                   help="directory containing the 8796 Mach-O ld")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--renderer", type=Path,
                      help="pinned real BootProgress.o for the isolated path (requires --link-dir)")
    mode.add_argument("--r35-dir", type=Path,
                      help="recorded r35 native link directory under device out/")
    p.add_argument("--cpu-only", action="store_true",
                   help="compile out GPU/DPU paths in the host display TU (requires --r35-dir)")
    p.add_argument("--no-software-vsync", action="store_true",
                   help="compile out the GOP software timer lifecycle (requires --cpu-only)")
    p.add_argument("--out", type=Path, required=True, help="new directory under out/")
    a = p.parse_args()
    base, cpo, linker, out = (x.resolve() for x in (a.base, a.cpo, a.linker_dir, a.out))
    if not out.is_relative_to((ROOT / "out").resolve()) or out == (ROOT / "out").resolve():
        p.error("--out must be a new directory inside device out/")
    if a.r35_dir:
        r35 = a.r35_dir.resolve()
        if a.link_dir or (ROOT / "out").resolve() not in r35.parents:
            p.error("--r35-dir must be inside device out/ and replaces --link-dir")
    elif not a.link_dir:
        p.error("--renderer requires --link-dir")
    if a.cpu_only and not a.r35_dir:
        p.error("--cpu-only requires --r35-dir")
    if a.no_software_vsync and not a.cpu_only:
        p.error("--no-software-vsync requires --cpu-only")
    out.mkdir(parents=True, exist_ok=False)
    donor = base / "out/ipsw/20H392/kernelcache.decompressed"
    require_pin(donor, DONOR_SHA)
    if a.renderer:
        renderer = a.renderer.resolve()
        link = a.link_dir.resolve()
        require_pin(renderer, RENDERER_SHA)
        require_pin(link.parent / "osfmk/DEVELOPMENT/startup.o.json", STARTUP_RECORD_SHA)
    run([sys.executable, "-B", ROOT / "scripts/derive-nuwa-display-abi.py",
         "--base", base, "--kernelcache", donor, "--out", out / "derived"])
    for name in ("OriginalLegacyFramebufferABI.h", "original-bindings.S",
                 "original-addresses.S", "nuwa-display-abi.json"):
        if (out / "derived" / name).read_bytes() != (ROOT / "package" / name).read_bytes():
            raise SystemExit(f"derived {name} differs from device package")
    host = out / "archive"
    features = [name for enabled, name in ((a.cpu_only, "--cpu-only"),
                (a.no_software_vsync, "--no-software-vsync")) if enabled]
    run([sys.executable, "-B", ROOT / "scripts/verify-nuwa-display-host-abi.py",
         "--base", base, "--cpo", cpo, "--out", host, *features])
    archive = host / "HOST-ONLY-incomplete-display.a"
    print(f"host-only archive SHA256 {digest(archive)}", flush=True)

    native = out / "HOST-ONLY-display-native.unstripped"
    if a.r35_dir:
        replay_r35(r35, linker, cpo, out, archive, native, cpu_only=a.cpu_only)
    else:
        # Replay XNU's exported link inputs, without its historical map output.
        stem = "mach.development.bcm2837"
        flags = shlex.split((link / (stem + ".linkarguments")).read_text())
        libs = shlex.split((link / (stem + ".linkarchives")).read_text())
        libs = [x for x in libs if not x.startswith("-Wl,-map,")]
        record = json.loads(cpo.read_text().strip().rstrip(","))
        target = [arg for arg in record["arguments"] if arg.startswith("--target=")][-1]
        command = [record["arguments"][0], target, "-B" + str(linker), *flags,
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
