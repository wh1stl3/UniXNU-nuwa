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
FRAME_OUTER = ROOT / "out/nuwa-crashframes-20261125-package"
FRAME_SHA = "b83021a7799cacb3bd4086162cae9474f267dc6dc6294eb11d5c4f0c6374e157"
FRAME_CHMH = bytes.fromhex(
    "0cf294e7bb627e97cbefc374476b2a6ff99dc2be649d48c78472d6f6cd17413059aca226947baf25ff6163fdc789415a")
PIX_OUTER = ROOT / "out/nuwa-pixsig-20261125-package"
PIX_SHA = "28d45ab6c3d7c5ec79cf14543af4836dadf04de7eddaa91fd876b36bc831dbcc"
PIX_CHMH = bytes.fromhex(
    "4d752ffcbe7e174d0dac4bddec403a8bc0bf809eb161cb08d81a1770f357832b6bb1aa713d185a73dc96127c00f55599")
DISPOSABLE_TEMPLATE_SHA = "18fa4941696667d1813442022ea71fc48e4c414b1abadb1caf73774fcc76202a"
DISPOSABLE_TEMPLATE_CHMH = bytes.fromhex(
    "e78df504dfaad23a15627d2651ce9c2bce7a1790e652dcfb2df24413ba3e37e96c4623008b8201a984d2ce43efccbc43")
DISPOSABLE_RAW_SHA = "26957263676b0312f3bebe213c2985deb8ce5652ac2ce3e99d59da77aba89584"
DISPOSABLE_SEED_ID = "a106b0ce026771e221f578125e104a4854c2cbcda7c1b8390f6e056a47c63743"
DISPOSABLE_ARG = b"nuwa-disposable-data=1"
V1_ARG = b"nuwa-data-write=1"
V1_NODUR = b"V1-NODUR"
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


def require_v1_kernel(kernel):
    if any(symbol in kernel for symbol in (
            b"_nuwa_disposable_fua_requests\0", b"_nuwa_disposable_flushes\0",
            b"_native_ufs_store_order\0")):
        raise SystemExit("v1 template excludes disposable kernel symbols")
    if any(symbol not in kernel for symbol in (
            b"_native_ufs_store_open\0", b"_native_ufs_store_write\0",
            b"_native_ufs_store_sync\0")):
        raise SystemExit("v1 template requires the Data provider")
    marker = b"__ZL12directDiskIO"
    at = kernel.find(marker)
    if at < 0 or b"N7persist7Overlay" not in kernel[at:].partition(b"\0")[0]:
        raise SystemExit("v1 template requires RamBlock's v1 directDiskIO")


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


def disposable_seed(base, seed):
    # Decode the bytes parsed from this outer, not an independently named seed.
    decoder = runpy.run_path(str(base / "drivers/DarwinBoot/Test/packed_ramdisk.py"))
    size, extents = decoder["regions"](seed)
    if size != 8 * 1024**3:
        raise SystemExit("disposable Data requires the pinned 8 GiB logical seed")
    logical = sha256()
    zeros = bytes(1024 * 1024)

    def pad(n):
        q, r = divmod(n, len(zeros))
        for _ in range(q):
            logical.update(zeros)
        logical.update(zeros[:r])

    end = 0
    for offset, data in extents:
        pad(offset - end)
        logical.update(data)
        end = offset + len(data)
    pad(size - end)
    out = {"seed_logical_bytes": size, "seed_raw_sha256": logical.hexdigest(),
           "seed_identity": decoder["seed_identity"](size, extents), "seed_extents": len(extents)}
    if (out["seed_raw_sha256"], out["seed_identity"]) != (DISPOSABLE_RAW_SHA, DISPOSABLE_SEED_ID):
        raise SystemExit(f"disposable FAT seed decoded identity mismatch: {out}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, required=True, help="existing pinned UniXNU checkout")
    ap.add_argument("--kernel", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    profile = ap.add_mutually_exclusive_group()
    profile.add_argument("--crashframes", action="store_true", help="use the pinned DSP counter outer")
    profile.add_argument("--pixsig", action="store_true", help="use the pinned crashframes outer")
    profile.add_argument("--stage-channel", action="store_true", help="use the pinned PIX outer and keep STAGE dormant")
    profile.add_argument("--data-persist-diag", action="store_true", help="use the pinned PIX outer")
    profile.add_argument("--disposable-data-template", type=Path,
                         help="use the exact 18fa4941 read-root outer and append the experiment gate")
    profile.add_argument("--v1-data-template", type=Path,
                         help="use the exact 18fa4941 read-root outer and select v1 args (host only)")
    profile.add_argument("--v1-retained-template", type=Path,
                         help="use the exact 18fa4941 read-root outer for retained v1 (host only)")
    ap.add_argument("--v1-reset", action="store_true",
                    help="add sheng-data-reset=1 to a separate retained v1 host package")
    ap.add_argument("--post-event", action="store_true",
                    help="require the panic-safe post-event summary marker; pairs with a Data template")
    ap.add_argument("--ufs-desc", action="store_true", help="append the read-only UFS descriptor opt-in")
    ap.add_argument("--ufs-neon", action="store_true", help="append the staged read-only UFS evidence opt-in")
    ap.add_argument("--audit-only", action="store_true", help="read an existing outer and compare all FAT files")
    a = ap.parse_args()
    if a.ufs_desc and not a.data_persist_diag:
        ap.error("--ufs-desc requires --data-persist-diag")
    if a.ufs_neon and (not a.data_persist_diag or a.ufs_desc):
        ap.error("--ufs-neon requires --data-persist-diag and excludes --ufs-desc")
    disposable = a.disposable_data_template is not None
    retained = a.v1_retained_template is not None
    data_template = a.disposable_data_template or a.v1_data_template or a.v1_retained_template
    if a.v1_reset and not retained:
        ap.error("--v1-reset requires --v1-retained-template")
    if a.post_event and not data_template:
        ap.error("--post-event requires a Data template")
    out = a.out.resolve()
    assert out.is_relative_to(ROOT / "out") and out not in (ROOT / "out", OLD, DSP_OUTER, FRAME_OUTER, PIX_OUTER)
    kernel = a.kernel.resolve()
    assert kernel.is_relative_to(ROOT / "out") and kernel.name == "kernel.macho"
    new_kernel = kernel.read_bytes()
    if a.post_event and b"NUWA-POSTEVENT-20261127" not in new_kernel:
        raise SystemExit("--post-event kernel lacks the post-event summary marker")
    if data_template:
        if disposable:
            if b"_native_ufs_store_order\0" not in new_kernel:
                raise SystemExit("disposable template requires a disposable kernel")
        else:
            require_v1_kernel(new_kernel)
            if retained != (b"retained persistence window refused\0" in new_kernel):
                raise SystemExit("v1 kernel and selected retained/provider template profile differ")
            if retained and b"[" + V1_NODUR + b"] DATA0 not run\0" not in new_kernel:
                raise SystemExit("retained v1 template requires the V1-NODUR screen marker")
    template, template_sha, template_chmh = (
        (data_template.parent, DISPOSABLE_TEMPLATE_SHA, DISPOSABLE_TEMPLATE_CHMH) if data_template else
        (PIX_OUTER, PIX_SHA, PIX_CHMH) if a.data_persist_diag or a.stage_channel else
        (FRAME_OUTER, FRAME_SHA, FRAME_CHMH) if a.pixsig else
        (DSP_OUTER, DSP_SHA, DSP_CHMH) if a.crashframes else (OLD, ROLLBACK, OLD_CHMH))
    old_outer = pinned(data_template if data_template else template / "vendor_boot.img", template_sha)
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
    seed_report = disposable_seed(a.base.resolve(), before[SCRATCH]) if data_template else {}
    entry, = (e for e in tomllib.loads(before[CONFIG].decode())["entry"] if e["id"] == "xnu")
    args = entry["args"].encode()
    tokens = args.split()
    assert len(args) == (577 if data_template else 561)
    for token in (b"nuwa-sb-stack=900", b"disable-jobs=com.apple.iconservices.iconservicesagent"):
        assert tokens.count(token) == 1
    assert not any(t.split(b"=", 1)[0] == b"sheng-smp" for t in tokens)
    if a.stage_channel:
        assert not any(t.split(b"=", 1)[0] == b"nuwa-init" for t in tokens)
    if a.data_persist_diag or data_template:
        assert not any(t.split(b"=", 1)[0] == b"sheng-data-reset" for t in tokens)
        for token in (b"sheng-data-persist=2", b"sheng-log-reserve=1024"):
            assert tokens.count(token) == 1

    chmh = runpy.run_path(str(ROOT / "scripts/build-chmh-only-payload.py"))["digest_material"]
    loader = pinned(ROOT / ".cache/boot-stage12-v4-r4.img",
                    "692cfcca51af81230fecbba15425cf598182fbe53abb362b6046dec0f24dc2e5")
    parent = pinned(ROOT / "out/owner-pmap-ret-continuation-verifier-final-20261111/adt-generation/final.adt",
                    "885094de4597fb2d1734ba4092c805968097d021c8f482653b238436586d27a4")
    bound = {"kernel": before[KERNEL], "loader": loader, "trust": before[TRUST],
             "args": args, "parent-adt": parent}
    assert chmh(bound)[1] == template_chmh and before[ADT].count(template_chmh) == 1
    bound["kernel"] = new_kernel
    expected_config = before[CONFIG]
    changed = {KERNEL, ADT}
    if data_template:
        assert DISPOSABLE_ARG not in tokens and V1_ARG not in tokens
        assert b"nuwa-ufs-neon=1" in tokens and tokens.count(b"build-tag=nuwa-r35") == 1
        assert not {t.split(b"=", 1)[0] for t in tokens} & {
            b"nuwa-data-write", b"nuwa-disposable-data", b"sheng-data-reset", b"sheng-log"}
        prefix = b'args = "' + args + b'"'
        assert expected_config.count(prefix) == 1
        if retained:
            args = args.replace(b"build-tag=nuwa-r35", b"build-tag=" + V1_NODUR)
            if a.v1_reset:
                args += b" sheng-data-reset=1"
        else:
            args = args.replace(b"build-tag=nuwa-r35", b"build-tag=data-trial") + b" " + (
                DISPOSABLE_ARG if disposable else V1_ARG)
        # The actual 8796 arm64 consumer has 608 bytes including NUL,
        # smaller than the loader's generic 1024-byte buffer.
        assert len(args) < 608
        expected_config = expected_config.replace(prefix, b'args = "' + args + b'"')
        bound["args"] = args
        changed.add(CONFIG)
    elif a.ufs_desc or a.ufs_neon:
        assert not {t.split(b"=", 1)[0] for t in tokens} & {
            b"nuwa-ufs-desc", b"nuwa-ufs-neon", b"nuwa-data-write", b"sheng-data-reset", b"sheng-log"}
        if a.ufs_neon:
            assert b"NEON build=ufs-neon-20261126 cid=N261126A\0" in new_kernel
        prefix = b'args = "' + args + b'"'
        assert expected_config.count(prefix) == 1
        args += b" nuwa-ufs-neon=1" if a.ufs_neon else b" nuwa-ufs-desc=1"
        expected_config = expected_config.replace(prefix, b'args = "' + args + b'"')
        bound["args"] = args
        changed.add(CONFIG)
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
        payloads = [(kernel, KERNEL), (new_adt, ADT)]
        if CONFIG in changed:
            config_file = out / "unixnu.toml"
            config_file.write_bytes(expected_config)
            payloads.append((config_file, CONFIG))
        for source, dest in payloads:
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
    assert {path for path in before if before[path] != after[path]} == changed
    assert after[KERNEL] == new_kernel and after[ADT] == expected_adt and after[CONFIG] == expected_config
    entry_after, = (e for e in tomllib.loads(after[CONFIG].decode())["entry"] if e["id"] == "xnu")
    assert entry_after["args"].encode() == args
    chosen = parse_adt(after[ADT])["/chosen"]
    assert chosen["boot-manifest-hash"] == digest
    assert chosen["display-scale"] == bytes.fromhex("03000000") and "text-fixups" not in chosen
    free = sum(not (struct.unpack_from("<I", rb, fs.fat_offset + 4 * i)[0] & 0x0fffffff)
               for i in range(2, fs.cluster_count + 2)) * fs.cluster_size
    assert free >= 8 * 1024 * 1024
    report = dict(kernel_sha256=sha(after[KERNEL]), outer_sha256=sha(blob),
                  chmh_sha384=digest.hex(), fat_sha256=sha(rb), seed_sha256=sha(after[SCRATCH]),
                  fat_free_bytes=free, changed_files=sorted(changed), args_bytes=len(args))
    if a.ufs_neon:
        report.update(trust_sha256=sha(after[TRUST]), template_outer_sha256=template_sha,
                      diagnostic_arg="nuwa-ufs-neon=1", device_release=False)
    if data_template:
        report.update(seed_report, trust_sha256=sha(after[TRUST]),
                      template_outer_sha256=template_sha, device_release=False)
        if retained:
            report.update(data_profile="v1-retained", durability=V1_NODUR.decode(),
                          reset=a.v1_reset, args=args.decode())
        else:
            report["diagnostic_arg"] = (DISPOSABLE_ARG if disposable else V1_ARG).decode()
        if not disposable and not retained:
            report["data_profile"] = "v1-direct"
    if a.audit_only:
        assert rb == readback.read_bytes()
    else:
        readback.write_bytes(rb)
        (out / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
