#!/usr/bin/env python3
"""Host-only SB0-R2 check: fixture verdicts plus no-write kernel audit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = "test-nuwa-sb0-r2.cpp"
FIXTURE_SUMMARIES = {
    "healthy-log": "NUWA SB0-R2 ANCHOR=EXACT-SB0 HDR=1 REC=- REASON=NONE PAGES=3 WRITES=0",
    "log-crc": "NUWA SB0-R2 ANCHOR=EXACT-SB0 HDR=1 REC=1 REASON=LOG-CRC PAGES=0 WRITES=0",
    "data-crc": "NUWA SB0-R2 ANCHOR=EXACT-SB0 HDR=1 REC=1 REASON=DATA-CRC PAGES=2 WRITES=0",
    "anchor-other": "NUWA SB0-R2 ANCHOR=OTHER HDR=0 REC=- REASON=SB0-FOREIGN PAGES=0 WRITES=0",
}
FIXTURE_EXTRA = {
    "reread-empty": "NUWA SB0-R2 ANCHOR=EXACT-SB0 HDR=1 REC=0 REASON=LOG-EMPTY PAGES=3 WRITES=0",
    "gate-failure": "NUWA SB0-R2 ANCHOR=UNKNOWN HDR=UNKNOWN REC=- REASON=GUARD PAGES=0 WRITES=0",
    "sb0-io": "NUWA SB0-R2 ANCHOR=UNKNOWN HDR=UNKNOWN REC=- REASON=IO PAGES=0 WRITES=0",
    "sb1-io": "NUWA SB0-R2 ANCHOR=EXACT-SB0 HDR=1 REC=- REASON=IO PAGES=0 WRITES=0",
}
ADDRESS_LINE = ("PASS overlay address mapping: SB0=57393401 SB1=57393402 "
                "map=57393403 ring=57393659 data=59491333")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture(output):
    output.mkdir(parents=True, exist_ok=True)
    binary = output / "HOST-ONLY-SB0-R2"
    subprocess.run([
        os.environ.get("CXX", "c++"), "-std=c++17", "-O2", "-Wall", "-Wextra",
        "-Werror", "-no-pie", "-fsanitize=address,undefined",
        "-fno-sanitize-recover=all", "-I", str(ROOT), "-I", str(ROOT / "tests"),
        "-I", str(ROOT.parent / "UniXNU/drivers/RamBlock"),
        str(ROOT / "tests" / FIXTURE), "-o", str(binary)], check=True)
    run = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
    (output / "fixture.log").write_text(run.stdout + run.stderr)
    text = run.stdout
    for name, line in FIXTURE_SUMMARIES.items():
        assert f"CASE {name} " in text, name
        # Every required summary appears verbatim; healthy/log-CRC/data-CRC/
        # anchor-OTHER are the four brief cases.
        assert line in text, (name, line)
    for name, line in FIXTURE_EXTRA.items():
        assert line in text, (name, line)
    assert ADDRESS_LINE in text
    for line in ("PASS reverse re-read: Empty is a non-None refusal",
                 "PASS gate failure summary: ANCHOR/HDR are UNKNOWN",
                 "PASS SB0 read failure: ANCHOR/HDR are UNKNOWN",
                 "PASS SB1 read failure: SB1=UNKNOWN, SB0 facts retained"):
        assert line in text, line
    assert "PASS SB0-R2 host fixture" in text
    return sha(binary), text


def bodies(text):
    return dict(re.findall(r"^[0-9a-f]+ <([^>]+)>:\n((?:[0-9a-f]+:.*\n)+)", text, re.M))


def audit(build):
    build = build.resolve()
    kernel = build / "kernel.macho"
    symbols = subprocess.check_output(
        ["llvm-nm", "--format=darwin", "-n", str(kernel)], text=True)
    names = {line.split()[-1] for line in symbols.splitlines() if line.strip()}
    assert "__ZN12_GLOBAL__N_16sb0RunEv" in names
    assert "__ZN12_GLOBAL__N_19sb0StopR2ERKN8NuwaData5Sb0R29DiagnosisE" in names
    assert "__ZN12_GLOBAL__N_114sb0R2PreflightERN8NuwaData10GptBuffersE" in names
    for forbidden in ("sb0Submit", "sb0Consume", "sb0GrantBound", "disposableWrite",
                      "openDisposableData", "openCandidateData", "write10",
                      "disposableOrder", "disposableRead"):
        assert not any(forbidden in name for name in names), forbidden

    combined = (build / "nuwa-data-provider/CombinedRead.h").read_text()
    assert "WriteVolatile" not in combined
    assert "write10" not in combined
    assert "WriteFua" not in combined

    # GPT reads stay on the bare absolute-LBA port; only overlay-relative
    # pages go through Sb0R2Port, which must add Media.first.
    port_src = (ROOT / "package/nuwa-data-write/Sb0CandidatePort.inc").read_text()
    start = port_src.index("static Sb0R2::Diagnosis sb0R2Preflight(NuwaData::GptBuffers &g) {")
    pre = port_src[start:port_src.index("\n}\n", start)]
    for gpt in ("port.read(1, g.ph)", "port.read(2, g.pe)",
                "port.read(cap - 1, g.bh)", "port.read(backup, g.be)"):
        assert gpt in pre, gpt
    assert "Sb0R2Port overlay{port};" in pre
    assert "Sb0R2::parse(overlay" in pre
    assert "Sb0R2Port::read" not in pre
    r2_src = (ROOT / "package/nuwa-data-write/Sb0R2.h").read_text()
    assert "return p.read(Overlay::Media.first + rel" in r2_src
    assert "rel >= Overlay::Media.blocks" in r2_src

    blob = kernel.read_bytes()
    assert b"NUWA SB0-R2 READONLY\0" in blob
    assert b"NUWA SB0-R2 ANCHOR=" in blob
    for other in (b"NUWA SB0-W UNBOUND", b"NUWA SB0-R UNBOUND", b"NUWA SB0-R READONLY"):
        assert other not in blob

    wanted = (
        "__ZN9NativeUfs5startEP9IOService",
        "__ZN12_GLOBAL__N_16sb0RunEv",
        "__ZN12_GLOBAL__N_114sb0R2PreflightERN8NuwaData10GptBuffersE",
        "__ZN12_GLOBAL__N_19sb0StopR2ERKN8NuwaData5Sb0R29DiagnosisE",
        "__ZN14NativeUfsBlock5startEP9IOService",
        "__ZN9NativeUfs9startRootEP9IOService",
        "__ZN14NativeRamBlock5startEP9IOService",
        "__ZN12CombinedReadL5issueI16CombinedHardwareEENS_3EndERT_RNS_5StateENS_7CommandEPKh",
    )
    dis_path = build / "r2-final-disasm.txt"
    with dis_path.open("w") as f:
        subprocess.run(["llvm-objdump", "--disassemble-symbols=" + ",".join(wanted),
                        str(kernel)], stdout=f, check=True)
    body = bodies(dis_path.read_text())
    get = lambda fragment: next(v for k, v in body.items() if fragment in k)

    entry = get("NativeUfs5start")
    assert re.search(r"\bldaxr\b[\s\S]*\bstlxr\b[\s\S]*\bbl\s+.*<[^>]*sb0Run", entry)
    assert "startRoot" not in entry

    run = get("sb0Run")
    assert re.search(r"\bbl\s+.*<[^>]*sb0R2Preflight", run)
    assert re.search(r"\bbl\s+.*<[^>]*sb0StopR2", run)
    assert not re.search(r"sb0Preflight\b(?!R2)", run)
    assert "sb0Submit" not in run

    pre = get("sb0R2Preflight")
    assert re.search(r"\bbl\s+.*<[^>]*retainedReadLocked", pre)
    assert re.search(r"\bbl\s+.*<[^>]*Sb0R25parse", pre)

    stop = get("sb0StopR2")
    assert re.search(r"\bbl\s+.*<_panic>", stop)
    assert "_nuwa_ufs_marker" not in stop

    issue = get("CombinedReadL5issue")
    assert not re.search(r"\bmov\s+\w+, #301989888\b", issue)  # H2D UTRD
    assert "write10" not in issue

    for fragment in ("NativeUfsBlock5start", "NativeUfs9startRoot", "NativeRamBlock5start"):
        refusal = get(fragment)
        assert re.findall(r"\s((?:mov|ret)\b.*)", refusal) in (
            ["mov\tw0, #0", "ret"], ["mov\tx0, #0", "ret"]), fragment

    return dict(kernel_sha256=sha(kernel),
                combined_sha256=sha(build / "nuwa-data-provider/CombinedRead.h"),
                combined_no_write=True,
                symbols_absent=True,
                gpt_addresses_unchanged=True,
                overlay_address_translated=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("build", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    fx_sha, fx_text = fixture(args.output)
    report = audit(args.build)
    report["fixture_sha256"] = fx_sha
    report["fixture_summaries"] = {name: line for name, line in FIXTURE_SUMMARIES.items() if line in fx_text}
    (args.output / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
