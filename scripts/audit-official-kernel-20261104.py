#!/usr/bin/env python3
"""Offline audit: local nuwa kernel vs Apple official xnu-8796.141.3 source.

No device contact, no kernel rebuild, no image emission. Recomputes every
byte-level claim in reports/offline-official-kernel-audit-20261104/README.md
and writes evidence.json with hash bindings.
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "scripts"))
import flush_trace_inputs as t  # noqa: E402


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def word(raw, macho, va):
    b = t.builder()
    at = b.backed(macho, va, 4)
    return raw[at:at + 4].hex()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=pathlib.Path,
                    default=R / "reports/offline-official-kernel-audit-20261104/evidence.json")
    a = ap.parse_args()

    d = R / "reports/offline-official-kernel-audit-20261104"
    src = d / "official-source"
    official = {
        "vfs_vnops.c": "4a91ef466df3efa340b433ecf462a9fbc9afc6c31efa79c24bcf0c6bdc657a94",
        "mach_loader.c": "58a36847003e7eaf0bc5e2cc76cd206e0152ec601253888504a2a9f65dec7486",
        "bsd_init.c": "92ad5e66379c735878bd3d9822fe4916008447e60b4355300116e098208af630",
        "vnode.h": "3a14a8a7129960fd4c19abd8b609e3fc95b4ca24954b45df5893666411d63638",
        "uio.h": "b35dfa5abdad82d757d82045f869c2e6d3b861004e6929f1727d1fe16c6508b3",
        "vfs_subr.c": "0b301b017b91ca1909752dc62b124fb198d9b7ffefc8834f99a868efbae45aae",
        "arm_init.c": "5161a3fc8b31b3317e2dd745594ec8a6877590a3976147b52bfd1255d9eec47e",
    }
    official_checks = {}
    for name, want in official.items():
        got = sha(src / name)
        assert got == want, (name, got, want)
        official_checks[name] = dict(sha256=got, bytes=(src / name).stat().st_size)

    # Official source fragments that anchor the comparison.
    vnops = (src / "vfs_vnops.c").read_text()
    loader = (src / "mach_loader.c").read_text()
    bsdinit = (src / "bsd_init.c").read_text()
    subr = (src / "vfs_subr.c").read_text()
    vnode = (src / "vnode.h").read_text()
    fragments = {
        "vn_rdwr_len_negative_einval": "if (len < 0) {\n\t\treturn EINVAL;\n\t}" in vnops,
        "vn_rdwr_passes_local_resid_pointer": "&resid,\n\t    p);" in vnops,
        "vn_rdwr_64_mac_before_vnop_read": vnops.find("mac_vnode_check_read(&context") < vnops.find("VNOP_READ(vp, auio, ioflg, &context)"),
        "vn_rdwr_64_short_read_eio_when_aresid_null": "} else if (uio_resid(auio) && error == 0) {\n\t\terror = EIO;" in vnops,
        "header_read_uses_IO_UNIT_or_IO_NODELOCKED": "UIO_SYSSPACE, (IO_UNIT | IO_NODELOCKED)," in loader,
        "loadcmd_read_uses_IO_NODELOCKED_only": "UIO_SYSSPACE, IO_NODELOCKED, cred, &resid, p);" in loader,
        "header_read_checks_error_then_resid": "if (resid) {\n\t\t/* We must be able to read in as much as the mach_header indicated */" in loader,
        "bsd_init_breaks_on_mountroot_zero": "if (0 == (err = vfs_mountroot())) {\n\t\t\tbreak;" in bsdinit,
        "bsd_init_continues_with_VFS_ROOT": "if (VFS_ROOT(mountlist.tqh_first, &init_rootvnode, vfs_context_kernel()))" in bsdinit,
        "IO_UNIT_is_1": "#define IO_UNIT         0x0001" in vnode,
        "IO_NODELOCKED_is_8": "#define IO_NODELOCKED   0x0008" in vnode,
        "vfs_mountroot_present": "\nvfs_mountroot(void)\n" in subr,
    }
    assert all(fragments.values()), [k for k, v in fragments.items() if not v]

    # Local binaries.
    c9p = R / "out/ufs-check-9-r1/kernel.macho"
    crp = R / "out/kernel-entry-probe-61-init-bridge-r2/kernel-entry-probe.macho"
    c9 = c9p.read_bytes()
    cr = crp.read_bytes()
    b = t.builder()
    m9 = b.macho(c9)
    mc = b.macho(cr)
    proof = json.loads((R / "out/ufs-check-9-r1/kernel-proof.json").read_text())

    # Every declared 4-byte change must bind byte-for-byte to its baseline
    # and to the current kernel. This is what makes the 526 figure meaningful.
    changes = proof["changes"]
    n_before = n_after = 0
    for c in changes:
        va = int(c["address"], 16)
        n_before += word(cr, mc, va) == c["before"]
        n_after += word(c9, m9, va) == c["after"]
    assert n_before == n_after == len(changes), (n_before, n_after, len(changes))

    reason_groups = {}
    for c in changes:
        r = c.get("reason", "")
        k = ("retire legacy diagnostic body" if r.startswith("retire legacy diagnostic body")
             else "first-visit coarse milestone" if r.startswith("first-visit coarse milestone")
             else "retire old / early drawing-only hook" if r.startswith("retire old") or r.startswith("retire early")
             else "existing panic tile becomes red banner" if r.startswith("existing panic tile")
             else "other (functional / observer mix)")
        reason_groups[k] = reason_groups.get(k, 0) + 1

    sites = {
        "0xfffffff00769bf90": "read call site (b to cave, not bl)",
        "0xfffffff00769bf94": "return site (b to read_after hook)",
        "0xfffffff00769bf98": "native resid reload (preserved)",
        "0xfffffff00769bfa4": "native post-read continuation (preserved)",
        "0xfffffff0074669b0": "vn_rdwr_64 call (CHECK9 bl / carrier b)",
        "0xfffffff0074669b4": "aresid NULL check (CHECK9 cbz / carrier b)",
        "0xfffffff007673118": "mount_return_zero dispatch",
        "0xfffffff007673120": "mount_return_zero second slot",
        "0xfffffff0084d9be4": "legacy probe61 error dispatch (cbz w0)",
        "0xfffffff0084d9bec": "legacy probe61 success branch (b 0x769bf98)",
    }
    site_bytes = {}
    for k in sites:
        va = int(k, 16)
        site_bytes[k] = dict(check9=word(c9, m9, va), carrier=word(cr, mc, va),
                             meaning=sites[k])

    # Hard assertions from the disassembly in README.md.
    assert site_bytes["0xfffffff00769bf90"]["check9"] == "707d3814"
    assert site_bytes["0xfffffff00769bf94"]["check9"] == "7d7d3814"
    assert site_bytes["0xfffffff00769bf98"]["check9"] == "f71f40b9"
    assert site_bytes["0xfffffff00769bfa4"]["check9"] == "480340b9"
    assert site_bytes["0xfffffff0074669b0"]["check9"] == "0a000094"
    assert site_bytes["0xfffffff0074669b0"]["carrier"] == "27604114"
    assert site_bytes["0xfffffff0084d9be4"]["check9"] == "40000034"
    assert site_bytes["0xfffffff0084d9be4"]["carrier"] == "40000034"
    assert site_bytes["0xfffffff0084d9bec"]["check9"] == "eb08c717"

    obs = (R / "package/kernel-mainline/CoarseStages-ufs-check9-r1.S").read_text()
    obs_lines = obs.splitlines()
    observer_counts = dict(
        global_coarse_hooks=sum(1 for l in obs_lines if l.strip().startswith(".global coarse_")),
        bl_draw=sum(1 for l in obs_lines if l.strip() == "bl draw"),
        bl_phase_record=sum(1 for l in obs_lines if l.strip() == "bl phase_record"),
        source_sha256=sha(R / "package/kernel-mainline/CoarseStages-ufs-check9-r1.S"),
    )
    # phase_record must save and restore the full official argument/return ABI.
    pr = obs[obs.index("phase_record:"):obs.index(".global coarse_getattr_before")]
    abi = dict(
        saves_x0_x29=all("stp x%d,x%d" % (i, i + 1) in pr for i in range(0, 29, 2)),
        restores_x0_x29=all("ldp x%d,x%d" % (i, i + 1) in pr for i in range(0, 29, 2)),
        saves_x30="str x30,[sp,#240]" in pr,
        restores_x30="ldr x30,[sp,#240]" in pr,
        saves_nzcv="mrs x9,nzcv" in pr,
        restores_nzcv="msr nzcv,x9" in pr,
    )
    assert all(abi.values()), abi

    out = R / "out"
    inventory = dict(
        kernel_entry_probe_dirs=len([p for p in out.iterdir() if p.is_dir() and re.match(r"kernel-entry-probe-\d+", p.name)]),
        ufs_check_dirs=len([p for p in out.iterdir() if p.is_dir() and re.match(r"ufs-check-\d+-r1", p.name)]),
        coarse_stages_sources=len(list((R / "package/kernel-mainline").glob("CoarseStages*.S"))),
        patch_files=len(list((R / "patches").rglob("*.*"))),
        patch_subdirs=len([p for p in (R / "patches").iterdir() if p.is_dir()]),
        report_dirs=len([p for p in (R / "reports").iterdir() if p.is_dir()]),
        current_kernel_changes=len(changes),
        change_reason_groups=reason_groups,
    )

    evidence = dict(
        scope="Offline only. No device command, no kernel rebuild, no boot image emitted.",
        official=dict(repository="apple-oss-distributions/xnu", tag="xnu-8796.141.3",
                      url_template="https://raw.githubusercontent.com/apple-oss-distributions/xnu/xnu-8796.141.3/<path>",
                      files=official_checks,
                      excluded=["bsd/vfs/vfs_mount.c (HTTP 404 at this tag; vfs_mountroot lives in bsd/vfs/vfs_subr.c)"],
                      anchored_fragments=fragments),
        local=dict(
            check9_kernel=dict(path=str(c9p.relative_to(R)), sha256=sha(c9p)),
            carrier_kernel=dict(path=str(crp.relative_to(R)), sha256=sha(crp)),
            check9_image_sha256=json.loads((R / "out/ufs-check-9-r1/build.json").read_text())["image_sha256"],
            changes_total=len(changes), changes_before_bound_to_carrier=n_before,
            changes_after_bound_to_check9=n_after),
        site_bytes=site_bytes,
        observer=observer_counts,
        phase_record_abi=abi,
        inventory=inventory,
    )
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (src / "SHA256SUMS").write_text(
        "".join("%s  %s\n" % (v["sha256"], k) for k, v in sorted(official_checks.items())),
        encoding="utf-8")
    print("official files", len(official_checks), "fragments", sum(fragments.values()))
    print("changes", len(changes), "bound", n_before, n_after)
    print("inventory", json.dumps(inventory, ensure_ascii=False))
    print("ABI", json.dumps(abi))
    print("wrote", a.output)


if __name__ == "__main__":
    main()
