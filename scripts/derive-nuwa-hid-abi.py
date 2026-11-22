#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Patent
"""Generate and check the 20H392 IOHIDDevice stand-in's private ABI."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

SCRIPTS = Path(__file__).resolve().parent
FAMILY = "com.apple.iokit.IOHIDFamily"
EVENT = "com.apple.iokit.IOHIDEventDriver"
SLOTS, BASE, SIZE = 207, 168, 208
SLIDE = -0x1000000
VTABLE = 0xfffffff006cbe2c0
META = 0xfffffff007a128e0
C2, D2 = 0xfffffff005726b9c, 0xfffffff005726bbc
HID_INIT = 0xfffffff00572cd2c
TABLE = "__ZTV14NuwaHidStandin"
METATABLE = "__ZTVN14NuwaHidStandin9MetaClassE"
INIT = "__GLOBAL__sub_I_NuwaHidStandin.cpp"
OWNED = {0, 1, 7, 14, 21, 111, 180}
CHANGED = {0, 1, 7, 12, 14, 21, 23, 76, 81, 82, 86, 87, 91, 92, 93, 101, 132, 140}
PREFIX = "__ZN11IOHIDDevice"
METANAME = PREFIX + "10gMetaClassE"
VTNAME = "__ZTV11IOHIDDevice"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require(condition, message):
    if not condition:
        raise SystemExit(f"nuwa HID ABI: {message}")


def reader(blob, image):
    from native_prelink import backed_offset
    return lambda a, n: blob[(p := backed_offset(image["segments"], a, n, len(blob))):p+n]


def names(blob, image):
    from native_prelink import exports
    return {n: a for a, ns in exports(blob, image).items() for n in ns}


def meta_init_table(image):
    return next(s for g in image.module["segments"] for s in g["sections"]
                if s["name"] == "__mod_init_func")


def derive(base, donor):
    display = load("derive-nuwa-display-abi")
    image = display.Image(base, donor, FAMILY)
    symbols = names(image.blob, image.image)
    read = reader(image.blob, image.image)
    parent = struct.unpack(f"<{BASE}Q", read(symbols["__ZTV9IOService"] + 16, 8*BASE))
    data, contents = image.segments["__DATA_CONST"]
    text, code = image.segments["__TEXT_EXEC"]
    pure = symbols["___cxa_pure_virtual"]
    candidates = []
    for offset in range(0, len(contents) - (SLOTS + 5)*8, 8):
        if contents[offset:offset+16] != bytes(16):
            continue
        slots = struct.unpack_from(f"<{SLOTS}Q", contents, offset+16)
        if (contents[offset+(SLOTS+2)*8:offset+(SLOTS+5)*8] == bytes(24)
                and {i for i, (a, b) in enumerate(zip(parent, slots)) if a != b} == CHANGED
                and [i for i, a in enumerate(slots) if a == pure] == [180]
                and all(text <= a < text+len(code) for i, a in enumerate(slots)
                        if (i in CHANGED or i >= BASE) and i != 180)):
            candidates.append((data+offset, slots))
    require(len(candidates) == 1 and candidates[0][0] == VTABLE,
            "cannot uniquely identify the original 207-slot abstract vtable")
    _, slots = candidates[0]
    require(slots[7] == 0xfffffff005726bc8 and slots[86] == 0xfffffff005726f90,
            "getMetaClass/start slot moved")
    for a, raw, why in [
        (C2, "fd7bbfa9 fd030091 c2d60094 c8ac0090 08410b91 080000f9 fd7bc1a8 c0035fd6 bfd60014",
         "protected C2 vptr store and D2 tail call"),
        (slots[7], "60170190 00802391 c0035fd6", "independent getMetaClass pointer"),
        (HID_INIT+0x38, "201701d0 00802391 01b8fff0 21503191 62ac00d0 422447f9 031a8052 5bbd0094",
         "initializer constructs named IOHIDDevice, parent IOService, size 0xd0"),
        (0xfffffff00572703c, "680240f9 08bd41f9 e00313aa 00013fd6", "start calls getWorkLoop"),
        (0xfffffff0057271a8, "680240f9 08d142f9 e1630091 e00313aa 00013fd6 a02d0035 e00f40f9 602d00b4",
         "start calls slot 180 with descriptor out pointer and checks status"),
    ]:
        expected = bytes.fromhex(raw)
        require(image.read(a, len(expected)) == expected, f"{a:#x}: {why}")
    display.check_string(image, "4e2fc54", "IOHIDDevice")
    require(image.qword(meta_init_table(image)["va"]+6*8) == HID_INIT
            and image.read(META, 8) == bytes(8), "family initializer or metaclass storage")
    for site, n in native_imports().items():
        require(image.qword(site) == symbols[n], f"donor import {n}")
    return image, slots


def native_imports():
    return {0xfffffff006cbae48: "__ZN9IOService10gMetaClassE",
            0xfffffff006cbae98: "__ZN9IOServiceC2EPK11OSMetaClass",
            0xfffffff006cbaea0: "__ZN9IOServiceD2Ev"}


def header():
    # Base overrides follow the pinned UniXNU iOS17 HID recipe (same license).
    # Opaque appended entries are never called through these declarations.
    h = """// Generated from the pinned 20H392 donor; do not edit.
#pragma once
#include <IOKit/IOService.h>
#include <IOKit/IOMemoryDescriptor.h>
static_assert(sizeof(IOService) == 136, "20H392 IOService size");
class IOHIDDevice : public IOService {
    OSDeclareAbstractStructors(IOHIDDevice)
    uint8_t originalPrivate[72];
public:
    using IOService::setProperty;
    IOReturn Dispatch(IORPC) override;
    void free() override;
    bool init(OSDictionary *properties = nullptr) override;
    bool setProperty(const OSSymbol *, OSObject *) override;
    bool willTerminate(IOService *, IOOptionBits) override;
    IOReturn configureReport(IOReportChannelList *, IOReportConfigureAction, void *, void *) override;
    IOReturn updateReport(IOReportChannelList *, IOReportUpdateAction, void *, void *) override;
    bool start(IOService *) override;
    void stop(IOService *) override;
    bool handleOpen(IOService *, IOOptionBits, void *) override;
    void handleClose(IOService *, IOOptionBits) override;
    bool handleIsOpen(const IOService *) const override;
    bool matchPropertyTable(OSDictionary *, SInt32 *) override;
    IOReturn message(UInt32, IOService *, void *) override;
    IOReturn newUserClient(task_t, void *, UInt32, OSDictionary *, IOUserClient **) override;
"""
    for slot in range(BASE, SLOTS):
        h += ("    virtual IOReturn newReportDescriptor(IOMemoryDescriptor **) const = 0;\n"
              if slot == 180 else f'    virtual __attribute__((deprecated("ABI only"))) void opaque{slot}();\n')
    return h + '};\nstatic_assert(sizeof(IOHIDDevice) == 208, "20H392 IOHIDDevice size");\n'


def compile_archive(base, donor, cpo, out):
    image, slots = derive(base, donor)
    verify = load("verify-nuwa-display-host-abi")
    out.mkdir()
    (out/"OriginalHidDeviceABI.h").write_text(header())
    source = out/"NuwaHidStandin.cpp"
    source.write_text((SCRIPTS.parent/"package/NuwaHidStandin.cpp").read_text() +
                      f'\n__asm__(".globl {INIT}");\n')
    obj, late = out/"NuwaHidStandin.o", out/"NuwaHidStandin.manual.o"
    recipe = json.loads(cpo.read_text().strip().rstrip(","))
    argv = verify.compile_args(recipe, source, obj, out)
    subprocess.run(argv, cwd=recipe["directory"], check=True)
    raw = obj.read_bytes()
    sections, symbols = verify.object_layout(base, raw)
    (_, _, ordinal, _, value), = (r for r in symbols if r[0] == TABLE)
    sec = sections[ordinal-1]
    offset = value-sec["va"]
    end = offset+(SLOTS+2)*8
    require(any(n == METATABLE and s == ordinal and a-value == 0x690
                for n, _, s, _, a in symbols) and
            raw[sec["fileoff"]+end:sec["fileoff"]+end+8] == bytes(8),
            "compiled vtable extent/alignment padding")
    require(raw[sec["fileoff"]+offset:sec["fileoff"]+offset+16] == bytes(16), "RTTI header")
    relocs = {}
    for s, off, kind, name in verify.relocations(raw, sections, symbols):
        require(s is not sec or off != end, "unexpected virtual slot in vtable alignment padding")
        if s is sec and offset+16 <= off < offset+(2+SLOTS)*8:
            require(kind == 0x0e and off not in relocs and
                    struct.unpack_from("<Q", raw, sec["fileoff"]+off)[0] == 0, "invalid vtable relocation")
            relocs[off] = name
    require(len(relocs) == SLOTS, "compiled slot count")
    compiled = [relocs[offset+16+8*i] for i in range(SLOTS)]
    require({i for i, n in enumerate(compiled)
             if n.startswith(("__ZN14NuwaHidStandin", "__ZNK14NuwaHidStandin"))} == OWNED,
            "compiled stand-in override set")
    functions = {PREFIX+"C2EPK11OSMetaClass": C2, PREFIX+"D2Ev": D2}
    donor_symbols = names(image.blob, image.image)
    for i, n in enumerate(compiled):
        if i in OWNED:
            continue
        if i in CHANGED or i >= BASE:
            require("11IOHIDDevice" in n, f"slot {i} needs an IOHIDDevice declaration")
            require(functions.setdefault(n, slots[i]) == slots[i], f"ambiguous import {n}")
        else:
            require(donor_symbols.get(n) == slots[i], f"slot {i}: inherited IOService method {n}")
    data = {METANAME: META, VTNAME: VTABLE}
    undefined = {n for n, k, *_ in symbols if k == 1 and "11IOHIDDevice" in n}
    require(undefined == (functions.keys() | data.keys()), "unexpected or missing IOHIDDevice imports")
    def assemble(file, text):
        asm = out/(file+".S")
        asm.write_text(text)
        output = asm.with_suffix(".o")
        subprocess.run([argv[0], next(x for x in argv if x.startswith("--target=")),
                        "-c", asm, "-o", output], check=True)
        return output
    veneers = assemble("hid-bindings", ".text\n.p2align 2\n" + "".join(
        f".globl {n}\n{n}:\n    b {n}.original\n" for n in sorted(functions)))
    absolute = assemble("hid-addresses", "".join(
        f".globl {n}\n.set {n}, {a+SLIDE:#x}\n" for n, a in sorted(
            (data | {n+".original": a for n, a in functions.items()}).items())))
    auto, = verify.constructor_sections(raw, sections)
    require(auto["size"] == 8 and [(o, k, n) for s, o, k, n in
            verify.relocations(raw, sections, symbols) if s is auto] == [(0, 0x0e, INIT)],
            "initializer is not one pointer to the manual entry")
    subprocess.run(["llvm-objcopy", "--remove-section=__DATA,__mod_init_func", obj, late], check=True)
    manual = late.read_bytes()
    sec2, syms2 = verify.object_layout(base, manual)
    def text(blob, sections):
        s, = (s for s in sections if s["name"] == "__text")
        return blob[s["fileoff"]:s["fileoff"]+s["size"]]
    require(not verify.constructor_sections(manual, sec2) and any(
            n == INIT and k == 0x0f for n, k, *_ in syms2) and text(raw, sections) == text(manual, sec2),
            "automatic initializer survived or code changed")
    abi = dict(slots=slots, compiled=compiled, functions=functions, data=data,
               imports=sorted(n for n, k, *_ in symbols if k == 1),
               family_init=meta_init_table(image)["va"]+6*8, family_load=image.entry["_PrelinkExecutableLoadAddr"])
    (out/"hid-abi.json").write_text(json.dumps(abi, indent=2)+"\n")
    return [late, veneers, absolute]


def linked_symbols(blob, image):
    at, = (a for c, a, _ in image["commands"] if c == 2)
    sy, count, st, size = struct.unpack_from("<4I", blob, at+8)
    strings = blob[st:st+size]
    return [(strings[ix:strings.index(0, ix)].decode(), kind, sec, va)
            for ix, kind, sec, _, va in struct.iter_unpack("<IBBHQ", blob[sy:sy+count*16])
            if not kind & 0xe0]


def branch_target(pc, instruction):
    imm = instruction & 0x3ffffff
    return pc + ((imm ^ 0x2000000)-0x2000000)*4


def audit_linked(blob, abi):
    from native_prelink import macho
    im = macho(blob)
    read = reader(blob, im)
    rows = linked_symbols(blob, im)
    defined = {n: a for n, k, _, a in rows if k & 0x0e}
    imports = {n for n, k, _, _ in rows if k & 0x0f == 1}
    require(not imports.intersection(abi["imports"]) and set(abi["imports"]) <= defined.keys(),
            "one or more stand-in imports are unresolved")
    private = {n for n in defined if n.startswith((PREFIX, "__ZNK11IOHIDDevice", VTNAME))}
    require(private == (abi["functions"].keys() | abi["data"].keys() |
                       {n+".original" for n in abi["functions"]}), "linked original binding inventory")
    for n, a in abi["functions"].items():
        veneer = defined[n]
        word, = struct.unpack("<I", read(veneer, 4))
        require(word >> 26 == 5 and branch_target(veneer, word) == a+SLIDE and
                defined[n+".original"] == a+SLIDE, f"linked veneer {n}")
    for n, a in abi["data"].items():
        require(defined[n] == a+SLIDE, f"linked original object {n}")
    table = defined[TABLE]
    actual = struct.unpack(f"<{SLOTS+2}Q", read(table, (SLOTS+2)*8))
    require(actual[:2] == (0, 0), "linked stand-in vtable header")
    for i, (a, n) in enumerate(zip(actual[2:], abi["compiled"], strict=True)):
        require(a == defined[n], f"linked stand-in vtable slot {i}: {n}")
    require(defined[METATABLE] == table+len(actual)*8+8 and
            read(table+len(actual)*8, 8) == bytes(8),
            "linked stand-in vtable extent/alignment padding")

    sections = [s for g in im["segments"] for s in g["sections"]]
    init = defined[INIT]
    for s in sections:
        flags, = struct.unpack_from("<I", blob, s["command_offset"]+64)
        if flags & 0xff in (0x9, 0xa):
            require(all(a != init for a, in struct.iter_unpack("<Q", read(s["va"], s["size"]))),
                    "stand-in initializer appears in automatic tables")
        elif flags & 0xff == 0x16:
            raise SystemExit("nuwa HID ABI: unexpected initializer-offset table")

    def calls(n, targets):
        start = defined[n]
        sec = next(s for label, k, s, _ in rows if label == n and k & 0x0e == 0x0e)
        ends = [a for _, k, o, a in rows if o == sec and a > start and k & 0x0e == 0x0e]
        size = min(ends)-start
        want = [defined[t] for t in targets]
        found = []
        for off, (word,) in enumerate(struct.iter_unpack("<I", read(start, size))):
            pc = start+off*4
            if word >> 26 in (5, 0x25):
                target = branch_target(pc, word)
                if target in want:
                    found.append((pc, target))
        require([target for _, target in found] == want, f"{n}: expected call order {targets}")
        return [pc for pc, _ in found]

    boot_calls = calls("_bsd_autoconf", ["_IOKitBSDInit", "_nuwa_hid_standin_probe",
                                       "_native_legacy_display_late_probe"])
    # The compiler calls HID on the zero-result path before testing the
    # separate display condition. Verify that the gate skips that call.
    branch, = struct.unpack("<I", read(boot_calls[0]+4, 4))
    require(branch & 0xff00001f == 0x35000000, "post-IOBSD success gate is not CBNZ w0")
    skip = (branch >> 5) & 0x7ffff
    require(boot_calls[0]+4 + ((skip ^ 0x40000)-0x40000)*4 > boot_calls[1],
            "post-IOBSD failure does not skip the probe")
    probe_calls = calls("_nuwa_hid_standin_probe", [
        "_PE_parse_boot_argn", "_OSKextLoadKextWithIdentifier",
        "__ZN6OSKext22loadKextWithIdentifierEPKcbbhhP7OSArray",
        "__ZN9IOService22waitForMatchingServiceEP12OSDictionaryy",
        "__ZN11OSMetaClass10preModLoadEPKc", INIT, "__ZN11OSMetaClass11postModLoadEPv",
        "__ZN14NuwaHidStandinC1Ev", "_native_hid_live_checkpoint"])
    # Client init/attach/start are virtual and their target slots are
    # independently checked against the complete linked vtable above.
    lifecycle = read(probe_calls[-2]+4, 64)
    for word in (0xf9405508, 0xf941b108, 0xf9415908):
        at = lifecycle.find(struct.pack("<I", word))
        require(at >= 0 and at % 4 == 0, "missing ordered init/attach/start slot load")
        lifecycle = lifecycle[at+4:]
    meta = defined["__ZN14NuwaHidStandin9MetaClassC2Ev"]
    adrp, ldr = struct.unpack("<II", read(meta+0x10, 8))
    require(adrp & 0x9f00001f == 0x90000002 and ldr & 0xffc003ff == 0xf9400042,
            "stand-in metaclass C2 x2 GOT load")
    page = load("derive-nuwa-display-abi").adrp_page(meta+0x10, adrp)
    got = page+((ldr >> 10) & 0xfff)*8
    require(struct.unpack("<Q", read(got, 8))[0] == META+SLIDE and
            struct.unpack("<Q", read(defined["__ZN14NuwaHidStandin10superClassE"], 8))[0] == META+SLIDE,
            "stand-in metaclass superclass pointer")
    return dict(standin_vtable=table, slots=SLOTS, imports=abi["imports"],
                post_iobsd_call_sites=boot_calls, probe_call_sites=probe_calls, superclass_got=got)


def audit_family(blob, abi, report):
    from native_prelink import macho, backed_offset, unserialize_xml
    im = macho(blob)
    read = reader(blob, im)
    symbols = names(blob, im)
    require(report["slide"] == SLIDE and FAMILY in report["components"] and
            EVENT in report["codeless_components"],
            "selected original IOHIDFamily or IOHIDEventDriver missing")
    info = next(s for s in im["segments"] if s["name"] == "__PRELINK_INFO")
    metadata = unserialize_xml(blob[info["fileoff"]:info["fileoff"]+info["filesize"]])
    entries = {e.get("CFBundleIdentifier"): e for e in metadata["_PrelinkInfoDictionary"]}
    require(FAMILY in entries and EVENT in entries and
            entries[FAMILY]["_PrelinkExecutableLoadAddr"] == abi["family_load"]+SLIDE and
            not entries[EVENT].get("_PrelinkExecutableLoadAddr"),
            "emitted HID executable/codeless metadata")
    resource = entries[FAMILY]["IOKitPersonalities"]["IOHIDResource"]
    keyboard = entries[EVENT]["IOKitPersonalities"]["HID Keyboard Driver"]
    require((resource["IOProviderClass"], resource["IOResourceMatch"]) == ("IOResources", "IOBSD") and
            (keyboard["IOProviderClass"], keyboard["IOClass"], keyboard["CFBundleIdentifier"]) ==
            ("IOHIDInterface", "IOHIDEventDriver", FAMILY) and
            {"DeviceUsagePage": 1, "DeviceUsage": 6} in keyboard["DeviceUsagePairs"],
            "emitted resource/keyboard matching contract")
    load_at = backed_offset(im["segments"], abi["family_load"]+SLIDE, 32, len(blob))
    family = macho(blob, load_at)
    init_table = next(s for g in family["segments"] for s in g["sections"]
                      if s["name"] == "__mod_init_func")
    site = abi["family_init"]+SLIDE
    require(init_table["va"]+6*8 == site and struct.unpack("<Q", read(site, 8))[0] == HID_INIT+SLIDE
            and read(META+SLIDE, 8) == bytes(8), "emitted original HID initializer/metaclass storage")
    original = struct.unpack(f"<{SLOTS}Q", read(VTABLE+SLIDE+16, SLOTS*8))
    parent = struct.unpack(f"<{BASE}Q", read(symbols["__ZTV9IOService"]+16, BASE*8))
    for i, (a, old) in enumerate(zip(original, abi["slots"], strict=True)):
        expected = (symbols["___cxa_pure_virtual"] if i == 180 else
                    parent[i] if i < BASE and i not in CHANGED else old+SLIDE)
        require(a == expected, f"emitted donor IOHIDDevice slot {i}")
    for site, n in native_imports().items():
        require(struct.unpack("<Q", read(site+SLIDE, 8))[0] == symbols[n], f"emitted donor import {n}")
