#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Build the audited display archive or replay a native link.

The explicit candidate mode adds the device hooks to r35 and emits the final
diagnostic kernel. No mode qualifies the runtime 329/330 contracts.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
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
R35L_PINS = {
    "commands.json": "1800c58e47041f25c580458f05e169c4803aa6fdb7b15513e6b7b068d44f0818",
    "link.filelist": "f7ad5a33f2d9b924f18a8a367c7409e7e0b64c33faeba64910d3d9d1876ed19a",
    "native-link.map": "47883de722e9ba4d5ca39d2caf1f553939530a7d7b5f3c81d932716c034ce7d1",
    "native.macho": "d04e6044b6452737b3b0fe1734bd1ec1acb58e8230ba7b88c754e024470fa829",
    "libBootProgress.a": "1ec5b96a5dbddf9e2c81dab52051f38496e29f807271798e1e804a2358845ca9",
    "build-boot-progress-compact.py": "0d283d07764d9bdcf72bc756994592c5cdb2264dab87361601406ab21e227156",
    "BootProgressDisplay.h": "86311631e7cf66881bd6d1a57a927c78db9ea9bb579deb025136252e3e218c72",
}
DSP_SET = "_boot_progress_diag_set"
R35_CPO_SHA = "d390eb4440c6854e0243d041f0cd329be419a10ef78facf9a90102f3822e0c70"
R35_RENDERER_SHA = "491aa302b627be782abcd2991f3e723e559904a641689105efabb79e592fc144"
LINKER_SHA = "4f8a881dd4e4c1ff29c217a67bfd265582c1fb3bfebf989fdf5a3a4d9ba390a9"
R35_BSD_SHA = "a6cbabcb09456936471bb8d9bceb93e9b9257c3dc6025f57c21005286245b4bc"
R35_BUILD_SHA = "c2e8bcc0aae8a6736592079b4f0bd1fba9032490ddfa432f30df9e6fbc619979"
R35_PROVENANCE_SHA = "1183fe650735557053d09ef8de36ce9d689fe0b5b2f85acc677a0fb544a8d62d"
EARLY_COUNTERS = ("_native_legacy_early_failures", "_native_legacy_early_retires")
HOOKS = ("8796-offline-legacy-display-early.patch", "8796-offline-legacy-display-late.patch")
# 8796-native-text-fixup: inputs of the two rebuilt TUs and the patch itself.
TEXT_FIXUP_PATCH = ROOT / "patches/xnu/8796-native-text-fixup.patch"
TEXT_FIXUP_PATCH_SHA = "492355cfb37f87970de3444496aea488c7769704d94e97baa204fcc7b142344a"
R35L_UBC_SHA = "6d9dbdcda146110f1d739803630bae11a1d042a723f1acf76fdbe7c615739be0"
R35_VM_FAULT_SHA = "990814178e80da7c3d7ddff855d497f9b863fdb4a45415e71534cf4e2c75b934"
R35_VM_PROTOS_SHA = "3ef4c0ca9d71b329ad3952cb5f3f52c6ce157b0575f0bdb4eef044380d8679ee"


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


def audit_debug_strip(full, compact):
    from native_prelink import macho

    before, after = macho(full), macho(compact)
    if full[:32] != compact[:32] or before["commands"] != after["commands"]:
        raise SystemExit("debug-free relink changed Mach-O header or command layout")
    header_end = 32 + struct.unpack_from("<I", full, 20)[0]
    ignored = {2, 0x1b}  # LC_SYMTAB, LC_UUID
    for code, at, size in before["commands"]:
        orig, new = full[at:at + size], compact[at:at + size]
        if code == 0x19 and orig[8:24].rstrip(b"\0") == b"__LINKEDIT":
            # Only vmsize and filesize may change, not the mapping or protections.
            orig, new = (cmd[:32] + cmd[40:48] + cmd[56:] for cmd in (orig, new))
        elif code == 0xb:
            # The first six uint32s are the local/external/undefined table
            # ranges. All offsets and counts for auxiliary tables must agree.
            orig, new = orig[32:], new[32:]
        elif code in ignored:
            continue
        if orig != new:
            raise SystemExit(f"debug-free relink changed load command {code:#x}")
    for seg in before["segments"]:
        if seg["name"] != "__LINKEDIT":
            start, size = seg["fileoff"], seg["filesize"]
            if full[max(start, header_end):start + size] != compact[max(start, header_end):start + size]:
                raise SystemExit(f"debug-free relink changed mapped bytes of {seg['name']}")

    _, at, _ = next(cmd for cmd in before["commands"] if cmd[0] == 2)

    def symbols(blob):
        symoff, count, stroff, size = struct.unpack_from("<IIII", blob, at + 8)
        if not symoff + count * 16 == stroff or stroff + size != len(blob):
            raise SystemExit("unexpected linkedit symbol/string table extents")
        strings = blob[stroff:]
        entries, stabs = Counter(), 0
        for index, kind, section, desc, value in struct.iter_unpack("<IBBHQ", blob[symoff:stroff]):
            if kind & 0xe0:
                stabs += 1
            else:
                name = strings[index:strings.index(0, index)]
                entries[name, kind, section, desc, value] += 1
        return symoff, entries, stabs

    end, names, stabs = symbols(full)
    new_end, new_names, new_stabs = symbols(compact)
    linkedit = next(seg["fileoff"] for seg in before["segments"] if seg["name"] == "__LINKEDIT")
    if (not stabs or new_stabs or names != new_names or end != new_end
            or full[linkedit:end] != compact[linkedit:end] or len(compact) >= len(full)):
        raise SystemExit("debug-free relink did not remove only STABS and their strings")
    return {"stabs_removed": stabs, "non_debug_symbols_preserved": sum(names.values()),
            "native_bytes_saved": len(full) - len(compact)}


def load_o_json(path):
    """Parse one or more concatenated clang -MJ fragments."""
    raw = path.read_text()
    decoder, records, index = json.JSONDecoder(), [], 0
    while index < len(raw):
        while index < len(raw) and raw[index] in " \t\r\n,":
            index += 1
        if index >= len(raw):
            break
        record, index = decoder.raw_decode(raw, index)
        records.append(record)
    if len(records) != 1:
        raise SystemExit(f"{path}: expected one compile record")
    return records[0]


def text_fixup_objects(r35, out, records, env):
    """Rebuild the two TUs the signed-text fixup patch changes, from the same
    source bases the r35l kernel already used, and return their objects.

    ubc_subr.c comes from the r35l staged tree (it carries the 4K hash-cache
    change); vm_fault.c and vm_protos.h come from the xnu source tree recorded
    in that kernel's own compile database. The patch is applied to copies only.
    """
    require_pin(r35 / "tree/bsd/kern/ubc_subr.c", R35L_UBC_SHA)
    require_pin(TEXT_FIXUP_PATCH, TEXT_FIXUP_PATCH_SHA)
    ubc, = [r for r in records if r["label"] == "compile-ubc_subr" and r["exit"] == 0]
    ubc_argv = list(ubc["argv"])
    source_root_at, = [i for i, arg in enumerate(ubc_argv)
                       if arg.endswith("/.cache/xnu-work/bsd")]
    xnu = Path(ubc_argv[source_root_at]).parent
    require_pin(xnu / "osfmk/vm/vm_fault.c", R35_VM_FAULT_SHA)
    require_pin(xnu / "osfmk/vm/vm_protos.h", R35_VM_PROTOS_SHA)
    obj_root = Path(ubc["cwd"]).parent.parent
    vm = load_o_json(obj_root / "osfmk/DEVELOPMENT/vm_fault.o.json")

    tus = out / "tus"
    (tus / "bsd/kern").mkdir(parents=True)
    (tus / "osfmk/vm").mkdir(parents=True)
    shutil.copyfile(r35 / "tree/bsd/kern/ubc_subr.c", tus / "bsd/kern/ubc_subr.c")
    shutil.copyfile(xnu / "osfmk/vm/vm_fault.c", tus / "osfmk/vm/vm_fault.c")
    shutil.copyfile(xnu / "osfmk/vm/vm_protos.h", tus / "osfmk/vm/vm_protos.h")
    run(["patch", "--batch", "--fuzz=0", "-p1", "-i", TEXT_FIXUP_PATCH], cwd=tus)

    # The patched vm_protos.h must shadow the exported copy for both TUs.
    osfm = ["-I", str(tus / "osfmk")]

    ubc_argv[2:2] = osfm
    source_at = [i for i, arg in enumerate(ubc_argv)
                 if arg.endswith("/tree/bsd/kern/ubc_subr.c")]
    if len(source_at) != 1:
        raise SystemExit("expected one ubc_subr.c in the recorded compile")
    ubc_argv[source_at[0]] = str(tus / "bsd/kern/ubc_subr.c")
    ubc_obj = out / "ubc_subr.o"
    ubc_argv[ubc_argv.index("-o") + 1] = str(ubc_obj)
    (out / "text-fixup-ubc-argv.json").write_text(json.dumps(ubc_argv, indent=2) + "\n")
    subprocess.run(ubc_argv, cwd=ubc["cwd"], env=env, check=True)

    vm_argv = list(vm["arguments"])
    vm_argv[2:2] = osfm
    source_at, = [i for i, arg in enumerate(vm_argv)
                  if arg.endswith("/osfmk/vm/vm_fault.c")]
    vm_argv[source_at] = str(tus / "osfmk/vm/vm_fault.c")
    vm_obj = out / "vm_fault.o"
    vm_argv[vm_argv.index("-o") + 1] = str(vm_obj)
    (out / "text-fixup-vm-argv.json").write_text(json.dumps(vm_argv, indent=2) + "\n")
    subprocess.run(vm_argv, cwd=vm["directory"], env=env, check=True)

    (out / "text-fixup.json").write_text(json.dumps({
        "patch": {"path": str(TEXT_FIXUP_PATCH), "sha256": TEXT_FIXUP_PATCH_SHA},
        "sources_sha256": {
            "bsd/kern/ubc_subr.c": R35L_UBC_SHA,
            "osfmk/vm/vm_fault.c": R35_VM_FAULT_SHA,
            "osfmk/vm/vm_protos.h": R35_VM_PROTOS_SHA,
        },
        "objects_sha256": {"ubc_subr.o": digest(ubc_obj), "vm_fault.o": digest(vm_obj)},
    }, indent=2) + "\n")
    return {"ubc_subr.o": ubc_obj, "vm_fault.o": vm_obj}


def candidate_link(r35, out, records, argv, env, *, bringup_diag, hid, mg_reset, text_fixup=False):
    recipe, = [r for r in records if r["label"] == "compile-bsd_init" and r["exit"] == 0]
    command = list(recipe["argv"])
    source = r35 / "tree/bsd/kern/bsd_init.c"
    require_pin(source, R35_BSD_SHA)
    work = out / "tree"
    staged = work / "bsd/kern/bsd_init.c"
    staged.parent.mkdir(parents=True)
    shutil.copyfile(source, staged)
    series = (ROOT / "patches/xnu/series").read_text().splitlines()
    if [name for name in series if name in HOOKS] != list(HOOKS):
        raise SystemExit("display hook order differs from device series")
    for name in HOOKS:
        run(["patch", "--batch", "--fuzz=0", "-p1", "-i", ROOT / "patches/xnu" / name], cwd=work)
    obj = out / "bsd_init.o"
    source_at, = [i for i, arg in enumerate(command)
                  if arg.endswith("/tree/bsd/kern/bsd_init.c")]
    require_pin(Path(command[source_at]), digest(source))
    command[source_at] = str(staged)
    command[command.index("-o") + 1] = str(obj)
    command.append("-DXNU_NATIVE_LEGACY_DISPLAY=1")
    if hid:
        command.append("-DXNU_NUWA_HID_STANDIN=1")
    (out / "bsd-init-argv.json").write_text(json.dumps(command, indent=2) + "\n")
    subprocess.run(command, cwd=recipe["cwd"], env=env, check=True)

    filelist = (r35 / "link.filelist").read_text()
    old = recipe["argv"][recipe["argv"].index("-o") + 1] + "\n"
    require_pin(Path(old.strip()), digest(r35 / "bsd_init.o"))
    if filelist.splitlines(keepends=True).count(old) != 1:
        raise SystemExit("expected one r35 bsd_init.o in the native filelist")
    filelist = filelist.replace(old, str(obj) + "\n", 1)
    if text_fixup:
        for name, path in text_fixup_objects(r35, out, records, env).items():
            line, = [entry for entry in filelist.splitlines(keepends=True)
                     if entry.rstrip().endswith("/" + name)]
            if filelist.count(line) != 1:
                raise SystemExit(f"expected one {name} in the native filelist")
            filelist = filelist.replace(line, str(path) + "\n", 1)
    if bringup_diag:
        watchdog, = [r for r in records if r["label"] == "compile-nuwa_watchdog_policy"
                     and r["exit"] == 0]
        watchdog_command = list(watchdog["argv"])
        source_at, = [i for i, arg in enumerate(watchdog_command)
                      if arg.endswith("/package/nuwa-watchdog/nuwa_watchdog_policy.c")]
        old_obj = Path(watchdog_command[watchdog_command.index("-o") + 1])
        require_pin(old_obj, digest(r35 / old_obj.name))
        old_line = str(old_obj) + "\n"
        if filelist.splitlines(keepends=True).count(old_line) != 1:
            raise SystemExit("expected one r35 watchdog object in the native filelist")
        policy_source = ROOT / "package/nuwa-watchdog/nuwa_watchdog_policy.c"
        policy_obj = out / old_obj.name
        watchdog_command[source_at] = str(policy_source)
        watchdog_command[watchdog_command.index("-o") + 1] = str(policy_obj)
        if mg_reset:
            mg_command = list(watchdog_command)
            mg_command[source_at] = str(policy_source.with_name("nuwa_mg_reset.c"))
            mg_obj = out / "nuwa_mg_reset.o"
            mg_command[mg_command.index("-o") + 1] = str(mg_obj)
            (out / "mg-reset-argv.json").write_text(json.dumps(mg_command, indent=2) + "\n")
            subprocess.run(mg_command, cwd=watchdog["cwd"], env=env, check=True)
            watchdog_command.append("-DXNU_NUWA_MG_RESET=1")
            filelist = filelist.replace(old_line, old_line + str(mg_obj) + "\n", 1)
        (out / "watchdog-argv.json").write_text(json.dumps(watchdog_command, indent=2) + "\n")
        subprocess.run(watchdog_command, cwd=watchdog["cwd"], env=env, check=True)
        (out / "watchdog-inputs.json").write_text(json.dumps({
            "source_sha256": digest(policy_source),
            "recorded_object_sha256": digest(old_obj),
            "replacement_object_sha256": digest(policy_obj),
        }, indent=2) + "\n")
        filelist = filelist.replace(old_line, str(policy_obj) + "\n", 1)
    dest = out / "link.filelist"
    dest.write_text(filelist)
    adjusted = list(argv)
    adjusted[adjusted.index("-filelist") + 1] = str(dest)
    return adjusted


def diag_archive(r35, out, *, hid, mg_reset):
    from generate_r35_display_diag import generate

    source = out / "BootProgress.c"
    source.write_bytes(generate((r35 / "BootProgress.c").read_bytes(), mg_reset=mg_reset))
    shutil.copyfile(r35 / "BootProgressDisplay.h", out / "BootProgressDisplay.h")
    stubs = ROOT / "package/boot-progress-r13/nuwa_boot_progress_stubs.c"
    require_pin(stubs, "14817837f64b37f36c65ac5e6debd187c2d8e6a24e8b0396eb280239108c6b47")
    hid_define = ["--define", "NUWA_HID_STANDIN=1"] if hid else []
    run([sys.executable, "-B", r35 / "build-boot-progress-compact.py",
         "--out", out, "--tree", r35 / "tree", "--stubs", stubs, "--renderer", source,
         "--define", "NUWA_VIRTIO_STUBS=1", "--define", "NUWA_RENDER_FIXES=1",
         "--define", "NUWA_BOLD_GLYPHS=1", *hid_define])
    staged = out / "libBootProgress.a"
    expected = definitions(r35 / staged.name) + Counter({DSP_SET: 1, "_boot_progress_prop_set": 1})
    if hid:
        for name in ("seq", "count", "xs", "ys"):
            require = expected.pop(f"_native_touch_{name}", 0)
            if require != 1:
                raise SystemExit(f"expected one original renderer alias for native_touch_{name}")
    if definitions(staged) != expected:
        raise SystemExit("r35l renderer changed global definitions beyond DSP")
    return staged


def replay_r35(r35, linker, cpo, out, archive, native, *, cpu_only, candidate,
               keep_link_debug, bringup_diag=False, hid_objects=(), mg_reset=False,
               text_fixup=False):
    for name, pin in (R35L_PINS if bringup_diag else R35_PINS).items():
        require_pin(r35 / name, pin)
    require_pin(cpo, R35_CPO_SHA)
    require_pin(linker / "ld", LINKER_SHA)
    records = json.loads((r35 / "commands.json").read_text())
    record, = [r for r in records if r["label"] == "native-link" and r["exit"] == 0]
    argv = record["argv"]
    cwd = Path(record["cwd"])
    require_pin(cwd / "osfmk/DEVELOPMENT/startup.o.json", STARTUP_RECORD_SHA)
    # Replay requires the same input contents, not identical directory strings:
    # a worktree may have a different root, but changed inputs must still fail.
    require_pin(Path(argv[0]), digest(linker / Path(argv[0]).name))
    require_pin(Path(argv[argv.index("-filelist") + 1]), digest(r35 / "link.filelist"))
    original_map = r35 / "native-link.map"
    renderer = r35 / "libBootProgress.a"
    map_at, = [i for i, arg in enumerate(argv) if arg.startswith("-Wl,-map,")]
    require_pin(Path(argv[map_at].removeprefix("-Wl,-map,")), digest(original_map))
    force_at, = [i for i, arg in enumerate(argv)
                 if arg.startswith("-Wl,-force_load,") and arg.endswith("/libBootProgress.a")]
    require_pin(Path(argv[force_at].removeprefix("-Wl,-force_load,")), digest(renderer))
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
        # Preserve the ADRP/LDR GOT sequence required by the linked audit.
        if candidate:
            argv = candidate_link(r35, out, records, argv, env, bringup_diag=bringup_diag,
                                  hid=bool(hid_objects), mg_reset=mg_reset,
                                  text_fixup=text_fixup)
        if bringup_diag:
            argv = list(argv)
            diag = diag_archive(r35, out, hid=bool(hid_objects), mg_reset=mg_reset)
            argv[force_at] = f"-Wl,-force_load,{diag}"
        argv = [*argv, "-Wl,-ignore_optimization_hints", f"-Wl,-force_load,{archive}", *map(str, hid_objects)]
        if not candidate or keep_link_debug:
            return link("native-link", native, argv)
        full = out / "native-with-stabs.macho"
        link("native-with-stabs", full, argv)
        mapfile = link("native-link", native, [*argv, "-Wl,-S"])
        audit = audit_debug_strip(full.read_bytes(), native.read_bytes())
        (out / "debug-strip.json").write_text(json.dumps(audit, indent=2) + "\n")
        return mapfile

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
    mapfile = link("native-link", native, [*command, f"-Wl,-force_load,{archive}"])
    linked = definitions(native)
    if any(linked[name] != 1 for name in (*EARLY_COUNTERS, "_boot_progress_prepare_scanout")):
        raise SystemExit("linked renderer/display symbols are not single definitions")
    return mapfile


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


def build_archive(root, base, donor, cpo, out, features):
    require_pin(donor, DONOR_SHA)
    run([sys.executable, "-B", root / "scripts/derive-nuwa-display-abi.py",
         "--base", base, "--kernelcache", donor, "--out", out / "derived"])
    for name in ("OriginalLegacyFramebufferABI.h", "original-bindings.S",
                 "original-addresses.S", "nuwa-display-abi.json"):
        if (out / "derived" / name).read_bytes() != (root / "package" / name).read_bytes():
            raise SystemExit(f"derived {name} differs from device package")
    run([sys.executable, "-B", root / "scripts/verify-nuwa-display-host-abi.py",
         "--base", base, "--cpo", cpo, "--out", out / "archive", *features])
    return out / "archive/HOST-ONLY-incomplete-display.a"


def device_archive():
    """The pinned base's [kernel].archives callback, cwd = assembled tree."""
    if os.environ.get("XNU_NATIVE_LEGACY_DISPLAY") != "1":
        return
    root = Path(os.environ["UNIXNU_DEVICE"]).resolve()
    board = tomllib.loads((root / "board.toml").read_text())
    base = (root / board["package"]["unixnu"]).resolve()
    tree = Path.cwd()
    cpo = tree / "build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPMGR.cpo.json"
    scratch = root / "out"
    scratch.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="nuwa-display-archive-", dir=scratch))
    archive = build_archive(root, base, base / "out/ipsw/20H392/kernelcache.decompressed",
                            cpo, work, ["--cpu-only", "--no-software-vsync", "--strip-debug"])
    dest = tree / "build/native-legacy-display"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(archive, dest / "libNativeLegacyDisplay.late.a")
    sources = ("scripts/build-nuwa-display-native.py", "scripts/derive-nuwa-display-abi.py",
               "scripts/verify-nuwa-display-host-abi.py", "scripts/host/NuwaDisplayRefresh.cpp",
               "scripts/host/NuwaDisplayRefresh.h", "kits/nuwa/NuwaLegacyDisplay.cpp",
               "kits/nuwa/OriginalLegacyFramebufferABI.h", "kits/nuwa/original-bindings.S",
               "kits/nuwa/original-addresses.S", "kits/nuwa/nuwa-display-abi.json",
               "drivers/GopFramebuffer/NativeLegacyDisplay.cpp")
    (dest / "build-report.json").write_text(json.dumps({
        "archive_sha256": digest(archive),
        "source_sha256": {name: digest(tree / name) for name in sources},
    }, indent=2) + "\n")


def render_candidate(r35, out, native, mapfile):
    source = r35 / "build.py"
    require_pin(source, R35_BUILD_SHA)
    spec = importlib.util.spec_from_file_location("r35_display_renderer", source)
    recipe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recipe)
    render, _ = recipe.run_factory(out)
    return recipe.B.renderer(out, out / "prelink.macho", native, mapfile, render)


def main():
    if sys.argv[1:] == ["--device-archive"]:
        device_archive()
        return
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
    p.add_argument("--candidate", action="store_true",
                   help="apply device hooks and write the r35-display diagnostic kernel")
    p.add_argument("--r35l-dir", type=Path,
                   help="pinned full r35l inputs for the display bring-up probe")
    p.add_argument("--keep-link-debug", action="store_true",
                   help="measure the archive-only size reduction before stripping linked STABS")
    p.add_argument("--hid-standin", action="store_true",
                   help="include the default-off HID board probe and require its final ABI audit")
    p.add_argument("--mg-reset", action="store_true",
                   help="include the board cache reset (off unless nuwa-mg-reset=1)")
    p.add_argument("--text-fixup", action="store_true",
                   help="rebuild ubc_subr/vm_fault with the signed-text fixup patch (requires --r35l-dir)")
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
    if a.candidate and not (a.r35_dir and a.cpu_only and a.no_software_vsync):
        p.error("--candidate requires --r35-dir --cpu-only --no-software-vsync")
    if a.keep_link_debug and not a.candidate:
        p.error("--keep-link-debug requires --candidate")
    if a.r35l_dir and (not a.candidate or not a.r35l_dir.resolve().is_relative_to((ROOT / "out").resolve())):
        p.error("--r35l-dir requires --candidate and must be inside device out/")
    if a.hid_standin and not a.r35l_dir:
        p.error("--hid-standin requires the pinned --r35l-dir candidate")
    if a.mg_reset and not a.r35l_dir:
        p.error("--mg-reset requires the pinned --r35l-dir candidate")
    if a.text_fixup and not a.r35l_dir:
        p.error("--text-fixup requires the pinned --r35l-dir candidate")
    out.mkdir(parents=True, exist_ok=False)
    donor = base / "out/ipsw/20H392/kernelcache.decompressed"
    hid_objects = []
    if a.hid_standin:
        spec = importlib.util.spec_from_file_location("nuwa_hid_abi", ROOT / "scripts/derive-nuwa-hid-abi.py")
        hid = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hid)
        hid_objects = hid.compile_archive(base, donor, cpo, out / "hid")
    if a.renderer:
        renderer = a.renderer.resolve()
        link = a.link_dir.resolve()
        require_pin(renderer, RENDERER_SHA)
        require_pin(link.parent / "osfmk/DEVELOPMENT/startup.o.json", STARTUP_RECORD_SHA)
    features = [name for enabled, name in ((a.cpu_only, "--cpu-only"),
                 (a.no_software_vsync, "--no-software-vsync"),
                  (a.candidate, "--strip-debug"),
                  (a.r35l_dir, "--bringup-diag")) if enabled]
    archive = build_archive(ROOT, base, donor, cpo, out, features)
    print(f"host-only archive SHA256 {digest(archive)}", flush=True)

    native = out / ("native.macho" if a.candidate else "HOST-ONLY-display-native.unstripped")
    sys.path.insert(0, str(base / "kits/XnuPrelink"))
    if a.r35_dir:
        link_inputs = a.r35l_dir.resolve() if a.r35l_dir else r35
        mapfile = replay_r35(link_inputs, linker, cpo, out, archive, native,
                              cpu_only=a.cpu_only, candidate=a.candidate,
                              keep_link_debug=a.keep_link_debug, bringup_diag=bool(a.r35l_dir),
                              hid_objects=hid_objects, mg_reset=a.mg_reset,
                              text_fixup=a.text_fixup)
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

    import scoped_libm_emitter
    emit_prelink = scoped_libm_emitter.load(base)
    abi = json.loads((out / "derived/nuwa-display-abi.json").read_text())
    native_bytes = native.read_bytes()
    if a.hid_standin:
        hid_abi = json.loads((out / "hid/hid-abi.json").read_text())
        hid_native = hid.audit_linked(native_bytes, hid_abi)
    got = audit_linked_metaclass(native_bytes, abi["metaclass"])
    refs = json.loads((archive.parent / "archive.json").read_text())["original_relocations"]
    slots = audit_linked_originals(native_bytes, abi["original_imports"], refs)
    (out / "linked-original-slots.json").write_text(json.dumps(slots, indent=2) + "\n")
    if a.candidate:
        provenance = ROOT / "out/nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/provenance.json"
        require_pin(provenance, R35_PROVENANCE_SHA)
        roots = json.loads(provenance.read_text())["roots"]
    else:
        board = tomllib.loads((ROOT / "board.toml").read_text())
        roots = board["os_overrides"]["ios-16.7.16-20H392"]["kernel"]["prelink"]["roots"]
    roots = list(dict.fromkeys([*roots, FAMILY]))
    donor_bytes = donor.read_bytes()
    slide = abi["metaclass"]["collection_slide"]
    emitted, report = emit_prelink.emit(native_bytes, donor_bytes, roots, slide)
    emitted_segments = emit_prelink.macho(emitted)["segments"]
    region_at = emit_prelink.backed_offset(
        emitted_segments, scoped_libm_emitter.START + slide,
        scoped_libm_emitter.END - scoped_libm_emitter.START, len(emitted))
    if emitted[region_at:region_at + 1224] != donor_bytes[
            scoped_libm_emitter.FILE_OFFSET:scoped_libm_emitter.FILE_OFFSET + 1224]:
        raise ValueError("emitted Libm region differs from donor")
    print(f"host-only emitted SHA256 {hashlib.sha256(emitted).hexdigest()}", flush=True)
    audit_emitted_originals(emitted, report, abi)
    if audit_linked_metaclass(emitted, abi["metaclass"]) != got:
        raise SystemExit("prelink emission moved the native gMetaClass GOT entry")
    if audit_linked_originals(emitted, abi["original_imports"], refs) != slots:
        raise SystemExit("prelink emission changed a linked Legacy slot")
    if not a.candidate:
        print("strict emitter accepted; output discarded, runtime still ineligible")
        return
    (out / "prelink.macho").write_bytes(emitted)
    (out / "prelink.json").write_text(json.dumps(report, indent=2) + "\n")
    final = render_candidate(r35, out, native, mapfile)
    if a.r35l_dir and any(definitions(image)[DSP_SET] != 1 for image in (native, final)):
        raise SystemExit("DSP setter must have one linked definition")
    if (audit_linked_metaclass(final.read_bytes(), abi["metaclass"]) != got
            or audit_linked_originals(final.read_bytes(), abi["original_imports"], refs) != slots):
        raise SystemExit("r35 renderer changed the linked display ABI")
    if a.hid_standin:
        final_bytes = final.read_bytes()
        hid_final = hid.audit_linked(final_bytes, hid_abi)
        if hid_final != hid_native:
            raise SystemExit("rendered kernel changed the linked HID ABI")
        hid.audit_family(final_bytes, hid_abi, report)
        (out / "hid/final-audit.json").write_text(json.dumps({
            **hid_final, "kernel_sha256": digest(final)}, indent=2) + "\n")
    print(f"r35 display diagnostic candidate SHA256 {digest(final)}")


if __name__ == "__main__":
    main()
