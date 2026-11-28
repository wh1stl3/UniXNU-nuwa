#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Replay the V1-NODUR r3 link with only the RG renderer/display replacements."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "out/nuwa-v1-nodur-diag-20261128-build-r3"
R35 = ROOT / "out/nuwa-r35-20261119"
R35L = ROOT / "out/nuwa-r35l-regs-full-20261121"
PINS = {
    "BootProgress.c": "8e03abee2d32d43b31dee24db9012d10454cbe5cc2b5fc1f6a1a691f59adca51",
    "native.macho": "c574b944c8cf649aedd3a0a44d64d1f672fdf168ad553d6d0050eb8f5e846b6b",
    "kernel.macho": "03f228f685a888ad38378be65cac587e6c78febb969c954ddadcea56bbaa259e",
    "link.filelist": "95a4fbba9bed2987c3ea93098229c58f9548172b8dd04e0e58a4a14423c276ad",
    "native-link-argv.json": "970b62f44f2de9ccc48758ee0490c5816833094b8bedb688b424dac21bf8cfa7",
    "libNativeRamBlock.a": "3e163e822bad5bc6f32881ac08bf2967f4e13ad5e80a817b947085819de84f38",
    "nuwa-retained-persist/libObserveNativeUfs.a": "d5e17e7a1bab9bef237160f62d8b747e92fd2221dfe648f5bb375dc600c19976",
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load("display_build", ROOT / "scripts/build-nuwa-display-native.py")
diag = load("display_diag", ROOT / "scripts/generate_r35_display_diag.py")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--cpo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    a = parser.parse_args()
    base, cpo, out = a.base.resolve(), a.cpo.resolve(), a.out.resolve()
    if (ROOT / "out").resolve() not in out.parents or out.exists():
        parser.error("--out must be a new directory below device out/")
    for name, expected in PINS.items():
        build.require_pin(BASELINE / name, expected)
    build.require_pin(cpo, build.R35_CPO_SHA)
    for name, pin in build.R35L_PINS.items():
        build.require_pin(R35L / name, pin)
    linker = Path("/opt/unixnu-linux/CommandLineTools/usr/bin")
    build.require_pin(linker / "ld", build.LINKER_SHA)
    records = json.loads((R35L / "commands.json").read_text())
    record, = (r for r in records if r["label"] == "native-link" and r["exit"] == 0)
    cwd = Path(record["cwd"])
    build.require_pin(cwd / "osfmk/DEVELOPMENT/startup.o.json", build.STARTUP_RECORD_SHA)
    argv = json.loads((BASELINE / "native-link-argv.json").read_text())
    if Path(argv[argv.index("-filelist") + 1]) != BASELINE / "link.filelist":
        raise SystemExit("baseline filelist path changed")
    env = dict(os.environ, DARWIN_TRIPLE="arm64-apple-ios17.0",
               CROSS_CLANG="/opt/unixnu-linux/llvm/bin/clang",
               CROSS_EXTRA_FLAGS="-mllvm -disable-atexit-based-global-dtor-lowering",
               PYTHONDONTWRITEBYTECODE="1")
    env["PATH"] = str(linker) + ":/opt/unixnu-linux/bin:" + env.get("PATH", "")
    out.mkdir(parents=True)

    def link(label, replacements):
        command = list(argv)
        for old, new in replacements.items():
            if command.count(old) != 1:
                raise SystemExit(f"baseline link input not unique: {old}")
            command[command.index(old)] = new
        command[command.index("-o") + 1] = str(out / (label + ".macho"))
        map_at, = (i for i, value in enumerate(command) if value.startswith("-Wl,-map,"))
        command[map_at] = "-Wl,-map," + str(out / (label + ".map"))
        (out / (label + "-argv.json")).write_text(json.dumps(command, indent=2) + "\n")
        with (out / (label + ".log")).open("wb") as log:
            subprocess.run(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        return out / (label + ".macho"), out / (label + ".map")

    control, control_map = link("control", {})
    if (build.without_uuid(control.read_bytes()) != build.without_uuid((BASELINE / "native.macho").read_bytes())
            or control_map.read_bytes().partition(b"\n")[2] !=
            (BASELINE / "native-link.map").read_bytes().partition(b"\n")[2]):
        raise SystemExit("baseline link replay changed beyond UUID/map output path")
    print("r3 control link matches beyond UUID/map output path", flush=True)

    donor = base / "out/ipsw/20H392/kernelcache.decompressed"
    archive = build.build_archive(ROOT, base, donor, cpo, out,
                                  ["--cpu-only", "--no-software-vsync", "--pixsig",
                                   "--strip-debug", "--bringup-diag"])
    shutil.copyfile(out / "archive/NativeLegacyDisplay.cpp", out / "NativeLegacyDisplay.cpp")
    renderer = out / "BootProgress.c"
    renderer.write_bytes(diag.retire_generation((BASELINE / "BootProgress.c").read_bytes()))
    for name in ("BootProgressDisplay.h", "NuwaPixelSig.h"):
        shutil.copyfile(BASELINE / name, out / name)
    build.run([sys.executable, "-B", R35L / "build-boot-progress-compact.py",
               "--out", out, "--tree", R35L / "tree",
               "--stubs", ROOT / "package/boot-progress-r13/nuwa_boot_progress_stubs.c",
               "--renderer", renderer, "--define", "NUWA_VIRTIO_STUBS=1",
               "--define", "NUWA_RENDER_FIXES=1", "--define", "NUWA_BOLD_GLYPHS=1",
               "--define", "NUWA_HID_STANDIN=1"])
    if build.definitions(out / "libBootProgress.a") != build.definitions(BASELINE / "libBootProgress.a"):
        raise SystemExit("renderer global definition inventory changed")
    prefix = "-Wl,-force_load,"
    native, mapfile = link("native", {
        prefix + str(BASELINE / "libBootProgress.a"): prefix + str(out / "libBootProgress.a"),
        prefix + str(BASELINE / "archive/HOST-ONLY-incomplete-display.a"): prefix + str(archive),
    })

    sys.path.insert(0, str(base / "kits/XnuPrelink"))
    import scoped_libm_emitter
    emitter = scoped_libm_emitter.load(base)
    abi = json.loads((out / "derived/nuwa-display-abi.json").read_text())
    refs = json.loads((out / "archive/archive.json").read_text())["original_relocations"]
    native_bytes = native.read_bytes()
    got = build.audit_linked_metaclass(native_bytes, abi["metaclass"])
    slots = build.audit_linked_originals(native_bytes, abi["original_imports"], refs)
    provenance = ROOT / "out/nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/provenance.json"
    build.require_pin(provenance, build.R35_PROVENANCE_SHA)
    roots = list(dict.fromkeys([*json.loads(provenance.read_text())["roots"], build.FAMILY]))
    donor_bytes = donor.read_bytes()
    slide = abi["metaclass"]["collection_slide"]
    emitted, report = emitter.emit(native_bytes, donor_bytes, roots, slide)
    segments = emitter.macho(emitted)["segments"]
    region = emitter.backed_offset(segments, scoped_libm_emitter.START + slide,
                                  scoped_libm_emitter.END - scoped_libm_emitter.START, len(emitted))
    if emitted[region:region + 1224] != donor_bytes[scoped_libm_emitter.FILE_OFFSET:
                                                    scoped_libm_emitter.FILE_OFFSET + 1224]:
        raise SystemExit("emitted Libm region differs from donor")
    build.audit_emitted_originals(emitted, report, abi)
    if (build.audit_linked_metaclass(emitted, abi["metaclass"]) != got
            or build.audit_linked_originals(emitted, abi["original_imports"], refs) != slots):
        raise SystemExit("prelink changed the linked display ABI")
    (out / "prelink.macho").write_bytes(emitted)
    (out / "prelink.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "linked-original-slots.json").write_text(json.dumps(slots, indent=2) + "\n")
    final = build.render_candidate(R35, out, native, mapfile)
    if (build.audit_linked_metaclass(final.read_bytes(), abi["metaclass"]) != got
            or build.audit_linked_originals(final.read_bytes(), abi["original_imports"], refs) != slots):
        raise SystemExit("renderer changed the linked display ABI")
    hid = load("hid_abi", ROOT / "scripts/derive-nuwa-hid-abi.py")
    hid_abi = json.loads((BASELINE / "hid/hid-abi.json").read_text())
    hid_native = hid.audit_linked(native_bytes, hid_abi)
    if hid.audit_linked(final.read_bytes(), hid_abi) != hid_native:
        raise SystemExit("renderer changed the linked HID ABI")
    hid.audit_family(final.read_bytes(), hid_abi, report)
    print("kernel SHA-256 " + hashlib.sha256(final.read_bytes()).hexdigest(), flush=True)


if __name__ == "__main__":
    main()
