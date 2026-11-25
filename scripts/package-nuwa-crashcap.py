#!/usr/bin/env python3
"""Repack and audit a crash kernel against a pinned diagnostic outer (host only)."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import runpy
import struct
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "out/nuwa-stack900-20261125-package"
ROLLBACK = "66efdc7164d1385978309967f40f0495497237c3c7a92c43b7697496a55f6486"
SEED = "3c81135b384d8e090521205f2d69b3c197521e6d03c63682419d021bf0f24e5e"
OLD_CHMH = bytes.fromhex(
    "ecdd6f98859f52abe1ebe71dd32dc30d8859cb66a93bcfdaa96cd66f51ab140a43c90db09a2a9b7e38af1293286deced")
DSP_OUTER = ROOT / "out/nuwa-dspcount-20261125-package"
DSP_SHA = "7c8ee0d61e61951a6115e955dd650461848a0ab16111a89ce2816d6b2e7aba73"
DSP_CHMH = bytes.fromhex(
    "54ea450840ba0cd9ba4f2a02b7f2686653e459993f9822edc7a5df093ee71f2ad66bf5b97309134fdf6bbb58339b2ea2")
PAYLOAD = "EFI/UniXNU/Payloads/"
KERNEL, ADT, TRUST, SCRATCH = (PAYLOAD + name for name in
    ("kernel.macho", "kernel.macho.adt", "kernel.macho.trustcache", "scratch-data.img"))
CONFIG = "EFI/UniXNU/unixnu.toml"


def sha(blob):
    return sha256(blob).hexdigest()


def pinned(path, digest):
    blob = path.read_bytes()
    if sha(blob) != digest:
        raise ValueError(f"{path}: SHA-256 mismatch")
    return blob


def regions(blob):
    page, size = struct.unpack_from("<I8xI", blob, 12)
    assert blob[:8] == b"VNDRBOOT" and len(blob) == 100663296
    assert (page, size) == (4096, 67108864)
    return blob[:page], blob[page:page + size], blob[page + size:]


def files(fs):
    result, visited = {}, set()

    def walk(cluster, prefix):
        assert cluster not in visited
        visited.add(cluster)
        for short, long, attr, child, _ in fs.entries(cluster):
            name = long or short
            if name in (".", ".."):
                continue
            path = prefix + name
            if attr & 0x10:
                walk(child, path + "/")
            else:
                assert path not in result
                result[path] = fs.read(path)

    walk(fs.root, "")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, required=True, help="existing pinned UniXNU checkout")
    ap.add_argument("--kernel", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--crashframes", action="store_true", help="use the pinned DSP counter outer")
    ap.add_argument("--audit-only", action="store_true", help="read an existing outer and compare all FAT files")
    a = ap.parse_args()
    out = a.out.resolve()
    assert out.is_relative_to(ROOT / "out") and out not in (ROOT / "out", OLD, DSP_OUTER)
    kernel = a.kernel.resolve()
    assert kernel.is_relative_to(ROOT / "out") and kernel.name == "kernel.macho"
    new_kernel = kernel.read_bytes()
    template, template_sha, template_chmh = (
        (DSP_OUTER, DSP_SHA, DSP_CHMH) if a.crashframes else (OLD, ROLLBACK, OLD_CHMH))
    old_outer = pinned(template / "vendor_boot.img", template_sha)
    head, old_fat, tail = regions(old_outer)

    # Reuse the prior Python reader, not the rollback audit's executable main.
    parser = OLD / "audit2.py"
    text = pinned(parser, "9c482847481bfd9d2794bf469f8dfac9f99cf988286e893488360fdb4c85e582")
    ns = {"__file__": str(parser)}
    exec(compile(text.split(b"def main():", 1)[0], str(parser), "exec"), ns)
    FAT32, parse_adt = ns["FAT32"], ns["parse_adt"]
    before = files(FAT32(old_fat))
    assert before[KERNEL] != new_kernel
    assert sha(before[SCRATCH]) == SEED
    entry, = (e for e in tomllib.loads(before[CONFIG].decode())["entry"] if e["id"] == "xnu")
    args = entry["args"].encode()
    tokens = args.split()
    assert len(args) == 561
    for token in (b"nuwa-sb-stack=900", b"disable-jobs=com.apple.iconservices.iconservicesagent"):
        assert tokens.count(token) == 1
    assert not any(t.split(b"=", 1)[0] == b"sheng-smp" for t in tokens)

    chmh = runpy.run_path(str(ROOT / "scripts/build-chmh-only-payload.py"))["digest_material"]
    loader = pinned(ROOT / ".cache/boot-stage12-v4-r4.img",
                    "692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5")
    parent = pinned(ROOT / "out/owner-pmap-ret-continuation-verifier-final-20261111/adt-generation/final.adt",
                    "885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4")
    bound = {"kernel": before[KERNEL], "loader": loader, "trust": before[TRUST],
             "args": args, "parent-adt": parent}
    assert chmh(bound)[1] == template_chmh and before[ADT].count(template_chmh) == 1
    bound["kernel"] = new_kernel
    digest = chmh(bound)[1]
    expected_adt = before[ADT].replace(template_chmh, digest, 1)
    assert digest != template_chmh

    outer = out / "vendor_boot.img"
    fat = out / "payload.img"
    readback = out / "readback-fat.img"
    if not a.audit_only:
        stock = ROOT / ".cache/stock/vendor_boot_b.img"
        pinned(stock, "5ad2a9dc751870fa3c367fa2833582147541f5b62b880dcbdf525003ad68cc23")
        out.mkdir()
        fat.write_bytes(old_fat)
        new_adt = out / "kernel.macho.adt"
        new_adt.write_bytes(expected_adt)
        for source, dest in ((kernel, KERNEL), (new_adt, ADT)):
            subprocess.run(["mcopy", "-o", "-i", fat, source, "::/" + dest], check=True)
        base = a.base.resolve()
        config = ROOT / "out/nuwa-peer-probe-20261125-staging/build-input.toml"
        subprocess.run([sys.executable, "-B", base / "unixnu", "vendor_boot",
                        "--stock", stock, "--ramdisk", fat, "-o", outer, "-D", ROOT,
                        "--out", out / "context", "--config", config, "--local-module",
                        f"soc:sm8550={ROOT.parent / 'UniXNU-sm8550-common'}", "-j", "1"],
                       cwd=base, check=True)
    blob = outer.read_bytes()
    h, rb, t = regions(blob)
    assert (h, t) == (head, tail) and rb == fat.read_bytes()
    fs = FAT32(rb)
    after = files(fs)
    assert before.keys() == after.keys()
    assert {path for path in before if before[path] != after[path]} == {KERNEL, ADT}
    assert after[KERNEL] == new_kernel and after[ADT] == expected_adt
    chosen = parse_adt(after[ADT])["/chosen"]
    assert chosen["boot-manifest-hash"] == digest
    assert chosen["display-scale"] == bytes.fromhex("03000000") and "text-fixups" not in chosen
    free = sum(not (struct.unpack_from("<I", rb, fs.fat_offset + 4 * i)[0] & 0x0fffffff)
               for i in range(2, fs.cluster_count + 2)) * fs.cluster_size
    assert free >= 8 * 1024 * 1024
    report = dict(kernel_sha256=sha(after[KERNEL]), outer_sha256=sha(blob),
                  chmh_sha384=digest.hex(), fat_sha256=sha(rb), seed_sha256=sha(after[SCRATCH]),
                  fat_free_bytes=free, changed_files=sorted((KERNEL, ADT)), args_bytes=len(args))
    if a.audit_only:
        assert rb == readback.read_bytes()
    else:
        readback.write_bytes(rb)
        (out / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
