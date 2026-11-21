#!/usr/bin/env python3
"""Run the pinned r35 kernel recipe with the isolated r35b exit predicate."""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

BUILD_SHA = "c2e8bcc0aae8a6736592079b4f0bd1fba9032490ddfa432f30df9e6fbc619979"
HEADER_SHA = "86311631e7cf66881bd6d1a57a927c78db9ea9bb579deb025136252e3e218c72"
RENDERER_SHA = "a4163ecd10ecfd6bb429f2ce9c919f9a67a6dab85c936beeabb8f7fba2fe89be"
OLD_ASSERT = "assert ring_body.count('if(status || ns) {') == 1, 'ring must keep abnormal exits only'"
NEW_ASSERT = "assert ring_body.count('if(signal || ns) {') == 1 and ring_body.count('if(status || ns) {') == 0, 'ring must keep signal or reason exits only'"
BOOT_BUILD_SHA = "0d283d07764d9bdcf72bc756994592c5cdb2264dab87361601406ab21e227156"
DISPLAY_AUDIT_SHA = "5da768f17a93ad433c4a59edc7911ebac1fad9228ad64b79f629f24f6c9d9834"
OLD_NATIVE_SHA = "f4648bcfd02bbbabb7d2a5ac4719d62c9c62d5eb6c79f3a2b61770eda53bd668"
OLD_PRELINK_SHA = "ebec5e7b0df39d772e7a204108b799d280798d89d2a4edb455cd1a0d240496eb"
ARM_INIT_SHA = "a9931973da35aa0eaa50079ba1e011a02fad843e2c211648b284f313c2db28a4"
ARM_INIT_RECIPE_SHA = "3dc45c43fb9ae09ea9ef1a0430fe99e26a38234c1a64c79bf8069307e29362bb"


def pin(data, expected):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("pinned input mismatch: " + expected)
    return data


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("recipe anchor changed: " + old)
    return text.replace(old, new, 1)


def compact_recipe(build, r35, out, strip=True):
    recipe = r35.parent / "nuwa-r12bisect-20261116/build-boot-progress.py"
    boot_build = pin(recipe.read_bytes(), BOOT_BUILD_SHA).decode()
    slim = out / "build-boot-progress-compact.py"
    slim.write_text(replace_once(boot_build, "command_for(renderer, renderer_obj))",
                                 "command_for(renderer, renderer_obj) + ['-g0'])") if strip else boot_build)
    build = replace_once(build, "'-B', BOOT_PROGRESS_BUILD,",
                         f"'-B', {str(slim)!r},")
    # Preserve the compiler's literal-pool order as well as __FILE__ spelling.
    previous = r35.parent / "nuwa-r35b-exit-selection-20261120"
    build = replace_once(build, "        argv[argv.index(rec['file'])] = str(source)\n"
                                 "        argv[argv.index('-o') + 1] = str(out / (label + '.o'))",
                         "        if label in ('machine', 'vm_unix'):\n"
                         f"            old_source = Path({str(previous)!r}) / source.relative_to(out)\n"
                         "            assert old_source.read_bytes() == source.read_bytes(), label\n"
                         "            source = old_source\n"
                         "        argv[argv.index(rec['file'])] = str(source)\n"
                         "        argv[argv.index('-o') + 1] = str(out / (label + '.o'))")
    return replace_once(build, "    run('native-link', argv, link['cwd'])",
                        "    argv.append('-Wl,-S')\n    run('native-link', argv, link['cwd'])") if strip else build


def audit_compact(r35, out, before=None):
    root = r35.parents[1]
    legacy = before is None
    before = before or r35.parent / "nuwa-r35b-exit-selection-20261120"
    display = root / "scripts/build-nuwa-display-native.py"
    source = pin(display.read_bytes(), DISPLAY_AUDIT_SHA)
    sys.path.insert(0, str(root / "scripts"))
    namespace = {"__name__": "display_debug_audit", "__file__": str(display)}
    exec(compile(source, str(display), "exec"), namespace)
    audit = namespace["audit_debug_strip"](
        pin((before / "native.macho").read_bytes(), OLD_NATIVE_SHA) if legacy else (before / "native.macho").read_bytes(),
        (out / "native.macho").read_bytes())
    old_data = (before / "prelink.json").read_bytes()
    old = json.loads(pin(old_data, OLD_PRELINK_SHA) if legacy else old_data)
    new = json.loads((out / "prelink.json").read_bytes())
    # Symbol/string shrinkage changes file offsets, sizes and hashes, not bindings.
    fields = ("bindings", "original_sha256", "original_executable_sha256", "components",
              "codeless_components", "kernel_interfaces", "module_entrypoints", "pointer_counts",
              "slide", "early_security_initializers")
    for key in fields:
        if old[key] != new[key]:
            raise ValueError("prelink inventory changed: " + key)
    audit.update(prelink_bindings_preserved=len(new["bindings"]), matching_prelink_fields=fields)
    (out / "debug-strip.json").write_text(json.dumps(audit, indent=2) + "\n")


def ready_recipe(build, r35, out, reference):
    base = r35.parent / "nuwa-bootprogress-20261115-r1"
    original = base / "tree/osfmk/arm/arm_init.c"
    source = pin(original.read_bytes(), ARM_INIT_SHA).decode()
    source = replace_once(source, "#include <kern/boot_progress.h>\n",
                          "#include <kern/boot_progress.h>\nextern void boot_progress_thread_context_ready(void);\n")
    source = replace_once(source, "\tthread->machine.preemption_count = 0;\n\tcpu_bootstrap();",
                          "\tthread->machine.preemption_count = 0;\n\tboot_progress_thread_context_ready();\n\tcpu_bootstrap();")
    assert source.index("thread->machine.CpuDatap = &BootCpuData;") < source.index("machine_set_current_thread(thread);") < source.index("\tboot_progress_thread_context_ready();")
    local = out / "arm_init.c"
    local.write_bytes(source.encode())
    compile_source = reference / local.name if reference else local
    if compile_source.read_bytes() != local.read_bytes():
        raise ValueError("full/compact arm_init source mismatch")
    commands = json.loads(pin((base / "commands.json").read_bytes(), ARM_INIT_RECIPE_SHA))
    rec, = (c for c in commands if c["label"] == "compile-arm_init")
    argv = rec["argv"]
    argv[argv.index(str(original))] = str(compile_source)
    argv[argv.index("-o") + 1] = str(out / "arm_init.o")
    return replace_once(build, "    replacements = {\n",
                        f"    run('compile-arm_init', {argv!r}, {rec['cwd']!r})\n"
                        "    replacements = {\n"
                        f"        {str(base / 'arm_init.o')!r}: str(out / 'arm_init.o'),\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("r35", type=Path, help="original r35 directory")
    parser.add_argument("out", type=Path, help="new directory under the original repository out/")
    parser.add_argument("--compact", action="store_true", help="remove only debug metadata and audit against r35b")
    parser.add_argument("--detail", action="store_true", help="generate the detailed exit recorder")
    parser.add_argument("--audit-against", type=Path, help="unstripped build of identical detail source")
    args = parser.parse_args()
    r35 = args.r35.resolve()
    out = args.out.resolve()
    if r35.name != "nuwa-r35-20261119" or out.parent != r35.parent or out == r35:
        parser.error("output must be a new sibling of the original r35 directory")
    build = pin((r35 / "build.py").read_bytes(), BUILD_SHA).decode()
    header = pin((r35 / "BootProgressDisplay.h").read_bytes(), HEADER_SHA)
    spec = importlib.util.spec_from_file_location("selection", Path(__file__).with_name("generate-r35-exit-selection.py"))
    selection = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(selection)
    renderer = pin(selection.generate((r35 / "BootProgress.c").read_bytes()), RENDERER_SHA)
    if args.detail:
        spec = importlib.util.spec_from_file_location("detail", Path(__file__).with_name("generate-r35b-exit-detail.py"))
        detail = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(detail)
        renderer = detail.generate(renderer)
        build = replace_once(build, "assert 'bar(0, line,' in renderer_r35, 'row 0 not drawn from the ring'",
                             "assert 'if (!i) bar(0,b,' in renderer_r35, 'row 0 not drawn from the ring'")
        build = replace_once(build, "'\"%sEX%u %.6s %x:%x:%x\"', 'struct bp_exit_ring_entry'",
                             "'\"EX%u %-6.6s sig=%u ns=%08x code=0x%08x n=%u pc=%016llx\"', 'struct bp_exit_ring_entry'")
        build = replace_once(build, "b'EX%u %.6s %x:%x:%x'",
                             "b'EX%u %-6.6s sig=%u ns=%08x code=0x%08x n=%u pc=%016llx'")
        if args.compact and not args.audit_against:
            parser.error("--detail --compact requires --audit-against")
    build = replace_once(build, OLD_ASSERT, NEW_ASSERT)
    out.mkdir()
    (out / "BootProgress.c").write_bytes(renderer)
    (out / "BootProgressDisplay.h").write_bytes(header)
    namespace = {"__file__": str(r35 / "build.py"), "__name__": "r35b_recipe"}
    if args.compact or args.detail:
        build = compact_recipe(build, r35, out, strip=args.compact)
    if args.detail:
        build = ready_recipe(build, r35, out, args.audit_against.resolve() if args.compact else None)
    exec(compile(build, str(r35 / "build.py"), "exec"), namespace)
    namespace["RENDERER"] = out / "BootProgress.c"
    sys.argv = [str(r35 / "build.py"), "--out", str(out)]
    namespace["main"]()
    if args.compact:
        if args.detail:
            before = args.audit_against.resolve()
            if (before / "BootProgress.c").read_bytes() != renderer:
                raise ValueError("audit reference renderer differs")
            audit_compact(r35, out, before)
        else:
            audit_compact(r35, out)


if __name__ == "__main__":
    main()
