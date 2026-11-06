"""Read-only source integration and factory-config audit; emits text evidence only.

Never assembles, builds, stages firmware, invokes git, or writes to input trees.
The patch simulator checks exact context in RAM. This is not EDK build validation.
"""
import argparse
import ast
import csv
import hashlib
import json
import re
from pathlib import Path

from virtual_patch import Tree


ROOT = Path(__file__).resolve().parents[1]
BASE = "Platforms/Xiaomi/nuwaPkg/"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rows(text, c_source=False):
    result = []
    section = "MemoryMap"
    for line_number, line in enumerate(text.splitlines(), 1):
        clean = line.strip()
        if clean.startswith("["):
            section = clean.strip("[]")
        if c_source:
            match = re.match(r'\{\s*"([^"]+)"\s*,\s*(0x[0-9a-fA-F]+),\s*(0x[0-9a-fA-F]+),\s*(.*?)\}', clean)
            if not match:
                continue
            name, base, size, tail = match.groups()
            fields = [base, size, name] + [f.strip() for f in tail.split(",")]
        else:
            if not clean.startswith("0x"):
                continue
            fields = next(csv.reader([clean], skipinitialspace=True))
            fields = [f.strip() for f in fields]
        if len(fields) != 8:
            raise ValueError(f"Unexpected memory row at {line_number}: {fields}")
        result.append(dict(base=int(fields[0], 16), size=int(fields[1], 16),
                           name=fields[2], attributes=fields[3:],
                           section=section, line=line_number))
    return result


def row_identity(row):
    return (row["base"], row["size"], row["name"], tuple(row["attributes"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware", type=Path, default=Path("D:/Code/PortingiOSLegacy/common/sources/mu-nuwa-firmware"))
    parser.add_argument("--unixnu", type=Path, default=Path("D:/Code/PortingiOSLegacy/common/sources/UniXNU"))
    parser.add_argument("--reference", type=Path, default=Path("D:/Code/PortingiOSWithUniXNU"))
    parser.add_argument("--sheng", type=Path, default=Path("D:/Code/PortingiOSLegacy/common/sources/uefi-sheng"))
    parser.add_argument("--kernel", type=Path, default=ROOT / "out/kernel-ci/39755850870/nuwa-8796-source-39755850870/nuwa-8796-source/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped")
    parser.add_argument("--report-dir", type=Path, default=ROOT / "reports/loader-integration")
    args = parser.parse_args()
    roots = {key: value.resolve() for key, value in vars(args).items()}
    report_dir = args.report_dir
    manifest = json.loads((ROOT / "config/loader-candidate.json").read_text(encoding="utf-8"))
    checks = []

    def check(name, ok):
        checks.append(dict(name=name, passed=bool(ok)))
        if not ok:
            raise ValueError(name)

    # Pin inputs including the independently generated reference working files.
    for item in manifest["inputs"]:
        check("input hash: " + item["root"] + "/" + item["path"],
              sha((roots[item["root"]] / item["path"]).read_bytes()) == item["sha256"])
    for item in manifest["protected"]:
        check("protected hash: " + item["path"],
              sha((roots.get(item.get("root"), ROOT) / item["path"]).read_bytes()) == item["sha256"])
    kernel = args.kernel.read_bytes()
    check("downloaded CI15 linked kernel size and SHA", len(kernel) == manifest["kernel"]["bytes"]
          and sha(kernel) == manifest["kernel"]["sha256"])

    tree = Tree(args.firmware)
    sheng_tree = Tree(args.sheng)
    unixnu_tree = Tree(args.unixnu)
    patch_trees = {"firmware": tree, "sheng": sheng_tree, "unixnu": unixnu_tree}
    hunks = []
    for patch in manifest["patches"]:
        data = (ROOT / patch["path"]).read_bytes()
        check("patch hash: " + patch["path"], sha(data) == patch["sha256"])
        target = patch_trees[patch["root"]]
        hunks.extend(dict(root=patch["root"], **h) for h in target.apply(data.decode("utf-8")))
    expected_loader_files = {
        "drivers/DarwinBoot/DarwinBootPkg/Driver/BootArgs.h",
        "drivers/DarwinBoot/DarwinBootPkg/Driver/DarwinBoot.c"}
    check("Darwin22 patch only changes loader ABI and command-line source", set(unixnu_tree.files) == expected_loader_files)
    for item in manifest["post_patch_inputs"]:
        check("effective patched hash: " + item["path"],
              sha(patch_trees[item["root"]].read(item["path"]).encode()) == item["lf_sha256"])
    sec_base = "Silicon/Silicium/SiliciumPkg/"
    check("only wiring, shim and SEC HOB source files changed", set(tree.files) == {
        "BootShim/BootShim.S", BASE + "nuwa.dsc", BASE + "nuwa.fdf", BASE + "DeviceBuild.py",
        *(sec_base + p for p in ("SiliciumPkg.dec", "Sec/Sec.c", "Sec/Sec.inf", "Sec/AArch64/ModuleEntryPoint.S"))})
    dsc, fdf = tree.read(BASE + "nuwa.dsc"), tree.read(BASE + "nuwa.fdf")
    fvmain = fdf.split("[FV.FvMain]", 1)[1].split("[FV.FVMAIN_COMPACT]", 1)[0]
    modules = manifest["modules"]
    for module in modules:
        check("DSC component: " + module,
              dsc.split("[Components]", 1)[1].splitlines().count("  " + module) == 1)
        check("same FvMain: " + module, fvmain.splitlines().count("  INF " + module) == 1)

    parsed = ast.parse(tree.read(BASE + "DeviceBuild.py"))
    common = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == "CommonPlatform")
    packages = ast.literal_eval(next(n.value for n in common.body if isinstance(n, ast.Assign)
                                    and any(isinstance(t, ast.Name) and t.id == "PackagesPath" for t in n.targets)))
    check("external package root in build settings", packages.count(".unixnu-packages") == 1)

    links = manifest["package_links"]

    def resolve(module):
        package, rest = module.split("/", 1)
        if package == "MdePkg":
            return args.firmware / "Mu_Basecore" / module
        return Path(links[".unixnu-packages/" + package].format(unixnu=args.unixnu, sheng=args.sheng)) / rest

    module_evidence = []
    for module in modules:
        path = resolve(module)
        text = sheng_tree.read(path.relative_to(args.sheng).as_posix()) if module.startswith("shengPkg/") else path.read_text(encoding="utf-8")
        guid = re.search(r"FILE_GUID\s*=\s*([^\s]+)", text)[1]
        kind = re.search(r"MODULE_TYPE\s*=\s*([^\s]+)", text)[1]
        module_evidence.append(dict(module=module, resolved=str(path), guid=guid, kind=kind,
                                    source_sha256=sha(path.read_bytes()), effective_text_sha256=sha(text.encode("utf-8"))))
        sources = text.split("[Sources]", 1)[1].split("[", 1)[0]
        for source in sources.splitlines():
            source = source.split("#", 1)[0].strip()
            if source:
                check("module source exists: " + module + ":" + source, (path.parent / source).is_file())
    check("module types", [m["kind"] for m in module_evidence] == ["UEFI_APPLICATION", "DXE_DRIVER", "UEFI_DRIVER", "DXE_DRIVER"])
    for library in ["UniXNULib|UniXNUPkg/Library/UniXNULib/UniXNULib.inf", "FdtLib|MdePkg/Library/BaseFdtLib/BaseFdtLib.inf"]:
        check("library mapping: " + library, library in dsc and resolve(library.split("|", 1)[1]).is_file())
    dec = (args.unixnu / "package/UniXNUPkg/UniXNUPkg.dec").read_text()
    check("registrar PCD matches application GUID", 'GUID("' + module_evidence[0]["guid"] + '")' in dec)
    boot = (args.unixnu / "package/UniXNUPkg/Library/UniXNULib/Boot.c").read_text()
    driver = unixnu_tree.read("drivers/DarwinBoot/DarwinBootPkg/Driver/DarwinBoot.c")
    check("loader consumer and producer refer to same protocol", "LocateProtocol (&gUniXNULoaderProtocolGuid" in boot
          and "InstallMultipleProtocolInterfaces" in driver and "&gUniXNULoaderProtocolGuid" in driver)
    check("registrar waits for variable protocols", "gEfiVariableArchProtocolGuid AND gEfiVariableWriteArchProtocolGuid"
          in resolve(modules[1]).read_text())

    old_shim = (args.firmware / "BootShim/BootShim.S").read_text()
    new_shim = tree.read("BootShim/BootShim.S")
    check("shim change limited to image_size expression", new_shim == old_shim.replace(
        ".quad FD_SIZE         /* Image Size */", ".quad (_Payload - _Head) + FD_SIZE /* Shim + FD image size */"))
    check("FD copy length unchanged", "ldr   x6,  =FD_SIZE" in new_shim)
    for filename in ("nuwa.dsc", "nuwa.fdf"):
        old = (args.firmware / BASE / filename).read_text()
        new = tree.read(BASE + filename)
        # All existing PCD and FD assignment lines must remain byte-for-byte.
        protected = [line for line in old.splitlines() if re.search(r"Pcd|FD_|BaseAddress|BlockSize|NumBlocks", line)]
        check("PCD/FD assignments unchanged: " + filename, all(line in new.splitlines() for line in protected))
    check("memory and configuration maps not patched", not any("MapLib" in p for p in tree.files))
    sec_c = tree.read(sec_base + "Sec/Sec.c")
    sec_asm = tree.read(sec_base + "Sec/AArch64/ModuleEntryPoint.S")
    check("SEC producer and package declare borrowed HOB GUID", all("gSiliciumEntryArgHobGuid" in tree.read(sec_base + p)
          for p in ("SiliciumPkg.dec", "Sec/Sec.inf", "Sec/Sec.c")))
    check("SEC saves entry x0 before clobber", sec_asm.index("str   x0, [x1]") < sec_asm.index("bl    ASM_PFX (PlatformAssemblyInitialize)"))
    check("HOB built after memory initialization", sec_c.index("Status = InitializeMemory ();") <
          sec_c.index("BuildGuidDataHob (&gSiliciumEntryArgHobGuid, &EntryArg, sizeof (EntryArg));"))
    publisher_path = "Platforms/Xiaomi/shengPkg/Drivers/ShengBootMemoryDxe/ShengBootMemoryDxe.c"
    check("sheng patch only changes borrowed publisher and its INF", set(sheng_tree.files) == {
        publisher_path, publisher_path.removesuffix(".c") + ".inf"})
    publisher = sheng_tree.read(publisher_path)
    check("publisher no longer extends RAM", all(token not in publisher for token in
          ("AddMemory (", "AddMemorySpace", "SetMemorySpaceAttributes", "ADD_LIMIT", "ADD_BELOW", "gDS->")))
    check("publisher preserves readonly BlockIo", all(token in publisher for token in
          ("mMedia.ReadOnly         = TRUE", "return EFI_WRITE_PROTECTED;", "linux,initrd-start", "linux,initrd-end",
           "&gEfiBlockIoProtocolGuid", "GET_GUID_HOB_DATA_SIZE (Hob) < sizeof (UINT64)")))
    dxe = (args.firmware / BASE / "Include/DXE.inc").read_text()
    check("stock FAT and partition drivers wired", "INF FatPkg/EnhancedFatDxe/Fat.inf" in dxe
          and "INF MdeModulePkg/Universal/Disk/PartitionDxe/PartitionDxe.inf" in dxe)

    # Independently extract the exact ASCII property from the existing XBL dump.
    raw_path = args.reference / ".work/nuwa-xbl_config_a.img"
    raw = raw_path.read_bytes()
    marker = b"[Config]\nVersion = 3\nMaxMemoryRegions = 74\n"
    check("unique raw cfg header", raw.count(marker) == 1)
    start = raw.index(marker)
    end = raw.index(b"\0", start)
    cfg_data = raw[start:end]
    cfg = cfg_data.decode("ascii")
    original = rows(cfg)
    edited = (args.reference / "device/observed/nuwa-uefiplatLA.cfg").read_text()
    check("reference reassembly preserves all 42 memory rows",
          [row_identity(r) for r in original] == [row_identity(r) for r in rows(edited)] and len(original) == 42)
    c_rows = rows((args.reference / ("uefi-nuwa/" + BASE + "Library/MemoryMapLib/MemoryMapLib.c")).read_text(), True)
    diff = []
    for row in original:
        same_extent = [r for r in c_rows if (r["base"], r["size"]) == (row["base"], row["size"])]
        if not same_extent or any(row_identity(r) != row_identity(row) for r in same_extent):
            diff.append(dict(factory=row, reference_same_extent=same_extent))
    extra = [r for r in c_rows if not any((r["base"], r["size"]) == (o["base"], o["size"]) for o in original)]
    conventional = [r for r in original if r["section"] == "MemoryMap" and r["attributes"][0:2] == ["AddMem", "SYS_MEM"]
                    and r["attributes"][3] == "Conv"]
    heap = next(r for r in conventional if r["name"] == "DXE Heap")
    check("raw factory rows do not describe high bank", all(r["base"] + r["size"] <= 2**32 for r in original))
    check("dynamic TZ marker retained in original", next(r for r in original if r["name"] == "TZApps Reserved")["attributes"][0] == "AddDynamicMem")
    report = dict(result="static checks passed; no compile/emission/device execution", checks=checks, hunks=hunks,
                  modules=module_evidence, kernel=manifest["kernel"],
                  factory=dict(source=str(raw_path), source_sha256=sha(raw), offset=start, end_exclusive=end,
                               bytes=len(cfg_data), sha256=sha(cfg_data), rows=original,
                               memory_rows=sum(r["section"] == "MemoryMap" for r in original),
                               register_rows=sum(r["section"] == "RegisterMap" for r in original),
                               reference_cfg_is_verbatim=edited == cfg, dxe_heap_mib=heap["size"] / 2**20,
                               conventional_sys_mem_total_mib=sum(r["size"] for r in conventional) / 2**20),
                  reference_map=dict(rows=len(c_rows), changed_or_split=diff, added_or_split=extra),
                  unverified=["EDK full library resolution/compile/FV size", "DXE dispatch/BDS/protocol installation on device",
                              "ABL initrd properties, firmware mapping and reservation lifetime, FAT mount",
                              "NoMap/AddDynamicMem semantics and live UEFI memory map", "512 MiB-1 GiB contiguous allocation",
                              "CI15 runtime providers/timer/startup and donor prelink/ABI", "boot image and XNU execution"])
    report_dir.mkdir(parents=True, exist_ok=True)
    # Reuse the already committed byte-for-byte factory evidence for a new
    # audit directory. Do not duplicate it or trim its original whitespace.
    existing_factory = ROOT / "reports/loader-integration/factory-uefiplatLA-original.txt"
    if report_dir.resolve() != existing_factory.parent.resolve() and existing_factory.exists():
        check("existing verbatim factory evidence matches", existing_factory.read_bytes() == cfg_data)
    else:
        (report_dir / "factory-uefiplatLA-original.txt").write_bytes(cfg_data)
    (report_dir / "audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(checks=len(checks), cfg_offset=start, cfg_bytes=len(cfg_data),
                          memory_rows=report["factory"]["memory_rows"], register_rows=report["factory"]["register_rows"], dxe_heap_mib=heap["size"] / 2**20,
                          differing_factory_rows=len(diff), additional_or_split_reference_rows=len(extra))))


if __name__ == "__main__":
    main()
