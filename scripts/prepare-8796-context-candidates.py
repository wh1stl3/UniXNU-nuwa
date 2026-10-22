"""Generate five reviewed diff candidates in memory; never write source trees."""
import difflib
import hashlib
import json
from pathlib import Path
from datetime import datetime

from check_native_support import BASE, SOURCE, git

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "patches/xnu-8796-candidates"
REPORT = ROOT / "reports/xnu-8796-candidates"


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected unique anchor: {old!r}")
    return text.replace(old, new, 1)


def main():
    before = git(SOURCE, "status", "--porcelain", "--untracked-files=all")
    head = git(SOURCE, "rev-parse", "HEAD")
    if before["exit_code"] or before["stdout"] or head["stdout"].strip() != "1b191cb58250d0705d8a51287127505aa4bc0789":
        raise SystemExit("Unexpected or dirty XNU baseline")
    provenance = json.loads((ROOT / "reports/patch-portability-8796-recheck/results.json").read_text(encoding="utf-8"))
    if git(BASE, "rev-parse", "HEAD")["stdout"].strip() != provenance["base_head"]:
        raise SystemExit("Base HEAD changed: diff and review before regenerating")
    for entry in provenance["results"]:
        patch = BASE / "patches/xnu" / entry["patch"]
        if hashlib.sha256(patch.read_bytes()).hexdigest() != entry["sha256"]:
            raise SystemExit(f"Upstream patch changed: {patch.name}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    rows = []

    def emit(name, edits, reason):
        chunks = []
        for path, transform in edits:
            original = (SOURCE / path).read_text(encoding="utf-8")
            changed = transform(original)
            if original == changed:
                raise ValueError(f"No change for {path}")
            chunks.append("".join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
                                                      fromfile="a/" + path, tofile="b/" + path)))
        patch = OUTPUT / name
        text = "".join(chunks)
        patch.write_text(text, encoding="utf-8", newline="\n")
        result = git(SOURCE, "apply", "--check", "--verbose", patch)
        upstream = BASE / "patches/xnu" / name
        row = {"patch": name, "reason": reason,
               "upstream_sha256": hashlib.sha256(upstream.read_bytes()).hexdigest(),
               "candidate_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(), **result}
        rows.append(row)
        (REPORT / (name + ".log")).write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def start(text):
        text = replace_once(text, '#include <arm64/tunables/tunables.s>\n',
                            '#if defined(APPLE_ARM64_ARCH_FAMILY)\n#include <arm64/tunables/tunables.s>\n#endif\n')
        return replace_once(text, '\t// Read MIDR before start of per-SoC tunables\n\tmrs x12, MIDR_EL1\n\n\tAPPLY_TUNABLES x12, x13, x14\n',
                            '#if defined(APPLE_ARM64_ARCH_FAMILY)\n\t// Read MIDR before start of per-SoC tunables\n\tmrs x12, MIDR_EL1\n\n\tAPPLY_TUNABLES x12, x13, x14\n#endif\n')

    emit("apple-only-cpu-tunables.patch", [("osfmk/arm64/start.s", start)],
         "Keep 8796 assym.s include; guard the same Apple-only include and APPLY_TUNABLES block")

    def archive(text):
        target = '$(TARGET)/$(KERNEL_FILE_NAME).unstripped: $(addprefix'
        return replace_once(text, target,
                            '# Explicit external source archives participate in incremental relinking.\n'
                            '$(TARGET)/$(KERNEL_FILE_NAME).unstripped: $(XNU_EXTERNAL_KERNEL_ARCHIVES)\n\n' + target)

    emit("external-archive-dependencies.patch", [("makedefs/MakeInc.kernel", archive)],
         "8796 actual link target is .unstripped, not 10063 .unstripped.noctf; use actual target")

    upstream_aes = (BASE / "patches/xnu/native-aes-personality.patch").read_text(encoding="utf-8")
    additions = "".join(line[1:] for line in upstream_aes.splitlines(True)
                        if line.startswith("+") and not line.startswith("+++"))
    emit("native-aes-personality.patch", [("iokit/KernelConfigTables.cpp",
         lambda s: replace_once(s, '    ")";\n', additions + '    ")";\n'))],
         "Reuse original added personality strings verbatim after 8796 IOPanicPlatform, without IOExclaveProxy")

    def machine_master(text):
        anchor = 'options   NOS_ARM_ASM\t\t\t# <nos_arm_asm>\n'
        return replace_once(text, anchor, 'options   CONFIG_APPLE_AMCC\t\t\t# <apple_amcc>\n\n' + anchor)

    def machine_board(text):
        text = replace_once(text, 'arm64 config_pmap_ppl xsmall', 'arm64 config_pmap_ppl nos_arm_asm nos_arm_pmap xsmall')
        if text.count(' sched_hygiene_debug') != 2:
            raise ValueError("Unexpected sched_hygiene_debug entries")
        return text.replace(' sched_hygiene_debug', '')

    def machine_files(text):
        for line in ('osfmk/arm64/amcc_rorgn_ppl.c optional nos_arm_asm config_pmap_ppl',
                     'osfmk/arm64/amcc_rorgn_common.c optional nos_arm_asm'):
            text = replace_once(text, line + '\n', line + ' apple_amcc\n')
        return text

    emit("source-machine-layer.patch", [("config/MASTER", machine_master),
         ("config/MASTER.arm64.bcm2837", machine_board), ("osfmk/conf/files.arm64", machine_files)],
         "Preserve 8796 config context; gate only two existing AMCC units, no invented ctrr3/amcc files")

    upstream_pmap = (BASE / "patches/xnu/zzx-pmap-sync-64bit-pa.patch").read_text(encoding="utf-8")
    first = upstream_pmap.split('diff --git a/osfmk/arm64/sptm/pmap/pmap.c', 1)[0]
    old = '\tflush_dcache((vm_offset_t) (pp << PAGE_SHIFT), PAGE_SIZE, TRUE);\n'
    new = "".join(line[1:] for line in first.splitlines(True)
                  if line.startswith("+") and not line.startswith("+++"))
    emit("zzx-pmap-sync-64bit-pa.patch", [("osfmk/arm/pmap/pmap.c", lambda s: replace_once(s, old, new))],
         "Keep original ptoa PA-width fix; omit SPTM branch absent from 8796; no board memory changes")

    after = git(SOURCE, "status", "--porcelain", "--untracked-files=all")
    report = {"timestamp": datetime.now().astimezone().isoformat(), "mode": "Five independent candidate --check, not cumulative",
              "source_head": head, "base_head": git(BASE, "rev-parse", "HEAD"),
              "source_status_before": before, "source_status_after": after, "results": rows}
    (REPORT / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if after["exit_code"] or after["stdout"] or any(row["exit_code"] for row in rows):
        raise SystemExit("Candidate check failed or source status changed")
    print("Five candidate patches: independent static checks PASS; source status unchanged")


if __name__ == "__main__":
    main()
