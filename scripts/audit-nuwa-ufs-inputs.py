#!/usr/bin/env python3
"""Offline, read-only UFS input inventory; never enables or executes a driver.

Requires Python 3.11, dtc and fdtget. Only allowlisted resource properties leave
the compiled input. Full DTS/DTB and tool diagnostics remain local in ignored out.
Exit 0: inventory complete (NOT driver readiness); 2: unresolved/malformed input;
1: tool, provenance or syntax error. See the accompanying audit document.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib


PIN = "99d8bcd3e43dd24fc3c8437c67b5d4cc71ab94d0"
REFS = {"clocks": "#clock-cells", "assigned-clocks": "#clock-cells",
        "assigned-clock-parents": "#clock-cells", "resets": "#reset-cells",
        "phys": "#phy-cells", "iommus": "#iommu-cells",
        "interconnects": "#interconnect-cells", "power-domains": "#power-domain-cells",
        "gpios": "#gpio-cells", "reset-gpios": "#gpio-cells",
        "interrupt-parent": None, "shared-ice-cfg": None}
STRINGS = {"compatible", "status", "reg-names", "clock-names", "phy-names",
           "reset-names", "interconnect-names", "qcom,iommu-dma"}
NUMERIC = {"reg", "ranges", "interrupts", "interrupts-extended", "phandle",
           "linux,phandle", "lanes-per-direction", "dev-ref-clk-freq",
           "freq-table-hz", "clock-frequency", "assigned-clock-rates",
           "regulator-min-microvolt", "regulator-max-microvolt"}
BOOL = {"dma-coherent", "regulator-always-on", "regulator-boot-on",
        "interrupt-controller"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if p.returncode:
        # Do not echo arbitrary tool output containing raw device input.
        raise ValueError(f"{Path(args[0]).name} failed (exit {p.returncode}); raw diagnostics suppressed")
    return p.stdout.strip()


def verify_source(source, archive, catalog):
    components = tomllib.loads(catalog.read_text())
    # Catalog uses [[component]], not an inferred repository name.
    entry = next(c for c in components["component"] if c["id"] == "ShengUfs")
    if entry["revision"] != PIN:
        raise ValueError("catalog ShengUfs revision differs from this audit's fixed pin")
    files = {}
    with tarfile.open(archive, "r:gz") as tf:
        prefix = f"ShengUfs-{PIN}/"
        for member in tf.getmembers():
            if not member.isfile():
                continue
            if not member.name.startswith(prefix):
                raise ValueError("archive root differs from fixed commit")
            rel = Path(member.name[len(prefix):])
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError("unsafe source archive path")
            data = tf.extractfile(member).read()
            if (source / rel).read_bytes() != data:
                raise ValueError(f"driver source differs from archive: {rel}")
            files[rel.as_posix()] = hashlib.sha256(data).hexdigest()
    for required in ("NativeUfs.cpp", "GccUfs.h", "SmmuTakeover.h", "Info.plist"):
        if required not in files:
            raise ValueError(f"missing fixed-source input: {required}")
    return {"revision": PIN, "repository": entry["repository"],
            "os_abi": entry["os_abi"], "board_dependencies": entry["board_dependencies"],
            "archive_sha256": sha(archive), "files_sha256": files,
            "provenance": "HTTPS commit archive; all archived files compared; not a Git signature verification"}


class Tree:
    def __init__(self, dtb):
        self.dtb = str(dtb)
        self.props = {}
        self.handles = {}
        self.cache = {}
        pending = ["/"]
        while pending:
            path = pending.pop()
            names = run(["fdtget", "-p", self.dtb, path]).splitlines()
            self.props[path] = names
            for name in ("phandle", "linux,phandle"):
                if name in names:
                    cells = self.cells(path, name)
                    if len(cells) != 1 or cells[0] in (0, 0xffffffff):
                        raise ValueError(f"invalid phandle at {path}")
                    old = self.handles.get(cells[0])
                    if old and old != path:
                        raise ValueError(f"duplicate phandle {cells[0]:x}")
                    self.handles[cells[0]] = path
            pending.extend(path.rstrip("/") + "/" + child for child in
                           run(["fdtget", "-l", self.dtb, path]).splitlines())

    def cells(self, path, prop):
        key = (path, prop)
        if key not in self.cache:
            text = run(["fdtget", "-t", "x", self.dtb, path, prop])
            self.cache[key] = [int(v, 16) for v in text.split()]
        return self.cache[key]

    def strings(self, path, prop):
        # Byte mode preserves individual strings even if they contain spaces.
        text = run(["fdtget", "-t", "bx", self.dtb, path, prop])
        return bytes(int(v, 16) for v in text.split()).rstrip(b"\0").decode().split("\0")

    def count(self, path, prop, default=None):
        if prop not in self.props[path]:
            if default is not None:
                return default
            raise ValueError(f"missing {prop} at {path}")
        cells = self.cells(path, prop)
        if len(cells) != 1 or cells[0] > 16:
            raise ValueError(f"invalid {prop} at {path}")
        return cells[0]

    @staticmethod
    def parent(path):
        return path.rsplit("/", 1)[0] or "/"


def inventory(tree, host):
    nodes, edges, issues = {}, [], []
    pending = [host]
    while pending:
        path = pending.pop(0)
        if path in nodes:
            continue
        props = tree.props[path]
        item = {"properties": {}, "registers": []}
        nodes[path] = item
        for prop in props:
            ref = prop in REFS or prop.endswith("-supply")
            allowed = (ref or prop in STRINGS | NUMERIC | BOOL or prop.startswith("#")
                       or prop.endswith(("-microamp", "-microvolt", "-uV")))
            if not allowed:
                continue
            value = (tree.strings(path, prop) if prop in STRINGS else
                     True if prop in BOOL else tree.cells(path, prop))
            item["properties"][prop] = value
            if not ref:
                continue
            if REFS.get(prop) is None and len(value) != 1:
                issues.append(f"{path}:{prop} expected one phandle cell")
                continue
            at = 0
            while at < len(value):
                handle = value[at]
                target = tree.handles.get(handle)
                edge = {"from": path, "property": prop, "cell_offset": at,
                        "phandle": hex(handle), "to": target,
                        "status": "resolved" if target else "unresolved", "raw_cells": [handle]}
                edges.append(edge)
                if not target:
                    issues.append(f"{path}:{prop}[{at}] unresolved {hex(handle)}; remaining cells not guessed")
                    break
                count_prop = REFS.get(prop)
                try:
                    width = tree.count(target, count_prop) if count_prop else 0
                except ValueError as error:
                    edge["status"] = "unresolved"
                    issues.append(str(error))
                    break
                end = at + 1 + width
                edge["raw_cells"] = value[at:end]
                edge["specifier"] = value[at + 1:end]
                if end > len(value):
                    edge["status"] = "unresolved"
                    issues.append(f"{path}:{prop} truncated specifier")
                    break
                pending.append(target)
                at = end
        if "reg" in props:
            parent = tree.parent(path)
            ac = tree.count(parent, "#address-cells", 2)
            sc = tree.count(parent, "#size-cells", 1)
            cells = tree.cells(path, "reg")
            width = ac + sc
            if not width or len(cells) % width:
                issues.append(f"{path}:reg invalid tuple width {ac}+{sc}")
            else:
                names = item["properties"].get("reg-names", [])
                for at in range(0, len(cells), width):
                    def integer(seq):
                        return sum(v << (32 * (len(seq) - i - 1)) for i, v in enumerate(seq))
                    item["registers"].append({"name": names[at // width] if at // width < len(names) else None,
                        "bus_address": hex(integer(cells[at:at + ac])),
                        "size_bytes": integer(cells[at + ac:at + width]),
                        "raw_cells": cells[at:at + width], "parent_address_cells": ac,
                        "parent_size_cells": sc, "translation": "bus address only; ancestor ranges below"})
            # Preserve only bus translation metadata, never arbitrary root properties.
            item["ancestor_bus_metadata"] = []
            while True:
                meta = {"path": parent}
                for prop in ("#address-cells", "#size-cells", "ranges"):
                    if prop in tree.props[parent]:
                        meta[prop] = tree.cells(parent, prop)
                item["ancestor_bus_metadata"].append(meta)
                if parent == "/":
                    break
                parent = tree.parent(parent)
        if "interrupts-extended" in props:
            issues.append(f"{path}:interrupts-extended decoding unsupported (raw cells retained)")
        if "interrupts" in props:
            owner = path
            while "interrupt-parent" not in tree.props[owner] and owner != "/":
                owner = tree.parent(owner)
            if "interrupt-parent" not in tree.props[owner]:
                issues.append(f"{path}:interrupt parent missing")
                continue
            handles = tree.cells(owner, "interrupt-parent")
            target = tree.handles.get(handles[0]) if len(handles) == 1 else None
            edges.append({"from": path, "property": "interrupts (inherited interrupt-parent)",
                          "defined_at": owner, "raw_cells": handles, "to": target,
                          "status": "resolved" if target else "unresolved"})
            if not target:
                issues.append(f"{path}:unresolved interrupt-parent")
                continue
            pending.append(target)
            width = tree.count(target, "#interrupt-cells")
            cells = tree.cells(path, "interrupts")
            compat = tree.strings(target, "compatible") if "compatible" in tree.props[target] else []
            item["interrupts"] = []
            if not width or len(cells) % width:
                issues.append(f"{path}:invalid interrupt tuple width")
            else:
                for at in range(0, len(cells), width):
                    raw = cells[at:at + width]
                    irq = {"raw_cells": raw, "parent": target}
                    if "arm,gic-v3" in compat and width == 3:
                        irq.update(type={0: "SPI", 1: "PPI"}.get(raw[0], "unknown"),
                                   number=raw[1], flags=hex(raw[2]),
                                   number_semantics="DT binding number; no GIC offset added")
                    item["interrupts"].append(irq)
    return nodes, edges, issues


def self_test():
    """Real dtc/fdtget fixtures; no imported DTS data or hardware operations."""
    root = Path(__file__).resolve().parents[1] / "out/ufs-input-audit-20261110"
    root.mkdir(parents=True, exist_ok=True)
    fixture = """/dts-v1/;
    / { #address-cells = <2>; #size-cells = <2>;
      serial-number = "SENSITIVE_TEST_SENTINEL";
      soc { #address-cells = <1>; #size-cells = <1>; ranges;
        interrupt-parent = <1>;
        intc { compatible = "arm,gic-v3"; phandle = <1>;
          interrupt-controller; #interrupt-cells = <3>; #address-cells = <0>; };
        clk { phandle = <2>; #clock-cells = <1>; };
        phy { phandle = <3>; #phy-cells = <0>; resets = <4 0>; };
        ufshc@1d84000 { phandle = <4>; #reset-cells = <1>;
          reg = <0x1d84000 0x3000>; interrupts = <0 0x109 4>;
          clocks = <2 0x8a 2 1>; phys = <3>; dma-coherent;
          serial-number = "SENSITIVE_TEST_SENTINEL"; };
      };
    };"""
    checks = []
    with tempfile.TemporaryDirectory(dir=root) as temp:
        temp = Path(temp)

        def parse(text):
            dts, dtb = temp / "test.dts", temp / "test.dtb"
            dts.write_text(text)
            run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(dtb), str(dts)])
            return Tree(dtb)

        nodes, edges, issues = inventory(parse(fixture), "/soc/ufshc@1d84000")
        assert not issues and len(nodes) == 4
        host = nodes["/soc/ufshc@1d84000"]
        assert host["registers"][0]["size_bytes"] == 0x3000
        assert host["registers"][0]["bus_address"] == "0x1d84000"
        assert host["interrupts"][0]["number"] == 0x109
        assert host["interrupts"][0]["type"] == "SPI"
        assert host["interrupts"][0]["flags"] == "0x4"
        assert "SENSITIVE_TEST_SENTINEL" not in json.dumps([nodes, edges, issues])
        checks.append("valid cycle, widths, SPI number/flags and property allowlist")
        for name, text, expected in (
            ("unresolved", fixture.replace("phys = <3>", "phys = <0xdead>"), "unresolved"),
            ("truncated", fixture.replace("clocks = <2 0x8a 2 1>", "clocks = <2>"), "truncated"),
            ("missing-width", fixture.replace("#clock-cells = <1>;", ""), "missing #clock-cells"),
            ("bad-reg", fixture.replace("reg = <0x1d84000 0x3000>", "reg = <1 2 3>"), "invalid tuple"),
        ):
            _, _, found = inventory(parse(text), "/soc/ufshc@1d84000")
            assert any(expected in issue for issue in found), (name, found)
            checks.append(name)
        try:
            parse(fixture.replace("phandle = <3>", "phandle = <2>"))
        except ValueError:
            checks.append("duplicate phandle rejected by real parser or index")
        else:
            raise AssertionError("duplicate phandle accepted")
        try:
            parse("/dts-v1/; / { invalid")
        except ValueError:
            checks.append("DTS syntax error rejected")
        else:
            raise AssertionError("invalid syntax accepted")
    result = {"result": "self-checked", "checks": checks, "count": len(checks)}
    (root / "self-test.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    return 0


def main():
    if sys.argv[1:] == ["--self-test"]:
        return self_test()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dts", required=True, type=Path)
    parser.add_argument("--driver-source", required=True, type=Path)
    parser.add_argument("--driver-archive", required=True, type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--host", default="/soc/ufshc@1d84000")
    args = parser.parse_args()
    # Restrict generated artifacts to this device repository's ignored out tree.
    out = args.out.resolve()
    root = Path(__file__).resolve().parents[1] / "out"
    if not out.is_relative_to(root) or out == root:
        parser.error("--out must be a subdirectory of this device repository's out/")
    outputs = {out / name for name in ("input.dtb", "dtc-local.log", "resources.json", "resources.md", "error.json")}
    if (any(p.resolve() in outputs for p in (args.dts, args.driver_archive, args.catalog))
            or out.is_relative_to(args.driver_source.resolve())):
        parser.error("output must not overwrite audit inputs or reside inside driver source")
    out.mkdir(parents=True, exist_ok=True)
    try:
        for tool in ("dtc", "fdtget"):
            if not shutil.which(tool):
                raise ValueError(f"missing dependency: {tool}")
        source = verify_source(args.driver_source, args.driver_archive, args.catalog)
        dtb = out / "input.dtb"
        result = subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(dtb), str(args.dts)],
                                capture_output=True, text=True, timeout=120)
        (out / "dtc-local.log").write_text(result.stderr)
        if result.returncode:
            raise ValueError(f"DTS parse failed (exit {result.returncode}); see dtc-local.log")
        tree = Tree(dtb)
        if args.host not in tree.props:
            raise ValueError("requested UFS host path not present")
        nodes, edges, issues = inventory(tree, args.host)
        report = {"schema_version": 1, "result": "self-checked",
                  "inventory_status": "incomplete" if issues else "complete",
                  "driver_readiness": "BLOCKED", "device_access": False,
                  "input": {"dts_name": args.dts.name, "dts_sha256": sha(args.dts),
                            "driver_source_name": args.driver_source.name},
                  "tools": {"dtc": run(["dtc", "--version"]),
                            "fdtget": run(["fdtget", "--version"])},
                  "driver_source": source, "host": args.host, "nodes": nodes,
                  "references": edges, "issues": issues,
                  "units": {"reg_size": "bytes", "reg_address": "parent bus address",
                            "freq-table-hz": "Hz (Android table, not UEFI clock state)",
                            "*-microamp": "microampere", "*-microvolt / *-uV": "microvolt",
                            "other_cells": "binding-specific; raw, not inferred"},
                  "blockers": ["Catalog ABI is iPadOS 17, target is iOS 16 / XNU 8796; no ABI qualification",
                               "No nuwa UEFI clocks/PHY/power/reset or queue ownership handoff evidence",
                               "No DMA/SMMU coherency/ownership qualification; requires Deep review",
                               "No nuwa root layout qualification; stage5 APFS/UUID intentionally unchanged"],
                  "manual_mapping": "docs/nuwa-ufs-input-audit-20261110.md (not automatically inferred)"}
        (out / "resources.json").write_text(json.dumps(report, indent=2) + "\n")
        md = ["# UFS resource inventory (self-checked)", "", "Driver readiness: BLOCKED.", "",
              "| Node | Property | Parsed value (raw cells decimal) |", "|---|---|---|"]
        for path, item in nodes.items():
            for prop, value in item["properties"].items():
                md.append(f"| `{path}` | `{prop}` | `{json.dumps(value)}` |")
        md.extend(["", "## References", "", "| Source | Property | Target | Status |", "|---|---|---|---|"])
        for edge in edges:
            md.append(f"| `{edge['from']}` | `{edge['property']}` | `{edge['to']}` | {edge['status']} |")
        md.extend(["", "## Input issues"] + (issues or ["None in supported resource reference schema."]))
        md.extend(["", "## Independent readiness blockers"] + report["blockers"])
        (out / "resources.md").write_text("\n".join(md) + "\n")
        print(json.dumps({"inventory_status": report["inventory_status"], "nodes": len(nodes),
                          "references": len(edges), "issues": len(issues), "driver_readiness": "BLOCKED"}))
        return 2 if issues else 0
    except (ValueError, OSError, KeyError, StopIteration, subprocess.SubprocessError, tarfile.TarError) as error:
        (out / "error.json").write_text(json.dumps({"result": "self-checked", "status": "error",
                                                   "driver_readiness": "BLOCKED", "error": str(error)}, indent=2) + "\n")
        print(str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
