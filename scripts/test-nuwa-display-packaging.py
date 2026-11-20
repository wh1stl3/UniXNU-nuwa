#!/usr/bin/env python3
"""Regression: an authentic display build digest must not qualify as r35 OFF."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--kernel-sha256", required=True)
    a = parser.parse_args()
    if hashlib.sha256(a.kernel.read_bytes()).hexdigest() != a.kernel_sha256:
        parser.error("test requires the display kernel's correct SHA256")
    with tempfile.TemporaryDirectory(dir=ROOT / "out", prefix="r35-profile-test-") as tmp:
        output = Path(tmp) / "off"
        command = [sys.executable, "-B", ROOT / "scripts/build-ufs-apfs-root-chmh-r35-display.py",
                   "--kernel", a.kernel, "--kernel-sha256", a.kernel_sha256, "--output", output]
        result = subprocess.run(command, capture_output=True, text=True)
        if (result.returncode != 2 or output.exists()
                or "off profile requires the original r35 kernel SHA256" not in result.stderr):
            raise SystemExit("OFF did not reject the correctly hashed display kernel:\n" + result.stderr)
    print("PASS: correctly hashed display kernel rejected by OFF before output creation")


if __name__ == "__main__":
    main()
