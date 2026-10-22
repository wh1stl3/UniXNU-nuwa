"""Read-only git apply --check for NativePrelink; writes evidence only here."""
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("D:/Code/PortingiOS/common/sources/xnu-ios16-full")
BASE = Path("D:/Code/PortingiOS/common/sources/UniXNU")
GIT = "C:/Program Files/Git/cmd/git.exe"
OUTPUT = ROOT / "reports/native-prelink-8796"


def git(repo, *args):
    command = [GIT, "-c", f"safe.directory={repo.as_posix()}",
               "--no-optional-locks", "-C", str(repo), *map(str, args)]
    result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace")
    return {"command": command, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def main():
    before = git(SOURCE, "status", "--porcelain", "--untracked-files=all")
    if before["exit_code"] or before["stdout"]:
        raise SystemExit("Source baseline not clean/readable")
    patches = sorted((BASE / "kits/NativePrelink/patches").glob("*.patch"))
    if len(patches) != 2:
        raise SystemExit("Expected exactly two NativePrelink patches")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for patch in patches:
        row = git(SOURCE, "apply", "--check", "--verbose", patch)
        row.update(patch=patch.name, sha256=hashlib.sha256(patch.read_bytes()).hexdigest())
        rows.append(row)
        (OUTPUT / (patch.name + ".log")).write_text(
            subprocess.list2cmdline(row["command"]) + "\n"
            + f"exit_code={row['exit_code']}\n" + row["stdout"] + row["stderr"], encoding="utf-8")
    after = git(SOURCE, "status", "--porcelain", "--untracked-files=all")
    board_text = (ROOT / "board.toml").read_text(encoding="utf-8")
    board = tomllib.loads(board_text)
    report = {
        "timestamp": datetime.now().astimezone().isoformat(),
        "mode": "Independent --check; no patches applied, no cumulative or build claim",
        "source_head": git(SOURCE, "rev-parse", "HEAD"),
        "base_head": git(BASE, "rev-parse", "HEAD"),
        "base_status": git(BASE, "status", "--porcelain", "--untracked-files=no"),
        "source_status_before": before, "source_status_after": after,
        "board_toml": {"parse": "pass", "sha256": hashlib.sha256(board_text.encode()).hexdigest(),
                       "data": board},
        "results": rows,
    }
    (OUTPUT / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if after["exit_code"] or after["stdout"]:
        raise SystemExit("Source status changed during checks")
    for row in rows:
        print(row["patch"], "exit_code=" + str(row["exit_code"]))
    print("board.toml: TOML syntax parse PASS (not a complete board validation)")


if __name__ == "__main__":
    main()
