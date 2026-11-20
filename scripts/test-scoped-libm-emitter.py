#!/usr/bin/env python3
"""Negative tests against the actual donor and real display selection."""
import argparse
import ast
import copy
import hashlib
from pathlib import Path
import struct
import sys

import scoped_libm_emitter as scope


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(args.base / "kits/XnuPrelink"))
    emitter = scope.load(args.base)
    donor = (args.base / "out/ipsw/20H392/kernelcache.decompressed").read_bytes()
    native = (root / "out/nuwa-display-ignore-loh-02/HOST-ONLY-display-native.unstripped").read_bytes()
    text = (root / "board.toml").read_text().split("roots = [", 1)[1].split("]", 1)[0]
    roots = list(dict.fromkeys(ast.literal_eval("[" + text + "]") +
                               ["com.apple.iokit.IOMobileGraphicsFamily"]))
    report = emitter.plan(native, donor, roots, -0x1000000)
    parent = emitter.macho(donor)["segments"]
    info = next(s for s in parent if s["name"] == "__PRELINK_INFO")
    at = emitter.backed_offset(parent, info["va"], info["filesize"], len(donor))
    entries = emitter.unserialize_xml(donor[at:at + info["filesize"]])["_PrelinkInfoDictionary"]
    entries = {e["CFBundleIdentifier"]: e for e in entries}
    modules = {name: emitter.macho(donor, emitter.backed_offset(
        parent, entries[name]["_PrelinkExecutableLoadAddr"], 32, len(donor)))
        for name in report["components"]}
    positive = emitter.instruction_inventory(donor, parent, modules)
    assert any(x["module"] == scope.MODULE and x["va"] == scope.START
               and x["sha256"] == scope.REGION_SHA256 for x in positive["known_inline_data"])
    assert positive["register_dataflow_qualified"] is False

    def rejected(name, data, mods, bind_mutated=False):
        emitter.SCOPED_DONOR_SHA256 = hashlib.sha256(data).hexdigest() if bind_mutated else scope.DONOR_SHA256
        try:
            emitter.instruction_inventory(data, parent, mods)
        except ValueError as exc:
            print(name, "REJECTED", str(exc))
        else:
            raise AssertionError(name + " unexpectedly accepted")

    changed = bytearray(donor)
    changed[scope.FILE_OFFSET] ^= 1
    rejected("inside byte flip", changed, modules, True)
    for label, offset in (("outside injected branch", scope.FILE_OFFSET - 8),
                          ("external ADRP before", scope.FILE_OFFSET - 4),
                          ("external ADRP after", scope.FILE_OFFSET + 1224)):
        changed = bytearray(donor)
        # B to a distant external address; ADRP with a large positive page offset.
        struct.pack_into("<I", changed, offset, 0x15ffffff if "branch" in label else 0xf07fffe0)
        rejected(label, changed, modules, True)
    renamed = dict(modules)
    renamed[scope.MODULE + ".other"] = renamed.pop(scope.MODULE)
    rejected("same bytes different module", donor, renamed)
    moved = copy.deepcopy(modules)
    segment = next(s for s in moved[scope.MODULE]["segments"] if s["name"] == "__TEXT_EXEC")
    segment["va"] += 4
    segment["filesize"] -= 4
    rejected("same bytes different segment VA", donor, moved)
    changed = bytearray(donor)
    changed[-1] ^= 1
    rejected("different donor SHA", changed, modules)
    emitter.SCOPED_DONOR_SHA256 = scope.DONOR_SHA256
    emitted, emitted_report = emitter.emit(native, donor, roots, -0x1000000)
    output_segments = emitter.macho(emitted)["segments"]
    pos = emitter.backed_offset(output_segments, scope.START - 0x1000000, 1224, len(emitted))
    assert emitted[pos:pos + 1224] == donor[scope.FILE_OFFSET:scope.FILE_OFFSET + 1224]
    assert emitted_report["register_dataflow_qualified"] is False
    print("real display strict emit SHA256", hashlib.sha256(emitted).hexdigest(),
          "region byte-identical", True)


if __name__ == "__main__":
    main()
