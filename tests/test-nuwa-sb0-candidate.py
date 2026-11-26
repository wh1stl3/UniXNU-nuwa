#!/usr/bin/env python3
"""Run the exclusive staged SB0 transport against the retained host fixture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

MAIN = r"""
int main() {
  using Sb0::Result;
  NuwaData::FixtureGpt disk;
  NuwaData::GptBuffers buffers;
  constexpr bool wx = NUWA_SB0_PROFILE == 3;
  for (unsigned i = 0; i < (wx ? 22U : 18U); ++i) {
    combined_hardware = {};
    combined_state = {};
    combined_state.block = NuwaData::Block;
    combined_state.blocks = nuwaDataIdentity.capacity;
    combined_state.capacity = combined_state.blocks * NuwaData::Block;
    combined_state.setup.dma = Hardware::Dma;
    assert(PreservedNop::domain(combined_hardware, combined_state.setup));
    gHost = {true, false, &hostLock};
    new (&retainedSlot) NuwaData::Slot;
    disk = {};
    NuwaData::putLE(disk.b + 72, 61850619, 8); // Historical captured layout, with reserved tail.
    disk.repair();
    Sb0Media media;
    combined_hardware.sb0 = &media;
    combined_hardware.gpt = &disk;
    combined_hardware.grant = !wx && sb0Write && i != 0;
    Result expected = sb0Write ? Result::Good : Result::Blank;
    bool noWrite = !sb0Write;
    uint64_t lba = 0;
    switch (i) {
      case 0:
        if (wx) {
          assert(!combined_hardware.sb0BootWrite.consume());
          assert(combined_hardware.sb0BootWrite.begin());
          assert(combined_hardware.sb0BootWrite.consume());
          assert(!combined_hardware.sb0BootWrite.consume());
          expected = Result::Guard; lba = Sb0::First;
        } else expected = sb0Write ? Result::Unbound : Result::Blank;
        noWrite = true;
        break;
      case 1: break;
      case 2: // Full generated SB0 at the fixed page.
        media.corruptAt = Sb0::First;
        memcpy(media.existing.data(), Sb0::Payload, NuwaData::Block);
        expected = sb0Write ? Result::Mismatch : Result::Exact;
        lba = sb0Write ? Sb0::First : 0;
        noWrite = true;
        break;
      case 3:
        media.corruptAt = lba = Sb0::First + 769;
        media.existing.back() = 1; expected = Result::Mismatch; noWrite = true; break;
      case 4:
        media.readErrorAt = lba = Sb0::First + 490;
        expected = Result::Io; noWrite = true; break;
      case 5: disk.be[0] ^= 1; expected = Result::Gpt; noWrite = true; break;
      case 6: combined_state.block = 512; expected = Result::Geometry; noWrite = true; break;
      case 15:
        media.corruptAt = lba = Sb0::First;
        memcpy(media.existing.data(), Sb0::Payload, NuwaData::Block);
        media.existing.back() ^= 1; expected = Result::Mismatch; noWrite = true; break;
      case 16:
        disk.be[31 * 128 + 48] ^= 1; disk.repair(); // Both CRCs valid; arrays disagree.
        expected = Result::Gpt; noWrite = true; break;
      case 17:
        NuwaData::putLE(disk.b + 72, 57393401, 8); disk.repair();
        expected = Result::Gpt; noWrite = true; break;
      case 18:
        combined_hardware.forcedBusy = true;
        expected = Result::Io; noWrite = true; lba = 1; break;
      default:
        if (!sb0Write) continue;
        switch (i) {
          case 7:
            media.corruptAt = lba = Sb0::Remote;
            media.existing.back() = 1; expected = Result::Mismatch; noWrite = true; break;
          case 8: media.guardAfterPrepare = true; expected = Result::Guard; noWrite = true; lba = Sb0::First; break;
          case 9: case 10: case 11: case 14:
            combined_hardware.corrupt = i; expected = Result::Guard; noWrite = true; break;
          case 12: media.writeWire.timedOut = true; expected = Result::Unknown; break;
          case 13: media.writeWire.badTag = true; expected = Result::Unknown; break;
          case 19: case 20: case 21:
            combined_hardware.corrupt = i; expected = Result::Guard; noWrite = true; break;
        }
    }
    const auto got = sb0Preflight(buffers);
    // Guard after prepare is terminal without a DB0. No second call can retry.
    if (i == 8) lba = 0;
    if (got.result != expected || got.lba != lba)
      fprintf(stderr, "case=%u result=%u expected=%u lba=%llu expected=%llu\n", i,
              unsigned(got.result), unsigned(expected), (unsigned long long)got.lba,
              (unsigned long long)lba);
    assert(got.result == expected && got.lba == lba);
    const unsigned writes = noWrite ? 0 : 1;
    assert(combined_hardware.writeSubmissions == writes);
    assert(combined_hardware.consumed == writes);
    if (writes) assert(!combined_hardware.grant && combined_hardware.consumed == 1);
    if (wx) assert(combined_hardware.sb0BootWrite.spent() == (i == 0 || writes));
    if (got.result == Result::Blank || got.result == Result::Exact ||
        got.result == Result::Good || got.result == Result::Unbound) {
      assert(got.pages == 770 && media.reads.size() == (sb0Write ? 775 : 774));
      assert(media.reads[3] == 61850619);
    }
    if (i == 17) assert(media.reads.size() == 3);
    if (got.result == Result::Good)
      assert(!memcmp(media.persisted.data(), Sb0::Payload, NuwaData::Block));
    const auto commands = combined_hardware.submissions;
    assert(sb0Preflight(buffers).result != Result::Good);
    assert(combined_hardware.submissions == commands);
    printf("PASS %s case=%u pages=%u commands=%u write-DB0=%u once-consumed=%u\n",
           wx ? "WX" : sb0Write ? "W" : "R", i, got.pages, commands, writes, combined_hardware.consumed);
  }
}
"""


def fixture(build, output, role):
    stage = build / "nuwa-data-provider"
    original = ROOT / "tests/test-nuwa-retained-response.cpp"
    text = original.read_text().split("// Minimal kernel-only glue", 1)[0]
    text = text.replace("const auto *page = gpt->at(preparedLba);",
                        "const auto *page = preparedLba == 61850619 ? gpt->be : gpt->at(preparedLba);")
    text = text.replace('#include "CombinedRead.h"',
                        '#include "../package/nuwa-data-write/Sb0Candidate.h"\n#include "CombinedRead.h"')
    start = text.index("    assert(heldLocks && pa == Dma && (c ==")
    stop = text.index("    descriptor = ", start)
    writing = "c == CombinedRead::Command::WriteVolatile" if role != "R" else "false"
    text = text[:start] + f"""    assert(heldLocks && pa == Dma);
    ++prepares;
    preparedLba = lba;
    ocsReads = 0;
    writing = {writing};
""" + text[stop:]
    text = text.replace("case 0x58: return doorbell();",
                        "case 0x58: return forcedBusy ? 2 : doorbell();")
    consume = """          if (!grant) return false;
          grant = false;""" if role == "W" else """          if (!CombinedRead::guard(*this, s) || !sb0BootWrite.consume()) return false;"""
    text = text.replace("  Sb0Media *sb0 = nullptr;", """  Sb0Media *sb0 = nullptr;
  bool grant = false, forcedBusy = false;
  NuwaData::Sb0::BootWriteOnce sb0BootWrite;
  unsigned corrupt = 0, consumed = 0;
  bool sb0Consume(CombinedRead::State &s, const uint8_t *src) {
    if (corrupt == 9) virt[4098] ^= 1; // LU
    if (corrupt == 10) virt[4113] ^= 8; // FUA
    if (corrupt == 11) virt[5132] ^= 1; // PRD size
    if (corrupt == 14) virt[CombinedRead::Data + 4095] ^= 1; // full payload
    if (corrupt == 19) forcedBusy = true; // Queue becomes busy at the final guard.
    if (corrupt == 20) virt[4117] ^= 1; // CDB LBA.
    if (corrupt == 21) virt[4120] ^= 1; // CDB transfer count.
    return NuwaData::Sb0::checkAndConsume(virt, s.setup.dma, s.tag, s.block,
        s.readLba, s.readBlocks, src, [&] {
""" + consume + """
          ++consumed;
          return true;
        });
  }""")
    if role != "R":
        check = "sb0BootWrite.spent() && " if role == "WX" else ""
        text = text.replace("      ++writeSubmissions;",
                            f"      assert({check}!grant && consumed == 1);\n      ++writeSubmissions;")
    port = (ROOT / "package/nuwa-data-write/Sb0CandidatePort.inc").read_text()
    port = port[port.index("struct Sb0Port"):port.index("__attribute__((noinline, noreturn))")]
    port = port.replace("static constexpr bool sb0GrantBound() { return false; }",
                        "static bool sb0GrantBound() { return combined_hardware.grant; }")
    text += """
namespace Sb0 = NuwaData::Sb0;
constexpr bool sb0Write = NUWA_SB0_PROFILE != 2;
static const auto nuwaDataIdentity = NuwaData::FixtureGpt{}.id;
""" + port + MAIN
    source = output / f"host-only-{role}.cpp"
    source.write_text(text.replace('#include "../package/', '#include "package/'))
    base = ROOT / "out/nuwa-ufs-apfs-root-integration-20261114/run-r5-visible-candidate/source"
    binary = output / f"HOST-ONLY-SB0-{role}"
    subprocess.run([os.environ.get("CXX", "c++"), "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-Wno-unused-function", "-Wno-unused-variable", "-no-pie",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    f"-DNUWA_SB0_PROFILE={ {'W': 1, 'R': 2, 'WX': 3}[role]}",
                    "-I", str(ROOT), "-I", str(ROOT / "tests"), "-I", stage, "-I", base,
                    "-I", ROOT.parent.parent / "UniXNU/drivers/RamBlock", source, "-o", binary], check=True)
    subprocess.run([binary], check=True)
    return hashlib.sha256(binary.read_bytes()).hexdigest()


def audit(build, output, role):
    stage = build / "nuwa-data-provider"
    staged = (stage / "CombinedRead.h").read_text()
    assert "WriteFua" not in staged
    assert ("WriteVolatile" in staged) == (role != "R")
    if role == "R":
        assert "sb0Consume" not in staged and "write10" not in staged
    kernel = build / "kernel.macho"
    symbols = subprocess.check_output(["llvm-nm", "--format=darwin", "-n", kernel], text=True)
    (output / f"{role}-symbols.txt").write_text(symbols)
    assert "sb0Run" in symbols and "sb0Stop" in symbols
    assert all(name not in symbols for name in ("disposableWrite", "openDisposableData",
                                                "openCandidateData", "sb0GrantBound"))
    assert ("sb0Consume" in symbols and "sb0Submit" in symbols) == (role == "WX")
    names = [line.split()[-1] for line in symbols.splitlines() if " (__TEXT_EXEC,__text) " in line
             and any(x in line for x in ("sb0Run", "sb0Stop", "sb0Preflight", "sb0Submit", "sb0Consume",
                                         "nuwa_ufs_marker", "CombinedRead", "CombinedHardware6hwrite",
                                         "NuwaData7write10",
                                         "NativeUfs5start", "NativeUfs9startRoot",
                                         "NativeUfsBlock5start", "NativeRamBlock5start",
                                         "_native_ufs_store_", "_native_ufs_log_", "_native_ufs_export_",
                                         "_native_ufs_part_"))]
    dis_path = output / f"{role}-final-disasm.txt"
    with dis_path.open("w") as f:
        subprocess.run(["llvm-objdump", "--disassemble-symbols=" + ",".join(names), kernel],
                       stdout=f, check=True)
    dis = dis_path.read_text()
    bodies = dict(re.findall(r"^[0-9a-f]+ <([^>]+)>:\n((?:[0-9a-f]+:.*\n)+)", dis, re.M))
    refused = ("NativeUfs9startRoot", "NativeUfsBlock5start", "NativeRamBlock5start",
               "_native_ufs_store_mode", "_native_ufs_store_open", "_native_ufs_store_read",
               "_native_ufs_store_write", "_native_ufs_store_order", "_native_ufs_store_sync",
               "_native_ufs_log_write", "_native_ufs_log_sync", "_native_ufs_log_panic",
               "_native_ufs_export_write", "_native_ufs_export_blocks",
               "_native_ufs_part_find", "_native_ufs_part_read")
    for name in refused:
        body, = (v for k, v in bodies.items() if name in k)
        assert re.findall(r"\s((?:mov|ret)\b.*)", body) in (["mov\tw0, #0", "ret"],
                                                          ["mov\tx0, #0", "ret"]), name
        assert body.count("\n") == 2, name
    entry, = (v for k, v in bodies.items() if "NativeUfs5start" in k)
    assert re.search(r"\bbl\s+.*<[^>]*sb0Run", entry)
    assert re.search(r"\bldaxr\b[\s\S]*\bstlxr\b[\s\S]*\bbl\s+.*<[^>]*sb0Run", entry)
    assert "inspect" not in entry and "startRoot" not in entry
    issue, = (v for k, v in bodies.items() if "CombinedReadL5issue" in k)
    assert re.search(r"\bmov\s+\w+, #335544320\b", issue)  # UTRD with D2H data
    blob = kernel.read_bytes()
    identities = {"W": b"NUWA SB0-W UNBOUND", "R": b"NUWA SB0-R READONLY",
                  "WX": b"NUWA SB0-W EXPERIMENT"}
    assert identities[role] + b"\0" in blob
    assert all(label not in blob for key, label in identities.items() if key != role)
    if role == "WX":
        def body(fragment):
            match, = (v for k, v in bodies.items() if fragment in k)
            return match

        assert re.search(r"\bbl\s+.*<[^>]*sb0Preflight", body("sb0Run"))
        assert re.search(r"\bbl\s+.*<[^>]*sb0Submit", body("sb0Preflight"))
        assert re.search(r"\bbl\s+.*<[^>]*CombinedReadL5issue", body("sb0Submit"))
        assert re.search(r"\bmov\s+\w+, #301989888\b", issue)  # H2D UTRD
        assert re.search(r"\bbl\s+.*<[^>]*write10[^\n]*\n[^\n]*\bstrb\s+wzr, \[sp, #9\]", issue)
        db = re.search(r"\bbl\s+.*<[^>]*sb0Consume[^\n]*\n[^\n]*\btbz\s+w0, #0, (0x[0-9a-f]+)"
                       r"[\s\S]*\bmov\s+w0, #88\n[^\n]*\bmov\s+w1, #1\n([0-9a-f]+):[^\n]*\bbl\s+.*<[^>]*hwrite",
                       issue)
        assert db and int(db[1], 16) > int(db[2], 16)
        consume = body("sb0Consume")
        assert re.search(r"\bbl\s+.*<[^>]*CombinedReadL5guard", consume)
        assert re.search(r"\bbl\s+.*<_memcmp>", consume)
        stop = body("sb0Stop")
        assert re.search(r"\bbl\s+.*<_nuwa_ufs_marker>", stop)
        assert "DAIFSet" in stop and re.search(r"\bwfe\b", stop)
        assert not re.search(r"panic|reboot|_halt", stop, re.I)
    else:
        assert not re.search(r"\bmov\s+\w+, #301989888\b", issue)
    return hashlib.sha256(blob).hexdigest()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("role", choices=("W", "R", "WX"))
    p.add_argument("build", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    args.output.mkdir()
    report = dict(fixture_sha256=fixture(args.build.resolve(), args.output.resolve(), args.role),
                  kernel_sha256=audit(args.build, args.output, args.role))
    (args.output / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report)
