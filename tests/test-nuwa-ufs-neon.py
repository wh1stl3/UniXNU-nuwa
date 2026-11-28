#!/usr/bin/env python3
"""Test the neutral UFS status row and the generated diagnostic labels.

Host-only: no kernel, package or device is built.  The old UFS survey rows and
their reads stay removed; cid/phase and the other status fields remain visible.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from generate_nuwa_postevent import generate as generate_postevent
from generate_r35_display_diag import generate


def main(build=None):
    inc = (ROOT / "package/nuwa-data-write/RetainedNeon.inc").read_text()
    driver = (ROOT / "scripts/build-nuwa-display-native.py").read_text()
    core = (ROOT / "package/boot-progress/BootProgressCore.h").read_text()
    assert re.search(r"#define\s+BP_COLS\s+120\b", core)
    for name in ("boot-progress", "boot-progress-r12"):
        renderer = (ROOT / "package" / name / "BootProgress.c").read_bytes()
        assert b"build_tag[0]" not in renderer
        assert b'" UniXNU live diagnostics  t=%us  crashes=%u exits=%u"' in renderer
    builder = runpy.run_path(str(ROOT / "scripts/build-boot-progress-nuwa.py"))
    assert builder["PINS"]["BootProgress.c"] == sha256(
        (ROOT / "package/boot-progress/BootProgress.c").read_bytes()).hexdigest()
    for gone in ("NEON HC", "NEON DEV", "NEON LU", "NEON MS", "NEON PL",
                 "probeNeon", "neonPre", "neonDesc", "neonMedia", "neonHc"):
        assert gone not in inc, gone
    assert 'snprintf(rows[0], 120, "%s s=%u old=? rsr=?", NuwaNeon::Identity, phase);' in inc
    assert "neonBegin" in inc and "nuwa_ufs_neon_rows" in inc
    for gone in ("probeNeon", "neonPre", "__atomic_load_n(&neonPhase"):
        assert gone not in driver, gone
    assert "probeUfsDescriptors();" in driver
    if build is not None:
        renderer = (build / "BootProgress.c").read_text()
        assert "nuwa_ufs_neon_rows(evidence,6)" in renderer and "line(37+i,evidence[i]" in renderer
        assert "nuwa_ufs_neon_rows(rows,budget)" in renderer
        assert "bp_cr_rows(rows+neon,budget-neon)" in renderer
        assert not re.search(r'"NEON (HC|DEV|LU|MS|PL)', renderer)
        assert '"[nuwa-r35] t=' not in renderer
        assert '"[%s] %s",build_tag' not in renderer

    source = (ROOT / "out/nuwa-r35l-regs-full-20261121/BootProgress.c").read_bytes()
    for smp in (False, True):
        for pix in (False, True):
            renderer = generate(source, mg_reset=True, smp_observe=smp, pixsig=pix)
            for gone in (b'"[nuwa-r35] t=', b'build_tag[0]?"  [":"",build_tag',
                         b'" LIVE rc=%s aff=%s %.8s'):
                assert gone not in renderer, gone
            assert b'"t=%us m=%llu np=%d' in renderer
            if smp:
                assert b'" LIVE rc=%s aff=%s %us C%u E%u"' in renderer
            else:
                assert b'" UniXNU live diagnostics  t=%us  crashes=%u exits=%u"' in renderer

    texts = []
    for v1 in (False, True):
        for sb_threads in (False, True):
            text, _ = generate_postevent(generate(source, mg_reset=True, pixsig=True),
                                         v1_nodur=v1, sb_threads=sb_threads)
            for gone in (b'"[V1-NODUR]', b'"[%s] %s",build_tag', b'" FUA-EXP-nodur"'):
                assert gone not in text, gone
            assert (b'NUWA-V1-DIAG-20261128' in text) == v1
            if v1:
                assert text.count(b"bp_v1_status_suffix(data,sizeof data);") == 2
                assert b'"DATA0 not run dur=?"' in text
                assert text.index(b"static void bp_v1_status_suffix(char *,size_t);") < text.index(
                    b"bp_v1_status_suffix(data,sizeof data);")
            texts.append(text)

    packer = runpy.run_path(str(ROOT / "scripts/package-nuwa-crashcap.py"))
    for function, marker, legacy in (
            ("require_retained_diagnostics", b"NUWA-V1-DIAG-20261128\0",
             b"[V1-NODUR] DATA0 not run\0"),
            ("require_ufs_status", b"IO cid=N261126A\0",
             b"NEON build=ufs-neon-20261126 cid=N261126A\0")):
        check = packer[function]
        check(marker, audit_only=False)
        check(legacy, audit_only=True)
        for kernel, audit_only in ((b"", False), (legacy, False), (b"", True)):
            try:
                check(kernel, audit_only=audit_only)
            except SystemExit:
                pass
            else:
                raise AssertionError(f"{function} accepted {kernel!r}, audit_only={audit_only}")

    harness = r'''
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include "Provider.h"
#include "Neon.h"
static unsigned requested;
static int PE_parse_boot_argn(const char *, void *out, size_t) {
  *static_cast<uint32_t *>(out) = requested;
  return requested != 0;
}
#define NUWA_NEON_SETUP
#include "RetainedNeon.inc"
#undef NUWA_NEON_SETUP
#include "RetainedNeon.inc"
int main() {
  char rows[1][120] = {};
  assert(!neonBegin() && !nuwa_ufs_neon_rows(rows, 1));
  requested = 1;
  assert(neonBegin() && !nuwa_ufs_neon_rows(rows, 0));
  assert(nuwa_ufs_neon_rows(rows, 1) == 1);
  assert(!strcmp(rows[0], "IO cid=N261126A s=1 old=? rsr=?"));
  neonPhase = UINT32_MAX;
  assert(nuwa_ufs_neon_rows(rows, 1) == 1);
  assert(!strcmp(rows[0], "IO cid=N261126A s=4294967295 old=? rsr=?"));
  assert(strlen(rows[0]) < sizeof rows[0]);
  puts(rows[0]);
}
'''
    with tempfile.TemporaryDirectory(prefix="nuwa-status-test-") as directory:
        tmp = Path(directory)
        src, exe = tmp / "status.cpp", tmp / "status"
        src.write_text(harness)
        subprocess.run(["c++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-I", ROOT / "package/nuwa-data-write", src, "-o", exe], check=True)
        subprocess.run([exe], check=True)
        assert b"IO cid=N261126A\0" in exe.read_bytes()
        renderer = tmp / "BootProgress.c"
        for text in texts:
            renderer.write_bytes(text)
            subprocess.run([sys.executable, "-B", ROOT / "scripts/test-nuwa-postevent.py",
                            "--renderer", renderer, "--build-dir",
                            ROOT / "out/nuwa-r35l-regs-full-20261121", "--source-only"], check=True)
    print("status row and generated diagnostic labels: PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("build", type=Path, nargs="?")
    parser.add_argument("base", type=Path, nargs="?")
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    main(args.build.resolve() if args.build else None)
