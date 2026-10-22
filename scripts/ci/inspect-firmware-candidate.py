"""Inspect downloaded R-004 artifacts in memory; never rewrite binary images."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import struct
import uuid

ROOT = Path(__file__).resolve().parents[2]
MODULES = {
    "9b665204-a133-47a2-9396-9e2b370a4e25": ("UniXNU", 10, 9),
    "29b950cf-586d-49ea-9d71-f88645ccdaf6": ("UniXNUDxe", 11, 7),
    "1b64af87-8415-4b57-9b16-680d70913b9f": ("DarwinBoot", 11, 7),
    "5c0e4b7a-31d2-4e8f-9a66-0b1f7d2c8e43": ("ShengBootMemoryDxe", 11, 7),
}
LZMA_GUID = "ee4e5898-3914-4259-9d6e-dc7bd79403cf"
VARIABLE_GUIDS = {"6441f818-6362-4e44-b570-7dba31dd2453", "1e5668e2-8481-11d4-bcf1-0080c73c8881"}
LOADER_GUID = "0f0a492e-5a6a-49f6-a1bf-743c87ab1cfe"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def align(n, to):
    return (n + to - 1) & ~(to - 1)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pe(data):
    need(len(data) >= 64 and data[:2] == b"MZ", "Expected DOS/PE image")
    at = struct.unpack_from("<I", data, 60)[0]
    need(at + 24 + 70 <= len(data) and data[at:at + 4] == b"PE\0\0", "Invalid PE header")
    machine, sections = struct.unpack_from("<HH", data, at + 4)
    opt_size = struct.unpack_from("<H", data, at + 20)[0]
    need(machine == 0xaa64 and opt_size >= 112 and at + 24 + opt_size + sections * 40 <= len(data), "Invalid AARCH64 PE sections")
    opt = at + 24
    need(struct.unpack_from("<H", data, opt)[0] == 0x20b, "Expected PE32+")
    entry = struct.unpack_from("<I", data, opt + 16)[0]
    image_size = struct.unpack_from("<I", data, opt + 56)[0]
    subsystem = struct.unpack_from("<H", data, opt + 68)[0]
    need(0 < entry < image_size, "PE entry outside image")
    for index in range(sections):
        header = opt + opt_size + index * 40
        raw_size, raw_at = struct.unpack_from("<II", data, header + 16)
        need(raw_size == 0 or raw_at + raw_size <= len(data), "PE section outside file")
    return dict(machine=hex(machine), subsystem=subsystem, entry_rva=hex(entry), image_size=image_size,
                sections=sections, bytes=len(data), sha256=sha(data),
                loader_protocol_guid_present=uuid.UUID(LOADER_GUID).bytes_le in data,
                application_guid_present=uuid.UUID("9b665204-a133-47a2-9396-9e2b370a4e25").bytes_le in data)


def shim_copy_count(data, symbols):
    labels = {line.split()[-1]: int(line.split()[0], 16) for line in symbols.splitlines() if len(line.split()) == 3}
    start, end = labels["_Start"], labels["_CopyLoop"]
    need(0 <= start < end <= len(data) and (end - start) % 4 == 0, "Invalid shim instruction bounds")
    values = []
    for at in range(start, end, 4):
        word = struct.unpack_from("<I", data, at)[0]
        if word & 0xff80001f == 0xd2800006:  # MOVZ X6, immediate (assembler can lower ldr =constant)
            values.append(((word >> 5) & 0xffff) << (((word >> 21) & 3) * 16))
        elif word & 0xff00001f == 0x58000006:  # LDR X6, PC-relative literal
            imm = (word >> 5) & 0x7ffff
            target = at + (imm - (1 << 19) if imm & (1 << 18) else imm) * 4
            need(0 <= target <= len(data) - 8, "Shim literal outside image")
            values.append(struct.unpack_from("<Q", data, target)[0])
    need(len(values) == 1, "Unrecognized/ambiguous shim copy-count load")
    return values[0]


def depex(data):
    at, tokens = 0, []
    ops = {0: "BEFORE", 1: "AFTER", 2: "PUSH", 3: "AND", 4: "OR", 5: "NOT", 6: "TRUE", 7: "FALSE", 8: "END", 9: "SOR"}
    while at < len(data):
        opcode = data[at]
        at += 1
        need(opcode in ops, "Unknown DEPEX opcode")
        token = dict(op=ops[opcode])
        if opcode in (0, 1, 2):
            need(at + 16 <= len(data), "Truncated DEPEX GUID")
            token["guid"] = str(uuid.UUID(bytes_le=data[at:at + 16]))
            at += 16
        tokens.append(token)
        if opcode == 8:
            need(at == len(data), "Unexpected trailing DEPEX bytes")
            break
    need(tokens and tokens[-1]["op"] == "END", "Missing DEPEX terminator")
    return tokens


class Firmware:
    def __init__(self):
        self.volumes = []
        self.files = []
        self.guided = []

    def volume(self, data, label, depth=0):
        need(depth < 12 and len(data) >= 56 and data[40:44] == b"_FVH", "Invalid FV header")
        size = struct.unpack_from("<Q", data, 32)[0]
        header_len = struct.unpack_from("<H", data, 48)[0]
        need(56 <= header_len <= size <= len(data) and header_len % 2 == 0, "Invalid FV bounds")
        need(sum(struct.unpack_from("<" + "H" * (header_len // 2), data)) % 65536 == 0, "FV header checksum mismatch")
        self.volumes.append(dict(label=label, bytes=size, header_bytes=header_len, sha256=sha(data[:size])))
        at = align(header_len, 8)
        while at + 24 <= size:
            header = data[at:at + 24]
            if header in (b"\xff" * 24, b"\0" * 24):
                break
            guid = str(uuid.UUID(bytes_le=header[:16]))
            kind, attributes = header[18:20]
            file_size, hsize = int.from_bytes(header[20:23], "little"), 24
            if attributes & 1:
                need(at + 32 <= size, "Truncated extended FFS header")
                file_size, hsize = struct.unpack_from("<Q", data, at + 24)[0], 32
            need(hsize <= file_size <= size - at, "Invalid FFS length")
            # Header checksum excludes file checksum and state.
            need((sum(data[at:at + hsize]) - data[at + 17] - data[at + 23]) % 256 == 0, "FFS header checksum mismatch")
            body = data[at + hsize:at + file_size]
            if attributes & 0x40:
                need((sum(body) + data[at + 17]) % 256 == 0, "FFS body checksum mismatch")
            info = dict(guid=guid, type=kind, bytes=file_size, volume=label, offset=at, sections=[])
            self.files.append(info)
            if kind not in (1, 0xf0):  # raw and padding files are not section streams
                self.sections(body, info, depth + 1)
            at = align(at + file_size, 8)

    def sections(self, data, owner, depth):
        need(depth < 12, "Excessive section nesting")
        at = 0
        while at + 4 <= len(data):
            size, kind, hsize = int.from_bytes(data[at:at + 3], "little"), data[at + 3], 4
            if size == 0xffffff:
                need(at + 8 <= len(data), "Truncated extended section")
                size, hsize = struct.unpack_from("<I", data, at + 4)[0], 8
            need(hsize <= size <= len(data) - at, "Invalid section bounds")
            section = data[at:at + size]
            body = section[hsize:]
            detail = dict(type=hex(kind), bytes=size)
            owner["sections"].append(detail)
            if kind == 0x10 and owner["guid"] in MODULES:
                detail["pe"] = pe(body)
            elif kind == 0x13 and owner["guid"] in MODULES:
                detail["depex"] = depex(body)
            elif kind == 0x17:
                self.volume(body, owner["volume"] + "/" + owner["guid"] + "/FV", depth + 1)
            elif kind == 2:
                need(len(body) >= 20, "Truncated GUID-defined section")
                guid = str(uuid.UUID(bytes_le=body[:16]))
                offset, attributes = struct.unpack_from("<HH", body, 16)
                need(hsize + 20 <= offset <= size, "Invalid GUID section data offset")
                item = dict(guid=guid, attributes=attributes, encoded_bytes=size - offset)
                if guid == LZMA_GUID:
                    decoded = lzma.decompress(section[offset:], format=lzma.FORMAT_ALONE)
                    item.update(decoded_bytes=len(decoded), decoded_sha256=sha(decoded))
                    self.sections(decoded, owner, depth + 1)
                else:
                    item["decoded"] = False
                self.guided.append(item)
            elif kind == 1:
                # Target FDF uses the LZMA GUID; no unproven Tiano decoder fallback.
                need(len(body) >= 5, "Truncated compression section")
                if body[4] == 0:
                    self.sections(body[5:], owner, depth + 1)
                else:
                    detail["compression_uninspected"] = body[4]
            at = align(at + size, 4)


def inspect(artifact):
    artifact = artifact.resolve()
    inventory = json.loads((artifact / "inventory.json").read_text())
    for item in inventory:
        path = (artifact / item["path"]).resolve()
        need(path.is_relative_to(artifact), "Unsafe inventory path")
        need(path.stat().st_size == item["bytes"] and sha(path.read_bytes()) == item["sha256"], "Artifact hash mismatch: " + item["path"])
    result = json.loads((artifact / "result.json").read_text())
    settings = json.loads((artifact / "build-settings.json").read_text())
    fd = artifact / "build/FV/SILICIUM_UEFI.fd"
    data = fd.read_bytes()
    need(len(data) == settings["fd_size"] == result["fd_bytes"] and sha(data) == result["fd_sha256"], "FD does not match runner")
    fv = Firmware()
    fv.volume(data, "FD/FVMAIN_COMPACT")
    modules = []
    for guid, (name, subsystem, kind) in MODULES.items():
        matches = [item for item in fv.files if item["guid"] == guid]
        need(len(matches) == 1, name + " absent or duplicated inside actual FD")
        item = matches[0]
        need(item["type"] == kind, name + " wrong FFS type")
        images = [s["pe"] for s in item["sections"] if "pe" in s]
        need(len(images) == 1 and images[0]["subsystem"] == subsystem, name + " missing/wrong PE subsystem")
        if name in ("UniXNU", "DarwinBoot"):
            need(images[0]["loader_protocol_guid_present"], name + " loader protocol GUID absent from image")
        if name == "UniXNUDxe":
            need(images[0]["application_guid_present"], "Registrar application GUID absent from image")
        deps = [s["depex"] for s in item["sections"] if "depex" in s]
        if name == "UniXNUDxe":
            need(len(deps) == 1 and [x["op"] for x in deps[0]] == ["PUSH", "PUSH", "AND", "END"]
                 and {x["guid"] for x in deps[0] if "guid" in x} == VARIABLE_GUIDS, "Registrar DEPEX mismatch")
        if name == "ShengBootMemoryDxe":
            need(len(deps) == 1 and [x["op"] for x in deps[0]] == ["TRUE", "END"], "Initrd publisher DEPEX mismatch")
        outputs = []
        for path in artifact.rglob(name + ".efi"):
            parsed = pe(path.read_bytes())
            need(parsed["subsystem"] == subsystem, name + " standalone EFI subsystem mismatch")
            outputs.append(dict(path=path.relative_to(artifact).as_posix(), **parsed))
        need(bool(outputs), name + " standalone EFI missing")
        modules.append(dict(name=name, guid=guid, ffs=item, standalone=outputs,
                            embedded_matches_standalone=any(o["sha256"] == images[0]["sha256"] for o in outputs)))
    app = next(m for m in modules if m["name"] == "UniXNU")
    registrar = next(m for m in modules if m["name"] == "UniXNUDxe")
    need(app["ffs"]["volume"] == registrar["ffs"]["volume"], "Registrar/application in different FVs")
    shim = (artifact / "shim/shim.bin").read_bytes()
    recorded = json.loads((artifact / "shim.json").read_text())
    need(sha(shim) == recorded["sha256"] and shim[56:60] == b"ARM\x64", "Shim hash/magic mismatch")
    offset, image_size = struct.unpack_from("<QQ", shim, 8)
    need(offset == int(settings["fd_base"], 0) and image_size == len(shim) + len(data), "Shim header length/base mismatch")
    symbols = (artifact / "shim/symbols.txt").read_text()
    payload = next(int(line.split()[0], 16) for line in symbols.splitlines() if line.endswith(" _Payload"))
    need(payload == len(shim), "Shim literal pool/padding separates payload")
    copy_count = shim_copy_count(shim, symbols)
    need(copy_count == len(data), "Shim copy count is not FD size")
    need(not list(artifact.rglob("*.img")), "Out-of-scope .img artifact")
    return dict(result="downloaded EFI/FD/BootShim static inspection passed", inventory_files=len(inventory),
                fd=dict(bytes=len(data), sha256=sha(data)), shim=dict(bytes=len(shim), image_size=image_size,
                sha256=sha(shim), payload_offset=payload, copy_count=copy_count), volumes=fv.volumes, compression=fv.guided,
                modules=modules, device_executed=False, unverified=["DXE dispatch and protocol installation",
                "initrd mapping/reservation and FAT mount", "UEFI memory map and XNU window", "XNU and iOS execution"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    need(output.is_relative_to(ROOT) and output.suffix == ".json", "Evidence output must be repo-local JSON")
    report = inspect(args.artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(result=report["result"], fd=report["fd"], shim=report["shim"], modules=[m["name"] for m in report["modules"]])))


if __name__ == "__main__":
    main()
