#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Check the host-only v1 build, actual FAT args and closed provider gate."""
import argparse
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("NUWA_DATA_CANDIDATE", "NUWA_DISPOSABLE_DATA",
             "NUWA_DISPOSABLE_FUA_PERMISSIVE", "NUWA_DATA_WRITE_OPT_IN", "NUWA_FUA_TRIAL")


def definitions(argv):
    result = set()
    for index, arg in enumerate(argv):
        if arg == "-D":
            result.add(argv[index + 1].split("=", 1)[0])
        elif arg.startswith("-D"):
            result.add(arg[2:].split("=", 1)[0])
    return result


def args_from(config):
    entry, = (entry for entry in tomllib.loads(config.decode())["entry"] if entry["id"] == "xnu")
    return entry["args"].encode()


def invalid_cli():
    builder = ROOT / "scripts/build-nuwa-display-native.py"
    common = [sys.executable, "-B", str(builder), "--base", str(ROOT), "--cpo", str(ROOT),
              "--linker-dir", str(ROOT), "--r35-dir", str(ROOT / "out/nuwa-r35-20261119"),
              "--cpu-only", "--no-software-vsync", "--candidate",
              "--r35l-dir", str(ROOT / "out/nuwa-r35l-regs-full-20261121"),
              "--crashcap", "--pixsig", "--data-persist-diag",
              "--out", str(ROOT / "out/nuwa-v1-invalid-must-not-exist")]
    for extra in (["--data-v1-direct"],
                  ["--data-v1-direct", "--data-candidate-gpt", "unused", "--disposable-data"],
                  ["--data-v1-direct", "--data-candidate-gpt", "unused", "--disposable-fua-permissive"]):
        result = subprocess.run(common + extra, text=True, capture_output=True)
        assert result.returncode == 2 and "--data-v1-direct requires" in result.stderr, result.stderr
    assert not (ROOT / "out/nuwa-v1-invalid-must-not-exist").exists()
    print("PASS incompatible or missing v1 options rejected before output creation")


def main(build, package, baseline):
    invalid_cli()
    old_build = ROOT / "out/nuwa-no-glyph-20261128-build"
    packer = ROOT / "scripts/package-nuwa-crashcap.py"
    reject_out = ROOT / "out/nuwa-v1-invalid-package-must-not-exist"
    for kernel, option, expected in (
            (old_build / "kernel.macho", "--v1-data-template", "v1 template excludes"),
            (build / "kernel.macho", "--disposable-data-template", "requires a disposable kernel")):
        result = subprocess.run([sys.executable, "-B", str(packer), "--base", str(ROOT),
                                 "--kernel", str(kernel), "--out", str(reject_out),
                                 option, "unused"], text=True, capture_output=True)
        assert result.returncode != 0 and expected in result.stderr, result.stderr
    assert not reject_out.exists()
    print("PASS package rejects mismatched v1 and disposable kernels before creating output")
    require_v1_kernel = runpy.run_path(str(packer))["require_v1_kernel"]
    v3 = (ROOT.parent / "worktree-dualbank/out/nuwa-dualbank-20261126-build/kernel.macho").read_bytes()
    try:
        require_v1_kernel(v3)
    except SystemExit as error:
        assert str(error) == "v1 template requires RamBlock's v1 directDiskIO"
    else:
        raise AssertionError("non-disposable v3 kernel accepted as v1")
    print("PASS package rejects non-disposable v3 kernel lacking v1 directDiskIO")
    ram = json.loads((build / "ramblock-argv.json").read_text())
    provider = json.loads((build / "data-provider-argv.json").read_text())
    for label, command in (("ramblock", ram), ("provider", provider)):
        assert not definitions(command).intersection(FORBIDDEN), (label, definitions(command))
    renderer = json.loads((build / "build-boot-progress-report.json").read_text())
    assert not any(any(name in flag for name in FORBIDDEN) for flag in renderer["stub_defines"])
    link = json.loads((build / "native-link-argv.json").read_text())
    assert any("nuwa-data-provider/lib" in arg for arg in link)
    nm = subprocess.check_output(["llvm-nm", "-P", str(build / "native.macho")], text=True)
    for name in ("_native_ufs_store_open", "_native_ufs_store_write", "_native_ufs_store_sync"):
        assert any(row.split()[0] == name and row.split()[1] != "U"
                   for row in nm.splitlines() if row.split())
    for name in ("_nuwa_disposable_fua_requests", "_nuwa_disposable_flushes",
                 "_native_ufs_store_order"):
        assert not any(row.split()[0] == name for row in nm.splitlines() if row.split())
    ram_nm = subprocess.check_output(["llvm-nm", "-P", str(build / "NativeRamBlock.o")], text=True)
    assert any("__ZL12directDiskIO" in row and "N7persist7Overlay" in row
               for row in ram_nm.splitlines())
    print("PASS compiled RamBlock contains directDiskIO with persist::Overlay (v1)")
    assert "Provider<CandidatePort, false> dataProvider" in (
        ROOT / "package/nuwa-data-write/KernelPort.inc").read_text()
    print("PASS provider linked; forbidden command-line defines and disposable symbols absent")
    print("PASS source has Provider<CandidatePort, false>; device write remains unqualified")

    old_config = (baseline / "unixnu.toml").read_bytes()
    new_config = (package / "unixnu.toml").read_bytes()
    fat_config = subprocess.check_output(["mtype", "-i", str(package / "readback-fat.img"),
                                          "::/EFI/UniXNU/unixnu.toml"])
    assert new_config == fat_config
    old, new = args_from(old_config), args_from(fat_config)
    assert len(old) == 602 and old.count(b"nuwa-disposable-data=1") == 1
    assert new == old.replace(b"nuwa-disposable-data=1", b"nuwa-data-write=1")
    assert old_config.replace(old, new) == new_config
    tokens = new.split()
    assert len(new) <= 607
    for token in (b"nuwa-data-write=1", b"sheng-data-persist=2", b"sheng-log-reserve=1024"):
        assert tokens.count(token) == 1
    assert not {token.split(b"=", 1)[0] for token in tokens} & {
        b"nuwa-disposable-data", b"sheng-data-reset"}
    audit = json.loads((package / "audit.json").read_text())
    assert audit["args_bytes"] == len(new) and audit["device_release"] is False
    assert audit["data_profile"] == "v1-direct"
    print(f"PASS actual FAT args: {len(new)} bytes, exact token replacement from 602-byte baseline")
    print("args=" + new.decode())
    print("args_hex=" + new.hex())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("build", type=Path)
    parser.add_argument("package", type=Path)
    parser.add_argument("baseline", type=Path)
    options = parser.parse_args()
    main(options.build.resolve(), options.package.resolve(), options.baseline.resolve())
