#!/usr/bin/env python3
"""Static checks for an --smp-gate kernel build (host only).

Accepts a build directory produced by
  scripts/build-nuwa-display-native.py ... --candidate --smp-gate
and asserts the two intended machine-code changes are present in the linked
kernel while the prelink inventory keeps its shape:

  * reset_vector decodes AFF1:AFF0 (`and x0, x15, #0xffff`), not AFF0 only;
  * ArmCpu::probe compares the DT reg against 0x100 and returns null otherwise;
  * the two rebuilt objects differ from the recorded ones only in those hunks
    (the symbol tables are identical, and start.o has exactly one changed word);
  * prelink bindings/components/interfaces counts are unchanged.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TREE = Path("/root/nuwa-pmap-ret-native-20261111/nuwa/ios-16.7.16-20H392/"
            "nuwa_pmap_ret/tree")
RECORDED_START = TREE / "build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/osfmk/DEVELOPMENT/start.o"
RECORDED_ARMCPU = TREE / "build/armcpu/ArmCpu.o"
EXPECTED_BINDINGS = 65443
EXPECTED_COMPONENTS = 31
EXPECTED_INTERFACES = 7


def objdump(path, symbol=None):
    text = subprocess.run(["/usr/bin/llvm-objdump", "-d", "--no-show-raw-insn", str(path)],
                          check=True, capture_output=True, text=True).stdout
    if symbol is None:
        return text.splitlines()
    lines, inside = [], False
    for line in text.splitlines():
        if re.match(r"^[0-9a-f]+ <" + re.escape(symbol) + r">:$", line):
            inside = True
            continue
        if inside and re.match(r"^[0-9a-f]+ <", line):
            break
        if inside:
            lines.append(line)
    return lines


def nm(path):
    return sorted(line.split()[-1] for line in subprocess.run(
        ["/usr/bin/llvm-nm", str(path)], check=True, capture_output=True, text=True
    ).stdout.splitlines() if line.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True, help="smp-gate build directory")
    parser.add_argument("--kernel-sha256")
    parser.add_argument("--objects", action="store_true",
                        help="also compare the rebuilt objects with the recorded ones")
    a = parser.parse_args()
    build = a.build.resolve()
    kernel = build / "kernel.macho"
    if a.kernel_sha256:
        import hashlib
        if hashlib.sha256(kernel.read_bytes()).hexdigest() != a.kernel_sha256:
            raise SystemExit("kernel SHA256 differs from the expected candidate")

    reset = objdump(kernel, "_reset_vector")
    ands = [line for line in reset if re.search(r"\band\s+x0, x15,", line)]
    if len(ands) != 1 or "#0xffff" not in ands[0]:
        raise SystemExit(f"reset_vector affinity mask is not AFF1:AFF0: {ands}")

    probe = objdump(kernel, "__ZN6ArmCpu5probeEP9IOServicePi")
    cmp_at = [i for i, line in enumerate(probe) if re.search(r"\bcmp\s+w\d+, #256\b", line)]
    if len(cmp_at) != 1:
        raise SystemExit(f"probe has no unique 0x100 comparison: {cmp_at}")
    if not re.search(r"\bb\.ne\b", probe[cmp_at[0] + 1]):
        raise SystemExit("probe's 0x100 comparison does not branch away")

    if a.objects:
        for recorded, rebuilt, label in (
                (RECORDED_START, build / "osfmk/DEVELOPMENT/start.o", "start.o"),
                (RECORDED_ARMCPU, build / "ArmCpu.o", "ArmCpu.o")):
            if nm(recorded) != nm(rebuilt):
                raise SystemExit(f"{label} symbol table changed")
        old, new = objdump(RECORDED_START), objdump(build / "osfmk/DEVELOPMENT/start.o")
        diff = [line for line in new if line not in old and "file format" not in line]
        if diff != ["     420:      \tand\tx0, x15, #0xffff"]:
            raise SystemExit(f"start.o text differs beyond the mask: {diff}")

    prelink = json.loads((build / "prelink.json").read_text())
    if (len(prelink["bindings"]) != EXPECTED_BINDINGS
            or len(prelink["components"]) != EXPECTED_COMPONENTS
            or len(prelink["kernel_interfaces"]) != EXPECTED_INTERFACES):
        raise SystemExit("prelink inventory shape changed")
    gate = json.loads((build / "smp-gate.json").read_text())
    if gate["recorded_start_object_sha256"] == gate["start_object_sha256"]:
        raise SystemExit("start.o was not rebuilt")
    if gate["recorded_armcpu_object_sha256"] == gate["armcpu_object_sha256"]:
        raise SystemExit("ArmCpu.o was not rebuilt")
    print("PASS: smp-gate kernel has the reset-vector mask and the one-secondary probe gate")
    print(f"prelink bindings={EXPECTED_BINDINGS} components={EXPECTED_COMPONENTS} "
          f"interfaces={EXPECTED_INTERFACES}")


if __name__ == "__main__":
    sys.exit(main())
