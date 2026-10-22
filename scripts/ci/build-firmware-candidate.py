"""R-004 A: build EFI/FD/BootShim in fresh Actions temp trees, never boot images."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out/firmware-ci"


def digest(path, lf=False):
    data = path.read_bytes()
    return hashlib.sha256(data.replace(b"\r\n", b"\n") if lf else data).hexdigest()


def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Only the approved disposable Actions build environment is supported")
    temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    work = temp / "nuwa-firmware-candidate"
    if work.exists():
        raise RuntimeError("Fresh source/build tree required; refusing to overwrite")
    work.mkdir()
    OUT.mkdir(parents=True, exist_ok=False)
    recipe = json.loads((ROOT / "config/firmware-ci-inputs.json").read_text())
    candidate = json.loads((ROOT / "config/loader-candidate.json").read_text())
    sources = {name: work / name for name in recipe["sources"]}
    commands = []

    def run(argv, cwd=work, env=None, log="commands.log"):
        argv = [str(a) for a in argv]
        item = dict(argv=argv, cwd=str(cwd), started=time.time())
        commands.append(item)
        print("RUN:", " ".join(argv), flush=True)
        with (OUT / log).open("a", encoding="utf-8") as stream:
            stream.write("\nCOMMAND " + json.dumps(argv) + "\n")
            stream.flush()
            result = subprocess.run(argv, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT)
        item.update(exit_code=result.returncode, ended=time.time())
        save("commands.json", commands)
        if result.returncode:
            print((OUT / log).read_text(errors="replace")[-14000:], flush=True)
            raise RuntimeError(f"Command failed ({result.returncode}): {argv[0]}; see {log}")

    fw = sources["firmware"]
    try:
        for name, info in recipe["sources"].items():
            dest = sources[name]
            run(["git", "init", dest])
            run(["git", "remote", "add", "origin", f"https://github.com/{info['repository']}.git"], dest)
            run(["git", "fetch", "--depth", "1", "origin", info["commit"]], dest)
            run(["git", "checkout", "--detach", "FETCH_HEAD"], dest)
            head = subprocess.check_output(["git", "log", "-1", "--format=%H"], cwd=dest, text=True).strip()
            if head != info["commit"]:
                raise ValueError("Wrong source commit")
        run(["git", "submodule", "update", "--init", "--depth", "1", "--",
             "Common/Mu", "Common/Mu_OEM_Sample", "Mu_Basecore", "Silicium-ACPI",
             "Silicon/Silicium/OpensslPkg/Library/OpensslLib/openssl", "Binaries"], fw, log="submodules.log")
        checked = []
        for item in recipe["inputs"]:
            actual = digest(sources[item["root"]] / item["path"], lf=True)
            if actual != item["lf_sha256"]:
                raise ValueError(f"Source hash mismatch: {item['root']}/{item['path']}")
            checked.append(dict(**item, actual=actual))
        if digest(ROOT / "board.toml", True) != recipe["board_lf_sha256"]:
            raise ValueError("Device board changed")
        if digest(sources["unixnu"] / "feeds.toml", True) != recipe["feed_lf_sha256"]:
            raise ValueError("Base feed changed")
        save("inputs.json", dict(recipe=recipe, checks=checked, kernel=candidate["kernel"],
                                 kernel_included_in_firmware=False,
                                 device_commit=os.environ.get("GITHUB_SHA"), run_id=os.environ.get("GITHUB_RUN_ID")))
        normalized_inputs = []
        for patch in candidate["patches"]:
            path = ROOT / patch["path"]
            if digest(path) != patch["sha256"]:
                raise ValueError("Patch hash mismatch")
            # Some pinned Mu blobs contain CRLF even on Linux. Input hashes above
            # explicitly normalize CRLF; normalize only these exact patch targets,
            # retaining strict git-apply context checks (no ignore-whitespace flags).
            for line in path.read_text().splitlines():
                if not line.startswith("+++ b/"):
                    continue
                target = (sources[patch["root"]] / line[6:]).resolve()
                if not target.is_relative_to(sources[patch["root"]]):
                    raise ValueError("Patch target outside approved source root")
                raw = target.read_bytes()
                lf = raw.replace(b"\r\n", b"\n")
                if raw != lf:
                    normalized_inputs.append(dict(root=patch["root"], path=line[6:],
                                                  raw_sha256=hashlib.sha256(raw).hexdigest(),
                                                  lf_sha256=hashlib.sha256(lf).hexdigest()))
                    target.write_bytes(lf)
            save("line-ending-normalization.json", normalized_inputs)
            run(["git", "apply", "--check", path], sources[patch["root"]])
            run(["git", "apply", path], sources[patch["root"]])
        (fw / ".unixnu-packages").mkdir()
        for name, target in candidate["package_links"].items():
            path = Path(target.format(**{k: str(v) for k, v in sources.items()}))
            (fw / name).symlink_to(path, target_is_directory=True)
        run([sys.executable, "-m", "pip", "install", "-r", fw / "pip-requirements.txt"], log="dependencies.log")
        run([sys.executable, "-m", "pip", "freeze"], log="toolchain.log")
        for tool in ("clang", "llvm-objcopy", "llvm-nm", "ld.lld", "make"):
            run([tool, "--version"], log="toolchain.log")
        config = tomllib.loads((fw / "Resources/Configs/nuwa.toml").read_text())
        fd_base, fd_size = config["uefi_fd"]["base"], config["uefi_fd"]["size"]
        env = dict(os.environ, ENABLE_SECUREBOOT="1", FD_BASE=hex(fd_base), FD_SIZE=hex(fd_size),
                   FD_BLOCKS=hex(fd_size // 4096), DEVICE_MODEL="nuwa", CLANGPDB_AARCH64_PREFIX="aarch64-linux-gnu-")
        env["SOURCE_DATE_EPOCH"] = subprocess.check_output(["git", "log", "-1", "--format=%ct"], cwd=fw, text=True).strip()
        save("build-settings.json", dict(fd_base=hex(fd_base), fd_size=fd_size, target="DEBUG", toolchain="CLANGPDB",
                                         source_date_epoch=env["SOURCE_DATE_EPOCH"], approval="R-004 A",
                                         source_config_sha256=digest(fw / "Resources/Configs/nuwa.toml")))
        # Assemble shim before the full firmware, so its proof survives a later compiler failure.
        shimdir = OUT / "shim"
        shimdir.mkdir()
        run(["clang", "--target=aarch64-none-elf", "-c", f"-DFD_BASE={fd_base}", f"-DFD_SIZE={fd_size}",
             "-DREQUIRES_KERNEL_HEADER=1", fw / "BootShim/BootShim.S", "-o", shimdir / "shim.o"], log="shim-build.log")
        run(["llvm-objcopy", "-O", "binary", shimdir / "shim.o", shimdir / "shim.bin"], log="shim-build.log")
        symbols = subprocess.check_output(["llvm-nm", "-n", shimdir / "shim.o"], text=True)
        (shimdir / "symbols.txt").write_text(symbols)
        blob = (shimdir / "shim.bin").read_bytes()
        payload_offset = next(int(line.split()[0], 16) for line in symbols.splitlines() if line.endswith(" _Payload"))
        if (payload_offset != len(blob) or blob[56:60] != b"ARM\x64"
                or struct.unpack_from("<QQ", blob, 8) != (fd_base, len(blob) + fd_size)):
            raise ValueError("BootShim header/payload mismatch")
        save("shim.json", dict(bytes=len(blob), sha256=digest(shimdir / "shim.bin"), payload_offset=payload_offset,
                               fd_base=hex(fd_base), fd_size=fd_size, image_size=len(blob) + fd_size))
        driver = "Platforms/Xiaomi/nuwaPkg/DeviceBuild.py"
        run([sys.executable, driver, "--setup", "-t", "DEBUG"], fw, env, "setup.log")
        run([sys.executable, driver, "--update", "-t", "DEBUG"], fw, env, "update.log")
        run([sys.executable, driver, "TARGET=DEBUG", "ENABLE_SECUREBOOT=1", f"FD_BASE={hex(fd_base)}",
             f"FD_SIZE={hex(fd_size)}", f"FD_BLOCKS={hex(fd_size // 4096)}", "DEVICE_MODEL=nuwa",
             "BUILDREPORT_FILE=" + str(OUT / "BUILD_REPORT.txt")], fw, env, "build.log")
        fd = fw / "Build/nuwaPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd"
        if fd.stat().st_size != fd_size:
            raise ValueError("FD length does not match original config")
        # Recheck every protected source input after tooling; only approved patched files may differ.
        touched = {("firmware", "BootShim/BootShim.S"),
                   *(('firmware', 'Platforms/Xiaomi/nuwaPkg/' + n) for n in ('nuwa.dsc', 'nuwa.fdf', 'DeviceBuild.py')),
                   *(('firmware', 'Silicon/Silicium/SiliciumPkg/' + n) for n in
                     ('SiliciumPkg.dec', 'Sec/Sec.c', 'Sec/Sec.inf', 'Sec/AArch64/ModuleEntryPoint.S')),
                   *(('sheng', 'Platforms/Xiaomi/shengPkg/Drivers/ShengBootMemoryDxe/ShengBootMemoryDxe.' + ext) for ext in ('c', 'inf'))}
        for item in recipe["inputs"]:
            if (item["root"], item["path"]) not in touched:
                if digest(sources[item["root"]] / item["path"], True) != item["lf_sha256"]:
                    raise ValueError("Protected input changed during build: " + item["path"])
        save("result.json", dict(result="build succeeded; artifact inspection pending", fd_sha256=digest(fd),
                                 fd_bytes=fd.stat().st_size, device_executed=False, boot_image_generated=False))
    except Exception as error:
        save("failure.json", dict(error=str(error), commands_completed=len(commands)))
        raise
    finally:
        if (fw / ".git").exists():
            state = subprocess.run(["git", "submodule", "status", "--recursive"], cwd=fw, capture_output=True, text=True)
            (OUT / "submodules-final.txt").write_text(state.stdout + state.stderr)
        # Copy only build evidence and approved EFI/FD/FV artifacts, including on compiler failure.
        build = fw / "Build/nuwaPkg/DEBUG_CLANGPDB"
        if build.is_dir():
            names = {"UniXNU", "UniXNUDxe", "DarwinBoot", "ShengBootMemoryDxe"}
            for path in build.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(build)
                allowed = (rel.parts[0] == "FV" and path.suffix.lower() in {".fd", ".fv", ".ffs", ".map", ".txt", ".inf"}
                           or path.stem in names and path.suffix.lower() in {".efi", ".map", ".depex", ".inf", ".txt"})
                if allowed:
                    target = OUT / "build" / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
        inventory = [dict(path=p.relative_to(OUT).as_posix(), bytes=p.stat().st_size, sha256=digest(p))
                     for p in sorted(OUT.rglob("*")) if p.is_file()]
        save("inventory.json", inventory)


if __name__ == "__main__":
    main()
