"""Shared read-only Git runner for patch audit scripts."""
from pathlib import Path
import subprocess

BASE = Path("D:/Code/PortingiOS/common/sources/UniXNU")
SOURCE = Path("D:/Code/PortingiOS/common/sources/xnu-ios16-full")
GIT = "C:/Program Files/Git/cmd/git.exe"


def git(repo, *args):
    # Fail closed: this module is never a general Git command runner.
    if not args or args[0] not in {"status", "rev-parse", "log", "show", "diff", "apply"}:
        raise ValueError("Only read-only Git commands allowed")
    if args[0] == "apply" and "--check" not in args:
        raise ValueError("Only git apply --check allowed")
    command = [GIT, "-c", f"safe.directory={repo.as_posix()}", "--no-optional-locks", "-C", str(repo), *map(str, args)]
    result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace")
    return {"command": command, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
