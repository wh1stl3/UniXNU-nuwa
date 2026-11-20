#!/usr/bin/env python3
"""Read-only bounded Capstone inventory; unknown dataflow is never accepted."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tomllib

import capstone
from capstone import arm64

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parents[1] / "UniXNU"
DONOR = BASE / "out/ipsw/20H392/kernelcache.decompressed"
NATIVE = ROOT / "out/nuwa-display-ignore-loh-02/HOST-ONLY-display-native.unstripped"
START, END = 0xfffffff005b8c054, 0xfffffff005b8c51c
SLOTS = {0xfffffff007a3d488, 0xfffffff007a3d490}
MASK = (1 << 64) - 1


def main():
    tool = BASE / "kits/XnuPrelink/native_prelink.py"
    if hashlib.sha256(tool.read_bytes()).hexdigest() != "a2da7ea8a4431f6c26418ecab9be718c0fbd2f0aa2334ba8d32c2270d2ac81dc":
        raise ValueError("native_prelink.py source hash mismatch")
    sys.path.insert(0, str(BASE / "kits/XnuPrelink"))
    from native_prelink import macho, backed_offset, plan, unserialize_xml
    donor, native = DONOR.read_bytes(), NATIVE.read_bytes()
    digest = lambda b: hashlib.sha256(b).hexdigest()
    if digest(donor) != "2ec297bac95bcba01046fd0148e97e7e5885c05a6c18827f39f534ba375c1221":
        raise ValueError("donor hash mismatch")
    if digest(native) != "c690783526424828e23aae3e279f0db0b0141bb60af21a98233c13162b9a7c1c":
        raise ValueError("display native hash mismatch")
    board = tomllib.loads((ROOT / "board.toml").read_text())
    roots = board["os_overrides"]["ios-16.7.16-20H392"]["kernel"]["prelink"]["roots"]
    roots = list(dict.fromkeys([*roots, "com.apple.iokit.IOMobileGraphicsFamily"]))
    report = plan(native, donor, roots, -0x1000000)
    parent = macho(donor)
    segments = parent["segments"]
    def read(va, size):
        p = backed_offset(segments, va, size, len(donor))
        return donor[p:p + size]
    info = next(s for s in segments if s["name"] == "__PRELINK_INFO")
    metadata = unserialize_xml(read(info["va"], info["filesize"]))
    entries = {e["CFBundleIdentifier"]: e for e in metadata["_PrelinkInfoDictionary"]}
    modules = {}
    for name in report["components"]:
        entry = entries[name]
        va = entry.get("_PrelinkExecutableLoadAddr")
        if va is not None:
            modules[name] = macho(donor, backed_offset(segments, va, 32, len(donor)))
    selected_modules = set(modules)
    unparsed = []
    for name, entry in entries.items():
        va = entry.get("_PrelinkExecutableLoadAddr")
        if va is not None and entry.get("_PrelinkExecutableSize") and name not in modules and entry.get("OSKernelResource") is not True:
            try:
                modules[name] = macho(donor, backed_offset(segments, va, 32, len(donor)))
            except ValueError as exc:
                unparsed.append(dict(module=name, va=hex(va), error=str(exc)))
    pool_digest = digest(read(START, END - START))
    if pool_digest != "12d22dca8e3a79e476ab128f73e28f630bf902d5189ed1d5317589930c0c8622":
        raise ValueError("literal pool hash mismatch")
    engine = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    engine.detail = True
    lite = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    lite.skipdata = True
    def decode(va, data):
        return next(engine.disasm(data[:4], va), None)
    def reg(ins, op):
        return ins.reg_name(op.reg)
    def hx(n):
        return hex(n & MASK)
    entries_of_interest = {0xfffffff005b8bc80, 0xfffffff005b8bd5c}
    pointer_stubs = {0xfffffff00667e7a0, 0xfffffff00667e824}
    entry_pointer_slots = {0xfffffff006f41448, 0xfffffff006f414a0}
    for entry in entries_of_interest:
        prologue = list(engine.disasm(read(entry, 16), entry))
        if len(prologue) != 4 or prologue[0].mnemonic != "stp" or prologue[1].mnemonic != "mov":
            raise ValueError("candidate function prologue changed")
        if not any(i.mnemonic == "fmov" and i.op_str == "w0, s0" for i in prologue):
            raise ValueError("candidate function no longer overwrites w0 on entry")
    for stub, slot, entry in ((0xfffffff00667e7a0, 0xfffffff006f41448, 0xfffffff005b8bc80),
                              (0xfffffff00667e824, 0xfffffff006f414a0, 0xfffffff005b8bd5c)):
        instructions = list(engine.disasm(read(stub, 12), stub))
        if (len(instructions) != 3 or [i.mnemonic for i in instructions] != ["adrp", "ldr", "br"]
                or struct.unpack("<Q", read(slot, 8))[0] != entry):
            raise ValueError("candidate pointer stub or initial target changed")
    def caller_use(blob, offset, pc):
        """Follow caller paths until the returned x0 is used or killed."""
        base = pc-offset
        pending = [(pc+4, 0)]
        visited, outcomes = set(), []
        while pending:
            address, step = pending.pop()
            if address in visited:
                continue
            visited.add(address)
            if step >= 256:
                outcomes.append({"classification": "unresolved-window", "at": hx(address)})
                continue
            at = address-base
            n = decode(address, blob[at:at+4]) if 0 <= at <= len(blob)-4 else None
            if n is None:
                outcomes.append({"classification": "unresolved-decode", "at": hx(address)})
                continue
            reads, writes = n.regs_access()
            r = {n.reg_name(x) for x in reads}
            w = {n.reg_name(x) for x in writes}
            if n.mnemonic in ("blr", "br") and n.operands and reg(n, n.operands[0]) in ("x0", "w0"):
                kind = "control-flow"
            elif n.mnemonic in ("bl", "blr"):
                dst = n.operands[0].imm & MASK if n.mnemonic == "bl" and n.operands[0].type == arm64.ARM64_OP_IMM else None
                kind = "next-known-callee-overwrites-x0" if dst in pointer_stubs | entries_of_interest else "next-call-argument-unresolved"
            elif (n.mnemonic == "lsl" and len(n.operands) >= 2
                  and n.operands[0].type == arm64.ARM64_OP_REG
                  and n.operands[1].type == arm64.ARM64_OP_REG
                  and reg(n, n.operands[0]) in ("x0", "w0")
                  and reg(n, n.operands[1]) not in ("x0", "w0")):
                # Capstone 5.0.7 reports the LSL destination as read+write.
                kind = "overwritten"
            elif r.intersection({"x0", "w0"}):
                if n.mnemonic.startswith("st"):
                    kind = "memory-store-or-address-unresolved"
                elif n.mnemonic.startswith(("ldr", "ldp", "ld1")):
                    kind = "data-read-or-other-use"
                else:
                    kind = "other-use-unresolved"
            elif w.intersection({"x0", "w0"}):
                kind = "overwritten"
            elif n.mnemonic == "ret":
                kind = "returned-to-caller"
            else:
                if n.mnemonic == "b" or n.mnemonic.startswith(("b.", "cb", "tb")):
                    targets = [o.imm & MASK for o in n.operands if o.type == arm64.ARM64_OP_IMM]
                    if targets:
                        pending.append((targets[-1], step+1))
                    else:
                        outcomes.append({"classification": "branch-target-unresolved", "at": hx(address)})
                    if n.mnemonic == "b":
                        continue
                pending.append((address+4, step+1))
                continue
            outcomes.append({"classification": kind, "at": hx(n.address),
                             "instruction": n.mnemonic + " " + n.op_str})
        return outcomes
    def trace_address(blob, offset, ins):
        """Trace to clobber, return, unconditional branch or 256 instructions."""
        uses = []
        base = ins.address - offset
        pending = [(ins.address + 4, frozenset([reg(ins, ins.operands[0])]), 0)]
        seen = set()
        terminal = set()
        while pending:
            pc, current, steps = pending.pop()
            tracked = set(current)
            state = (pc, current)
            if state in seen:
                continue
            seen.add(state)
            if steps >= 256:
                terminal.add("unresolved-window")
                continue
            pos = pc - base
            n = decode(pc, blob[pos:pos+4]) if 0 <= pos <= len(blob)-4 else None
            if n is None:
                terminal.add("undecodable-or-outside-segment")
                continue
            ops = n.operands
            reads, writes = n.regs_access()
            read_names = {n.reg_name(r) for r in reads}
            written = {n.reg_name(r) for r in writes}
            memops = [o.mem for o in ops if o.type == arm64.ARM64_OP_MEM]
            based = any(n.reg_name(m.base) in tracked or n.reg_name(m.index) in tracked
                        for m in memops)
            if n.mnemonic in ("br", "blr") and ops and reg(n, ops[0]) in tracked:
                return uses + [hx(n.address) + " " + n.mnemonic], "control-flow-target"
            if n.mnemonic in ("bl", "blr") and tracked.intersection({f"x{k}" for k in range(8)}):
                args = sorted(tracked.intersection({f"x{k}" for k in range(8)}))
                return uses + [hx(n.address) + " " + n.mnemonic + " " + n.op_str +
                               " arguments=" + ",".join(args)], "unresolved-call-callee"
            if n.mnemonic.startswith("st") and read_names.intersection(tracked) and not based:
                return uses + [hx(n.address) + " " + n.mnemonic], "stored-address"
            if based:
                if n.mnemonic.startswith(("ldr", "ldp", "ld1")):
                    uses.append(hx(n.address) + " " + n.mnemonic + " " + n.op_str)
                    if n.writeback:
                        written.difference_update(n.reg_name(m.base) for m in memops)
                else:
                    return uses + [hx(n.address) + " " + n.mnemonic], "unresolved-memory-use"
            if n.mnemonic == "add" and len(ops) >= 3 and ops[1].type == arm64.ARM64_OP_REG and reg(n, ops[1]) in tracked:
                tracked.add(reg(n, ops[0]))
                uses.append(hx(n.address) + " " + n.mnemonic + " " + n.op_str)
                written.discard(reg(n, ops[0]))
            elif read_names.intersection(tracked) and not based:
                return uses + [hx(n.address) + " " + n.mnemonic], "unresolved-register-use"
            tracked.difference_update(written)
            if n.mnemonic == "ret" and "x0" in tracked:
                return uses + [hx(n.address) + " ret x0"], "return-address-escape"
            if not tracked or n.mnemonic == "ret":
                terminal.add("terminated")
                continue
            if n.mnemonic == "b":
                uses.append(hx(n.address) + " b " + n.op_str + " live=" + ",".join(sorted(tracked)))
                terminal.add("unresolved-unconditional-branch")
                continue
            if n.mnemonic.startswith(("b.", "cb", "tb")):
                targets = [o.imm & MASK for o in ops if o.type == arm64.ARM64_OP_IMM]
                if not targets:
                    terminal.add("unresolved-conditional-target")
                else:
                    pending.append((targets[-1], frozenset(tracked), steps + 1))
            pending.append((pc + 4, frozenset(tracked), steps + 1))
        unresolved = sorted(t for t in terminal if t != "terminated")
        return uses, ",".join(unresolved) if unresolved else (
            "data-read" if any(" ld" in u for u in uses) else "unresolved-no-data-read")
    a1, a2, pointers, coverage, page_limits = [], [], [], [], []
    direct_calls, indirect_calls, entry_pointers, tail_entries, pointer_uses = [], [], [], [], []
    images = {"kernel": parent, **modules}
    for name, image in images.items():
        for seg in image["segments"]:
            if not seg["filesize"]:
                continue
            if seg["name"] == "__TEXT_EXEC":
                coverage.append(dict(module=name, segment=seg["name"], va=hx(seg["va"]),
                                     size=seg["filesize"]))
                blob = read(seg["va"], seg["filesize"])
                for pc, size, mnemonic, _ in lite.disasm_lite(blob, seg["va"]):
                    if mnemonic in ("b", "bl", "blr"):
                        i = pc - seg["va"]
                        call = decode(pc, blob[i:i+4])
                        if call and mnemonic == "blr":
                            indirect_calls.append(dict(module=name, pc=hx(pc), instruction=call.mnemonic+" "+call.op_str))
                        elif call and call.operands and call.operands[0].type == arm64.ARM64_OP_IMM:
                            dst = call.operands[0].imm & MASK
                            if dst in entries_of_interest | pointer_stubs:
                                if mnemonic == "bl":
                                    direct_calls.append(dict(module=name, pc=hx(pc), target=hx(dst),
                                                             x0_use=caller_use(blob, i, pc)))
                                elif mnemonic == "b":
                                    tail_entries.append(dict(module=name, pc=hx(pc), target=hx(dst)))
                    if mnemonic not in ("adr", "adrp", "ldr"):
                        continue
                    i = pc - seg["va"]
                    ins = decode(pc, blob[i:i+4])
                    if ins is None or len(ins.operands) < 2 or ins.operands[1].type != arm64.ARM64_OP_IMM:
                        continue
                    target = ins.operands[1].imm & MASK
                    if mnemonic != "adrp":
                        if target in SLOTS:
                            a2.append(dict(module=name, pc=hx(pc), target=hx(target),
                                           instruction=ins.mnemonic+" "+ins.op_str,
                                           classification="direct-slot-address-or-read"))
                        if START <= target < END:
                            if START <= pc < END:
                                uses, classification = [], "candidate-self-reference-not-proven-code"
                            elif mnemonic == "ldr":
                                uses, classification = [], "literal-data-read"
                            else:
                                uses, classification = trace_address(blob, i, ins)
                            a1.append(dict(module=name, pc=hx(pc), target=hx(target),
                                           instruction=ins.mnemonic+" "+ins.op_str,
                                           uses=uses, classification=classification))
                        continue
                    if target not in (START & ~4095, min(SLOTS) & ~4095,
                                      min(entry_pointer_slots) & ~4095):
                        continue
                    base = reg(ins, ins.operands[0])
                    addresses = {base: target}
                    for j in range(1, 257):
                        n = decode(pc + j*4, blob[i+j*4:i+j*4+4])
                        if n is None:
                            break
                        ops = n.operands
                        address = None
                        new_address = None
                        if n.mnemonic == "add" and len(ops) >= 3 and ops[1].type == arm64.ARM64_OP_REG and reg(n, ops[1]) in addresses and ops[2].type == arm64.ARM64_OP_IMM:
                            address = (addresses[reg(n, ops[1])] + ops[2].imm) & MASK
                            new_address = (reg(n, ops[0]), address)
                        elif n.mnemonic in ("ldr", "str", "ldp", "stp", "prfm"):
                            mem = next((o.mem for o in ops if o.type == arm64.ARM64_OP_MEM), None)
                            if mem and n.reg_name(mem.base) in addresses and not mem.index:
                                address = (addresses[n.reg_name(mem.base)] + mem.disp) & MASK
                        if address is not None:
                            row = dict(module=name, pc=hx(n.address), adrp=hx(pc),
                                       target=hx(address), instruction=n.mnemonic+" "+n.op_str)
                            if START <= address < END:
                                a1.append({**row, "classification": "unresolved"})
                            if address in SLOTS or (n.mnemonic in ("ldp", "stp") and address + 8 in SLOTS):
                                a2.append({**row, "classification": "unresolved-value-source" if n.mnemonic.startswith("st") else "read-or-address"})
                            if address in entry_pointer_slots:
                                use = {**row, "following": [], "classification": "address-only-unresolved"}
                                if n.mnemonic == "ldr" and ops[0].type == arm64.ARM64_OP_REG:
                                    loaded = reg(n, ops[0])
                                    use["classification"] = "loaded-value-unresolved"
                                    for k in range(1, 33):
                                        follow = decode(n.address + k*4, blob[i+(j+k)*4:i+(j+k)*4+4])
                                        if follow is None:
                                            break
                                        reads, writes = follow.regs_access()
                                        rn = {follow.reg_name(x) for x in reads}
                                        wn = {follow.reg_name(x) for x in writes}
                                        if loaded in rn:
                                            use["following"].append(hx(follow.address) + " " + follow.mnemonic + " " + follow.op_str)
                                            use["classification"] = ("indirect-call" if follow.mnemonic == "blr" and follow.operands and reg(follow, follow.operands[0]) == loaded else "other-use-unresolved")
                                            break
                                        if loaded in wn or follow.mnemonic in ("b", "br", "ret", "bl", "blr") or follow.mnemonic.startswith(("b.", "cb", "tb")):
                                            break
                                pointer_uses.append(use)
                        reads, writes = n.regs_access()
                        for written in writes:
                            addresses.pop(n.reg_name(written), None)
                        if new_address:
                            addresses[new_address[0]] = new_address[1]
                        if n.mnemonic in ("ret", "br", "blr", "bl", "b") or not addresses:
                            if addresses and n.mnemonic != "ret" and target == (min(SLOTS) & ~4095):
                                page_limits.append(dict(module=name, adrp=hx(pc), at=hx(n.address),
                                                        instruction=n.mnemonic+" "+n.op_str))
                            break
                    else:
                        if target == (min(SLOTS) & ~4095):
                            page_limits.append(dict(module=name, adrp=hx(pc), at=hx(pc+1024),
                                                    instruction="256-instruction-limit"))
            elif seg["name"] in ("__TEXT", "__DATA", "__DATA_CONST", "__PRELINK_DATA",
                                  "__PLK_DATA_CONST", "__LASTDATA_CONST", "__KLDDATA",
                                  "__BOOTDATA"):
                coverage.append(dict(module=name, segment=seg["name"], va=hx(seg["va"]),
                                     size=seg["filesize"]))
                blob = read(seg["va"], seg["filesize"])
                for width, fmt in ((8, "<Q"), (4, "<I")):
                    for off in range(0, len(blob)-width+1, width):
                        value = struct.unpack_from(fmt, blob, off)[0]
                        if width == 8 and value in entries_of_interest:
                            entry_pointers.append(dict(module=name, segment=seg["name"],
                                                       site=hx(seg["va"]+off), target=hx(value)))
                        if START <= value < END or value in SLOTS:
                            pointers.append(dict(module=name, segment=seg["name"], site=hx(seg["va"]+off), width=width, target=hx(value)))
    libm = modules["com.apple.kec.Libm"]
    initial = []
    for slot in sorted(SLOTS):
        value = struct.unpack("<Q", read(slot, 8))[0]
        executable = any(s["name"] == "__TEXT_EXEC" and s["va"] <= value < s["va"] + s["filesize"] for s in libm["segments"])
        body = [i.mnemonic + " " + i.op_str for i in engine.disasm(read(value, 8), value)]
        initial.append(dict(slot=hx(slot), value=hx(value), in_libm_exec=executable,
                            outside_pool=not START <= value < END, function_entry="two-instruction return stub; entry metadata absent",
                            body=body))
    libm_entry = entries["com.apple.kec.Libm"]
    kmod_va = libm_entry["_PrelinkKmodInfo"]
    kmod_start, kmod_stop = struct.unpack_from("<QQ", read(kmod_va, 196), 180)
    init_sections = [dict(segment=s["name"], section=x["name"], va=hx(x["va"]), size=x["size"])
                     for s in libm["segments"] for x in s["sections"]
                     if x["name"] == "__mod_init_func"]
    result = dict(capstone_runtime=capstone.__version__, donor_sha256=digest(donor),
                  native_sha256=digest(native), pool_sha256=pool_digest, roots=roots,
                  modules=[dict(name=n, path=entries[n].get("_PrelinkBundlePath"),
                                va=hx(entries[n]["_PrelinkExecutableLoadAddr"]),
                                selected=n in selected_modules) for n in modules],
                  a1=a1, a2=a2, data_pointers=pointers, initial=initial,
                  scan_coverage=coverage, page_tracking_limits=page_limits,
                  unselected_executable_modules=sorted(set(modules) - selected_modules),
                  unparsed_modules=unparsed,
                  candidate_function_entries=[hx(x) for x in sorted(entries_of_interest)],
                  direct_calls_to_candidate_entries=direct_calls,
                  direct_tail_branches_to_candidate_entries=tail_entries,
                  raw_entry_pointer_candidates=entry_pointers,
                  entry_pointer_slot_uses=pointer_uses,
                  indirect_call_sites=indirect_calls,
                  libm_init_sections=init_sections, libm_kmod_info=hx(kmod_va),
                  libm_kmod_start=hx(kmod_start), libm_kmod_stop=hx(kmod_stop),
                  conclusion="NOT-QUALIFIED: unresolved address lifetimes and indirect slot writers")
    print(json.dumps(result, indent=2))
    return 2


if __name__ == "__main__":
    sys.exit(main())
