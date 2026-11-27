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
import zlib
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
R35L_EXEC_SHA = "18943db0ecb642fdf64626b489a6657ea53ab39baa078c126b184cf9a8e7bd1b"
R35L_EXEC_OBJECT_SHA = "e9d5f1552d1606ba8f6a7ad4f288cde700c61c23daa7c997b19911da5cff7ca3"
STAGE_PATCH = ROOT / "patches/xnu/8796-nuwa-boot-progress.patch"
EARLY_COUNTERS = ("_native_legacy_early_failures", "_native_legacy_early_retires")
HOOKS = ("8796-offline-legacy-display-early.patch", "8796-offline-legacy-display-late.patch")
# SMP bring-up gate (--smp-gate): the reset-vector affinity fix and the one-secondary admission.
# The two sources are pinned by their upstream contents; the built objects are audited to differ
# from the recorded originals only through the intended hunks (the unmodified recipes reproduce
# both recorded objects bit for bit - see docs/nuwa-smp-gate-20261123.md).
SMP_START_PATCH = ROOT / "patches/xnu/8796-nuwa-smp-affinity.patch"
SMP_START_PATCH_SHA = "bd19f351eb63f1d628815192f98a27444a5df8f10a9b8e732349c888e385e4ff"
SMP_ARMCPU_PATCH = ROOT / "patches/armcpu/nuwa-smp-one-secondary.patch"
SMP_ARMCPU_PATCH_SHA = "cdd58b888871f33d2df8e271c9796d74822c482f41421a840f3b8670849a9fcc"
SMP_OBSERVE_PATCH = ROOT / "patches/armcpu/nuwa-smp-observe.patch"
SMP_OBSERVE_PATCH_SHA = "e582d12bcf043968bce6b24529dce1415fd68b6e367290c560a6bdbd31595669"
XNU_START_SHA = "58e5235c3392802782f28bebc3d16e0db17be8fbea9ca87c2a40880257c5ca31"
START_RECORD_SHA = "889aef40dcdc5c9f97167f270b230603da85ff1f26862ae69e0bb5e0f36e53aa"
ARMCPU_SOURCE_SHA = "7671ab15842f26db3081526e3e546faa8d48c7787f78edddc4815dc5b292845c"
ARMCPU_RECORD_SHA = "5ac144f5734e33011f60997afaa1ade7f5d6b7a5f7db7cfce95a31f52790207e"
ARMCPU_RECORDED_OBJECT_SHA = "c18059c1354a6012c878ae059145b2c2b4c57679cd8a1ea7aea4bc895d63b73f"


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


def smp_gate_link(base, out, cwd, filelist, argv, *, smp_observe):
    """Replace start.o and the ArmCpu archive with builds of the two gated sources.

    Both hunks are no-ops without sheng-smp: the boot CPU never enters reset_vector and
    the ArmCpu probe keeps its sheng-smp==0 early return. The unmodified recipes (same
    toolchain, same cwd, same flags) reproduce the recorded start.o and ArmCpu.o bit for
    bit, so the recorded objects and the two sources stay pinned while the new objects
    come from the staged copies. The ArmCpu component checkout is CRLF on this host; the
    staged copy is normalised to LF before patching, and -ffile-prefix-map keeps the
    embedded __FILE__ at the upstream path so the object differs only by the hunk.
    """
    require_pin(SMP_START_PATCH, SMP_START_PATCH_SHA)
    require_pin(SMP_ARMCPU_PATCH, SMP_ARMCPU_PATCH_SHA)
    tree = cwd.parents[3]
    work = out / "tree"

    # reset_vector affinity mask: 0xFF -> 0xFFFF when BCM2837 is configured.
    start_source = tree / ".cache/xnu-work/osfmk/arm64/start.s"
    require_pin(start_source, XNU_START_SHA)
    staged_start = work / "osfmk/arm64/start.s"
    staged_start.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(start_source, staged_start)
    run(["patch", "--batch", "--fuzz=0", "--no-backup-if-mismatch", "-p1",
         "-i", SMP_START_PATCH], cwd=work)
    start_record = cwd / "osfmk/DEVELOPMENT/start.o.json"
    require_pin(start_record, START_RECORD_SHA)
    record = json.loads(start_record.read_text().strip().rstrip(","))
    command = list(record["arguments"])
    start_object = out / "osfmk/DEVELOPMENT/start.o"
    start_object.parent.mkdir(parents=True, exist_ok=True)
    command[command.index(record["file"])] = str(staged_start)
    command[command.index("-o") + 1] = str(start_object)
    run(command, cwd=record["directory"])
    old_line = str(cwd / "osfmk/DEVELOPMENT/start.o") + "\n"
    if filelist.splitlines(keepends=True).count(old_line) != 1:
        raise SystemExit("expected one r35 start.o in the native filelist")
    filelist = filelist.replace(old_line, str(start_object) + "\n", 1)

    # One admitted secondary: the ArmCpu probe keeps only reg 0x100 when sheng-smp is set.
    armcpu_source = base / "drivers/ArmCpu/ArmCpu.cpp"
    require_pin(armcpu_source, ARMCPU_SOURCE_SHA)
    raw = armcpu_source.read_bytes()
    if b"\r\n" not in raw:
        raise SystemExit("ArmCpu component checkout is not the expected CRLF copy")
    lf = raw.replace(b"\r\n", b"\n")
    if b"\r" in lf:
        raise SystemExit("ArmCpu component has a bare CR after normalisation")
    staged_armcpu = work / "drivers/ArmCpu/ArmCpu.cpp"
    staged_armcpu.parent.mkdir(parents=True, exist_ok=True)
    staged_armcpu.write_bytes(lf)
    run(["patch", "--batch", "--fuzz=0", "--no-backup-if-mismatch", "-p1",
         "-i", SMP_ARMCPU_PATCH], cwd=work)
    if smp_observe:
        require_pin(SMP_OBSERVE_PATCH, SMP_OBSERVE_PATCH_SHA)
        run(["patch", "--batch", "--fuzz=0", "--no-backup-if-mismatch", "-p1",
             "-i", SMP_OBSERVE_PATCH], cwd=work)
    armcpu_dir = cwd.parents[2] / "armcpu"
    armcpu_record = armcpu_dir / "compile-command.json"
    require_pin(armcpu_record, ARMCPU_RECORD_SHA)
    require_pin(armcpu_dir / "ArmCpu.o", ARMCPU_RECORDED_OBJECT_SHA)
    command = json.loads(armcpu_record.read_text())
    command[command.index("-xc++") + 1] = str(staged_armcpu)
    command[command.index("-o") + 1] = str(out / "ArmCpu.o")
    # Two warnings clang-24 raises on this source that the recorded machine did not have
    # enabled; they change no code (the unmodified compile reproduces ArmCpu.o bit for bit
    # with them added). -ffile-prefix-map keeps __FILE__ at the upstream tree path.
    command += ["-Wno-missing-designated-field-initializers", "-Wno-unused-but-set-global",
                "-ffile-prefix-map=" + str(work) + "=" + str(tree)]
    run(command, cwd=cwd / "iokit/DEVELOPMENT")
    run(["llvm-ar", "rcs", out / "libArmCpu.a", out / "ArmCpu.o"], cwd=armcpu_dir)
    force_at, = [i for i, arg in enumerate(argv)
                 if arg.startswith("-Wl,-force_load,") and arg.endswith("/build/armcpu/libArmCpu.a")]
    argv[force_at] = "-Wl,-force_load," + str(out / "libArmCpu.a")
    (out / "smp-gate.json").write_text(json.dumps({
        "tree": str(tree),
        "xnu_start_sha256": digest(start_source),
        "armcpu_source_sha256": digest(armcpu_source),
        "armcpu_source_normalised_sha256": digest(staged_armcpu),
        "start_patch_sha256": digest(SMP_START_PATCH),
        "armcpu_patch_sha256": digest(SMP_ARMCPU_PATCH),
        **({"observe_patch_sha256": digest(SMP_OBSERVE_PATCH)} if smp_observe else {}),
        "start_object_sha256": digest(start_object),
        "armcpu_object_sha256": digest(out / "ArmCpu.o"),
        "armcpu_archive_sha256": digest(out / "libArmCpu.a"),
        "recorded_start_object_sha256": digest(cwd / "osfmk/DEVELOPMENT/start.o"),
        "recorded_armcpu_object_sha256": digest(armcpu_dir / "ArmCpu.o"),
        "recorded_armcpu_archive_sha256": digest(armcpu_dir / "libArmCpu.a"),
        "armcpu_extra_flags": ["-Wno-missing-designated-field-initializers",
                               "-Wno-unused-but-set-global",
                               "-ffile-prefix-map=" + str(work) + "=" + str(tree)],
        "filelist_start_line": str(start_object),
        "argv_armcpu_force_load": argv[force_at],
    }, indent=2) + "\n")
    return filelist


def stage_sources(patch, source, header):
    """Replay only the new additions onto the already-patched r35l tree."""
    from generate_r35_display_diag import replace_once

    def addition(start, end):
        first = patch.splitlines(keepends=True)
        a, = (i for i, line in enumerate(first) if line == b"+" + start + b"\n")
        b = first.index(b"+" + end + b"\n", a + 1)
        if not all(line.startswith(b"+") for line in first[a:b + 1]):
            raise ValueError("stage-channel patch block contains non-additions")
        return b"".join(line[1:] for line in first[a:b + 1])

    hook = addition(b"#if defined(XNU_BOOT_PROGRESS) && XNU_BOOT_PROGRESS && defined(XNU_NUWA_STAGE_CHANNEL)",
                    b"#endif /* XNU_NUWA_STAGE_CHANNEL */")
    declaration = addition(b"#if defined(XNU_NUWA_STAGE_CHANNEL)", b"#endif")
    point = b"\t\terror = proc_process_signature(p, &signature_failure_reason);\n"
    return (replace_once(source, point, hook + point),
            replace_once(header, b"#else\n", declaration + b"#else\n"))


def stage_exec_link(r35, out, records, filelist, env):
    recipe, = (r for r in records if r["label"] == "compile-kern_exec" and r["exit"] == 0)
    command = list(recipe["argv"])
    source_at, = (i for i, arg in enumerate(command) if arg.endswith("/tree/bsd/kern/kern_exec.c"))
    original = Path(command[source_at])
    recorded_tree = original.parents[2]
    output_at = command.index("-o") + 1
    old_obj = Path(command[output_at])
    for location in (original, r35 / original.relative_to(recorded_tree.parent)):
        require_pin(location, R35L_EXEC_SHA)
    for location in (old_obj, r35 / old_obj.name):
        require_pin(location, R35L_EXEC_OBJECT_SHA)
    old_line = str(old_obj) + "\n"
    if filelist.splitlines(keepends=True).count(old_line) != 1:
        raise SystemExit("expected one pinned kern_exec.o in the native filelist")

    work = out / "tree"
    header = Path("osfmk/kern/boot_progress.h")
    staged_source = work / original.relative_to(recorded_tree)
    staged_header = work / header
    staged_source.parent.mkdir(parents=True, exist_ok=True)
    staged_header.parent.mkdir(parents=True, exist_ok=True)
    require_pin(recorded_tree / header, digest(r35 / "tree" / header))
    src, hdr = stage_sources(STAGE_PATCH.read_bytes().replace(b"\r\n", b"\n"), original.read_bytes(),
                             (recorded_tree / header).read_bytes())
    staged_source.write_bytes(src)
    staged_header.write_bytes(hdr)

    obj = out / old_obj.name
    command[source_at] = str(staged_source)
    command[output_at] = str(obj)
    include_at, = (i for i in range(1, len(command)) if command[i - 1] == "-I"
                   and command[i] == str(recorded_tree / "osfmk"))
    command[include_at - 1:include_at - 1] = ["-I", str(work / "osfmk")]
    command += [f"-ffile-prefix-map={work}={recorded_tree}", "-DXNU_NUWA_STAGE_CHANNEL=1"]
    (out / "kern-exec-argv.json").write_text(json.dumps(command, indent=2) + "\n")
    subprocess.run(command, cwd=recipe["cwd"], env=env, check=True)
    return filelist.replace(old_line, str(obj) + "\n", 1)


def candidate_link(r35, out, records, argv, env, *, bringup_diag, hid, mg_reset,
                    smp_gate=False, smp_observe=False, crashcap=False, stage=False,
                    base=None, cwd=None):
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
    if crashcap:
        from generate_nuwa_crashcap import generate_handler, generate_ux

        ux, = (r for r in records if r["label"] == "compile-ux_exception" and r["exit"] == 0)
        command = list(ux["argv"])
        old_obj = Path(command[command.index("-o") + 1])
        old_source = old_obj.with_suffix(".c")
        require_pin(old_source, digest(r35 / old_source.name))
        require_pin(old_obj, digest(r35 / old_obj.name))
        new_source = out / old_source.name
        new_source.write_bytes(generate_ux(old_source.read_bytes()))
        new_obj = new_source.with_suffix(".o")
        command[command.index(str(old_source))] = str(new_source)
        command[command.index("-o") + 1] = str(new_obj)
        (out / "ux-exception-argv.json").write_text(json.dumps(command, indent=2) + "\n")
        subprocess.run(command, cwd=ux["cwd"], env=env, check=True)
        old_line = str(old_obj) + "\n"
        if filelist.splitlines(keepends=True).count(old_line) != 1:
            raise SystemExit("expected one pinned ux_exception.o in the native filelist")
        filelist = filelist.replace(old_line, str(new_obj) + "\n", 1)
        handler_obj = cwd / "osfmk/DEVELOPMENT/ux_handler.o"
        record = json.loads(handler_obj.with_suffix(".o.json").read_text().strip().rstrip(","))
        command = list(record["arguments"])
        source = out / "ux_handler.c"
        source.write_bytes(generate_handler(Path(record["file"]).read_bytes()))
        obj = source.with_suffix(".o")
        command[command.index(record["file"])] = str(source)
        command[command.index("-o") + 1] = str(obj)
        (out / "ux-handler-argv.json").write_text(json.dumps(command, indent=2) + "\n")
        subprocess.run(command, cwd=record["directory"], env=env, check=True)
        old_line = str(handler_obj) + "\n"
        if filelist.splitlines(keepends=True).count(old_line) != 1:
            raise SystemExit("expected one ux_handler.o in the native filelist")
        filelist = filelist.replace(old_line, str(obj) + "\n", 1)
    if smp_gate:
        if base is None or cwd is None:
            raise SystemExit("--smp-gate requires the base checkout and the XNU build cwd")
        filelist = smp_gate_link(base, out, cwd, filelist, argv, smp_observe=smp_observe)
    if stage:
        filelist = stage_exec_link(r35, out, records, filelist, env)
    dest = out / "link.filelist"
    dest.write_text(filelist)
    adjusted = list(argv)
    adjusted[adjusted.index("-filelist") + 1] = str(dest)
    return adjusted


def diag_archive(r35, out, *, hid, mg_reset, smp_observe, crashcap=False, pixsig=False,
                 data_persist=False, stage=False, post_event=False, fua_permissive=False,
                 sb_threads=False, disposable=False):
    from generate_r35_display_diag import generate, data_persist_row, stage_channel

    source = out / "BootProgress.c"
    text = generate((r35 / "BootProgress.c").read_bytes(),
                    mg_reset=mg_reset, smp_observe=smp_observe, pixsig=pixsig)
    if post_event:
        from generate_nuwa_postevent import generate as generate_postevent
        text, _ = generate_postevent(text, sb_threads=sb_threads)
    if crashcap:
        from generate_nuwa_crashcap import generate_banner

        text = generate_banner(text)
    if data_persist:
        text = data_persist_row(text)
        from generate_r35_display_diag import replace_once
        text = replace_once(text, b"static unsigned bp_banner_priority(",
                            b"extern unsigned nuwa_ufs_desc_row(char *, size_t) __attribute__((weak_import));\n"
                            b"extern unsigned nuwa_ufs_mode_row(char *, size_t) __attribute__((weak_import));\n"
                            b"static unsigned bp_banner_priority(")
        text = replace_once(text, b"extern void native_ufs_progress_text(char *, size_t);",
                            b"extern void native_ufs_progress_text(char *, size_t);\n"
                            b"extern unsigned nuwa_ufs_neon_rows(char (*)[120], unsigned) __attribute__((weak_import));")
        text = replace_once(text, b"#if NUWA_GLYPH_SELFTEST\n  nuwa_glyph_selftest(now);",
                            b"  if (&nuwa_ufs_neon_rows) {\n"
                            b"    char evidence[6][120]; unsigned used=nuwa_ufs_neon_rows(evidence,6);\n"
                            b"    for (unsigned i=0;i<used;++i) line(37+i,evidence[i],0xff00ffcc);\n"
                            b"  }\n#if NUWA_GLYPH_SELFTEST\n  nuwa_glyph_selftest(now);")
        text = replace_once(text, b"  unsigned cr=bp_cr_rows(rows,budget),n=cr;",
                            b"  unsigned neon=&nuwa_ufs_neon_rows ? nuwa_ufs_neon_rows(rows,budget) : 0;\n"
                            b"  unsigned cr=neon+bp_cr_rows(rows+neon,budget-neon),n=cr;")
        text = replace_once(text, b'!strncmp(s,"PROC",4) ||',
                            b'!strncmp(s,"UFS lu=",7) || !strncmp(s,"UFS err=",8) || !strncmp(s,"UFS2 ",5) || !strncmp(s,"PROC",4) ||')
        text = replace_once(text, b'    snprintf(rows[n++],120,"PROC n=%d SB=%s",nprocs,value);\n',
                            b'    snprintf(rows[n++],120,"PROC n=%d SB=%s",nprocs,value);\n'
                            b'    if (n < 64 && &nuwa_ufs_desc_row)\n'
                            b'      n += nuwa_ufs_desc_row(rows[n], sizeof rows[0]);\n'
                            b'    if (n < 64 && &nuwa_ufs_mode_row)\n'
                            b'      n += nuwa_ufs_mode_row(rows[n], sizeof rows[0]);\n')
    if stage:
        text = stage_channel(text)
    source.write_bytes(text)
    shutil.copyfile(r35 / "BootProgressDisplay.h", out / "BootProgressDisplay.h")
    if pixsig:
        shutil.copyfile(ROOT / "package/NuwaPixelSig.h", out / "NuwaPixelSig.h")
    stubs = ROOT / "package/boot-progress-r13/nuwa_boot_progress_stubs.c"
    require_pin(stubs, "14817837f64b37f36c65ac5e6debd187c2d8e6a24e8b0396eb280239108c6b47")
    hid_define = ["--define", "NUWA_HID_STANDIN=1"] if hid else []
    fua_define = ["--define", "NUWA_FUA_TRIAL=1"] if fua_permissive else []
    disposable_define = ["--define", "NUWA_DISPOSABLE_DATA=1"] if disposable else []
    run([sys.executable, "-B", r35 / "build-boot-progress-compact.py",
         "--out", out, "--tree", r35 / "tree", "--stubs", stubs, "--renderer", source,
         "--define", "NUWA_VIRTIO_STUBS=1", "--define", "NUWA_RENDER_FIXES=1",
         "--define", "NUWA_BOLD_GLYPHS=1", *hid_define, *fua_define, *disposable_define])
    staged = out / "libBootProgress.a"
    expected = definitions(r35 / staged.name) + Counter({DSP_SET: 1, "_boot_progress_prop_set": 1})
    if post_event:
        expected["_boot_progress_exit_parent"] = 1
        expected["_boot_progress_critical_capture"] = 1
        expected["_boot_progress_critical_paint"] = 1
    if crashcap:
        expected["_boot_progress_lsd_crash"] = 1
    if stage:
        expected["_boot_progress_stage_publish"] = 1
    if hid:
        for name in ("seq", "count", "xs", "ys"):
            require = expected.pop(f"_native_touch_{name}", 0)
            if require != 1:
                raise SystemExit(f"expected one original renderer alias for native_touch_{name}")
    if definitions(staged) != expected:
        raise SystemExit("r35l renderer global definitions differ from the selected features")
    return staged


def persist_diag_link(r35, out, records, argv, env, data_candidate=False, disposable=False,
                      fua_permissive=False):
    recipe, = (r for r in records if r["label"] == "compile-NativeRamBlock" and r["exit"] == 0)
    archive_recipe, = (r for r in records if r["label"] == "archive-NativeRamBlock" and r["exit"] == 0)
    command = list(recipe["argv"])
    at, = (i for i, arg in enumerate(command) if arg.endswith("/nuwa-ramblock/NativeRamBlock.cpp"))
    command[at] = str(ROOT / "package/nuwa-ramblock/NativeRamBlock.cpp")
    obj = out / "NativeRamBlock.o"
    command[command.index("-o") + 1] = str(obj)
    if data_candidate:
        command.append("-DNUWA_DATA_CANDIDATE=1")
    if disposable:
        command.append("-DNUWA_DISPOSABLE_DATA=1")
    if fua_permissive:
        command.append("-DNUWA_DISPOSABLE_FUA_PERMISSIVE=1")
    (out / "ramblock-argv.json").write_text(json.dumps(command, indent=2) + "\n")
    with (out / "compile-NativeRamBlock.log").open("wb") as log:
        subprocess.run(command, cwd=recipe["cwd"], env=env, stdout=log, stderr=subprocess.STDOUT, check=True)

    spec = importlib.util.spec_from_file_location("nuwa_late", ROOT / "scripts/build-nuwa-platform-power.py")
    late = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(late)
    late.INIT_NAME = "__GLOBAL__sub_I_NativeRamBlock.cpp"
    late_obj = out / "NativeRamBlock.late.o"
    late.late_transform(obj, late_obj, late.INIT_NAME)
    late.verify_late(late_obj.read_bytes())
    # Prove the reused transformer reproduces the historical late object.
    control = out / "ramblock-late-control.o"
    late.late_transform(r35 / obj.name, control, late.INIT_NAME)
    require_pin(control, digest(r35 / late_obj.name))

    dest = out / "libNativeRamBlock.a"
    original = Path(archive_recipe["argv"][2])
    pin = "fe0c663a1fd9ec6346d0498b11e7f0228c18e9cf743242fc69378b5d490ef6fa"
    require_pin(original, pin)
    require_pin(r35 / dest.name, pin)
    run([*archive_recipe["argv"][:2], dest, late_obj])
    expected = definitions(original) + Counter({"_nuwa_data_persist_open_why": 1})
    if disposable:
        expected += Counter({"_nuwa_disposable_fua_requests": 1, "_nuwa_disposable_flushes": 1})
    if definitions(dest) != expected:
        raise SystemExit("RamBlock diagnostic archive definitions changed beyond the reason and FUA counters")
    args = list(argv)
    force_at, = (i for i, arg in enumerate(args) if arg == f"-Wl,-force_load,{original}")
    args[force_at] = f"-Wl,-force_load,{dest}"
    return args


def data_candidate_link(out, argv, env, gpt, disposable=False):
    root = ROOT / "out/nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate"
    source = root / "source/NativeUfs.cpp"
    require_pin(source, "bb994c583382755ddfae954b23aff94d77a97428c7c933232b574ad3cd64b2bf")
    require_pin(source.with_name("RootCommands.h"), "a16e55e1c1b3665231ec5d4c07fe9b1cdeb7edf834bd48f79e3aa80d6f8fa13a")
    combined = source.with_name("CombinedRead.h")
    require_pin(combined, "1adfeb01ca8c1621d83499179fdc0a026abb083f2f22c6eedc02c9b0b3eaaa5d")
    raw = gpt.read_bytes()
    h, table = raw[4096:8192], raw[8192:12288]
    u = table[31 * 128:]

    def num(buf, pos, width=8):
        return int.from_bytes(buf[pos:pos + width], "little")

    if (len(table) != 4096 or h[:8] != b"EFI PART" or
            (num(h, 8, 4), num(h, 12, 4), num(h, 24), num(h, 32), num(h, 40),
             num(h, 48), num(h, 72), num(h, 80, 4), num(h, 84, 4),
             num(u, 32), num(u, 40)) !=
            (0x10000, 92, 1, 61850623, 6, 61850618, 2, 32, 128, 3110976, 61850618) or
            zlib.crc32(h[:16] + b"\0"*4 + h[20:92]) != num(h, 16, 4) or
            zlib.crc32(table) != num(h, 88, 4) or
            u[56:128] != "userdata".encode("utf-16-le").ljust(72, b"\0") or
            not all(any(x) for x in (h[56:72], u[:16], u[16:32]))):
        raise SystemExit("local nuwa GPT identity capture failed validation")
    private = out / "nuwa-data-provider"
    private.mkdir()
    code = ROOT / "package/nuwa-data-write"
    guids = ", ".join("{" + ",".join(map(str, value)) + "}" for value in (h[56:72], u[:16], u[16:32]))
    text = source.read_text()

    def replace(old, new):
        nonlocal text
        if text.count(old) != 1:
            raise SystemExit(f"unexpected retained provider splice anchor: {old[:100]!r}")
        text = text.replace(old, new)

    text = f'#include "{code / "Provider.h"}"\n#include "{code / "Neon.h"}"\n' + text
    if disposable:
        text = (f'#include "{code / "DisposableData.h"}"\n'
                'extern "C" uint8_t native_ram_block_seed_sha256[32];\n' + text)
    preserved = source.with_name("PreservedNop.h")
    # Keep the exact order and short-circuiting of the pre-write HC reads.
    # Cache only values already read; never read old bases or RSR for NEON.
    preserved_text = preserved.read_text()
    from generate_r35_display_diag import replace_once
    old = b"  if (!p.claim()) return End::Claimed;\n  s.stage = 1;"
    preserved_text = replace_once(preserved_text.encode(), old, old.replace(
        b"  s.stage = 1;", b"  neonBegin();\n  s.stage = 1;")).decode()
    start = preserved_text.index("  if (!s.dma ||")
    stop = preserved_text.index("  s.stage = 2;", start)
    prereq = preserved_text[start:stop].replace("  if (", "  const bool reject = (", 1)
    if not prereq.endswith("\n    return End::Prerequisite;\n"):
        raise SystemExit("unexpected retained NEON prerequisites")
    prereq = prereq.removesuffix("\n    return End::Prerequisite;\n") + ";\n"
    for i, offset in enumerate(("0", "0x34", "0x30", "0x58", "0x78", "0x20")):
        old = f"p.hread({offset})"
        if prereq.count(old) != 1:
            raise SystemExit(f"unexpected retained NEON HC read {offset}")
        prereq = prereq.replace(old, f"hcRead({i}, {offset})")
    (private / preserved.name).write_text(
        f'#include "{code / "Neon.h"}"\n'
        "static bool neonBegin();\n" +
        preserved_text[:start] +
        "  const auto hcRead = [&](unsigned, unsigned off) {\n"
        "    return p.hread(off);\n"
        "  };\n" + prereq +
        "  if (reject) return End::Prerequisite;\n" +
        preserved_text[stop:])
    replace('#include "PreservedNop.h"',
            f'#define NUWA_NEON_SETUP\n#include "{code / "RetainedNeon.inc"}"\n'
            '#undef NUWA_NEON_SETUP\n#include "PreservedNop.h"')
    combined_text = combined.read_text()
    for old, new in (
        ("Capacity, Read, Sense };", "Capacity, Read, Sense, WriteFua, QueryDesc, ModeSense };"),
        ("Capacity, Claimed };", "Capacity, Claimed, QueryError };"),
        ("  PreservedNop::State setup;", "  PreservedNop::State setup;\n  NuwaUfsDesc::Request desc;"),
        ("  return c == Command::Capacity ? 8 :", "  if (c == Command::ModeSense) return NuwaUfsDesc::ModeBytes;\n"
         "  return c == Command::Capacity ? 8 :"),
        ("c == Command::Read ? block :", "(c == Command::Read || c == Command::WriteFua) ? block :"),
        ("unsigned blocks = 1) {\n  if (c == Command::Read",
         "unsigned blocks = 1, const uint8_t *writeSource = nullptr, NuwaUfsDesc::Request desc = {}) {\n"
         "  if (c == Command::QueryDesc && !desc.valid()) return false;\n"
         "  if ((c == Command::WriteFua) != bool(writeSource) ||\n"
         "      (writeSource && (block != NuwaData::Block || blocks != 1 || lba > UINT32_MAX))) return false;\n"
         "  if (c == Command::Read"),
        ("w[0] = 0x10000000U | (n ? 2U << 25 : 0);",
         "w[0] = 0x10000000U | (n ? (writeSource ? 1U : 2U) << 25 : 0);"),
        ("u[1] = n ? 0x40 : 0;", "u[1] = n ? (writeSource ? 0x20 : 0x40) : 0;"),
        ("  if (c == Command::Query) {", "  if (c == Command::QueryDesc) return NuwaUfsDesc::encode(desc, u);\n"
                                       "  if (c == Command::Query) {"),
        ("    case Command::Sense: u[16]",
         "    case Command::ModeSense: memcpy(u + 16, NuwaUfsDesc::ModeCdb, sizeof NuwaUfsDesc::ModeCdb); break;\n"
         "    case Command::WriteFua: {\n"
         "      uint8_t cdb[10];\n"
         "      NuwaData::write10(cdb, uint32_t(lba));\n"
         "      memcpy(u + 16, cdb, sizeof cdb);\n"
         "      memcpy(v + Data, writeSource, NuwaData::Block);\n"
         "      break;\n"
         "    }\n"
         "    case Command::Sense: u[16]"),
        ("static End issue(P &p, State &s, Command c) {",
         "static End issue(P &p, State &s, Command c, const uint8_t *writeSource = nullptr) {"),
        ("s.readLba, s.readBlocks))", "s.readLba, s.readBlocks, writeSource, s.desc))"),
    ):
        if combined_text.count(old) != 1:
            raise SystemExit("unexpected retained WRITE(10) splice anchor")
        combined_text = combined_text.replace(old, new)
    if disposable:
        for old, new in (
            ("WriteFua, QueryDesc", "WriteFua, WriteVolatile, QueryDesc"),
            ("c == Command::WriteFua", "(c == Command::WriteFua || c == Command::WriteVolatile)"),
            ("case Command::WriteFua: {", "case Command::WriteVolatile:\n    case Command::WriteFua: {"),
            ("NuwaData::write10(cdb, uint32_t(lba));",
             "NuwaData::write10(cdb, uint32_t(lba));\n"
             "      if (c == Command::WriteVolatile) cdb[1] = 0; // no FUA"),
        ):
            if old not in combined_text:
                raise SystemExit("unexpected disposable WRITE(10) splice anchor")
            combined_text = combined_text.replace(old, new)
    replace("unsigned blocks = 1) {\n    // Bounded pre-command markers",
            "unsigned blocks = 1, const uint8_t *writeSource = nullptr, NuwaUfsDesc::Request desc = {}) {\n"
            "    // Bounded pre-command markers")
    replace("CombinedRead::encode(virt, pa, c, tag, block, lba, blocks)",
            "CombinedRead::encode(virt, pa, c, tag, block, lba, blocks, writeSource, desc)")
    start = combined_text.index("// Valid CHECK CONDITION is a SCSI endpoint")
    end = combined_text.index("template<class P> static bool guard", start)
    combined_text = (combined_text[:start] + f'#include "{code / "RetainedResponse.inc"}"\n' +
                     combined_text[end:])
    old = "if (s.finaldb || s.poll.ocs || (p.hread(0x20) & kUfsFatalStatus))"
    if combined_text.count(old) != 1:
        raise SystemExit("unexpected retained completion splice anchor")
    (private / combined.name).write_text(combined_text.replace(
        old, "if ((s.poll.doorbellSeen & ~1U) || s.finaldb || s.poll.ocs ||\n"
        "      (p.hread(0x20) & kUfsFatalStatus))"))
    commands = source.with_name("RootCommands.h").read_text()
    for old, new in (
        ("gHost.ready && !gHost.poisoned && !combined_state.quarantined",
         "retainedReadyLocked()"),
        ("RootReadSession::read(combined_hardware, combined_state, lba, blocks)",
         "retainedReadLocked(lba, blocks)"),
        ("gHost.ready = false; gHost.poisoned = true;\n"
         "        result = end == CombinedRead::End::Transport &&\n"
         "                 combined_hardware.expired() ? kIOReturnTimeout : kIOReturnIOError;",
         "result = retainedSlot.state() == NuwaData::State::TIMEOUT_ORPHAN ?\n"
         "                 kIOReturnTimeout : kIOReturnIOError;"),
    ):
        if commands.count(old) != 1:
            raise SystemExit("unexpected retained root read splice anchor")
        commands = commands.replace(old, new)
    (private / "RootCommands.h").write_text(commands)
    replace('#include "RootCommands.h"',
            f'#include "{code / "RetainedRead.inc"}"\n#include "{code / "RetainedDesc.inc"}"\n'
            '#include "RootCommands.h"')
    replace('extern "C" void native_ufs_progress_text (char *out, size_t size)',
             'extern "C" unsigned nuwa_ufs_desc_row (char *out, size_t size)\n'
             '{\n  return cachedUfsDescRow(out, size);\n}\n\n'
             'extern "C" unsigned nuwa_ufs_mode_row (char *out, size_t size)\n'
             '{\n  return cachedUfsModeRow(out, size);\n}\n\n'
            'extern "C" void native_ufs_progress_text (char *out, size_t size)')
    replace("  gPendingProvider->release ();  // Balanced with successful thread dispatch.",
            "  if (result.phase == UfsRootPhase::Complete)\n"
            "    probeUfsDescriptors();\n"
            "  gPendingProvider->release ();  // Balanced with successful thread dispatch.")
    replace("if (gHost.ready) return true;", "if (retainedReadySnapshot()) return true;")
    replace("if (!gHost.ready || !name || !lun || !first || !blocks) return 0;",
            "if (!name || !lun || !first || !blocks || !retainedReadySnapshot()) return 0;")
    replace("if (!gHost.ready || !dst || !blocks || lun > 5) return 0;",
            "if (!dst || !blocks || lun > 5 || !retainedReadySnapshot()) return 0;")
    replace("\nStoreGeometry gStoreGeometry;", "\nStoreGeometry gStoreGeometry;\n"
            "static constexpr NuwaData::GptIdentity nuwaDataIdentity = "
            "{61850624, 6, 61850618, 3110976, 61850618, " + guids + "};\n"
            f'#include "{code / "KernelPort.inc"}"\n'
            'constexpr uint32_t kDefaultReserveMiB = 1024;\n'
            f'#include "{code / "RetainedNeon.inc"}"')
    replace("constexpr uint32_t kDefaultReserveMiB = 1024;\nstatic uint64_t",
            "static uint64_t")
    replace("!hostStoreOpen (first, blocks)", "!openCandidateData (first, blocks, reserve)")
    replace('if (!storeMode ()) reason = "off";\n'
            '  else if (!gStoreGeometry.valid || !gHost.ready) reason = "no root layout";',
            'if (!storeMode ()) reason = "off";\n'
            '  else if (!gStoreGeometry.valid || !retainedReadySnapshot()) reason = "no root layout";')
    replace("  if (!gStoreRegionBlocks || !dst || !blocks || rel >= gStoreRegionBlocks || blocks > gStoreRegionBlocks - rel) return 0;",
            "  if (storeMode () == 2) return gHost.lock && dataProvider.read (rel, blocks, dst);\n"
            "  if (!gStoreRegionBlocks || !dst || !blocks || rel >= gStoreRegionBlocks || blocks > gStoreRegionBlocks - rel) return 0;")
    write_start = text.index('extern "C" int native_ufs_store_write ')
    write_end = text.index("// ---- Read-only access", write_start)
    text = text[:write_start] + '''extern "C" int native_ufs_store_write (uint64_t rel, uint32_t blocks, const void *src)
{
  return storeMode () == 2 && gHost.lock && dataProvider.write (rel, blocks, src);
}

extern "C" int native_ufs_store_sync (void)
{
  return storeMode () == 2 && gHost.lock && dataProvider.sync ();
}

''' + text[write_end:]
    if disposable:
        replace("return static_cast<unsigned> (cached);\n}\n}\n\nextern \"C\" unsigned native_ufs_store_mode",
                "return cached == 2 && disposableRequested() ? 2U : 0U;\n}\n}\n\n"
                "extern \"C\" unsigned native_ufs_store_mode")
        replace("!openCandidateData (first, blocks, reserve)", "!openDisposableData (first, blocks, reserve)")
        replace("gHost.lock && dataProvider.read (rel, blocks, dst)", "disposableRead (rel, blocks, dst)")
        replace("gHost.lock && dataProvider.write (rel, blocks, src)", "disposableWrite (rel, blocks, src)")
        replace("return storeMode () == 2 && gHost.lock && dataProvider.sync ();",
                "return 0; // No exposed durability contract.")
        replace("// ---- Read-only access",
                'extern "C" int native_ufs_store_order (void)\n'
                '{\n  return storeMode () == 2 && disposableOrder ();\n}\n\n'
                "// ---- Read-only access")
    log_start = text.index('extern "C" int native_ufs_log_open ')
    log_end = text.index("// One read-only window of the root image", log_start)
    text = text[:log_start] + '''extern "C" int native_ufs_log_open (uint64_t *, uint64_t *, const char **why)
{
  if (why) *why = "UFS diagnostics disabled";
  return 0;
}
extern "C" int native_ufs_log_write (uint64_t, uint32_t, const void *) { return 0; }
extern "C" uint64_t native_ufs_export_blocks (void) { return 0; }
extern "C" int native_ufs_export_write (uint64_t, uint32_t, const void *) { return 0; }
extern "C" int native_ufs_log_sync (void) { return 0; }
extern "C" int native_ufs_log_panic (void) { return 0; }

// Snapshot only: successful root layout qualification already checked GPT.
// Publish before the block services. This is not a fresh media observation.
extern "C" unsigned native_ufs_store_gpt_check (void)
{
  return gStoreGeometry.valid ? 0 : 1;
}

''' + text[log_end:]
    panic_start = text.index("__attribute__((noinline, noreturn)) static void rootReadFailureVisible(")
    panic_end = text.index("static void rootDiagnosticFailure", panic_start)
    text = text[:panic_start] + text[panic_end:]
    replace('''    // Failure is terminal; never call completion after publishing the panic.
    rootReadFailureVisible(operations.verifyStatus ? "integrity" :
      operations.copyFailed ? "short copy" :
      !operations.snapshot.attempted ? "transport rejected" : "transport failed",
      operations.snapshot, operations.verifyIndex, operations.verifyStatus, result);''',
            '''    // Complete accepted I/O after both guards have released their locks.
    // Return success below to acknowledge dispatch, not disk success.''')
    staged = private / source.name
    staged.write_text(text)
    records = json.loads((root / "commands.json").read_text())
    recipe, = (r for r in records if r["label"] == "driver-compile" and r["exit"] == 0)
    command = list(recipe["argv"])
    at, = (i for i, arg in enumerate(command) if arg.endswith("/source/NativeUfs.cpp"))
    command[at] = str(staged)
    obj = private / "NativeUfs.o"
    command[command.index("-o") + 1] = str(obj)
    command.extend(("-I", str(source.parent), "-Wno-unused-function"))
    if disposable:
        command.append("-DNUWA_DISPOSABLE_DATA=1")
    (out / "data-provider-argv.json").write_text(json.dumps(command, indent=2) + "\n")
    with (out / "compile-data-provider.log").open("wb") as log:
        subprocess.run(command, cwd=recipe["cwd"], env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    spec = importlib.util.spec_from_file_location("ufs_late", ROOT / "scripts/build-nuwa-platform-power.py")
    late = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(late)
    late.INIT_NAME = "__GLOBAL__sub_I_NativeUfs.cpp"
    late_obj = private / "NativeUfs.late.o"
    late.late_transform(obj, late_obj, late.INIT_NAME)
    late.verify_late(late_obj.read_bytes())
    rec, = (r for r in records if r["label"] == "ufs-archive" and r["exit"] == 0)
    ar, mode, original, _, *members = rec["argv"]
    require_pin(Path(original), "150bc8439d365249a884033011ef255537618909f97c42fc9bdfad6476a89c75")
    dst = private / Path(original).name
    run([ar, mode, dst, late_obj, *members])
    added = Counter({"_nuwa_ufs_desc_row": 1, "_nuwa_ufs_mode_row": 1, "_nuwa_ufs_neon_rows": 1})
    if disposable:
        added["_native_ufs_store_order"] = 1
    if definitions(dst) != definitions(Path(original)) + added:
        raise SystemExit("restricted provider changed the retained archive export inventory")
    args = list(argv)
    at, = (i for i, arg in enumerate(args) if arg == f"-Wl,-force_load,{original}")
    args[at] = f"-Wl,-force_load,{dst}"
    return args


KERN_EXIT_INPUT_SHA = "72073bac1f8df8e664eba539e7568229e2c863848808ffc9c349826e3e7fc691"
KERN_EXIT_HOOK_OLD = b"""\tboot_progress_exit(proc_getpid(p),p->p_name,rv,
\t    p->p_exit_reason ? p->p_exit_reason->osr_namespace : 0,
\t    p->p_exit_reason ? p->p_exit_reason->osr_code : 0);

\tif (p->p_crash_behavior != 0 || p == initproc) {
\t\tproc_handle_critical_exit(p, rv);
\t}"""
KERN_EXIT_HOOK_NEW = b"""\tboot_progress_exit_parent(proc_getpid(p), p->p_ppid);
\tboot_progress_exit(proc_getpid(p),p->p_name,rv,
\t    p->p_exit_reason ? p->p_exit_reason->osr_namespace : 0,
\t    p->p_exit_reason ? p->p_exit_reason->osr_code : 0);

\tif (p->p_crash_behavior != 0 || p == initproc) {
\t\tproc_handle_critical_exit(p, rv);
\t}"""
KERN_EXIT_CAPTURE_OLD = b"""#endif /* DEVELOPMENT */

\tchar *exit_reason_desc = exit_reason_get_string_desc(p->p_exit_reason);"""
KERN_EXIT_CAPTURE_NEW = b"""#endif /* DEVELOPMENT */

\tboot_progress_critical_capture(proc_getpid(p), p->p_name, rv,
\t    p->p_exit_reason ? p->p_exit_reason->osr_namespace : 0,
\t    p->p_exit_reason ? p->p_exit_reason->osr_code : 0, p->p_ppid);

\tchar *exit_reason_desc = exit_reason_get_string_desc(p->p_exit_reason);"""
KERN_EXIT_PAINT_OLD = b"""\tproc_crash_coredump(p);

\tsync(p, (void *)NULL, (int *)NULL);

\tif (p->p_exit_reason == OS_REASON_NULL) {"""
KERN_EXIT_PAINT_NEW = b"""\tproc_crash_coredump(p);

\tsync(p, (void *)NULL, (int *)NULL);

\tboot_progress_critical_paint();

\tif (p->p_exit_reason == OS_REASON_NULL) {"""


def post_event_link(r35, out, records, argv, env, *, sb_threads=False):
    """Recompile only the three diagnostic TUs the post-event row needs.

    nuwa_data_mount.c latches the completed first mount attempt, nuwa_systemos.c
    publishes pid 1 and SpringBoard from the existing two-second probe, and
    kern_exit.c supplies the parent pid and paints before the critical-exit
    panic.  The filelist replacement keeps the same link order.
    """
    filelist = out / "link.filelist"
    lines = filelist.read_text().splitlines(keepends=True)

    def replace_line(old_obj, new_obj):
        line = str(old_obj) + "\n"
        if lines.count(line) != 1:
            raise SystemExit("post-event: expected one " + old_obj.name + " in link.filelist")
        lines[lines.index(line)] = str(new_obj) + "\n"

    def compile_record(record, source, obj, label, extra=()):
        command = list(record["argv"])
        source_at, = [i for i, arg in enumerate(command) if arg.endswith("/" + source.name)]
        command[source_at] = str(source)
        command[command.index("-o") + 1] = str(obj)
        command.extend(extra)
        with (out / ("compile-" + label + ".log")).open("wb") as log:
            done = subprocess.run(command, cwd=record["cwd"], env=env, stdout=log,
                                  stderr=subprocess.STDOUT)
        if done.returncode:
            raise SystemExit(f"post-event: {label} exit {done.returncode}; see compile-{label}.log")
        return obj

    records = list(records)
    dm_record, = (r for r in records if r["label"] == "compile-nuwa_data_mount" and r["exit"] == 0)
    dm_old, = [Path(line.strip()) for line in lines
               if line.strip().endswith("/nuwa_data_mount.o")]
    dm_obj = compile_record(dm_record, ROOT / "package/nuwa-data/nuwa_data_mount.c",
                            out / "nuwa_data_mount.o", "nuwa_data_mount")
    replace_line(dm_old, dm_obj)

    sm_record, = (r for r in records if r["label"] == "compile-nuwa_systemos" and r["exit"] == 0)
    sm_old, = [Path(line.strip()) for line in lines
               if line.strip().endswith("/nuwa_systemos.o")]
    sm_obj = compile_record(sm_record, ROOT / "package/nuwa-systemos/nuwa_systemos.c",
                            out / "nuwa_systemos.o", "nuwa_systemos",
                            ["-DNUWA_SB_THREADS=1"] if sb_threads else [])
    replace_line(sm_old, sm_obj)

    kx_old, = [Path(line.strip()) for line in lines if line.strip().endswith("/kern_exit.o")]
    kx_recipe = json.loads((kx_old.parent / "commands.json").read_text())
    kx_record, = (r for r in kx_recipe if r["label"] == "compile-kern_exit" and r["exit"] == 0)
    kx_source, = [Path(arg) for arg in kx_record["argv"]
                  if arg.endswith("/tree/bsd/kern/kern_exit.c")]
    if hashlib.sha256(kx_source.read_bytes()).hexdigest() != KERN_EXIT_INPUT_SHA:
        raise SystemExit("post-event: patched kern_exit.c input changed")
    staged = out / "kern_exit.c"
    data = kx_source.read_bytes()
    if data.count(KERN_EXIT_HOOK_OLD) != 1:
        raise SystemExit("post-event: kern_exit.c hook anchor changed")
    data = data.replace(KERN_EXIT_HOOK_OLD, KERN_EXIT_HOOK_NEW, 1)
    if data.count(KERN_EXIT_CAPTURE_OLD) != 1:
        raise SystemExit("post-event: kern_exit.c critical-capture anchor changed")
    data = data.replace(KERN_EXIT_CAPTURE_OLD, KERN_EXIT_CAPTURE_NEW, 1)
    if data.count(KERN_EXIT_PAINT_OLD) != 1:
        raise SystemExit("post-event: kern_exit.c critical-paint anchor changed")
    data = data.replace(KERN_EXIT_PAINT_OLD, KERN_EXIT_PAINT_NEW, 1)
    include = b"#include <kern/boot_progress.h>\n"
    if data.count(include) != 1:
        raise SystemExit("post-event: kern_exit.c include anchor changed")
    data = data.replace(include, include +
                        b"extern void boot_progress_exit_parent(int, int);\n"
                        b"extern void boot_progress_critical_capture(int, const char *, int, unsigned, uint64_t, int);\n"
                        b"extern void boot_progress_critical_paint(void);\n", 1)
    staged.write_bytes(data)
    kx_obj = compile_record(kx_record, staged, out / "kern_exit.o", "kern_exit")
    replace_line(kx_old, kx_obj)

    filelist.write_text("".join(lines))
    (out / "post-event-inputs.json").write_text(json.dumps({
        "kern_exit_source": {"path": str(kx_source), "sha256": KERN_EXIT_INPUT_SHA},
        "kern_exit_staged": {"path": str(staged), "sha256": hashlib.sha256(data).hexdigest()},
        "objects": {obj.name: {"path": str(obj), "sha256": digest(obj)}
                    for obj in (dm_obj, sm_obj, kx_obj)},
    }, indent=2) + "\n")
    return argv


def replay_r35(r35, linker, cpo, out, archive, native, *, cpu_only, candidate,
               keep_link_debug, bringup_diag=False, hid_objects=(), mg_reset=False,
               smp_gate=False, smp_observe=False, crashcap=False, pixsig=False,
               data_persist=False, data_gpt=None, disposable=False, stage=False,
               post_event=False, fua_permissive=False, sb_threads=False,
               data_v1_direct=False, base=None):
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
                                  smp_gate=smp_gate, smp_observe=smp_observe, crashcap=crashcap,
                                  stage=stage, base=base, cwd=cwd)
        if bringup_diag:
            argv = list(argv)
            diag = diag_archive(r35, out, hid=bool(hid_objects), mg_reset=mg_reset,
                                 smp_observe=smp_observe, crashcap=crashcap, pixsig=pixsig,
                                 data_persist=data_persist, stage=stage, post_event=post_event,
                                 fua_permissive=fua_permissive, sb_threads=sb_threads,
                                 disposable=disposable)
            argv[force_at] = f"-Wl,-force_load,{diag}"
        if data_persist:
            argv = persist_diag_link(r35, out, records, argv, env,
                                     data_candidate=data_gpt is not None and not data_v1_direct,
                                     disposable=disposable, fua_permissive=fua_permissive)
        if post_event:
            argv = post_event_link(r35, out, records, argv, env, sb_threads=sb_threads)
        if data_gpt is not None:
            argv = data_candidate_link(out, argv, env, data_gpt, disposable=disposable)
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
    p.add_argument("--pixsig", action="store_true",
                   help="add bounded CPU source pixel diagnostics to the crashframes replay")
    p.add_argument("--stage-channel", action="store_true",
                   help="add the default-off initproc thread-name row to the PIX candidate")
    p.add_argument("--data-persist-diag", action="store_true",
                   help="show the unchanged Data store open's reason in the PIX candidate")
    p.add_argument("--data-candidate-gpt", type=Path,
                   help="link the write-disabled v2 Data candidate using this local 4 KiB GPT capture")
    p.add_argument("--data-v1-direct", action="store_true",
                   help="link the Data provider but compile RamBlock's v1 mode-2 branch; "
                        "host build only, production writes remain disabled")
    p.add_argument("--disposable-data", action="store_true",
                   help="compile the opt-in disposable Data experiment (no durability or initialization)")
    p.add_argument("--disposable-fua-permissive", action="store_true",
                   help="diagnostic experiment: accept FUA and flushes without a durability claim; "
                        "requires --disposable-data --post-event and is off by default")
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
    p.add_argument("--smp-gate", action="store_true",
                   help="rebuild start.o and ArmCpu.o: reset-vector affinity fix plus one-secondary admission")
    p.add_argument("--smp-observe", action="store_true",
                   help="show CPU_ON and secondary affinity observations; does not enable SMP")
    p.add_argument("--crashcap", action="store_true",
                   help="include the lsd-only saved-register recorder in the single-core candidate")
    p.add_argument("--post-event", action="store_true",
                   help="add the panic-safe pid 1/SpringBoard/exit-parent/Data-first-attempt summary")
    p.add_argument("--sb-threads", action="store_true",
                   help="sample SpringBoard user saved state using the --post-event process probe")
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
    if a.smp_gate and not (a.candidate and a.cpu_only):
        p.error("--smp-gate requires --candidate --cpu-only")
    if a.smp_observe and not (a.smp_gate and a.r35l_dir):
        p.error("--smp-observe requires --smp-gate and the pinned --r35l-dir candidate")
    if a.crashcap and (not a.r35l_dir or a.smp_gate):
        p.error("--crashcap requires the pinned single-core --r35l-dir candidate")
    if a.post_event and not (a.crashcap and a.data_persist_diag and not a.smp_gate):
        p.error("--post-event requires --crashcap --data-persist-diag and excludes --smp-gate")
    if a.sb_threads and not a.post_event:
        p.error("--sb-threads requires --post-event")
    if a.pixsig and not (a.crashcap and a.no_software_vsync):
        p.error("--pixsig requires --crashcap and --no-software-vsync")
    if a.stage_channel and not (a.pixsig and not a.data_persist_diag):
        p.error("--stage-channel requires the single-core PIX candidate without Data changes")
    if a.data_persist_diag and not (a.pixsig and not a.smp_gate):
        p.error("--data-persist-diag requires --pixsig and the single-core candidate")
    if a.data_candidate_gpt and not a.data_persist_diag:
        p.error("--data-candidate-gpt requires --data-persist-diag")
    if a.data_v1_direct and (not a.data_candidate_gpt or a.disposable_data or a.disposable_fua_permissive):
        p.error("--data-v1-direct requires --data-candidate-gpt and excludes disposable options")
    if a.disposable_data and not a.data_candidate_gpt:
        p.error("--disposable-data requires the pinned single-core Data GPT candidate")
    if a.disposable_fua_permissive and not (a.disposable_data and a.post_event):
        p.error("--disposable-fua-permissive requires --disposable-data --post-event")
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
                  (a.pixsig, "--pixsig"),
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
                              smp_gate=a.smp_gate, smp_observe=a.smp_observe, crashcap=a.crashcap,
                               pixsig=a.pixsig, data_persist=a.data_persist_diag,
                               data_gpt=a.data_candidate_gpt, disposable=a.disposable_data,
                                stage=a.stage_channel, post_event=a.post_event,
                                fua_permissive=a.disposable_fua_permissive,
                                sb_threads=a.sb_threads, data_v1_direct=a.data_v1_direct,
                                base=base)
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
