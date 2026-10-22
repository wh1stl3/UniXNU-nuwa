"""Compare strict in-memory patching with independent Git evidence; audit order."""
import difflib
import hashlib
import json
from pathlib import Path
from datetime import datetime

from check_native_support import BASE, SOURCE, git
from virtual_patch import PatchError, Tree

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports/xnu-8796-sequence"
CANDIDATES = ROOT / "patches/xnu-8796-candidates"
OMITTED = {
    "pgz-aligned-validation.patch": "8796 lacks zone_id_require_aligned; not transplanted as a new API",
    "offline-pgz-alignment-probe.patch": "Optional probe calls that absent aligned API; deferred, not claimed compatible",
    "published-freezer-condition.patch": "8796 lacks the malformed 10063 conditional; preserve 8796 freezer policy",
}


def diff_files(tree):
    chunks = []
    for path, changed in tree.files.items():
        source = SOURCE / path
        original = source.read_text(encoding="utf-8") if source.exists() else ""
        chunks.append("".join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
                      fromfile="a/" + path if source.exists() else "/dev/null", tofile="b/" + path)))
    return "".join(chunks)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    before = git(SOURCE, "status", "--porcelain", "--untracked-files=all")
    if before["exit_code"] or before["stdout"]:
        raise SystemExit("Dirty or unreadable source")
    original = json.loads((ROOT / "reports/patch-portability-8796-recheck/results.json").read_text(encoding="utf-8"))
    native = json.loads((ROOT / "reports/native-prelink-8796/results.json").read_text(encoding="utf-8"))
    baseline = original["results"] + native["results"]
    if git(SOURCE, "rev-parse", "HEAD")["stdout"].strip() != original["source_head"] or git(BASE, "rev-parse", "HEAD")["stdout"].strip() != original["base_head"]:
        raise SystemExit("Baseline changed")
    upstream = sorted((BASE / "patches/xnu").glob("*.patch")) + sorted((BASE / "kits/NativePrelink/patches").glob("*.patch"))
    if len(upstream) != len(baseline):
        raise SystemExit("Patch count changed")
    comparison = []
    for patch, recorded in zip(upstream, baseline):
        if patch.name != recorded["patch"] or hashlib.sha256(patch.read_bytes()).hexdigest() != recorded["sha256"]:
            raise SystemExit("Patch provenance mismatch")
        try:
            Tree(SOURCE).apply(patch.read_text(encoding="utf-8"))
            passed, error = True, ""
        except PatchError as exc:
            passed, error = False, str(exc)
        comparison.append({"patch": patch.name, "upstream_sha256": recorded["sha256"], "virtual_pass": passed,
                           "git_pass": recorded["exit_code"] == 0, "error": error})

    # Two remaining text/context candidates. No content dropped beyond absent includes.
    public = (BASE / "patches/xnu/public-entitlements-header.patch").read_text(encoding="utf-8")
    public = public.split("diff --git a/bsd/net/necp_client.c", 1)[0]
    (CANDIDATES / "public-entitlements-header.patch").write_text(public, encoding="utf-8", newline="\n")

    owner = (BASE / "patches/xnu/offline-owner-systemos-mount.patch").read_text(encoding="utf-8")
    rest = owner[owner.index("@@ -7013"):]
    adapted = ('--- a/bsd/kern/kern_exec.c\n+++ b/bsd/kern/kern_exec.c\n'
               '@@ -183,3 +183,4 @@\n \n #include "kern_exec_internal.h"\n'
               '+#include <CoreEntitlements/CoreEntitlements.h>\n \n' + rest)
    (CANDIDATES / "offline-owner-systemos-mount.patch").write_text(adapted, encoding="utf-8", newline="\n")

    boot = (BASE / "patches/xnu/zzz-boot-progress.patch").read_text(encoding="utf-8")
    boot = boot.replace(' * Copyright (c) 2012-2023 Apple Inc.', ' * Copyright (c) 2012-2020 Apple Inc.')
    boot = boot.replace(' \tcpc.h \\\n', ' \tcpu_quiesce.h \\\n')
    # 8796 has no self-restrict/JIT-fatal block. Observe the same terminal
    # user-abort path after PAC classification and before exception triage.
    begin = boot.index('@@ -1671,6 +1673,7 @@')
    end = boot.index('@@ -2111', begin)
    boot = (boot[:begin] + '@@ -1484,3 +1484,4 @@\n'
            ' #endif /* __has_feature(ptrauth_calls) */\n'
            '+\tboot_progress_user_abort(state, esr, fault_addr);\n'
            ' \texception_triage(exc, codes, numcodes);\n'
            ' \t__builtin_unreachable();\n' + boot[end:])
    anchor = ' \ttask_t task = proc_task(p);\n \n \n'
    if boot.count(anchor) != 1:
        raise SystemExit("Critical exit anchor changed")
    boot = boot.replace(anchor, ' \tint kr = 0;\n \tint create_corpse = FALSE;\n \n')
    (CANDIDATES / "zzz-boot-progress.patch").write_text(boot, encoding="utf-8", newline="\n")

    rows, tree, failed = [], Tree(SOURCE), False
    for patch in upstream:
        if patch.name in OMITTED:
            rows.append({"patch": patch.name, "upstream_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
                         "status": "deferred/not-applicable", "reason": OMITTED[patch.name]})
            continue
        candidate = CANDIDATES / patch.name
        chosen = candidate if candidate.exists() else patch
        row = {"patch": patch.name, "chosen": str(chosen), "sha256": hashlib.sha256(chosen.read_bytes()).hexdigest(),
               "upstream_sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}
        try:
            row.update(status="virtual-pass", hunks=tree.apply(chosen.read_text(encoding="utf-8")))
        except PatchError as exc:
            row.update(status="virtual-fail", error=str(exc))
            failed = True
        rows.append(row)
        if failed:
            break  # Do not claim downstream patches passed after a missing dependency.

    # Independent git check of collapsed cumulative diff verifies final text applicability.
    # No source files are materialized and git is never asked to write them.
    combined = OUTPUT / "selected-combined.patch"
    combined.write_text(diff_files(tree), encoding="utf-8", newline="\n")
    combined_check = git(SOURCE, "apply", "--check", "--verbose", combined)
    after = git(SOURCE, "status", "--porcelain", "--untracked-files=all")
    report = {"timestamp": datetime.now().astimezone().isoformat(),
              "mode": "Strict in-memory sequence; final collapsed diff checked by read-only Git; no on-disk application/build",
              "source_head": original["source_head"], "base_head": original["base_head"],
              "base_status": git(BASE, "status", "--porcelain", "--untracked-files=no"),
              "comparison": comparison, "selection": rows,
              "complete_sequence": not failed, "combined_diff_check": combined_check,
              "source_status_before": before, "source_status_after": after}
    (OUTPUT / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    mismatches = [row for row in comparison if row["virtual_pass"] != row["git_pass"]]
    print("Baseline virtual/Git pass-fail mismatches:", len(mismatches))
    print("Selected sequence complete:", not failed)
    for row in rows:
        if row["status"] == "virtual-fail":
            print(row["error"])
    print("Combined diff --check exit:", combined_check["exit_code"])
    if after["exit_code"] or after["stdout"] or failed or combined_check["exit_code"] or mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
